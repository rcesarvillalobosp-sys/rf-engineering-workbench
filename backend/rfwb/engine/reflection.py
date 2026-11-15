"""Coeficiente de reflexión, VSWR, Return Loss y balance de potencias.

Referencia Z0 real y positiva (definición clásica de onda de tensión):
    Γ = (Z − Z0) / (Z + Z0)        Z = Z0 · (1 + Γ) / (1 − Γ)
Para fuentes complejas se usa el coeficiente de onda de potencia (Kurokawa):
    Γp = (ZL − Zs*) / (ZL + Zs)
"""
from __future__ import annotations

import cmath
import math

import numpy as np

from .steps import Trace
from .units import RFInputError, fmt_complex, require_positive

INF = complex(math.inf, 0.0)


def is_open(z: complex) -> bool:
    return cmath.isinf(z) or abs(z) > 1e15


def gamma_from_z(z: complex, z0: float = 50.0) -> complex:
    z0 = require_positive("Z0", z0)
    if is_open(z):
        return 1 + 0j
    den = z + z0
    if abs(den) < 1e-15:
        raise RFInputError("Z = −Z0: coeficiente de reflexión no definido (carga activa singular).")
    return (z - z0) / den


def z_from_gamma(g: complex, z0: float = 50.0) -> complex:
    z0 = require_positive("Z0", z0)
    if abs(1 - g) < 1e-14:
        return INF
    return z0 * (1 + g) / (1 - g)


def power_wave_gamma(zl: complex, zs: complex) -> complex:
    """Γ de onda de potencia respecto a una fuente compleja Zs (Re{Zs} > 0)."""
    if zs.real <= 0:
        raise RFInputError("La impedancia de fuente debe tener parte real positiva.")
    if is_open(zl):
        return 1 + 0j
    return (zl - zs.conjugate()) / (zl + zs)


def vswr(mag_gamma: float) -> float:
    if mag_gamma < 0:
        raise RFInputError("|Γ| no puede ser negativo.")
    if mag_gamma >= 1.0 - 1e-12:
        return math.inf
    return (1 + mag_gamma) / (1 - mag_gamma)


def gamma_from_vswr(s: float) -> float:
    if s < 1:
        raise RFInputError("VSWR debe ser ≥ 1.")
    return (s - 1) / (s + 1)


def return_loss_db(mag_gamma: float) -> float:
    """RL = −20·log10|Γ| (positivo). |Γ| = 0 → ∞."""
    if mag_gamma <= 0:
        return math.inf
    return -20.0 * math.log10(mag_gamma)


def mismatch_loss_db(mag_gamma: float) -> float:
    """ML = −10·log10(1 − |Γ|²)."""
    if mag_gamma >= 1:
        return math.inf
    return -10.0 * math.log10(1 - mag_gamma ** 2)


# Versiones vectoriales (NumPy) para barridos
def vswr_arr(mag: np.ndarray) -> np.ndarray:
    mag = np.asarray(mag, dtype=float)
    with np.errstate(divide="ignore"):
        out = (1 + mag) / (1 - mag)
    out[mag >= 1 - 1e-12] = np.inf
    return out


def rl_arr(mag: np.ndarray) -> np.ndarray:
    mag = np.asarray(mag, dtype=float)
    with np.errstate(divide="ignore"):
        return -20 * np.log10(mag)


def reflection_metrics(z: complex, z0: float = 50.0, trace: Trace | None = None,
                       p_inc_w: float = 1.0) -> dict:
    """Todas las magnitudes de reflexión para una impedancia Z respecto a Z0."""
    g = gamma_from_z(z, z0)
    mag = abs(g)
    ang = math.degrees(cmath.phase(g)) if mag > 0 else 0.0
    s = vswr(mag)
    rl = return_loss_db(mag)
    ml = mismatch_loss_db(mag)
    open_ = is_open(z)
    zn = INF if open_ else z / z0
    yn = 0j if open_ else (math.inf if abs(z) == 0 else z0 / z)
    if trace is not None:
        trace.add("Impedancia normalizada", "z = Z / Z0",
                  "∞" if open_ else f"z = ({fmt_complex(z)}) / {z0:g} Ω", "∞" if open_ else fmt_complex(zn, ""),
                  "adimensional", "Normalizar permite leer la carta de Smith para cualquier Z0.")
        trace.add("Coeficiente de reflexión", "Γ = (Z − Z0) / (Z + Z0)",
                  "Carga abierta → Γ = 1" if open_ else
                  f"Γ = ({fmt_complex(z - z0)}) / ({fmt_complex(z + z0)})",
                  f"{fmt_complex(g, '')}  =  {mag:.5f} ∠ {ang:.3f}°", "",
                  "Fracción (compleja) de la onda de tensión incidente que se refleja.")
        trace.add("Relación de onda estacionaria", "VSWR = (1 + |Γ|) / (1 − |Γ|)",
                  f"VSWR = (1 + {mag:.5f}) / (1 − {mag:.5f})",
                  "∞" if math.isinf(s) else f"{s:.4f}", ":1",
                  "VSWR = 1 indica adaptación perfecta; ∞ indica reflexión total.")
        trace.add("Return Loss", "RL = −20 · log10 |Γ|", f"RL = −20 · log10({mag:.5f})",
                  "∞" if math.isinf(rl) else f"{rl:.3f}", "dB",
                  "Cuanto mayor es RL, menor es la potencia reflejada. |S11|dB = −RL.")
        trace.add("Potencia reflejada / transmitida", "Pr/Pi = |Γ|² ;  Pt/Pi = 1 − |Γ|²",
                  f"|Γ|² = {mag ** 2:.5f}", f"Reflejada {100 * mag ** 2:.3f} % · Entregada {100 * (1 - mag ** 2):.3f} %",
                  "", "Supone fuente adaptada a Z0 y carga pasiva; no incluye pérdidas en línea.")
        trace.add("Mismatch loss", "ML = −10 · log10(1 − |Γ|²)", f"ML = −10 · log10(1 − {mag ** 2:.5f})",
                  "∞" if math.isinf(ml) else f"{ml:.4f}", "dB")
    return {
        "z": z, "z0": z0, "z_norm": zn, "y": (0j if open_ else (INF if z == 0 else 1 / z)), "y_norm": yn,
        "gamma": g, "gamma_mag": mag, "gamma_deg": ang,
        "vswr": s, "return_loss_db": rl, "s11_db": (-rl if math.isfinite(rl) else -math.inf),
        "mismatch_loss_db": ml,
        "p_reflected_w": p_inc_w * mag ** 2, "p_delivered_w": p_inc_w * (1 - mag ** 2),
        "reflected_pct": 100 * mag ** 2, "delivered_pct": 100 * (1 - mag ** 2),
        "z_mag": math.inf if open_ else abs(z), "z_deg": 0.0 if open_ else math.degrees(cmath.phase(z)),
        "is_open": open_,
    }
