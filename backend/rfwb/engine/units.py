"""Unidades, prefijos SI, validación de entradas y parseo de números complejos.

Convenciones del motor (válidas en todo el paquete):
  * Frecuencia en Hz, longitud en m, L en H, C en F, R/X en Ω, G/B en S.
  * Dependencia temporal e^{+jωt}:  Z_L = +jωL ,  Z_C = 1/(jωC) = -j/(ωC).
    Reactancia inductiva positiva, capacitiva negativa.
  * Return Loss positivo:  RL = -20·log10|Γ|  (|S11| en dB es negativo).
"""
from __future__ import annotations

import cmath
import math
import re

C0 = 299_792_458.0  # velocidad de la luz en el vacío, m/s
NP_TO_DB = 20.0 / math.log(10.0)  # 8.685889638...

SI_PREFIX = {
    "f": 1e-15, "p": 1e-12, "n": 1e-9, "u": 1e-6, "µ": 1e-6, "μ": 1e-6,
    "m": 1e-3, "": 1.0, "k": 1e3, "K": 1e3, "M": 1e6, "G": 1e9, "T": 1e12,
}

FREQ_UNITS = {"hz": 1.0, "khz": 1e3, "mhz": 1e6, "ghz": 1e9, "thz": 1e12}


class RFInputError(ValueError):
    """Error de validación de entrada con mensaje para el usuario."""


def require_finite(name: str, v: float) -> float:
    try:
        v = float(v)
    except (TypeError, ValueError):
        raise RFInputError(f"{name}: valor numérico no válido ({v!r}).")
    if not math.isfinite(v):
        raise RFInputError(f"{name}: el valor debe ser finito.")
    return v


def require_positive(name: str, v: float) -> float:
    v = require_finite(name, v)
    if v <= 0:
        raise RFInputError(f"{name}: debe ser mayor que cero (recibido {v}).")
    return v


def require_nonneg(name: str, v: float) -> float:
    v = require_finite(name, v)
    if v < 0:
        raise RFInputError(f"{name}: no puede ser negativo (recibido {v}).")
    return v


def require_range(name: str, v: float, lo: float, hi: float) -> float:
    v = require_finite(name, v)
    if not (lo <= v <= hi):
        raise RFInputError(f"{name}: debe estar entre {lo} y {hi} (recibido {v}).")
    return v


def freq_to_hz(value: float, unit: str = "Hz") -> float:
    u = unit.strip().lower()
    if u not in FREQ_UNITS:
        raise RFInputError(f"Unidad de frecuencia desconocida: {unit!r}.")
    return require_positive("Frecuencia", value) * FREQ_UNITS[u]


_Q_RE = re.compile(r"^\s*([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)\s*([fpnuµμmkKMGT]?)\s*([A-Za-zΩ]*)\s*$")


def parse_quantity(text: str | float, expected_unit: str = "") -> float:
    """'10nH' -> 1e-8 ; '2.4 GHz' -> 2.4e9 ; '4.7p' -> 4.7e-12 ; 50 -> 50."""
    if isinstance(text, (int, float)):
        return require_finite("Valor", text)
    s = str(text).strip().replace(",", ".")
    # Unidad de frecuencia compuesta (MHz, GHz) con 'M'/'G' ambiguos.
    m = _Q_RE.match(s)
    if not m:
        raise RFInputError(f"No se puede interpretar la magnitud {text!r}.")
    num, prefix, unit = m.groups()
    if prefix == "m" and unit.lower() == "hz" and s.lower().endswith("mhz"):
        # 'MHz' escrito en minúsculas: interpretar como mega si se espera frecuencia.
        prefix = "M" if "M" in s or expected_unit.lower() == "hz" else "m"
    if expected_unit and unit and unit.lower() not in (expected_unit.lower(), "ohm", "Ω".lower()):
        if not (expected_unit.lower() == "ohm" and unit in ("Ω", "R")):
            raise RFInputError(f"Unidad {unit!r} incompatible; se esperaba {expected_unit}.")
    return float(num) * SI_PREFIX[prefix]


_NUM = r"(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"


def parse_complex(text: str | float | complex) -> complex:
    """Interpreta '80+j30', '80 - j30 Ω', 'j25', '-j10', '50', '30-12j', '100∠45' (polar, grados)."""
    if isinstance(text, (int, float, complex)):
        z = complex(text)
        if not (math.isfinite(z.real) and math.isfinite(z.imag)):
            raise RFInputError("El número complejo debe ser finito.")
        return z
    s = str(text).strip().replace(",", ".")
    for token in ("Ω", "ohms", "ohm", " "):
        s = s.replace(token, "")
    s = s.replace("i", "j").replace("J", "j").replace("I", "j")
    if not s:
        raise RFInputError("Valor complejo vacío.")
    try:
        if "∠" in s or "<" in s:
            mag_s, ang_s = re.split(r"[∠<]", s, maxsplit=1)
            ang = float(ang_s.replace("°", "").replace("deg", ""))
            return cmath.rect(float(mag_s), math.radians(ang))
        if re.search(r"\d[-+]j$", s):
            raise ValueError  # '80+j' incompleto
        # 'a+jb' -> 'a+bj' ;  'j' aislado -> '1j'
        s = re.sub(r"j(" + _NUM + r")", r"\1j", s)
        s = re.sub(r"(^|[-+])j(?![\d.])", r"\g<1>1j", s)
        if not re.fullmatch(r"[-+]?" + _NUM + r"j?(?:[-+]" + _NUM + r"j?)?", s):
            raise ValueError
        z = complex(s)
    except (ValueError, TypeError):
        raise RFInputError(f"No se puede interpretar {text!r} como número complejo (ej.: 80+j30).")
    if not (math.isfinite(z.real) and math.isfinite(z.imag)):
        raise RFInputError("El número complejo debe ser finito.")
    return z

def fmt_si(v: float, unit: str = "", digits: int = 4) -> str:
    """Formatea con prefijo SI: 1.2e-8,'H' -> '12 nH'."""
    if v is None or not math.isfinite(v):
        return "∞" if v and v > 0 else ("-∞" if v else "—")
    if v == 0:
        return f"0 {unit}".strip()
    exp = int(math.floor(math.log10(abs(v)) / 3) * 3)
    exp = max(-15, min(12, exp))
    prefixes = {-15: "f", -12: "p", -9: "n", -6: "µ", -3: "m", 0: "", 3: "k", 6: "M", 9: "G", 12: "T"}
    return f"{v / 10 ** exp:.{digits}g} {prefixes[exp]}{unit}".strip()


def fmt_complex(z: complex, unit: str = "Ω", digits: int = 5) -> str:
    if cmath.isinf(z):
        return "∞ (circuito abierto)"
    sign = "+" if z.imag >= 0 else "−"
    return f"{z.real:.{digits}g} {sign} j{abs(z.imag):.{digits}g} {unit}".strip()


def cx(z: complex | None) -> dict | None:
    """Serialización JSON de un complejo (∞ -> None en los campos)."""
    if z is None:
        return None
    z = complex(z)
    if not (math.isfinite(z.real) and math.isfinite(z.imag)):
        return {"re": None, "im": None, "inf": True}
    return {"re": z.real, "im": z.imag}


def finite_or_none(v: float) -> float | None:
    return v if (v is not None and math.isfinite(v)) else None
