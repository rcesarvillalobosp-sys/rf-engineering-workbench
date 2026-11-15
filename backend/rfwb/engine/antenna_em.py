"""Modelo electromagnético ANALÍTICO de antenas de hilo delgado (dipolo y monopolo).

Hipótesis (Balanis, Antenna Theory, caps. 4 y 8):
  * Hilo recto, delgado (radio a ≪ λ y a ≪ L), alimentado en el centro, en espacio libre.
  * Distribución de corriente sinusoidal  I(z) = I0·sin(k(L/2 − |z|)).
  * Monopolo de altura h sobre plano de masa infinito y perfecto: teoría de imágenes (dipolo de L = 2h).
Resultados: diagrama de campo lejano, directividad, resistencia de radiación, reactancia (FEM inducida),
pérdidas óhmicas del hilo, eficiencia de radiación y ganancia. Son resultados de MODELO, no mediciones:
no incluyen el entorno, el cable de alimentación, balun ni planos de masa finitos.
"""
from __future__ import annotations

import math

import numpy as np
from scipy.integrate import quad
from scipy.special import sici

from .steps import Trace
from .units import C0, RFInputError, fmt_si, require_positive

ETA0 = 376.730313668
MU0 = 4e-7 * math.pi
EULER = 0.5772156649015329


def _pattern(kl: float, theta: np.ndarray) -> np.ndarray:
    """F(θ) = [cos(kL/2·cosθ) − cos(kL/2)] / sinθ   (dipolo de longitud total L, kl = kL)."""
    s = np.sin(theta)
    with np.errstate(divide="ignore", invalid="ignore"):
        f = (np.cos(kl / 2 * np.cos(theta)) - math.cos(kl / 2)) / s
    return np.where(np.abs(s) < 1e-12, 0.0, f)


def _rad_integral(kl: float) -> float:
    g = lambda t: float(_pattern(kl, np.array([t]))[0]) ** 2 * math.sin(t)
    val, _ = quad(g, 0, math.pi, limit=400, epsabs=1e-13, epsrel=1e-11)
    return val


def dipole_impedance_max(kl: float, ka: float) -> complex:
    """Impedancia referida a la corriente máxima I0 (Balanis 8-60a/8-60b), FEM inducida."""
    si1, ci1 = sici(kl)
    si2, ci2 = sici(2 * kl)
    _, ci_h = sici(2 * ka * ka / kl) if ka > 0 else (0, 0)
    rr = ETA0 / (2 * math.pi) * (EULER + math.log(kl) - ci1 + 0.5 * math.sin(kl) * (si2 - 2 * si1)
                                 + 0.5 * math.cos(kl) * (EULER + math.log(kl / 2) + ci2 - 2 * ci1))
    xm = ETA0 / (4 * math.pi) * (2 * si1 + math.cos(kl) * (2 * si1 - si2)
                                 - math.sin(kl) * (2 * ci1 - ci2 - ci_h))
    return complex(rr, xm)


def wire_antenna(kind: str, f: float, length: float, radius: float, sigma: float = 5.8e7,
                 z0: float = 50.0, sweep_span: float = 0.5, n_sweep: int = 401) -> dict:
    kind = kind.lower()
    if kind not in ("dipole", "monopole"):
        raise RFInputError("Tipo de antena: dipole | monopole.")
    f = require_positive("Frecuencia", f)
    length = require_positive("Longitud", length)
    radius = require_positive("Radio del hilo", radius)
    sigma = require_positive("Conductividad", sigma)
    lam = C0 / f
    k = 2 * math.pi / lam
    L = 2 * length if kind == "monopole" else length       # dipolo equivalente
    kl, ka = k * L, k * radius
    t = Trace()
    warnings = []
    if radius > 0.01 * lam or L / radius < 50:
        warnings.append("El hilo no es delgado (a > 0.01λ o L/a < 50): la distribución sinusoidal pierde precisión.")
    if L > 1.5 * lam:
        warnings.append("L > 1.5λ: la aproximación de corriente sinusoidal es menos fiable cerca de los nulos de corriente.")
    t.add("Número de onda", "k = 2π/λ ;  λ = c/f", f"λ = {fmt_si(lam, 'm')}", f"k = {k:.6g} rad/m · L/λ = {L / lam:.5f}", "",
          "Monopolo: se analiza su dipolo imagen de longitud 2h." if kind == "monopole" else "")
    integ = _rad_integral(kl)
    rr_max = ETA0 / (2 * math.pi) * integ
    t.add("Diagrama de campo lejano", "F(θ) = [cos(kL/2·cosθ) − cos(kL/2)] / sinθ", "Corriente sinusoidal, hilo delgado",
          "", "", "Plano E: dependencia en θ. Plano H (θ = 90°): omnidireccional.")
    t.add("Resistencia de radiación (ref. I máx.)", "R_r = (η/2π)·∫₀^π F(θ)²·sinθ dθ", f"∫ = {integ:.6f}", f"{rr_max:.4f}", "Ω")
    th = np.linspace(0, math.pi, 3601)
    fpat = _pattern(kl, th)
    fmax2 = float(np.max(fpat ** 2))
    d = 2 * fmax2 / integ
    t.add("Directividad", "D = 4π·U_max/P_rad = 2·F_max² / ∫F²·sinθ dθ", f"F_max² = {fmax2:.6f}", f"{d:.5f} ({10 * math.log10(d):.3f} dBi)", "")
    zmax = dipole_impedance_max(kl, ka)
    s_feed = math.sin(kl / 2)
    if abs(s_feed) < 1e-6:
        raise RFInputError("La corriente en el punto de alimentación es nula (L ≈ nλ): la impedancia de entrada del "
                           "modelo sinusoidal diverge. Alimente fuera del centro o use un método numérico (MoM).")
    zin = zmax / s_feed ** 2
    rs = math.sqrt(2 * math.pi * f * MU0 / (2 * sigma))
    rl_max = rs / (2 * math.pi * radius) * (L / 2 - math.sin(kl) / (2 * k))
    t.add("Impedancia de entrada", "Z_in = Z_m / sin²(kL/2)  (Z_m por FEM inducida, Balanis 8-60)",
          f"Z_m = {zmax.real:.4f} {'+' if zmax.imag >= 0 else '−'} j{abs(zmax.imag):.4f} Ω · sin²(kL/2) = {s_feed ** 2:.5f}",
          f"{zin.real:.4f} {'+' if zin.imag >= 0 else '−'} j{abs(zin.imag):.4f}", "Ω (dipolo)")
    t.add("Pérdidas óhmicas del hilo", "R_s = √(ωμ0/2σ) ;  R_L = R_s/(2πa)·∫|I(z)/I0|² dz",
          f"R_s = {rs:.6g} Ω/□ · a = {fmt_si(radius, 'm')}", f"{rl_max:.5g}", "Ω (ref. I máx.)",
          "Sólo pérdidas del conductor; no incluye plano de masa, balun ni cable.")
    eff = rr_max / (rr_max + rl_max)
    if kind == "monopole":
        d *= 2
        zin /= 2
        t.add("Monopolo (teoría de imágenes)", "D_mono = 2·D_dip ;  Z_mono = Z_dip / 2", "Plano de masa infinito y perfecto",
              f"D = {d:.5f} ({10 * math.log10(d):.3f} dBi) · Z = {zin.real:.4f} {'+' if zin.imag >= 0 else '−'} j{abs(zin.imag):.4f} Ω", "")
    gain = eff * d
    t.add("Eficiencia y ganancia", "e = R_r/(R_r + R_L) ;  G = e·D", f"e = {eff:.6f}",
          f"G = {gain:.5f} ({10 * math.log10(gain):.3f} dBi)", "")
    # Barrido de impedancia (mismas dimensiones físicas)
    fs = np.linspace(f * (1 - sweep_span), f * (1 + sweep_span), n_sweep)
    zs = []
    for ff in fs:
        kk = 2 * math.pi * ff / C0
        sf = math.sin(kk * L / 2)
        z = dipole_impedance_max(kk * L, kk * radius) / sf ** 2 if abs(sf) > 1e-6 else complex(np.nan, np.nan)
        zs.append(z / 2 if kind == "monopole" else z)
    zs = np.array(zs)
    deg = np.degrees(th)
    pat_db = 10 * np.log10(np.maximum(fpat ** 2 / fmax2, 1e-6))
    if kind == "monopole":
        keep = deg <= 90
        deg, pat_db = deg[keep], pat_db[keep]
    return {"kind": kind, "f": f, "lambda": lam, "length": length, "radius": radius, "L_over_lambda": L / lam,
            "rr_max": rr_max * (0.5 if kind == "monopole" else 1), "z_in": zin, "directivity": d,
            "directivity_dbi": 10 * math.log10(d), "efficiency": eff, "gain": gain, "gain_dbi": 10 * math.log10(gain),
            "rl_max": rl_max * (0.5 if kind == "monopole" else 1), "rs": rs,
            "pattern": {"theta_deg": deg, "db": pat_db}, "sweep": {"f": fs, "z": zs},
            "warnings": warnings, "trace": t,
            "model": "Analítico: hilo delgado, corriente sinusoidal (Balanis caps. 4 y 8). Resultado de modelo, no medición."}
