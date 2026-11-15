"""Estabilidad de dos puertos y círculos de ganancia (Pozar, Microwave Engineering, cap. 12)."""
from __future__ import annotations

import numpy as np


def stability(s: np.ndarray) -> dict:
    s11, s12, s21, s22 = s[:, 0, 0], s[:, 0, 1], s[:, 1, 0], s[:, 1, 1]
    delta = s11 * s22 - s12 * s21
    with np.errstate(divide="ignore", invalid="ignore"):
        k = (1 - np.abs(s11) ** 2 - np.abs(s22) ** 2 + np.abs(delta) ** 2) / (2 * np.abs(s12 * s21))
        mu = (1 - np.abs(s11) ** 2) / (np.abs(s22 - delta * np.conj(s11)) + np.abs(s12 * s21))
        mu_p = (1 - np.abs(s22) ** 2) / (np.abs(s11 - delta * np.conj(s22)) + np.abs(s12 * s21))
        msg = np.abs(s21) / np.abs(s12)
        mag = np.where(k >= 1, msg * (k - np.sqrt(np.maximum(k ** 2 - 1, 0))), np.nan)
        u = np.abs(s12 * s21 * s11 * s22) / ((1 - np.abs(s11) ** 2) * (1 - np.abs(s22) ** 2))
    return {"delta": delta, "k": k, "mu": mu, "mu_prime": mu_p, "msg_db": 10 * np.log10(msg),
            "mag_db": 10 * np.log10(mag), "unconditionally_stable": mu > 1, "u": u}


def stability_circles(s2: np.ndarray) -> dict:
    """Para una matriz 2×2 (una frecuencia). Centros/radios en el plano ΓL (salida) y ΓS (entrada)."""
    s11, s12, s21, s22 = s2[0, 0], s2[0, 1], s2[1, 0], s2[1, 1]
    d = s11 * s22 - s12 * s21
    den_l = abs(s22) ** 2 - abs(d) ** 2
    den_s = abs(s11) ** 2 - abs(d) ** 2
    out = {}
    if abs(den_l) > 1e-15:
        out["load"] = {"center": np.conj(s22 - d * np.conj(s11)) / den_l, "radius": abs(s12 * s21 / den_l)}
    if abs(den_s) > 1e-15:
        out["source"] = {"center": np.conj(s11 - d * np.conj(s22)) / den_s, "radius": abs(s12 * s21 / den_s)}
    # Región estable: se determina si el origen (Γ=0, |Γin|=|S11|) es estable y si está dentro del círculo
    for key, sref in (("load", s11), ("source", s22)):
        if key in out:
            c, r = out[key]["center"], out[key]["radius"]
            origin_inside = abs(c) < r
            origin_stable = abs(sref) < 1
            out[key]["stable_inside"] = bool(origin_inside == origin_stable)
    return out


def power_gain_circle(s2: np.ndarray, gp_db: float) -> dict | None:
    """Círculo de ganancia de potencia Gp constante en el plano ΓL."""
    s11, s12, s21, s22 = s2[0, 0], s2[0, 1], s2[1, 0], s2[1, 1]
    d = s11 * s22 - s12 * s21
    gp = 10 ** (gp_db / 10) / abs(s21) ** 2
    c2 = s22 - d * np.conj(s11)
    k = (1 - abs(s11) ** 2 - abs(s22) ** 2 + abs(d) ** 2) / (2 * abs(s12 * s21))
    den = 1 + gp * (abs(s22) ** 2 - abs(d) ** 2)
    rad2 = 1 - 2 * k * abs(s12 * s21) * gp + abs(s12 * s21) ** 2 * gp ** 2
    if rad2 < 0 or abs(den) < 1e-15:
        return None
    return {"center": gp * np.conj(c2) / den, "radius": float(np.sqrt(rad2) / abs(den)), "gain_db": gp_db, "plane": "ΓL"}


def available_gain_circle(s2: np.ndarray, ga_db: float) -> dict | None:
    """Círculo de ganancia disponible Ga constante en el plano ΓS."""
    s11, s12, s21, s22 = s2[0, 0], s2[0, 1], s2[1, 0], s2[1, 1]
    d = s11 * s22 - s12 * s21
    ga = 10 ** (ga_db / 10) / abs(s21) ** 2
    c1 = s11 - d * np.conj(s22)
    k = (1 - abs(s11) ** 2 - abs(s22) ** 2 + abs(d) ** 2) / (2 * abs(s12 * s21))
    den = 1 + ga * (abs(s11) ** 2 - abs(d) ** 2)
    rad2 = 1 - 2 * k * abs(s12 * s21) * ga + abs(s12 * s21) ** 2 * ga ** 2
    if rad2 < 0 or abs(den) < 1e-15:
        return None
    return {"center": ga * np.conj(c1) / den, "radius": float(np.sqrt(rad2) / abs(den)), "gain_db": ga_db, "plane": "ΓS"}


def simultaneous_conjugate_match(s2: np.ndarray) -> dict | None:
    s11, s12, s21, s22 = s2[0, 0], s2[0, 1], s2[1, 0], s2[1, 1]
    d = s11 * s22 - s12 * s21
    b1 = 1 + abs(s11) ** 2 - abs(s22) ** 2 - abs(d) ** 2
    b2 = 1 + abs(s22) ** 2 - abs(s11) ** 2 - abs(d) ** 2
    c1 = s11 - d * np.conj(s22)
    c2 = s22 - d * np.conj(s11)
    if abs(c1) < 1e-15 or abs(c2) < 1e-15:
        return None
    disc1, disc2 = b1 ** 2 - 4 * abs(c1) ** 2, b2 ** 2 - 4 * abs(c2) ** 2
    if disc1 < 0 or disc2 < 0:
        return None
    gs = (b1 - np.sign(b1) * np.sqrt(disc1)) / (2 * c1)
    gl = (b2 - np.sign(b2) * np.sqrt(disc2)) / (2 * c2)
    if abs(gs) >= 1 or abs(gl) >= 1:
        return None
    return {"gamma_s": complex(gs), "gamma_l": complex(gl)}
