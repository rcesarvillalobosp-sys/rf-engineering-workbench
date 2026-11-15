"""Redes en cascada mediante matrices ABCD.

Una red es una lista de elementos ordenados desde la FUENTE (puerto 1) hacia la CARGA (puerto 2).
Elemento (dict):
  {"kind": "series"|"shunt", "part": "L"|"C"|"R"|"Z", "value": float | {"re","im"}, "q": opcional}
  {"kind": "line", "z0": Ω, "length_m": m, "vf": 0..1, "atten_db_m": dB/m (a f_ref), "f_ref": Hz}
  {"kind": "shunt"|"series", "part": "stub_open"|"stub_short", "z0", "length_m", "vf", "atten_db_m"}
La atenuación se escala como √f (pérdidas de conductor) si se indica f_ref; si no, constante.
"""
from __future__ import annotations

import math

import numpy as np

from .units import C0, NP_TO_DB, RFInputError

TWO_PI = 2 * math.pi


def _gamma_prop(f: np.ndarray, el: dict) -> np.ndarray:
    vf = float(el.get("vf", 1.0))
    if not (0 < vf <= 1):
        raise RFInputError("El factor de velocidad debe estar en (0, 1].")
    beta = TWO_PI * f / (vf * C0)
    a_db = float(el.get("atten_db_m", 0.0) or 0.0)
    alpha = a_db / NP_TO_DB
    if a_db and el.get("f_ref"):
        alpha = alpha * np.sqrt(f / float(el["f_ref"]))
    return alpha + 1j * beta


def element_z(f: np.ndarray, el: dict) -> np.ndarray:
    """Impedancia del elemento concentrado o stub (como bipolo)."""
    w = TWO_PI * f
    part = el["part"]
    with np.errstate(divide="ignore", invalid="ignore"):
        if part == "L":
            x = w * el["value"]
            r = x / el["q"] if el.get("q") else 0.0
            return r + 1j * x
        if part == "C":
            x = -1 / (w * el["value"])
            r = np.abs(x) / el["q"] if el.get("q") else 0.0
            return r + 1j * x
        if part == "R":
            return np.full(f.shape, float(el["value"]), dtype=complex)
        if part == "Z":
            v = el["value"]
            return np.full(f.shape, complex(v["re"], v["im"]) if isinstance(v, dict) else complex(v))
        if part in ("stub_open", "stub_short"):
            gl = _gamma_prop(f, el) * el["length_m"]
            th = np.tanh(gl)
            return el["z0"] / th if part == "stub_open" else el["z0"] * th
    raise RFInputError(f"Elemento desconocido: {part}")


def element_abcd(f: np.ndarray, el: dict) -> np.ndarray:
    n = f.size
    m = np.zeros((n, 2, 2), dtype=complex)
    if el["kind"] == "line":
        gl = _gamma_prop(f, el) * el["length_m"]
        z0 = el["z0"]
        m[:, 0, 0] = np.cosh(gl)
        m[:, 0, 1] = z0 * np.sinh(gl)
        m[:, 1, 0] = np.sinh(gl) / z0
        m[:, 1, 1] = np.cosh(gl)
        return m
    z = element_z(f, el)
    m[:, 0, 0] = 1
    m[:, 1, 1] = 1
    if el["kind"] == "series":
        m[:, 0, 1] = z
    elif el["kind"] == "shunt":
        with np.errstate(divide="ignore", invalid="ignore"):
            z = np.where(np.abs(z) < 1e-12, 1e-12, z)  # stub en corto de longitud nula ≈ cortocircuito
            m[:, 1, 0] = np.where(np.isinf(z), 0, 1 / z)
    else:
        raise RFInputError(f"Tipo de conexión desconocido: {el['kind']}")
    return m


def cascade_abcd(f, elements: list[dict]) -> np.ndarray:
    f = np.atleast_1d(np.asarray(f, dtype=float))
    total = np.tile(np.eye(2, dtype=complex), (f.size, 1, 1))
    for el in elements:
        total = total @ element_abcd(f, el)
    return total


def zin_cascade(f, elements: list[dict], zl) -> np.ndarray:
    """Impedancia vista desde la fuente con carga ZL (escalar o array por frecuencia)."""
    f = np.atleast_1d(np.asarray(f, dtype=float))
    abcd = cascade_abcd(f, elements)
    zl = np.broadcast_to(np.asarray(zl, dtype=complex), f.shape)
    a, b, c, d = abcd[:, 0, 0], abcd[:, 0, 1], abcd[:, 1, 0], abcd[:, 1, 1]
    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.where(np.isinf(zl), a / c, (a * zl + b) / (c * zl + d))
    return out


def abcd_to_s(abcd: np.ndarray, z0: float = 50.0) -> np.ndarray:
    a, b, c, d = abcd[:, 0, 0], abcd[:, 0, 1], abcd[:, 1, 0], abcd[:, 1, 1]
    den = a + b / z0 + c * z0 + d
    s = np.empty_like(abcd)
    s[:, 0, 0] = (a + b / z0 - c * z0 - d) / den
    s[:, 0, 1] = 2 * (a * d - b * c) / den
    s[:, 1, 0] = 2 / den
    s[:, 1, 1] = (-a + b / z0 - c * z0 + d) / den
    return s


def trajectory(f0: float, elements: list[dict], zl: complex, steps: int = 60) -> list[dict]:
    """Recorrido en la carta de Smith: se parte de ZL y se añaden los elementos desde la carga
    hacia la fuente, variando cada uno desde 0 hasta su valor final.
    Devuelve una lista de tramos {label, z: [complejos]}.
    """
    f = np.array([f0], dtype=float)
    segments = []
    applied: list[dict] = []
    for el in reversed(elements):
        zs = []
        for k in np.linspace(0.0, 1.0, steps):
            partial = dict(el)
            if el["kind"] == "line" or el["part"] in ("stub_open", "stub_short"):
                partial["length_m"] = el["length_m"] * k
            elif el["part"] in ("L",):
                partial["value"] = el["value"] * k if el["kind"] == "series" else el["value"] / max(k, 1e-9)
            elif el["part"] == "C":
                partial["value"] = el["value"] / max(k, 1e-9) if el["kind"] == "series" else el["value"] * k
            elif el["part"] == "R":
                partial["value"] = el["value"] * k if el["kind"] == "series" else el["value"] / max(k, 1e-9)
            zs.append(complex(zin_cascade(f, [partial] + applied, zl)[0]))
        applied = [el] + applied
        segments.append({"label": describe(el), "z": zs})
    return segments


def describe(el: dict) -> str:
    from .units import fmt_si
    if el["kind"] == "line":
        return f"Línea Z0={el['z0']:g} Ω, ℓ={fmt_si(el['length_m'], 'm')}"
    p = el["part"]
    where = "serie" if el["kind"] == "series" else "paralelo"
    if p in ("stub_open", "stub_short"):
        t = "abierto" if p == "stub_open" else "cortocircuitado"
        return f"Stub {t} en {where}, ℓ={fmt_si(el['length_m'], 'm')}"
    unit = {"L": "H", "C": "F", "R": "Ω"}.get(p, "Ω")
    return f"{p} {where} = {fmt_si(el['value'], unit) if p != 'Z' else el['value']}"
