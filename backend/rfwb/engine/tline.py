"""Líneas de transmisión: propagación, transformación de impedancias y perfiles a lo largo de la línea.

Convención: d = distancia medida desde la carga hacia el generador (d = 0 en la carga).
    γ = α + jβ ,  Γ(d) = ΓL · e^{−2γd}
    Zin(d) = Z0 · (ZL + Z0·tanh(γd)) / (Z0 + ZL·tanh(γd))
"""
from __future__ import annotations

import cmath
import math

import numpy as np

from .reflection import gamma_from_z, is_open, return_loss_db, vswr
from .steps import Trace
from .units import C0, NP_TO_DB, RFInputError, fmt_complex, fmt_si, require_nonneg, require_positive, require_range

LINE_TYPES = {
    "ideal": "Línea genérica (Z0 y vf definidos por el usuario)",
    "coax": "Coaxial (geometría D/d, εr)",
    "microstrip": "Microstrip (Hammerstad–Jensen, cuasi-estático)",
    "twowire": "Bifilar (D, d, εr)",
}


def line_from_geometry(kind: str, **g) -> dict:
    """Z0 y factor de velocidad a partir de la geometría. Devuelve {z0, vf, eps_eff, note}."""
    if kind == "coax":
        D, d, er = require_positive("D", g["D"]), require_positive("d", g["d"]), require_positive("εr", g.get("er", 1.0))
        if D <= d:
            raise RFInputError("El diámetro interior del blindaje D debe ser mayor que el del conductor d.")
        z0 = 60 / math.sqrt(er) * math.log(D / d)
        return {"z0": z0, "vf": 1 / math.sqrt(er), "eps_eff": er,
                "formula": "Z0 = (60/√εr)·ln(D/d) ; vf = 1/√εr"}
    if kind == "twowire":
        D, d, er = require_positive("D", g["D"]), require_positive("d", g["d"]), require_positive("εr", g.get("er", 1.0))
        if D <= d:
            raise RFInputError("La separación entre centros D debe ser mayor que el diámetro d.")
        z0 = 120 / math.sqrt(er) * math.acosh(D / d)
        return {"z0": z0, "vf": 1 / math.sqrt(er), "eps_eff": er,
                "formula": "Z0 = (120/√εr)·acosh(D/d) ; vf = 1/√εr"}
    if kind == "microstrip":
        W, h, er = require_positive("W", g["W"]), require_positive("h", g["h"]), require_positive("εr", g.get("er", 4.4))
        u = W / h
        # Hammerstad & Jensen (1980), espesor de pista despreciable
        a = 1 + (1 / 49) * math.log((u ** 4 + (u / 52) ** 2) / (u ** 4 + 0.432)) + (1 / 18.7) * math.log(1 + (u / 18.1) ** 3)
        b = 0.564 * ((er - 0.9) / (er + 3)) ** 0.053
        eeff = (er + 1) / 2 + (er - 1) / 2 * (1 + 10 / u) ** (-a * b)
        fu = 6 + (2 * math.pi - 6) * math.exp(-((30.666 / u) ** 0.7528))
        z01 = 60 * math.log(fu / u + math.sqrt(1 + (2 / u) ** 2))
        z0 = z01 / math.sqrt(eeff)
        return {"z0": z0, "vf": 1 / math.sqrt(eeff), "eps_eff": eeff,
                "formula": "Hammerstad–Jensen cuasi-estático (t→0, sin dispersión). Precisión típica < 1 %."}
    raise RFInputError(f"Tipo de línea sin geometría: {kind}")


def propagation(f: float, vf: float, atten_db_per_m: float = 0.0) -> dict:
    f = require_positive("Frecuencia", f)
    vf = require_range("Factor de velocidad", vf, 1e-3, 1.0)
    atten_db_per_m = require_nonneg("Atenuación", atten_db_per_m)
    lam = vf * C0 / f
    beta = 2 * math.pi / lam
    alpha = atten_db_per_m / NP_TO_DB
    return {"lambda": lam, "lambda0": C0 / f, "beta": beta, "alpha": alpha, "gamma": complex(alpha, beta),
            "vp": vf * C0}


def microstrip_dispersive(W: float, h: float, er: float, f: float, t: float = 35e-6, tand: float = 0.0,
                          rho: float = 1.68e-8, rough: float = 0.0, f_er: float = 1e9) -> dict:
    """Microstrip a la frecuencia f con scikit-rf (MLine): Hammerstad–Jensen con espesor de pista,
    dispersión de Kirschning–Jansen, dieléctrico de Djordjevic–Svensson (εr y tanδ dados a f_er)
    y pérdidas de conductor (resistividad ρ, rugosidad RMS) y dieléctricas."""
    import warnings

    import skrf
    from skrf.media import MLine
    for name, v in (("W", W), ("h", h), ("εr", er), ("f", f), ("f_er", f_er)):
        require_positive(name, v)
    for name, v in (("t", t), ("tanδ", tand), ("ρ", rho), ("rugosidad", rough)):
        require_nonneg(name, v)
    freq = skrf.Frequency.from_f([f], unit="Hz")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        m = MLine(freq, w=W, h=h, t=t if t > 0 else None, ep_r=er, tand=tand, rho=rho if rho > 0 else None,
                  rough=rough, f_epr_tand=f_er)
        z0c = complex(np.atleast_1d(m.z0_characteristic)[0])
        eeff = complex(np.atleast_1d(m.ep_reff_f)[0]).real
        ac = float(np.atleast_1d(m.alpha_conductor)[0]) if rho > 0 else 0.0
        ad = float(np.atleast_1d(m.alpha_dielectric)[0])
    return {"z0": z0c.real, "z0_imag": z0c.imag, "eps_eff": eeff, "vf": 1 / math.sqrt(eeff),
            "alpha_c_db_m": ac * NP_TO_DB, "alpha_d_db_m": ad * NP_TO_DB, "atten_db_per_m": (ac + ad) * NP_TO_DB,
            "f": f, "formula": "scikit-rf MLine: Hammerstad–Jensen (con espesor) + dispersión Kirschning–Jansen; "
                               "dieléctrico Djordjevic–Svensson; pérdidas de conductor con rugosidad (Hammerstad)."}


def scaled_attenuation(atten_ref_db_m: float, f_ref: float, f: float) -> float:
    """α(f) = α(f_ref)·√(f/f_ref): modelo de pérdidas de conductor para cables coaxiales."""
    require_positive("Frecuencia de referencia de la atenuación", f_ref)
    return require_nonneg("Atenuación", atten_ref_db_m) * math.sqrt(require_positive("Frecuencia", f) / f_ref)


def zin_line(zl: complex, z0: float, gamma: complex, d: float | np.ndarray):
    d = np.asarray(d, dtype=float)
    t = np.tanh(gamma * d)
    if is_open(zl):
        with np.errstate(divide="ignore", invalid="ignore"):
            return z0 / t
    with np.errstate(divide="ignore", invalid="ignore"):
        return z0 * (zl + z0 * t) / (z0 + zl * t)


def analyze_line(z0: float, f: float, length: float, vf: float = 1.0, atten_db_per_m: float = 0.0,
                 load: str = "arbitrary", zl: complex = 50 + 0j, p_inc_w: float = 1.0,
                 profile_points: int = 401, atten_ref_hz: float | None = None) -> dict:
    z0 = require_positive("Z0", z0)
    length = require_nonneg("Longitud", length)
    if load == "open":
        zl = complex(math.inf, 0)
    elif load == "short":
        zl = 0j
    elif load == "matched":
        zl = complex(z0, 0)
    elif load != "arbitrary":
        raise RFInputError(f"Tipo de carga desconocido: {load}")
    if not is_open(zl) and zl.real < 0:
        raise RFInputError("La carga debe ser pasiva (R ≥ 0).")
    t = Trace()
    if atten_ref_hz and atten_db_per_m > 0:
        a_ref = atten_db_per_m
        atten_db_per_m = scaled_attenuation(a_ref, atten_ref_hz, f)
        t.add("Atenuación a la frecuencia de trabajo", "α(f) = α(f_ref) · √(f / f_ref)",
              f"α = {a_ref:g} dB/m · √({fmt_si(f, 'Hz')} / {fmt_si(atten_ref_hz, 'Hz')})", f"{atten_db_per_m:.6g}", "dB/m",
              "Aproximación de pérdidas de conductor (efecto pelicular). Desprecia las pérdidas dieléctricas, "
              "que crecen ∝ f: conviene usar el dato del fabricante a una frecuencia cercana.")
    pr = propagation(f, vf, atten_db_per_m)
    lam, beta, alpha, gam = pr["lambda"], pr["beta"], pr["alpha"], pr["gamma"]
    t.add("Longitud de onda en la línea", "λ = vf · c / f", f"λ = {vf:g} · 299 792 458 / {fmt_si(f, 'Hz')}",
          fmt_si(lam, "m"), "", f"En el vacío λ0 = {fmt_si(pr['lambda0'], 'm')}.")
    t.add("Constante de fase", "β = 2π / λ", f"β = 2π / {lam:.6g}", f"{beta:.6g}", "rad/m")
    t.add("Constante de atenuación", "α[Np/m] = α[dB/m] / 8.686", f"α = {atten_db_per_m:g} / 8.686", f"{alpha:.6g}",
          "Np/m", "Modelo de atenuación constante a la frecuencia indicada.")
    t.add("Constante de propagación", "γ = α + jβ", "", fmt_complex(gam, "1/m"), "1/m")
    theta = beta * length
    t.add("Longitud eléctrica", "θ = β·ℓ ;  ℓ/λ", f"θ = {beta:.6g} · {length:g}",
          f"{math.degrees(theta):.4f}° ({length / lam:.5f} λ)", "",
          "El patrón de impedancias se repite cada λ/2.")
    gl = gamma_from_z(zl, z0)
    t.add("Coeficiente de reflexión en la carga", "ΓL = (ZL − Z0)/(ZL + Z0)",
          "ZL = ∞ → ΓL = 1" if is_open(zl) else f"ZL = {fmt_complex(zl)}",
          f"{abs(gl):.5f} ∠ {math.degrees(cmath.phase(gl)) if abs(gl) else 0:.3f}°")
    zin = complex(zin_line(zl, z0, gam, length))
    gin = gl * cmath.exp(-2 * gam * length)
    t.add("Coeficiente de reflexión a la entrada", "Γin = ΓL · e^{−2γℓ}",
          f"|Γin| = {abs(gl):.5f} · e^(−2·{alpha:.4g}·{length:g})", f"{abs(gin):.5f} ∠ {math.degrees(cmath.phase(gin)) if abs(gin) else 0:.3f}°",
          "", "Las pérdidas reducen |Γ| hacia el generador: mejora aparente del VSWR medido.")
    if load == "open":
        formula = "Zin = Z0 · coth(γℓ)"
    elif load == "short":
        formula = "Zin = Z0 · tanh(γℓ)"
    else:
        formula = "Zin = Z0 (ZL + Z0 tanh γℓ)/(Z0 + ZL tanh γℓ)"
    t.add("Impedancia de entrada", formula, "", fmt_complex(zin) if np.isfinite(zin) else "∞", "Ω")
    s_load, s_in = vswr(abs(gl)), vswr(abs(gin))
    rl_in = return_loss_db(abs(gin))
    t.add("VSWR", "VSWR = (1+|Γ|)/(1−|Γ|)", "", f"en carga {s_load:.4g} · en entrada {s_in:.4g}", ":1")
    # Balance de potencias (hipótesis explícitas)
    p_ref = p_inc_w * abs(gin) ** 2
    p_in = p_inc_w - p_ref
    p_load = p_inc_w * math.exp(-2 * alpha * length) * (1 - abs(gl) ** 2)
    p_lost = p_in - p_load
    t.add("Balance de potencia", "P_refl = Pinc|Γin|² ; P_carga = Pinc·e^{−2αℓ}(1−|ΓL|²)",
          f"Pinc = {p_inc_w:g} W", f"Reflejada {p_ref:.5g} W · Carga {p_load:.5g} W · Disipada en línea {p_lost:.5g} W",
          "W", "Hipótesis: generador adaptado a Z0 que entrega Pinc como onda incidente; Z0 real; régimen estacionario.")

    d = np.linspace(0, length if length > 0 else lam / 2, profile_points)
    zd = zin_line(zl, z0, gam, d)
    gd = gl * np.exp(-2 * gam * d)
    v_rel = np.abs(np.exp(gam * d) * (1 + gd))  # |V(d)| / |V+ en la carga|
    i_rel = np.abs(np.exp(gam * d) * (1 - gd)) / z0
    return {
        "lambda": lam, "lambda0": pr["lambda0"], "beta": beta, "alpha": alpha, "gamma": gam, "vp": pr["vp"],
        "theta_deg": math.degrees(theta), "length_lambda": length / lam, "zl": zl, "gamma_load": gl,
        "gamma_in": gin, "zin": zin, "vswr_load": s_load, "vswr_in": s_in, "return_loss_in_db": rl_in,
        "atten_db_per_m": atten_db_per_m, "p_inc": p_inc_w, "p_reflected": p_ref, "p_into_line": p_in, "p_load": p_load, "p_line_loss": p_lost,
        "profile": {"d": d, "z": zd, "gamma": gd, "v_rel": v_rel, "i_rel": i_rel},
        "trace": t,
    }
