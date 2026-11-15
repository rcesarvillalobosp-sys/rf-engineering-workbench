"""Diseño de redes de adaptación.

Objetivo: que la impedancia vista desde la fuente sea Zs* (adaptación conjugada → máxima transferencia).
Todas las soluciones se VERIFICAN numéricamente evaluando la red resultante; las que no cumplen se descartan.
Cualquier adaptación con elementos reactivos es exacta sólo a f0: se calcula la respuesta en frecuencia,
el ancho de banda real para el VSWR objetivo y el límite teórico de Bode–Fano.
"""
from __future__ import annotations

import cmath
import math

import numpy as np
from scipy.optimize import brentq

from .network import describe, element_z, zin_cascade
from .reflection import gamma_from_z, power_wave_gamma, rl_arr, vswr, vswr_arr
from .steps import Trace
from .units import C0, RFInputError, fmt_complex, fmt_si, require_positive

TWO_PI = 2 * math.pi
METHODS = {
    "L": "Red L (2 elementos)",
    "PI": "Red Pi (Q seleccionable)",
    "T": "Red T (Q seleccionable)",
    "QWT": "Transformador λ/4",
    "STUB1": "Stub simple en paralelo",
    "STUB2": "Doble stub en paralelo",
}


# ───────────────────────── Utilidades ─────────────────────────
def _x_to_element(x: float, kind: str, f0: float, q: float | None) -> dict | None:
    """Reactancia serie X (Ω) o susceptancia paralelo B (S) → L o C."""
    w = TWO_PI * f0
    if kind == "series":
        if abs(x) < 1e-9:
            return None
        el = {"kind": "series", "part": "L", "value": x / w} if x > 0 else {"kind": "series", "part": "C", "value": -1 / (w * x)}
    else:
        if abs(x) < 1e-12:
            return None
        el = {"kind": "shunt", "part": "C", "value": x / w} if x > 0 else {"kind": "shunt", "part": "L", "value": -1 / (w * x)}
    if q:
        el["q"] = q
    return el


def _l_solutions(zl: complex, zt: complex) -> list[list[tuple[str, float]]]:
    """Redes L ideales que transforman ZL en Zt. Devuelve listas de (tipo, X o B) fuente→carga."""
    out = []
    yl = 1 / zl
    gl, bl = yl.real, yl.imag
    rt, xt = zt.real, zt.imag
    # A: paralelo junto a la carga, serie hacia la fuente
    disc = gl / rt - gl * gl
    if disc >= -1e-15:
        for sgn in (1, -1):
            b = -bl + sgn * math.sqrt(max(disc, 0))
            yp = complex(gl, bl + b)
            xs = xt - (1 / yp).imag
            out.append([("series", xs), ("shunt", b)])
            if disc <= 1e-15:
                break
    # B: serie junto a la carga, paralelo hacia la fuente
    yt = 1 / zt
    gt, bt = yt.real, yt.imag
    rl, xl = zl.real, zl.imag
    disc = rl / gt - rl * rl
    if disc >= -1e-15:
        for sgn in (1, -1):
            x = -xl + sgn * math.sqrt(max(disc, 0))
            zs = complex(rl, xl + x)
            b = bt - (1 / zs).imag
            out.append([("shunt", b), ("series", x)])
            if disc <= 1e-15:
                break
    return out


def _to_elements(desc, f0, q):
    els = []
    for kind, v in desc:
        el = _x_to_element(v, kind, f0, q)
        if el:
            els.append(el)
    return els


def _verify(elements, zl, zt, f0, tol=1e-6) -> bool:
    zin = complex(zin_cascade([f0], elements, zl)[0])
    return abs(power_wave_gamma(zin, zt.conjugate())) < tol if zt.real > 0 else False


def _lambda(f0, vf):
    return vf * C0 / f0


# ───────────────────────── Métodos ─────────────────────────
def design_l(zl, zs, f0, q=None):
    zt = zs.conjugate()
    sols = []
    for desc in _l_solutions(zl, zt):
        els = _to_elements(desc, f0, None)
        if _verify(els, zl, zt, f0):
            topo = "Paralelo en carga + serie" if desc[-1][0] == "shunt" else "Serie en carga + paralelo"
            sols.append({"topology": topo, "elements": _apply_q(els, q), "ideal_elements": els})
    return sols


def _apply_q(els, q):
    if not q:
        return els
    return [dict(e, q=q) if e.get("part") in ("L", "C") else e for e in els]


def design_pi(zl, zs, f0, q_net, q=None):
    zt = zs.conjugate()
    rmax = max(zl.real, zt.real)
    rv = rmax / (1 + q_net ** 2)
    if rv >= min(zl.real, zt.real):
        raise RFInputError(f"Q = {q_net:g} demasiado bajo para una red Pi: se requiere Q > "
                           f"{math.sqrt(rmax / min(zl.real, zt.real) - 1):.3f}.")
    sols = []
    for d1 in _l_solutions(zl, complex(rv, 0)):
        if d1[-1][0] != "shunt":
            continue  # parte 1: paralelo en la carga + serie
        for d2 in _l_solutions(complex(rv, 0), zt):
            if d2[0][0] != "shunt":
                continue  # parte 2: serie en Rv + paralelo en la fuente
            desc = [d2[0], ("series", d2[1][1] + d1[0][1]), d1[1]]
            els = _to_elements(desc, f0, None)
            if _verify(els, zl, zt, f0):
                sols.append({"topology": f"Pi (Rv = {rv:.4g} Ω)", "elements": _apply_q(els, q), "ideal_elements": els,
                             "virtual_r": rv})
    return sols


def design_t(zl, zs, f0, q_net, q=None):
    zt = zs.conjugate()
    rmin = min(zl.real, zt.real)
    rv = rmin * (1 + q_net ** 2)
    if rv <= max(zl.real, zt.real):
        raise RFInputError(f"Q = {q_net:g} demasiado bajo para una red T: se requiere Q > "
                           f"{math.sqrt(max(zl.real, zt.real) / rmin - 1):.3f}.")
    sols = []
    for d1 in _l_solutions(zl, complex(rv, 0)):
        if d1[-1][0] != "series":
            continue  # parte 1: serie en la carga + paralelo
        for d2 in _l_solutions(complex(rv, 0), zt):
            if d2[-1][0] != "shunt":
                continue  # parte 2: paralelo en Rv + serie hacia la fuente
            desc = [d2[0], ("shunt", d2[1][1] + d1[0][1]), d1[1]]
            els = _to_elements(desc, f0, None)
            if _verify(els, zl, zt, f0):
                sols.append({"topology": f"T (Rv = {rv:.4g} Ω)", "elements": _apply_q(els, q), "ideal_elements": els,
                             "virtual_r": rv})
    return sols


def design_qwt(zl, zs, f0, vf=1.0):
    if abs(zs.imag) > 1e-9:
        raise RFInputError("El transformador λ/4 requiere una fuente/línea de alimentación real.")
    rs = zs.real
    lam = _lambda(f0, vf)
    gl = gamma_from_z(zl, rs)
    sols = []
    if abs(zl.imag) < 1e-9:
        z1 = math.sqrt(rs * zl.real)
        sols.append({"topology": f"λ/4 directo, Z1 = {z1:.4g} Ω",
                     "elements": [{"kind": "line", "z0": z1, "length_m": lam / 4, "vf": vf}], "z1": z1})
    else:
        phi = cmath.phase(gl) % (2 * math.pi)
        s = vswr(abs(gl))
        d_max = phi / (4 * math.pi) * lam  # Γ real positivo: R = Rs·VSWR
        for d, r, name in ((d_max, rs * s, "máximo de tensión"), ((d_max + lam / 4) % (lam / 2), rs / s, "mínimo de tensión")):
            z1 = math.sqrt(rs * r)
            sols.append({"topology": f"Línea {d / lam:.4f}λ hasta {name} (R = {r:.4g} Ω) + λ/4 con Z1 = {z1:.4g} Ω",
                         "elements": [{"kind": "line", "z0": z1, "length_m": lam / 4, "vf": vf},
                                      {"kind": "line", "z0": rs, "length_m": d, "vf": vf}], "z1": z1})
    zt = zs.conjugate()
    return [s for s in sols if _verify(s["elements"], zl, zt, f0, 1e-6)]


def _stub_length(b_needed: float, y0: float, stub: str, lam: float) -> float:
    """Longitud de stub (paralelo) con susceptancia de entrada b_needed (S)."""
    if stub == "open":       # Y = jY0·tan(βl)
        bl = math.atan(b_needed / y0)
    else:                     # Y = −jY0·cot(βl)
        bl = math.pi / 2 if abs(b_needed) < 1e-15 else math.atan(-y0 / b_needed)
    bl %= math.pi
    return bl / (2 * math.pi) * lam


def _y_line(zl, z0, beta, d):
    t = math.tan(beta * d)
    if cmath.isinf(zl):
        return complex(0, t) / z0 if abs(t) < 1e15 else complex(math.inf)
    z = z0 * (zl + 1j * z0 * t) / (z0 + 1j * zl * t)
    return 1 / z


def design_stub1(zl, zs, f0, z0, stub="short", vf=1.0):
    lam = _lambda(f0, vf)
    beta = TWO_PI / lam
    yt = 1 / zs.conjugate()
    fn = lambda d: _y_line(zl, z0, beta, d).real - yt.real
    ds = np.linspace(1e-9, lam / 2 - 1e-9, 4001)
    vals = np.array([fn(d) for d in ds])
    roots = []
    for i in range(len(ds) - 1):
        if np.isfinite(vals[i]) and np.isfinite(vals[i + 1]) and vals[i] * vals[i + 1] < 0:
            roots.append(brentq(fn, ds[i], ds[i + 1], xtol=1e-15))
    sols = []
    for d in roots:
        y = _y_line(zl, z0, beta, d)
        b = yt.imag - y.imag
        ls = _stub_length(b, 1 / z0, stub, lam)
        els = [{"kind": "shunt", "part": f"stub_{stub}", "z0": z0, "length_m": ls, "vf": vf},
               {"kind": "line", "z0": z0, "length_m": d, "vf": vf}]
        if _verify(els, zl, zs.conjugate(), f0, 1e-6):
            sols.append({"topology": f"Stub {'abierto' if stub == 'open' else 'cortocircuitado'}: d = {d / lam:.4f}λ, ℓ = {ls / lam:.4f}λ",
                         "elements": els, "d_lambda": d / lam, "l_lambda": ls / lam})
    return sols


def design_stub2(zl, zs, f0, z0, stub="short", vf=1.0, d1_lambda=0.1, spacing_lambda=0.125):
    lam = _lambda(f0, vf)
    beta = TWO_PI / lam
    if abs((spacing_lambda * 2) % 1) < 1e-6:
        raise RFInputError("La separación entre stubs no puede ser múltiplo de λ/2.")
    yt = 1 / zs.conjugate()
    y1 = _y_line(zl, z0, beta, d1_lambda * lam)
    ds = spacing_lambda * lam

    def y2_of(b1):
        y = y1 + 1j * b1
        return 1 / (z0 * ((1 / y) + 1j * z0 * math.tan(beta * ds)) / (z0 + 1j * (1 / y) * math.tan(beta * ds)))

    fn = lambda psi: y2_of(math.tan(psi) / z0).real - yt.real
    psis = np.linspace(-math.pi / 2 + 1e-6, math.pi / 2 - 1e-6, 6001)
    vals = np.array([fn(p) for p in psis])
    sols = []
    for i in range(len(psis) - 1):
        if np.isfinite(vals[i]) and np.isfinite(vals[i + 1]) and vals[i] * vals[i + 1] < 0:
            p = brentq(fn, psis[i], psis[i + 1], xtol=1e-14)
            b1 = math.tan(p) / z0
            b2 = yt.imag - y2_of(b1).imag
            l1 = _stub_length(b1, 1 / z0, stub, lam)
            l2 = _stub_length(b2, 1 / z0, stub, lam)
            els = [{"kind": "shunt", "part": f"stub_{stub}", "z0": z0, "length_m": l2, "vf": vf},
                   {"kind": "line", "z0": z0, "length_m": ds, "vf": vf},
                   {"kind": "shunt", "part": f"stub_{stub}", "z0": z0, "length_m": l1, "vf": vf},
                   {"kind": "line", "z0": z0, "length_m": d1_lambda * lam, "vf": vf}]
            if _verify(els, zl, zs.conjugate(), f0, 1e-6):
                sols.append({"topology": f"Doble stub: ℓ1 = {l1 / lam:.4f}λ, ℓ2 = {l2 / lam:.4f}λ",
                             "elements": els, "l1_lambda": l1 / lam, "l2_lambda": l2 / lam})
    if not sols:
        g_norm = (y1 * z0).real
        raise RFInputError(f"La carga transformada (g = {g_norm:.3f}) cae en la región prohibida del doble stub "
                           f"para separación {spacing_lambda}λ. Cambie la distancia d1 o la separación.")
    return sols


# ───────────────────────── Análisis de soluciones ─────────────────────────
def load_model_z(zl: complex, f0: float, f: np.ndarray, model: str) -> np.ndarray:
    """Modelo de la carga en frecuencia. 'constant': ZL fijo. 'series_equiv': R + L o C serie equivalente a f0."""
    if model == "constant" or abs(zl.imag) < 1e-12:
        return np.full(f.shape, zl)
    w0 = TWO_PI * f0
    if zl.imag > 0:
        return zl.real + 1j * (zl.imag / w0) * TWO_PI * f
    c = -1 / (w0 * zl.imag)
    return zl.real - 1j / (TWO_PI * f * c)


def transducer_gain(f, elements, zl_f, zs):
    from .network import cascade_abcd
    abcd = cascade_abcd(f, elements)
    a, b, c, d = abcd[:, 0, 0], abcd[:, 0, 1], abcd[:, 1, 0], abcd[:, 1, 1]
    i2 = 1 / ((a * zl_f + b) + zs * (c * zl_f + d))
    pl = 0.5 * np.abs(i2) ** 2 * zl_f.real
    pav = 1 / (8 * zs.real)
    return pl / pav


def bandwidth_around(f, vs, f0, target):
    i0 = int(np.argmin(np.abs(f - f0)))
    if not np.isfinite(vs[i0]) or vs[i0] > target:
        return None
    lo = i0
    while lo > 0 and vs[lo - 1] <= target:
        lo -= 1
    hi = i0
    while hi < len(f) - 1 and vs[hi + 1] <= target:
        hi += 1

    def cross(i, j):
        if vs[i] == vs[j]:
            return f[i]
        return f[i] + (target - vs[i]) * (f[j] - f[i]) / (vs[j] - vs[i])

    f_lo = f[0] if lo == 0 else cross(lo - 1, lo)
    f_hi = f[-1] if hi == len(f) - 1 else cross(hi, hi + 1)
    return {"f_low": f_lo, "f_high": f_hi, "bw": f_hi - f_lo, "fractional": (f_hi - f_lo) / f0,
            "edge_limited": lo == 0 or hi == len(f) - 1}


def bode_fano(zl: complex, f0: float, vswr_target: float) -> dict | None:
    if abs(zl.imag) < 1e-12 or zl.real <= 0:
        return None
    gm = (vswr_target - 1) / (vswr_target + 1)
    q = abs(zl.imag) / zl.real
    frac = math.pi / (q * math.log(1 / gm))
    eq = "R–L serie" if zl.imag > 0 else "R–C serie"
    return {"q_load": q, "gamma_m": gm, "max_fractional_bw": frac, "max_bw": frac * f0, "equivalent": eq,
            "formula": "Δf/f0 ≤ π / (Q_L · ln(1/Γm)) ,  Q_L = |X_L|/R_L"}


def analyze_solution(sol: dict, zl: complex, zs: complex, f0: float, z0: float, vswr_target: float,
                     span: float, load_model: str, n: int = 401) -> dict:
    f = np.linspace(f0 * (1 - span), f0 * (1 + span), n)
    f = f[f > 0]
    zl_f = load_model_z(zl, f0, f, load_model)
    zin = zin_cascade(f, sol["elements"], zl_f)
    g = (zin - zs.conjugate()) / (zin + zs)
    mag = np.abs(g)
    vs = vswr_arr(mag)
    gt = transducer_gain(f, sol["elements"], zl_f, zs)
    zin0 = complex(zin_cascade([f0], sol["elements"], zl)[0])
    g0 = power_wave_gamma(zin0, zs)
    bw = bandwidth_around(f, vs, f0, vswr_target)
    gt0 = float(transducer_gain(np.array([f0]), sol["elements"], np.array([zl]), zs)[0])
    return {
        **sol,
        "description": [describe(e) for e in sol["elements"]],
        "zin_f0": zin0, "gamma_after": g0, "vswr_after": vswr(abs(g0)),
        "transducer_gain_db_f0": 10 * math.log10(gt0) if gt0 > 0 else -math.inf,
        "bandwidth": bw,
        "sweep": {"f": f, "gamma": g, "s11_db": -rl_arr(mag), "vswr": vs, "gt_db": 10 * np.log10(np.maximum(gt, 1e-30)),
                  "zin": zin},
    }


def design(method: str, zl: complex, zs: complex, f0: float, z0: float = 50.0, q_net: float = 2.0,
           comp_q: float | None = None, stub: str = "short", vf: float = 1.0, vswr_target: float = 2.0,
           span: float = 0.5, load_model: str = "series_equiv", d1_lambda: float = 0.1,
           spacing_lambda: float = 0.125) -> dict:
    f0 = require_positive("Frecuencia", f0)
    z0 = require_positive("Z0", z0)
    if method not in METHODS:
        raise RFInputError(f"Método desconocido: {method}")
    if zl.real <= 0:
        raise RFInputError("La carga debe tener parte real positiva: una carga puramente reactiva no puede absorber potencia.")
    if zs.real <= 0:
        raise RFInputError("La impedancia de fuente debe tener parte real positiva.")
    if vswr_target <= 1:
        raise RFInputError("El VSWR objetivo debe ser > 1.")
    t = Trace()
    g_before = power_wave_gamma(zl, zs)
    t.add("Objetivo de adaptación", "Zin = Zs*  (adaptación conjugada)", f"Zs = {fmt_complex(zs)}",
          f"Zin objetivo = {fmt_complex(zs.conjugate())}", "",
          "Con Zin = Zs* la fuente entrega su potencia disponible a la red sin pérdidas.")
    t.add("Desadaptación inicial", "Γ = (ZL − Zs*)/(ZL + Zs)", f"ZL = {fmt_complex(zl)}",
          f"|Γ| = {abs(g_before):.4f} → VSWR = {vswr(abs(g_before)):.4g}")
    if method == "L":
        sols = design_l(zl, zs, f0, comp_q)
        t.add("Red L", "Paralelo en carga: (B + B_L)² = G_L/R_t − G_L² ;  Serie en carga: (X + X_L)² = R_L/G_t − R_L²",
              "", f"{len(sols)} soluciones válidas", "",
              "Q de la red L fijado por la relación de resistencias: Q = √(R_alta/R_baja − 1).")
        rl_, rt_ = zl.real, zs.real
        qmin = math.sqrt(max(rl_, rt_) / min(rl_, rt_) - 1)
        t.add("Q nodal mínimo", "Q = √(R_max/R_min − 1)", f"√({max(rl_, rt_):g}/{min(rl_, rt_):g} − 1)", f"{qmin:.4g}",
              "", f"Ancho de banda aproximado BW ≈ f0/Q ≈ {fmt_si(f0 / (qmin * 2) if qmin else math.inf, 'Hz')} (Q cargado ≈ Q/2).")
    elif method == "PI":
        sols = design_pi(zl, zs, f0, q_net, comp_q)
        t.add("Red Pi", "Rv = R_max / (1 + Q²)", f"Rv = {max(zl.real, zs.real):g}/(1 + {q_net:g}²)",
              f"{max(zl.real, zs.real) / (1 + q_net ** 2):.5g} Ω", "",
              "Dos redes L espalda con espalda a través de una resistencia virtual Rv < min(Rs, RL). Mayor Q → menor ancho de banda.")
    elif method == "T":
        sols = design_t(zl, zs, f0, q_net, comp_q)
        t.add("Red T", "Rv = R_min · (1 + Q²)", f"Rv = {min(zl.real, zs.real):g}·(1 + {q_net:g}²)",
              f"{min(zl.real, zs.real) * (1 + q_net ** 2):.5g} Ω", "", "Rv > max(Rs, RL).")
    elif method == "QWT":
        sols = design_qwt(zl, zs, f0, vf)
        t.add("Transformador λ/4", "Z1 = √(Rs · R)", "Si ZL es complejo, se añade una línea hasta un punto de impedancia real (máximo o mínimo de tensión).",
              f"{len(sols)} soluciones", "", "La longitud λ/4 sólo es exacta a f0: el ancho de banda decrece al aumentar la relación R/Rs.")
    elif method == "STUB1":
        sols = design_stub1(zl, zs, f0, z0, stub, vf)
        t.add("Stub simple", "Re{Y(d)} = Re{Yt} ;  B_stub = Im{Yt} − Im{Y(d)}",
              "Búsqueda de d en [0, λ/2) con verificación numérica", f"{len(sols)} soluciones", "",
              "Stub abierto: Y = jY0·tan(βℓ). Stub en corto: Y = −jY0·cot(βℓ).")
    else:
        sols = design_stub2(zl, zs, f0, z0, stub, vf, d1_lambda, spacing_lambda)
        t.add("Doble stub", "Re{Y2} = Re{Yt} tras la sección de separación", f"d1 = {d1_lambda}λ, separación = {spacing_lambda}λ",
              f"{len(sols)} soluciones", "", "Existe una región prohibida de cargas que no pueden adaptarse con una separación dada.")
    if not sols:
        raise RFInputError("No existe solución con este método para la carga indicada.")
    analyzed = [analyze_solution(s, zl, zs, f0, z0, vswr_target, span, load_model) for s in sols]
    for a in analyzed:
        a["trajectory"] = _traj(f0, a["elements"], zl)
    bf = bode_fano(zl, f0, vswr_target)
    if bf:
        t.add("Límite de Bode–Fano", bf["formula"], f"Q_L = {bf['q_load']:.4g}, Γm = {bf['gamma_m']:.4f} (VSWR {vswr_target:g})",
              f"Δf máx ≈ {fmt_si(bf['max_bw'], 'Hz')} ({100 * bf['max_fractional_bw']:.2f} %)", "",
              "Cota teórica para CUALQUIER red sin pérdidas con esta carga (modelo " + bf["equivalent"] + " a f0).")
    return {"method": method, "method_name": METHODS[method], "zl": zl, "zs": zs, "f0": f0, "z0": z0,
            "gamma_before": g_before, "vswr_before": vswr(abs(g_before)), "solutions": analyzed,
            "bode_fano": bf, "vswr_target": vswr_target, "load_model": load_model, "trace": t,
            "lambda_m": _lambda(f0, vf), "vf": vf,
            "narrowband_warning": "La adaptación es exacta sólo en f0. Fuera de f0 el VSWR crece; consulte el ancho de banda calculado."}


def _traj(f0, elements, zl):
    from .network import trajectory
    return trajectory(f0, elements, zl, steps=48)


# ───────────────────────── Ajuste a valores normalizados ─────────────────────────
E_SERIES = {
    "E6": [1.0, 1.5, 2.2, 3.3, 4.7, 6.8],
    "E12": [1.0, 1.2, 1.5, 1.8, 2.2, 2.7, 3.3, 3.9, 4.7, 5.6, 6.8, 8.2],
    "E24": [1.0, 1.1, 1.2, 1.3, 1.5, 1.6, 1.8, 2.0, 2.2, 2.4, 2.7, 3.0, 3.3, 3.6, 3.9, 4.3, 4.7, 5.1, 5.6, 6.2,
            6.8, 7.5, 8.2, 9.1],
}


def nearest_e_value(v: float, series: str = "E24") -> float:
    if v <= 0:
        return v
    dec = math.floor(math.log10(v))
    cands = [m * 10 ** d for d in (dec - 1, dec, dec + 1) for m in E_SERIES[series]]
    return min(cands, key=lambda c: abs(math.log(c / v)))


def snap_elements(elements: list[dict], series: str | None = "E24", available: dict | None = None) -> list[dict]:
    """Sustituye L/C por el valor normalizado (serie E) o por el más cercano disponible en la biblioteca.
    available = {"L": [{"value":..,"q":..,"id":..,"name":..}], "C": [...]}"""
    out = []
    for e in elements:
        if e.get("part") in ("L", "C"):
            e2 = dict(e)
            if available and available.get(e["part"]):
                best = min(available[e["part"]], key=lambda c: abs(math.log(c["value"] / e["value"])))
                e2["value"] = best["value"]
                if best.get("q"):
                    e2["q"] = best["q"]
                e2["component"] = {"id": best.get("id"), "name": best.get("name")}
            elif series:
                e2["value"] = nearest_e_value(e["value"], series)
            out.append(e2)
        else:
            out.append(e)
    return out
