"""Parámetros S: conversiones, métricas, marcadores, bandas y resonancias.
Las operaciones se hacen SIEMPRE con datos complejos; las magnitudes en dB sólo se derivan para mostrar.
Z0 de referencia real y común a todos los puertos (como en Touchstone v1).
"""
from __future__ import annotations

import math

import numpy as np

from .reflection import rl_arr, vswr_arr
from .units import RFInputError


def s_to_z(s: np.ndarray, z0: float = 50.0) -> np.ndarray:
    """S (N,n,n) → Z.  Z = Z0·(I + S)(I − S)^{-1}"""
    s = np.asarray(s, dtype=complex)
    n = s.shape[-1]
    eye = np.eye(n)
    return z0 * np.linalg.solve((eye - s).transpose(0, 2, 1), (eye + s).transpose(0, 2, 1)).transpose(0, 2, 1)


def z_to_s(z: np.ndarray, z0: float = 50.0) -> np.ndarray:
    """S = (Z − Z0·I)(Z + Z0·I)^{-1}"""
    z = np.asarray(z, dtype=complex)
    n = z.shape[-1]
    eye = np.eye(n) * z0
    return np.linalg.solve((z + eye).transpose(0, 2, 1), (z - eye).transpose(0, 2, 1)).transpose(0, 2, 1)


def s_to_y(s, z0=50.0):
    return np.linalg.inv(s_to_z(s, z0))


def y_to_s(y, z0=50.0):
    """S = (I + Z0·Y)⁻¹ (I − Z0·Y): directo, válido aunque Y sea singular (Z inexistente)."""
    a = np.asarray(y, dtype=complex) * z0
    eye = np.broadcast_to(np.eye(a.shape[-1]), a.shape)
    return np.linalg.solve(eye + a, eye - a)


def h_to_z(h):
    """Parámetros híbridos H (2 puertos) → Z:  z11 = Δh/h22, z12 = h12/h22, z21 = −h21/h22, z22 = 1/h22."""
    h = np.asarray(h, dtype=complex)
    h11, h12, h21, h22 = h[:, 0, 0], h[:, 0, 1], h[:, 1, 0], h[:, 1, 1]
    if np.any(np.abs(h22) < 1e-300):
        raise RFInputError("h22 = 0: la matriz Z no existe para estos parámetros H.")
    z = np.empty_like(h)
    z[:, 0, 0] = (h11 * h22 - h12 * h21) / h22
    z[:, 0, 1] = h12 / h22
    z[:, 1, 0] = -h21 / h22
    z[:, 1, 1] = 1 / h22
    return z


def h_to_s(h, z0=50.0):
    """H → S directo (Frickey, IEEE MTT 1994), válido aunque Z no exista (p. ej. resistencia serie, h22 = 0):
        Δ = (h11+Z0)(1+h22·Z0) − h12·h21·Z0
        S11 = ((h11−Z0)(1+h22·Z0) − h12·h21·Z0)/Δ   S12 = 2·h12·Z0/Δ
        S21 = −2·h21·Z0/Δ                            S22 = ((h11+Z0)(1−h22·Z0) + h12·h21·Z0)/Δ"""
    h = np.asarray(h, dtype=complex)
    h11, h12, h21, h22 = h[:, 0, 0], h[:, 0, 1], h[:, 1, 0], h[:, 1, 1]
    d = (h11 + z0) * (1 + h22 * z0) - h12 * h21 * z0
    if np.any(np.abs(d) < 1e-300):
        raise RFInputError("Conversión H→S singular (Δ = 0).")
    s = np.empty_like(h)
    s[:, 0, 0] = ((h11 - z0) * (1 + h22 * z0) - h12 * h21 * z0) / d
    s[:, 0, 1] = 2 * h12 * z0 / d
    s[:, 1, 0] = -2 * h21 * z0 / d
    s[:, 1, 1] = ((h11 + z0) * (1 - h22 * z0) + h12 * h21 * z0) / d
    return s


def g_to_s(g, z0=50.0):
    """G = H⁻¹ (parámetros híbridos inversos)."""
    g = np.asarray(g, dtype=complex)
    if np.any(np.abs(np.linalg.det(g)) < 1e-300):
        raise RFInputError("Matriz G singular: no se puede convertir a S.")
    return h_to_s(np.linalg.inv(g), z0)


def s11_to_z(s11, z0=50.0):
    s11 = np.asarray(s11, dtype=complex)
    with np.errstate(divide="ignore", invalid="ignore"):
        return z0 * (1 + s11) / (1 - s11)


def z_to_s11(z, z0=50.0):
    z = np.asarray(z, dtype=complex)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(np.isinf(z), 1 + 0j, (z - z0) / (z + z0))


def s2_to_abcd(s, z0=50.0):
    s11, s12, s21, s22 = s[:, 0, 0], s[:, 0, 1], s[:, 1, 0], s[:, 1, 1]
    out = np.empty_like(s)
    out[:, 0, 0] = ((1 + s11) * (1 - s22) + s12 * s21) / (2 * s21)
    out[:, 0, 1] = z0 * ((1 + s11) * (1 + s22) - s12 * s21) / (2 * s21)
    out[:, 1, 0] = ((1 - s11) * (1 - s22) - s12 * s21) / (2 * s21 * z0)
    out[:, 1, 1] = ((1 - s11) * (1 + s22) + s12 * s21) / (2 * s21)
    return out


def gamma_in(s, gamma_l):
    """Γin = S11 + S12·S21·ΓL / (1 − S22·ΓL)"""
    s11, s12, s21, s22 = s[:, 0, 0], s[:, 0, 1], s[:, 1, 0], s[:, 1, 1]
    return s11 + s12 * s21 * gamma_l / (1 - s22 * gamma_l)


def db20(x):
    with np.errstate(divide="ignore"):
        return 20 * np.log10(np.abs(x))


def phase_deg(x, unwrap=False):
    ph = np.angle(x)
    return np.degrees(np.unwrap(ph) if unwrap else ph)


def group_delay(f, x):
    """τg = −dφ/dω (s), con fase desenrollada."""
    f = np.asarray(f, dtype=float)
    if f.size < 3:
        return np.full(f.shape, np.nan)
    ph = np.unwrap(np.angle(x))
    return -np.gradient(ph, 2 * np.pi * f)


def trace_metrics(f, x, z0=50.0, reflection=True) -> dict:
    """Métricas de una traza Sij (compleja)."""
    x = np.asarray(x, dtype=complex)
    mag = np.abs(x)
    out = {"db": db20(x), "deg": phase_deg(x), "deg_unwrapped": phase_deg(x, True), "mag": mag,
           "group_delay": group_delay(f, x)}
    if reflection:
        out.update({"vswr": vswr_arr(np.minimum(mag, 1.0)), "return_loss": rl_arr(mag), "z": s11_to_z(x, z0)})
    else:
        out.update({"insertion_loss": -db20(x)})
    return out


def interp_complex(f, x, f_target: float) -> complex:
    f = np.asarray(f, dtype=float)
    if not (f[0] <= f_target <= f[-1]):
        raise RFInputError("La frecuencia del marcador está fuera del rango de datos.")
    return complex(np.interp(f_target, f, np.real(x)), np.interp(f_target, f, np.imag(x)))


def find_bands(f, y, threshold: float, below=True) -> list[dict]:
    """Bandas contiguas donde y ≤ threshold (below) o y ≥ threshold. Cruces por interpolación lineal."""
    f = np.asarray(f, dtype=float)
    y = np.asarray(y, dtype=float)
    ok = (y <= threshold) if below else (y >= threshold)
    ok &= np.isfinite(y) | (below is False)
    bands = []
    i = 0
    n = len(f)
    while i < n:
        if ok[i]:
            j = i
            while j + 1 < n and ok[j + 1]:
                j += 1

            def cross(a, b):
                if y[b] == y[a]:
                    return f[a]
                return f[a] + (threshold - y[a]) * (f[b] - f[a]) / (y[b] - y[a])

            lo = f[0] if i == 0 else cross(i - 1, i)
            hi = f[-1] if j == n - 1 else cross(j, j + 1)
            k = i + int(np.argmin(y[i:j + 1])) if below else i + int(np.argmax(y[i:j + 1]))
            fc = math.sqrt(lo * hi) if lo > 0 else (lo + hi) / 2
            bands.append({"f_low": float(lo), "f_high": float(hi), "bw": float(hi - lo), "f_best": float(f[k]),
                          "best": float(y[k]), "fractional": float((hi - lo) / fc) if fc else None,
                          "open_low": i == 0, "open_high": j == n - 1})
            i = j + 1
        else:
            i += 1
    return bands


def find_minima(f, y, max_count=5) -> list[dict]:
    """Mínimos locales de y (p. ej. |S11| dB) con refinamiento parabólico."""
    y = np.asarray(y, dtype=float)
    f = np.asarray(f, dtype=float)
    idx = [i for i in range(1, len(y) - 1) if y[i] < y[i - 1] and y[i] <= y[i + 1]]
    out = []
    for i in idx:
        y0, y1, y2 = y[i - 1], y[i], y[i + 1]
        den = y0 - 2 * y1 + y2
        p = 0.5 * (y0 - y2) / den if den != 0 else 0.0
        p = max(-1.0, min(1.0, p))
        df = (f[i + 1] - f[i - 1]) / 2
        out.append({"f": float(f[i] + p * df), "value": float(y1 - 0.25 * (y0 - y2) * p), "index": i})
    out.sort(key=lambda d: d["value"])
    return out[:max_count]


def zero_crossings(f, y) -> list[dict]:
    """Cruces por cero de y (p. ej. Im{Z}) con su pendiente (resonancia serie si dX/df > 0)."""
    f = np.asarray(f, dtype=float)
    y = np.asarray(y, dtype=float)
    out = []
    for i in range(len(y) - 1):
        if np.isfinite(y[i]) and np.isfinite(y[i + 1]) and y[i] * y[i + 1] < 0:
            fz = f[i] - y[i] * (f[i + 1] - f[i]) / (y[i + 1] - y[i])
            out.append({"f": float(fz), "kind": "serie" if y[i + 1] > y[i] else "paralelo (antirresonancia)"})
    return out
