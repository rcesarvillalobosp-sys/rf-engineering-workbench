"""Lector/escritor Touchstone propio (v1.0/v1.1 y v2.0 básico), contrastado con scikit-rf.

Soporta: .s1p … .s4p (y .sNp genérico), parámetros S/Y/Z, formatos RI/MA/DB, unidades Hz…GHz,
[Reference] por puerto (v2), [Two-Port Data Order], [Matrix Format] Full/Lower/Upper,
datos de ruido en v1 2 puertos (se separan, no se interpretan como red).
Parámetros híbridos H/G (sólo 2 puertos) se convierten a S.
[Mixed-Mode Order] (v2): los datos se conservan en modo mixto con etiquetas D/C/S.
No soportado: nada más, [Begin Information] (se ignora con aviso).
"""
from __future__ import annotations

import math
import os
import re
import tempfile
from dataclasses import dataclass, field

import numpy as np

from ..engine.units import RFInputError

FREQ_MULT = {"HZ": 1.0, "KHZ": 1e3, "MHZ": 1e6, "GHZ": 1e9}


@dataclass
class TouchstoneData:
    f: np.ndarray
    s: np.ndarray            # (N, n, n) complejos
    z0: np.ndarray           # (n,) referencias por puerto (Ω)
    nports: int
    version: str = "1.0"
    param: str = "S"
    fmt: str = "MA"
    freq_unit: str = "GHZ"
    comments: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    noise: list[list[float]] | None = None
    filename: str = ""
    port_labels: list[str] | None = None

    def summary(self) -> dict:
        return {"filename": self.filename, "nports": self.nports, "points": int(self.f.size),
                "f_start": float(self.f[0]), "f_stop": float(self.f[-1]), "version": self.version,
                "param": self.param, "format": self.fmt, "freq_unit": self.freq_unit,
                "z0": [float(z) for z in self.z0], "comments": self.comments[:40], "warnings": self.warnings,
                "has_noise": bool(self.noise), "port_labels": self.port_labels}


def _ports_from_name(name: str) -> int | None:
    m = re.search(r"\.s(\d+)p$", name.strip().lower())
    return int(m.group(1)) if m else None


def _to_complex(a: np.ndarray, b: np.ndarray, fmt: str) -> np.ndarray:
    if fmt == "RI":
        return a + 1j * b
    if fmt == "MA":
        return a * np.exp(1j * np.radians(b))
    if fmt == "DB":
        return 10 ** (a / 20) * np.exp(1j * np.radians(b))
    raise RFInputError(f"Formato de datos no soportado: {fmt}")


def parse_touchstone(text: str, filename: str = "data.s1p") -> TouchstoneData:
    if not text or not text.strip():
        raise RFInputError("El archivo está vacío.")
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    comments, warnings = [], []
    option = None
    version = "1.0"
    nports = _ports_from_name(filename)
    two_port_order = "21_12"
    matrix_format = "FULL"
    reference: list[float] | None = None
    reading_ref = False
    n_freq_decl = None
    data_rows: list[tuple[int, list[str]]] = []
    noise_rows: list[list[float]] = []
    in_noise = False
    in_info = False
    mm_order: list[str] | None = None
    for ln_no, raw in enumerate(lines, start=1):
        if "!" in raw:
            raw, c = raw.split("!", 1)
            if c.strip():
                comments.append(c.strip())
        line = raw.strip()
        if not line:
            continue
        if line.startswith("["):
            m = re.match(r"\[([^\]]+)\]\s*(.*)$", line)
            if not m:
                raise RFInputError(f"Línea {ln_no}: palabra clave mal formada.")
            key, val = m.group(1).strip().lower(), m.group(2).strip()
            reading_ref = False
            if key == "version":
                version = val
                if not val.startswith("2"):
                    warnings.append(f"Versión declarada {val}; se trata como v2.")
            elif key == "number of ports":
                nports = int(val)
            elif key == "two-port data order":
                two_port_order = val.replace(" ", "")
            elif key == "number of frequencies":
                n_freq_decl = int(val)
            elif key == "reference":
                reference = [float(v) for v in val.split()] if val else []
                reading_ref = True
            elif key == "matrix format":
                matrix_format = val.upper()
            elif key == "network data":
                in_noise = False
            elif key == "noise data":
                in_noise = True
            elif key == "begin information":
                in_info = True
                warnings.append("Sección [Begin Information] ignorada.")
            elif key == "end information":
                in_info = False
            elif key == "end":
                break
            elif key in ("number of noise frequencies",):
                pass
            elif key == "mixed-mode order":
                mm_order = val.split()
            else:
                warnings.append(f"Palabra clave ignorada: [{m.group(1)}]")
            continue
        if in_info:
            continue
        if line.startswith("#"):
            if option is None:
                option = line[1:].split()
            else:
                warnings.append(f"Línea {ln_no}: línea de opciones duplicada ignorada.")
            continue
        if reading_ref and reference is not None and nports and len(reference) < nports:
            reference += [float(v) for v in line.split()]
            continue
        toks = line.split()
        if in_noise:
            noise_rows.append([float(t) for t in toks])
            continue
        data_rows.append((ln_no, toks))

    if nports is None:
        raise RFInputError("No se puede determinar el número de puertos: use extensión .sNp o [Number of Ports].")
    if not (1 <= nports <= 32):
        raise RFInputError(f"Número de puertos no válido: {nports}.")
    # Opciones
    unit, param, fmt, r = "GHZ", "S", "MA", 50.0
    if option is None:
        warnings.append("Sin línea de opciones '#': se asume '# GHz S MA R 50'.")
    else:
        toks = [t.upper() for t in option]
        i = 0
        while i < len(toks):
            t = toks[i]
            if t in FREQ_MULT:
                unit = t
            elif t in ("S", "Y", "Z", "G", "H"):
                param = t
            elif t in ("RI", "MA", "DB"):
                fmt = t
            elif t == "R":
                if i + 1 >= len(toks):
                    raise RFInputError("Línea de opciones: falta el valor tras 'R'.")
                r = float(toks[i + 1])
                i += 1
            else:
                raise RFInputError(f"Línea de opciones: token desconocido '{option[i]}'.")
            i += 1
    if param in ("G", "H") and nports != 2:
        raise RFInputError(f"Los parámetros {param} (híbridos) sólo están definidos para 2 puertos.")
    if r <= 0:
        raise RFInputError("La resistencia de referencia R debe ser positiva.")
    is_v2 = version.startswith("2")

    # Tokens numéricos de red
    n = nports
    per_point = 1 + (2 * n * n if matrix_format == "FULL" else n * (n + 1))
    nums: list[float] = []
    line_of: list[int] = []
    prev_f = -math.inf
    for ln_no, toks in data_rows:
        try:
            vals = [float(t) for t in toks]
        except ValueError:
            bad = next(t for t in toks if not _isnum(t))
            raise RFInputError(f"Línea {ln_no}: valor no numérico '{bad}'.")
        # Ruido v1 2 puertos: fila de 5 valores con frecuencia ≤ última frecuencia de red
        if not is_v2 and n == 2 and len(vals) == 5 and len(nums) % per_point == 0 and nums and vals[0] <= prev_f:
            noise_rows.append(vals)
            continue
        if noise_rows and not is_v2 and n == 2:
            noise_rows.append(vals)
            continue
        if len(nums) % per_point == 0:
            prev_f = vals[0]
        nums.extend(vals)
        line_of.extend([ln_no] * len(vals))
    if not nums:
        raise RFInputError("El archivo no contiene datos de red.")
    if len(nums) % per_point != 0:
        raise RFInputError(f"Datos incompletos: {len(nums)} valores no es múltiplo de {per_point} "
                           f"(1 frecuencia + {per_point - 1} valores por punto para {n} puertos). "
                           f"Revise la línea {line_of[-1]}.")
    arr = np.asarray(nums, dtype=float).reshape(-1, per_point)
    f = arr[:, 0] * FREQ_MULT[unit]
    if n_freq_decl is not None and n_freq_decl != f.size:
        raise RFInputError(f"[Number of Frequencies] = {n_freq_decl} pero hay {f.size} puntos.")
    if f.size > 1 and np.any(np.diff(f) <= 0):
        k = int(np.argmax(np.diff(f) <= 0)) + 1
        raise RFInputError(f"Frecuencias no estrictamente crecientes en el punto {k + 1} ({f[k]:g} Hz).")
    if np.any(f < 0):
        raise RFInputError("Frecuencias negativas en el archivo.")
    vals = _to_complex(arr[:, 1::2], arr[:, 2::2], fmt)
    m = np.zeros((f.size, n, n), dtype=complex)
    if matrix_format == "FULL":
        m[:] = vals.reshape(f.size, n, n)
        if n == 2 and (not is_v2 or two_port_order == "21_12"):
            m = m.transpose(0, 2, 1).copy()  # orden S11 S21 S12 S22
    else:
        idx = 0
        for i in range(n):
            js = range(0, i + 1) if matrix_format == "LOWER" else range(i, n)
            for j in js:
                m[:, i, j] = vals[:, idx]
                m[:, j, i] = vals[:, idx]
                idx += 1
    z0 = np.full(n, r, dtype=float)
    if reference:
        if len(reference) not in (1, n):
            raise RFInputError(f"[Reference] debe tener 1 o {n} valores.")
        z0 = np.array(reference if len(reference) == n else reference * n, dtype=float)
    # Conversión Y/Z → S
    if param in ("Y", "Z"):
        from ..engine.sparams import y_to_s, z_to_s
        if np.unique(z0).size > 1:
            raise RFInputError("Conversión Y/Z con referencias distintas por puerto no soportada.")
        zref = float(z0[0])
        # v1: Z e Y vienen normalizados a R ; v2: valores absolutos (Ω / S)
        mm = m if is_v2 else (m * r if param == "Z" else m / r)
        m = z_to_s(mm, zref) if param == "Z" else y_to_s(mm, zref)
        warnings.append(f"Parámetros {param} convertidos a S con Z0 = {zref:g} Ω.")
    elif param in ("H", "G"):
        from ..engine.sparams import g_to_s, h_to_s
        if np.unique(z0).size > 1:
            raise RFInputError("Conversión H/G con referencias distintas por puerto no soportada.")
        zref = float(z0[0])
        mm = m.copy()
        if not is_v2:  # v1: h11 (Ω) y h22 (S) normalizados a R ; en G al revés
            if param == "H":
                mm[:, 0, 0] *= r
                mm[:, 1, 1] /= r
            else:
                mm[:, 0, 0] /= r
                mm[:, 1, 1] *= r
        m = h_to_s(mm, zref) if param == "H" else g_to_s(mm, zref)
        warnings.append(f"Parámetros híbridos {param} convertidos a S con Z0 = {zref:g} Ω.")
    if np.unique(z0).size > 1:
        warnings.append("Referencias distintas por puerto: las conversiones a Z usan cada Z0 de puerto.")
    labels = None
    if mm_order is not None:
        if len(mm_order) != n:
            raise RFInputError(f"[Mixed-Mode Order] tiene {len(mm_order)} entradas; se esperaban {n}.")
        if param != "S":
            raise RFInputError("Modo mixto sólo soportado con parámetros S.")
        labels, z_mm = [], []
        for tok in mm_order:
            mt = re.fullmatch(r"([DCS])(\d+)(?:,(\d+))?", tok.upper())
            if not mt or (mt.group(1) in "DC") != (mt.group(3) is not None):
                raise RFInputError(f"[Mixed-Mode Order]: entrada no válida '{tok}'.")
            idx = [int(mt.group(2))] + ([int(mt.group(3))] if mt.group(3) else [])
            if any(not (1 <= i <= n) for i in idx):
                raise RFInputError(f"[Mixed-Mode Order]: puerto fuera de rango en '{tok}'.")
            zse = float(np.mean([z0[i - 1] for i in idx]))
            z_mm.append(2 * zse if mt.group(1) == "D" else zse / 2 if mt.group(1) == "C" else zse)
            labels.append(tok.upper())
        z0 = np.array(z_mm)
        warnings.append("Datos en modo mixto: se conservan tal como vienen en el archivo (referencias: D = 2·Z0, C = Z0/2).")
    passive = np.max(np.abs(m)) if m.size else 0
    if passive > 1.0 + 1e-6 and n == 1:
        warnings.append(f"|S11| máx = {passive:.4f} > 1: dispositivo activo o datos no calibrados.")
    return TouchstoneData(port_labels=labels, f=f, s=m, z0=z0, nports=n, version="2.0" if is_v2 else "1.x", param=param, fmt=fmt,
                          freq_unit=unit, comments=comments, warnings=warnings,
                          noise=noise_rows or None, filename=filename)


def _isnum(t: str) -> bool:
    try:
        float(t)
        return True
    except ValueError:
        return False


def skrf_crosscheck(text: str, filename: str, data: TouchstoneData) -> dict:
    """Lee el mismo archivo con scikit-rf y devuelve la máxima diferencia absoluta en S."""
    try:
        import skrf
    except ImportError:
        return {"available": False}
    if data.port_labels:
        return {"available": True, "ok": None, "skipped": True, "skrf_version": skrf.__version__,
                "note": "Comparación omitida: scikit-rf reordena los puertos de los archivos en modo mixto; "
                        "la lectura propia conserva el orden y las etiquetas del archivo."}
    if data.version != "2.0" and data.param in ("Y", "H", "G"):
        # scikit-rf 2.2 desnormaliza Y/H/G de v1 multiplicando TODOS los elementos por R (sólo es correcto para Z):
        # la comparación no es significativa. La lectura propia se valida con redes de resultado analítico conocido.
        return {"available": True, "ok": None, "skipped": True, "skrf_version": skrf.__version__,
                "note": f"Comparación omitida: scikit-rf {skrf.__version__} desnormaliza {data.param} (v1) multiplicando "
                        "todos los elementos por R, lo que sólo es correcto para Z. Lectura validada con casos analíticos."}
    suffix = os.path.splitext(filename)[1] or f".s{data.nports}p"
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "check" + suffix)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(text)
        try:
            ntw = skrf.Network(p)
        except Exception as e:  # noqa: BLE001
            return {"available": True, "ok": False, "error": f"scikit-rf no pudo leer el archivo: {e}"}
    if ntw.s.shape != data.s.shape:
        return {"available": True, "ok": False, "error": f"Dimensiones distintas: skrf {ntw.s.shape} vs {data.s.shape}"}
    diff = float(np.max(np.abs(ntw.s - data.s)))
    fdiff = float(np.max(np.abs(ntw.f - data.f)))
    return {"available": True, "ok": diff < 1e-9 and fdiff < 1e-3, "max_abs_diff_s": diff, "max_abs_diff_f": fdiff,
            "skrf_version": skrf.__version__}


def write_touchstone(f: np.ndarray, s: np.ndarray, z0: float = 50.0, fmt: str = "RI", unit: str = "GHZ",
                     comments: list[str] | None = None) -> str:
    fmt, unit = fmt.upper(), unit.upper()
    if unit not in FREQ_MULT:
        raise RFInputError("Unidad no válida.")
    n = s.shape[1]
    out = [f"! {c}" for c in (comments or [])]
    out.append(f"# {unit.replace('HZ', 'Hz').replace('KHz', 'kHz')} S {fmt} R {z0:g}")
    mat = s.transpose(0, 2, 1) if n == 2 else s  # v1: S11 S21 S12 S22
    for k in range(f.size):
        vals = mat[k].reshape(-1)
        if fmt == "RI":
            pairs = [(v.real, v.imag) for v in vals]
        elif fmt == "MA":
            pairs = [(abs(v), math.degrees(np.angle(v))) for v in vals]
        elif fmt == "DB":
            pairs = [(20 * math.log10(abs(v)) if abs(v) > 0 else -300.0, math.degrees(np.angle(v))) for v in vals]
        else:
            raise RFInputError("Formato no válido.")
        nums = [f"{a:.12g} {b:.12g}" for a, b in pairs]
        fstr = f"{f[k] / FREQ_MULT[unit]:.12g}"
        if n <= 2:
            out.append(fstr + " " + " ".join(nums))
        else:
            for i in range(n):
                row = nums[i * n:(i + 1) * n]
                out.append((fstr if i == 0 else " " * len(fstr)) + " " + " ".join(row))
    return "\n".join(out) + "\n"
