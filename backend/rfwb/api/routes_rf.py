"""Endpoints: reflexión / carta de Smith, circuitos, componentes, líneas y adaptación."""
from __future__ import annotations

import math

import numpy as np
from fastapi import APIRouter

from ..engine import impedance as imp
from ..engine import matching as mt
from ..engine import reflection as rfl
from ..engine import tline as tl
from ..engine import tolerance as tol
from ..engine.network import describe, zin_cascade
from ..engine.sparams import z_to_s11
from ..engine.steps import Trace
from ..engine.units import RFInputError, fmt_si, require_positive
from .common import J, Model, cplx, qty

router = APIRouter(prefix="/api")
TWO_PI = 2 * math.pi


def gam(z, z0):
    return z_to_s11(np.asarray(z, dtype=complex), z0)


# ───────────── Reflexión / Smith ─────────────
class ReflReq(Model):
    z: str | dict | None = None
    gamma: dict | None = None
    z0: float = 50.0
    f: float | str | None = None


@router.post("/rf/reflection")
def reflection(r: ReflReq):
    z0 = require_positive("Z0", r.z0)
    if r.gamma is not None:
        g = complex(r.gamma["re"], r.gamma["im"])
        if abs(g) > 1 + 1e-9:
            raise RFInputError("|Γ| > 1 corresponde a una carga activa (R < 0); fuera de la carta pasiva.")
        z = rfl.z_from_gamma(g, z0)
    else:
        z = cplx(r.z)
    t = Trace()
    m = rfl.reflection_metrics(z, z0, t)
    eq = None
    if r.f not in (None, "", 0) and not m["is_open"]:
        f = qty(r.f, "Frecuencia")
        w = TWO_PI * require_positive("Frecuencia", f)
        x = z.imag
        eq = {"f": f, "series": {"R": z.real, "kind": "L" if x > 0 else ("C" if x < 0 else None),
                                 "value": (x / w) if x > 0 else (-1 / (w * x) if x < 0 else None)}}
        if z != 0:
            y = 1 / z
            eq["parallel"] = {"R": (1 / y.real) if y.real else math.inf,
                              "kind": "C" if y.imag > 0 else ("L" if y.imag < 0 else None),
                              "value": (y.imag / w) if y.imag > 0 else ((-1 / (w * y.imag)) if y.imag < 0 else None)}
        if eq["series"]["kind"]:
            t.add("Equivalente serie a f", "X > 0 → L = X/ω ;  X < 0 → C = −1/(ωX)", f"f = {fmt_si(f, 'Hz')}",
                  f"R = {z.real:.5g} Ω en serie con {eq['series']['kind']} = "
                  f"{fmt_si(eq['series']['value'], 'H' if eq['series']['kind'] == 'L' else 'F')}", "",
                  "Válido sólo a esta frecuencia: una impedancia medida no determina el circuito en otras frecuencias.")
    m["trace"] = t
    m["equivalent"] = eq
    return J(m)


class RotateReq(Model):
    z: str | dict
    z0: float = 50.0
    length_lambda: float = 0.25
    toward: str = "generator"


@router.post("/rf/line-rotate")
def line_rotate(r: RotateReq):
    z = cplx(r.z)
    z0 = require_positive("Z0", r.z0)
    g = rfl.gamma_from_z(z, z0)
    sign = -1 if r.toward == "generator" else 1
    d = np.linspace(0, r.length_lambda, 181)
    gs = g * np.exp(sign * 4j * np.pi * d)
    zend = rfl.z_from_gamma(complex(gs[-1]), z0)
    return J({"gamma": gs, "d_lambda": d, "z_end": zend, "gamma_end": gs[-1],
              "note": "Línea sin pérdidas de impedancia Z0: el punto gira sobre un círculo de |Γ| constante "
                      "(sentido horario hacia el generador; una vuelta completa = λ/2)."})


# ───────────── Circuitos ─────────────
class SweepReq(Model):
    start: float | str
    stop: float | str
    n: int = 401
    log: bool = True


class CircuitReq(Model):
    topology: str
    f: float | str
    R: float | str = 0
    L: float | str = 0
    C: float | str = 0
    z0: float = 50.0
    v_rms: float = 1.0
    sweep: SweepReq | None = None


def _sweep_block(f, z, z0):
    g = gam(z, z0)
    with np.errstate(divide="ignore", invalid="ignore"):
        return {"f": f, "z": z, "z_mag": np.abs(z), "z_deg": np.degrees(np.angle(z)), "gamma": g,
                "vswr": rfl.vswr_arr(np.minimum(np.abs(g), 1.0)), "s11_db": -rfl.rl_arr(np.abs(g))}


@router.post("/circuit/analyze")
def circuit(r: CircuitReq):
    R, L, C = qty(r.R, "R"), qty(r.L, "L"), qty(r.C, "C")
    f = qty(r.f, "Frecuencia")
    res = imp.analyze_circuit(r.topology, f, R, L, C, r.z0, r.v_rms)
    if not math.isinf(abs(res["z"])):
        res["reflection"] = rfl.reflection_metrics(res["z"], r.z0)
        res["reflection"]["trace"] = None
    if r.sweep:
        fs, zs = imp.sweep_circuit(r.topology, qty(r.sweep.start), qty(r.sweep.stop), r.sweep.n, R, L, C, r.sweep.log)
        res["sweep"] = _sweep_block(fs, zs, r.z0)
    return J(res)


class NetworkReq(Model):
    expr: str
    f: float | str
    z0: float = 50.0
    sweep: SweepReq | None = None


@router.post("/circuit/network")
def network(r: NetworkReq):
    node = imp.parse_network(r.expr)
    f = require_positive("Frecuencia", qty(r.f, "Frecuencia"))
    z = complex(imp.network_z(node, f)[0])
    t = Trace()
    t.add("Red interpretada", "'+' = serie (Z suman) ;  '||' = paralelo (Y suman)", imp.network_to_text(node), "", "")
    w = TWO_PI * f
    t.add("Impedancias de los elementos", "Z_R = R ; Z_L = jωL ; Z_C = 1/(jωC)", f"ω = {w:.6g} rad/s")
    out = {"tree": node, "text": imp.network_to_text(node), "z": z, "f": f}
    if math.isfinite(abs(z)):
        t.add("Impedancia equivalente", "Reducción serie/paralelo recursiva", "", f"{z.real:.6g} {'+' if z.imag >= 0 else '−'} j{abs(z.imag):.6g}", "Ω")
        m = rfl.reflection_metrics(z, r.z0, t)
        out.update({"reflection": m, "z_mag": abs(z), "z_deg": math.degrees(math.atan2(z.imag, z.real))})
        if z != 0:
            out["y"] = 1 / z
    out["trace"] = t
    if r.sweep:
        a, b = qty(r.sweep.start), qty(r.sweep.stop)
        if b <= a:
            raise RFInputError("La frecuencia final debe ser mayor que la inicial.")
        fs = np.geomspace(a, b, r.sweep.n) if r.sweep.log else np.linspace(a, b, r.sweep.n)
        out["sweep"] = _sweep_block(fs, imp.network_z(node, fs), r.z0)
    return J(out)


class CompReq(Model):
    kind: str
    value: float | str
    q: float | None = None
    q_freq: float | str | None = None
    esr: float | None = None
    srf: float | str | None = None
    f_start: float | str = 1e6
    f_stop: float | str = 3e9
    n: int = 601


@router.post("/component/impedance")
def component(r: CompReq):
    v = qty(r.value, "Valor")
    real = imp.ComponentModel(r.kind, v, q=r.q, q_freq=qty(r.q_freq) if r.q_freq else None, esr=r.esr,
                              srf=qty(r.srf) if r.srf else None)
    ideal = imp.ComponentModel(r.kind, v)
    f = np.geomspace(qty(r.f_start), qty(r.f_stop), r.n)
    zr, zi = real.z(f), ideal.z(f)
    notes = []
    if real.srf:
        notes.append(f"Por encima de la SRF ({fmt_si(real.srf, 'Hz')}) el componente cambia de carácter "
                     f"({'capacitivo' if r.kind.upper() == 'L' else 'inductivo'}).")
    if real.is_ideal():
        notes.append("Sin datos de Q/ESR/SRF: el modelo real coincide con el ideal.")
    return J({"f": f, "ideal": {"z": zi, "mag": np.abs(zi)}, "real": {"z": zr, "mag": np.abs(zr),
              "q": np.abs(zr.imag) / np.where(zr.real > 0, zr.real, np.nan)}, "notes": notes,
              "model": {"kind": r.kind, "value": v, "q": r.q, "esr": r.esr, "srf": real.srf}})


# ───────────── Líneas de transmisión ─────────────
class GeoReq(Model):
    kind: str
    D: float | str | None = None
    d: float | str | None = None
    er: float = 1.0
    W: float | str | None = None
    h: float | str | None = None
    # Microstrip completa (opcional): si se da f, se usa el modelo dispersivo con pérdidas
    f: float | str | None = None
    t: float | str | None = None      # espesor del cobre (35u = 1 oz)
    tand: float = 0.0
    rho: float = 1.68e-8              # resistividad del conductor (cobre)
    rough: float | str | None = None  # rugosidad RMS


@router.post("/tline/geometry")
def tline_geometry(r: GeoReq):
    """Longitudes en metros con prefijo SI opcional: '2.95m' = 2.95 mm."""
    g = {k: (qty(v, k) if v not in (None, "") else None) for k, v in (("D", r.D), ("d", r.d), ("W", r.W), ("h", r.h))}
    out = tl.line_from_geometry(r.kind, er=r.er, **g)
    if r.kind == "microstrip" and r.f not in (None, ""):
        out["quasi_static"] = {"z0": out["z0"], "eps_eff": out["eps_eff"]}
        full = tl.microstrip_dispersive(g["W"], g["h"], r.er, qty(r.f, "Frecuencia"), qty(r.t, "t") if r.t not in (None, "") else 0.0,
                                        r.tand, r.rho, qty(r.rough, "rugosidad") if r.rough not in (None, "") else 0.0)
        out.update(full)
    return J(out)


class LineReq(Model):
    z0: float = 50.0
    f: float | str
    length: float
    length_unit: str = "m"     # m | lambda | deg
    vf: float = 1.0
    atten_db_per_m: float = 0.0
    load: str = "arbitrary"
    zl: str | dict = "100+j50"
    p_inc: float = 1.0
    sweep_span: float = 0.5
    atten_ref_hz: float | str | None = None   # si se indica, α escala con √(f/f_ref)


@router.post("/tline/analyze")
def tline_analyze(r: LineReq):
    f = qty(r.f, "Frecuencia")
    lam = tl.propagation(f, r.vf)["lambda"]
    length = r.length * lam if r.length_unit == "lambda" else (r.length / 360 * lam if r.length_unit == "deg" else r.length)
    zl = cplx(r.zl, "Carga") if r.load == "arbitrary" else 0j
    f_ref = qty(r.atten_ref_hz, "Frecuencia de referencia") if r.atten_ref_hz not in (None, "") else None
    res = tl.analyze_line(r.z0, f, length, r.vf, r.atten_db_per_m, r.load, zl, r.p_inc, atten_ref_hz=f_ref)
    res["length_m"] = length
    res["profile"]["gamma_rel"] = res["profile"]["gamma"]
    zl_ = res["zl"]
    # Zin frente a frecuencia (misma longitud física)
    fs = np.linspace(max(f * (1 - r.sweep_span), f * 0.01), f * (1 + r.sweep_span), 301)
    a_at = (lambda ff: tl.scaled_attenuation(r.atten_db_per_m, f_ref, ff)) if f_ref else (lambda ff: r.atten_db_per_m)
    zin_f = np.array([complex(tl.zin_line(zl_, r.z0, tl.propagation(ff, r.vf, a_at(ff))["gamma"], length)) for ff in fs])
    res["freq_sweep"] = {"f": fs, "zin": zin_f, "gamma": gam(zin_f, r.z0)}
    return J(res)


# ───────────── Adaptación ─────────────
class MatchReq(Model):
    method: str = "L"
    zl: str | dict
    zs: str | dict = "50"
    f0: float | str
    z0: float = 50.0
    q_net: float = 2.0
    comp_q: float | None = None
    stub: str = "short"
    vf: float = 1.0
    vswr_target: float = 2.0
    span: float = 0.5
    load_model: str = "series_equiv"
    d1_lambda: float = 0.1
    spacing_lambda: float = 0.125
    snap: str = "none"          # none | E12 | E24 | library
    library_ids: list[int] | None = None


def _traj_gamma(sol, z0):
    return [{"label": seg["label"], "gamma": gam(np.array(seg["z"]), z0)} for seg in sol["trajectory"]]


@router.post("/match/design")
def match_design(r: MatchReq):
    zl, zs, f0 = cplx(r.zl, "Carga"), cplx(r.zs, "Fuente"), qty(r.f0, "Frecuencia")
    res = mt.design(r.method, zl, zs, f0, r.z0, r.q_net, r.comp_q, r.stub, r.vf, r.vswr_target, r.span,
                    r.load_model, r.d1_lambda, r.spacing_lambda)
    available = None
    if r.snap == "library":
        from .routes_sys import library_values
        available = library_values(r.library_ids)
    for s in res["solutions"]:
        s["trajectory_gamma"] = _traj_gamma(s, r.z0)
        del s["trajectory"]
        s["sweep"]["gamma_ref"] = gam(s["sweep"]["zin"], r.z0)
        if r.snap != "none" and any(e.get("part") in ("L", "C") for e in s["elements"]):
            snapped = mt.snap_elements(s["elements"], r.snap if r.snap in ("E12", "E24", "E6") else None, available)
            a = mt.analyze_solution({"topology": s["topology"], "elements": snapped}, zl, zs, f0, r.z0, r.vswr_target,
                                    r.span, r.load_model)
            s["snapped"] = {"elements": snapped, "description": a["description"], "gamma_after": a["gamma_after"],
                            "vswr_after": a["vswr_after"], "bandwidth": a["bandwidth"],
                            "sweep": {"f": a["sweep"]["f"], "s11_db": a["sweep"]["s11_db"], "vswr": a["sweep"]["vswr"]},
                            "series": r.snap}
    res["target_gamma"] = gam(np.array([zs.conjugate()]), r.z0)[0]
    res["load_gamma"] = gam(np.array([zl]), r.z0)[0]
    return J(res)


class TolReq(Model):
    elements: list[dict]
    zl: str | dict
    zs: str | dict = "50"
    f0: float | str
    span: float = 0.2
    load_model: str = "series_equiv"
    tol_l: float = 5.0
    tol_c: float = 5.0
    tol_len: float = 1.0
    n: int = 500
    dist: str = "uniform"
    vswr_target: float = 2.0


@router.post("/match/tolerance")
def match_tolerance(r: TolReq):
    zl, zs, f0 = cplx(r.zl), cplx(r.zs), qty(r.f0)
    f = np.linspace(f0 * (1 - r.span), f0 * (1 + r.span), 121)
    zl_f = mt.load_model_z(zl, f0, f, r.load_model)
    return J(tol.monte_carlo(r.elements, zl_f, zs, f, f0, r.tol_l, r.tol_c, r.tol_len, r.n, r.dist, r.vswr_target))


@router.post("/match/evaluate")
def match_evaluate(r: TolReq):
    """Evalúa una red arbitraria (lista de elementos) — usado tras editar valores manualmente."""
    zl, zs, f0 = cplx(r.zl), cplx(r.zs), qty(r.f0)
    a = mt.analyze_solution({"topology": "Manual", "elements": r.elements}, zl, zs, f0, 50.0, r.vswr_target, r.span,
                            r.load_model)
    a["description"] = [describe(e) for e in r.elements]
    return J(a)
