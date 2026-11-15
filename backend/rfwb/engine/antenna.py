"""Análisis de antenas a partir de su impedancia de entrada / S11.

Sólo se derivan magnitudes de PUERTO (impedancia, adaptación, ancho de banda, Q).
Ganancia, directividad, eficiencia de radiación y diagrama NO se pueden obtener de S11:
requieren medidas de campo o un modelo electromagnético.
"""
from __future__ import annotations

import math

import numpy as np

from .sparams import find_bands, find_minima, s11_to_z, z_to_s11, zero_crossings
from .reflection import rl_arr, vswr_arr
from .units import RFInputError

TWO_PI = 2 * math.pi
NOT_AVAILABLE = ["Ganancia", "Directividad", "Eficiencia de radiación", "Diagrama de radiación", "Polarización"]
# (para dipolos y monopolos canónicos existe un modelo EM analítico en antenna_em.py)


def equivalent_model(kind: str, f0: float, r: float, q: float, f: np.ndarray) -> np.ndarray:
    """Modelo de circuito equivalente (SIMULADO). series_rlc: antena tipo dipolo cerca de resonancia;
    parallel_rlc: antirresonancia (p.ej. dipolo de onda completa, ranura)."""
    if f0 <= 0 or r <= 0 or q <= 0:
        raise RFInputError("f0, R y Q deben ser positivos.")
    w0 = TWO_PI * f0
    w = TWO_PI * np.asarray(f, dtype=float)
    if kind == "series_rlc":
        L = q * r / w0
        C = 1 / (w0 ** 2 * L)
        return r + 1j * (w * L - 1 / (w * C))
    if kind == "parallel_rlc":
        L = r / (q * w0)
        C = q / (w0 * r)
        return 1 / (1 / r + 1 / (1j * w * L) + 1j * w * C)
    raise RFInputError(f"Modelo desconocido: {kind}")


def q_from_impedance(f, z, i) -> float | None:
    """Q de Yaghjian–Best:  Q_Z(ω0) = (ω0 / 2R0)·√(R'² + (X' + |X|/ω0)²) ."""
    f = np.asarray(f, dtype=float)
    if i <= 0 or i >= len(f) - 1:
        return None
    w = TWO_PI * f
    dr = np.gradient(z.real, w)[i]
    dx = np.gradient(z.imag, w)[i]
    r0 = z.real[i]
    if r0 <= 0:
        return None
    return float(w[i] / (2 * r0) * math.sqrt(dr ** 2 + (dx + abs(z.imag[i]) / w[i]) ** 2))


def analyze_antenna(f, s11=None, z=None, z0=50.0, vswr_threshold=2.0) -> dict:
    f = np.asarray(f, dtype=float)
    if s11 is None and z is None:
        raise RFInputError("Se requiere S11 o Z(f).")
    if s11 is None:
        z = np.asarray(z, dtype=complex)
        s11 = z_to_s11(z, z0)
    else:
        s11 = np.asarray(s11, dtype=complex)
        z = s11_to_z(s11, z0)
    mag = np.abs(s11)
    vs = vswr_arr(np.minimum(mag, 1.0))
    rl = rl_arr(mag)
    s11_db = -rl
    mins = find_minima(f, s11_db)
    xcross = zero_crossings(f, z.imag)
    bands = find_bands(f, vs, vswr_threshold, below=True)
    best = None
    if mins:
        m = mins[0]
        i = m["index"]
        best = {"f": m["f"], "s11_db": m["value"], "z": complex(z[i]), "vswr": float(vs[i]),
                "q_z": q_from_impedance(f, z, i)}
        if best["q_z"]:
            s = vswr_threshold
            best["fbw_estimate_from_q"] = (s - 1) / (math.sqrt(s) * best["q_z"])
    return {"f": f, "s11": s11, "z": z, "vswr": vs, "return_loss": rl, "s11_db": s11_db,
            "minima": mins, "reactance_zero_crossings": xcross, "bands": bands, "best": best,
            "not_available": NOT_AVAILABLE}
