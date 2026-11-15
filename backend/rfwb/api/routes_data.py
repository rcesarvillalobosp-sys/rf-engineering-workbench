"""Endpoints: Touchstone, conjuntos de datos, parámetros S, estabilidad, TDR, antenas y calibración."""
from __future__ import annotations

import math

import numpy as np
from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from .. import datasets as dsets
from ..engine import antenna as ant
from ..engine import calibration as cal
from ..engine import impedance as imp
from ..engine import sparams as sp
from ..engine import stability as stb
from ..engine import tdr as tdrm
from ..engine import mixedmode as mm
from ..engine.network import abcd_to_s, cascade_abcd
from ..engine.units import RFInputError
from ..io.touchstone import parse_touchstone, skrf_crosscheck, write_touchstone
from .common import J, Model, qty

router = APIRouter(prefix="/api")

ORIGIN_LABEL = {"imported": "Datos importados desde Touchstone", "simulated": "Simulado — modelo",
                "measured": "Medición real — VNA conectado", "derived": "Derivado (procesado)"}


def _param_dict(s):
    n = s.shape[1]
    return {f"S{i + 1}{j + 1}": s[:, i, j] for i in range(n) for j in range(n)}


# ───────────── Touchstone ─────────────
class TSReq(Model):
    filename: str
    text: str
    save: bool = False
    name: str | None = None


@router.post("/touchstone/parse")
def ts_parse(r: TSReq):
    if len(r.text) > 50_000_000:
        raise RFInputError("Archivo demasiado grande (> 50 MB).")
    d = parse_touchstone(r.text, r.filename)
    check = skrf_crosscheck(r.text, r.filename, d)
    out = {"summary": d.summary(), "skrf_check": check, "f": d.f,
           "params": _param_dict(d.s), "db": {k: sp.db20(v) for k, v in _param_dict(d.s).items()}, "origin": "imported",
           "origin_label": ORIGIN_LABEL["imported"]}
    if r.save:
        meta = {"summary": d.summary(), "skrf_check": check}
        out["dataset_id"] = dsets.save(r.name or r.filename, "imported", d.f, d.s, d.z0, r.filename, meta)
    return J(out)


@router.get("/datasets")
def ds_list():
    return J(dsets.listing())


@router.get("/datasets/{ds_id}")
def ds_get(ds_id: int):
    d = dsets.load(ds_id)
    d["params"] = _param_dict(d.pop("s"))
    d["origin_label"] = ORIGIN_LABEL.get(d["origin"], d["origin"])
    return J(d)


@router.delete("/datasets/{ds_id}")
def ds_delete(ds_id: int):
    dsets.delete(ds_id)
    return {"ok": True}


@router.get("/datasets/{ds_id}/export")
def ds_export(ds_id: int, kind: str = "touchstone", fmt: str = "RI", unit: str = "GHZ"):
    d = dsets.load(ds_id)
    if len(set(d["z0"])) > 1:
        raise RFInputError("Exportación v1 requiere Z0 común a todos los puertos.")
    comments = [f"RF Engineering Workbench — {d['name']}", f"Origen: {ORIGIN_LABEL.get(d['origin'], d['origin'])}"]
    if kind == "touchstone":
        txt = write_touchstone(d["f"], d["s"], d["z0"][0], fmt, unit, comments)
        return PlainTextResponse(txt, headers={"Content-Disposition": f'attachment; filename="{_safe(d["name"])}.s{d["nports"]}p"'})
    if kind == "csv":
        p = _param_dict(d["s"])
        head = ["f_Hz"] + [f"{k}_{c}" for k in p for c in ("re", "im", "dB", "deg")]
        lines = ["# " + c for c in comments] + [";".join(head)]
        for i, f in enumerate(d["f"]):
            row = [f"{f:.10g}"]
            for v in p.values():
                x = v[i]
                row += [f"{x.real:.10g}", f"{x.imag:.10g}", f"{20 * math.log10(abs(x)) if abs(x) else -300:.6f}",
                        f"{math.degrees(math.atan2(x.imag, x.real)):.4f}"]
            lines.append(";".join(row))
        return PlainTextResponse("\n".join(lines) + "\n",
                                 headers={"Content-Disposition": f'attachment; filename="{_safe(d["name"])}.csv"'})
    raise RFInputError("Tipo de exportación no válido.")


def _safe(s):
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in s)[:80] or "datos"


class SimReq(Model):
    name: str
    kind: str = "twoport"       # twoport (cascada) | oneport (expresión a masa)
    elements: list[dict] | None = None
    expr: str | None = None
    f_start: float | str
    f_stop: float | str
    n: int = 401
    z0: float = 50.0


@router.post("/datasets/simulated")
def ds_simulated(r: SimReq):
    a, b = qty(r.f_start), qty(r.f_stop)
    if b <= a or a <= 0:
        raise RFInputError("Rango de frecuencias no válido.")
    if not (2 <= r.n <= 20001):
        raise RFInputError("Número de puntos entre 2 y 20001.")
    f = np.linspace(a, b, r.n)
    if r.kind == "oneport":
        z = imp.network_z(imp.parse_network(r.expr or ""), f)
        s = sp.z_to_s11(z, r.z0).reshape(-1, 1, 1)
        meta = {"model": r.expr}
    else:
        if not r.elements:
            raise RFInputError("Defina al menos un elemento.")
        els = [_norm_el(e) for e in r.elements]
        s = abcd_to_s(cascade_abcd(f, els), r.z0)
        meta = {"model": els}
    ds_id = dsets.save(r.name, "simulated", f, s, r.z0, None, meta)
    return {"id": ds_id}


def _norm_el(e: dict) -> dict:
    """Convierte valores con prefijo SI ('100n', '0.1') a float y valida el elemento."""
    out = dict(e)
    for k in ("value", "z0", "length_m", "vf"):
        if k in out and isinstance(out[k], str):
            out[k] = qty(out[k], k)
    if out.get("kind") == "line":
        if not (out.get("z0", 0) > 0 and out.get("length_m", -1) >= 0 and 0 < out.get("vf", 1) <= 1):
            raise RFInputError("Línea: Z0 > 0, longitud ≥ 0 y 0 < vf ≤ 1.")
    elif out.get("part") in ("L", "C", "R") and not (out.get("value", 0) > 0):
        raise RFInputError(f"{out.get('part')}: el valor debe ser positivo.")
    return out


# ───────────── Parámetros S ─────────────
class SPReq(Model):
    dataset_id: int
    marker_f: float | str | None = None
    rl_threshold_db: float = 10.0
    vswr_threshold: float = 2.0


@router.post("/sparams/analyze")
def sp_analyze(r: SPReq):
    d = dsets.load(r.dataset_id)
    f, s, n = d["f"], d["s"], d["nports"]
    z0 = d["z0"][0]
    traces = {}
    for i in range(n):
        for j in range(n):
            name = f"S{i + 1}{j + 1}"
            refl = i == j
            m = sp.trace_metrics(f, s[:, i, j], d["z0"][i], reflection=refl)
            m["x"] = s[:, i, j]
            if refl:
                m["bands"] = sp.find_bands(f, -m["return_loss"], -r.rl_threshold_db, below=True)
                m["minima"] = sp.find_minima(f, m["db"])
                m["x_zero_crossings"] = sp.zero_crossings(f, np.imag(m["z"]))
            else:
                m["bands_3db"] = sp.find_bands(f, m["db"], float(np.nanmax(m["db"])) - 3, below=False)
            traces[name] = m
    labs = (d["meta"].get("summary") or {}).get("port_labels") or d["meta"].get("port_labels")
    out = {"f": f, "nports": n, "z0": d["z0"], "name": d["name"], "origin": d["origin"],
           "labels": {f"S{i + 1}{j + 1}": f"S[{labs[i]},{labs[j]}]" for i in range(n) for j in range(n)} if labs else None,
           "origin_label": ORIGIN_LABEL.get(d["origin"]), "traces": traces}
    if n == 2:
        st = stb.stability(s)
        out["stability"] = st
    if r.marker_f not in (None, ""):
        fm = qty(r.marker_f, "Frecuencia del marcador")
        mk = {"f": fm, "values": {}}
        for name in traces:
            i, j = int(name[1]) - 1, int(name[2]) - 1
            x = sp.interp_complex(f, s[:, i, j], fm)
            v = {"x": x, "db": 20 * math.log10(abs(x)) if abs(x) else -math.inf,
                 "deg": math.degrees(math.atan2(x.imag, x.real)), "mag": abs(x)}
            if i == j:
                from ..engine.reflection import reflection_metrics, z_from_gamma
                zz = z_from_gamma(x, d["z0"][i]) if abs(x) <= 1 + 1e-9 else complex(sp.s11_to_z(np.array([x]), d["z0"][i])[0])
                v["z"] = zz
                if abs(x) < 1:
                    rm = reflection_metrics(zz, d["z0"][i])
                    v.update({"vswr": rm["vswr"], "return_loss": rm["return_loss_db"]})
            else:
                v["insertion_loss"] = -v["db"]
            mk["values"][name] = v
        if n >= 2:
            k = int(np.argmin(np.abs(f - fm)))
            zm = sp.s_to_z(s[k:k + 1], z0)[0]
            mk["z_matrix"] = zm
            mk["nearest_index"] = k
        out["marker"] = mk
    return J(out)


class CirReq(Model):
    dataset_id: int
    f: float | str
    gains_db: list[float] = []


@router.post("/sparams/circles")
def sp_circles(r: CirReq):
    d = dsets.load(r.dataset_id)
    if d["nports"] != 2:
        raise RFInputError("Los círculos de estabilidad/ganancia requieren un dispositivo de 2 puertos.")
    f = d["f"]
    fm = qty(r.f)
    k = int(np.argmin(np.abs(f - fm)))
    s2 = d["s"][k]
    st = stb.stability(d["s"][k:k + 1])
    out = {"f": f[k], "k": st["k"][0], "mu": st["mu"][0], "delta": st["delta"][0], "mag_db": st["mag_db"][0],
           "msg_db": st["msg_db"][0], "unconditionally_stable": bool(st["unconditionally_stable"][0]),
           "stability_circles": stb.stability_circles(s2), "gain_circles": [], "available_gain_circles": [],
           "conjugate_match": stb.simultaneous_conjugate_match(s2)}
    for g in r.gains_db:
        c = stb.power_gain_circle(s2, g)
        if c:
            out["gain_circles"].append(c)
        c2 = stb.available_gain_circle(s2, g)
        if c2:
            out["available_gain_circles"].append(c2)
    return J(out)


class TDRReq(Model):
    dataset_id: int
    param: str = "S11"
    mode: str = "lowpass"
    window: str = "kaiser"
    beta: float = 6.0
    vf: float = 1.0


@router.post("/sparams/tdr")
def sp_tdr(r: TDRReq):
    d = dsets.load(r.dataset_id)
    i, j = int(r.param[1]) - 1, int(r.param[2]) - 1
    if i != j:
        raise RFInputError("TDR se aplica a parámetros de reflexión (S11, S22…).")
    res = tdrm.tdr(d["f"], d["s"][:, i, j], d["z0"][i], r.vf, r.mode, r.window, r.beta)
    res["origin"] = d["origin"]
    return J(res)


# ───────────── Antenas ─────────────
class AntModel(Model):
    kind: str = "series_rlc"
    f0: float | str = 433e6
    R: float = 50.0
    Q: float = 10.0
    f_start: float | str = 380e6
    f_stop: float | str = 480e6
    n: int = 801


class AntReq(Model):
    source: str = "model"            # model | dataset | table
    dataset_id: int | None = None
    port: int = 1
    model: AntModel | None = None
    table: list[dict] | None = None   # [{f, r, x}]
    z0: float = 50.0
    vswr_threshold: float = 2.0
    label: str | None = None


@router.post("/antenna/analyze")
def antenna(r: AntReq):
    if r.source == "dataset":
        d = dsets.load(r.dataset_id)
        p = r.port - 1
        res = ant.analyze_antenna(d["f"], s11=d["s"][:, p, p], z0=d["z0"][p], vswr_threshold=r.vswr_threshold)
        origin, detail = d["origin"], f"{d['name']} (puerto {r.port})"
    elif r.source == "table":
        rows = sorted(r.table or [], key=lambda q: float(q["f"]))
        if len(rows) < 3:
            raise RFInputError("Introduzca al menos 3 filas (f, R, X).")
        f = np.array([qty(q["f"]) for q in rows])
        z = np.array([complex(float(q["r"]), float(q["x"])) for q in rows])
        res = ant.analyze_antenna(f, z=z, z0=r.z0, vswr_threshold=r.vswr_threshold)
        origin, detail = "calculated", "Tabla de impedancias introducida manualmente"
    else:
        m = r.model or AntModel()
        f = np.linspace(qty(m.f_start), qty(m.f_stop), m.n)
        z = ant.equivalent_model(m.kind, qty(m.f0), m.R, m.Q, f)
        res = ant.analyze_antenna(f, z=z, z0=r.z0, vswr_threshold=r.vswr_threshold)
        origin = "simulated"
        detail = f"Modelo de circuito equivalente {'RLC serie' if m.kind == 'series_rlc' else 'RLC paralelo'}: f0={qty(m.f0):g} Hz, R={m.R:g} Ω, Q={m.Q:g}"
    res["gamma"] = res["s11"]
    res["origin"] = origin
    res["origin_label"] = ORIGIN_LABEL.get(origin, "Calculado — datos introducidos")
    res["source_detail"] = detail
    res["label"] = r.label or detail
    return J(res)


# ───────────── Calibración SOL ─────────────
class CalReq(Model):
    raw_id: int
    open_id: int
    short_id: int
    load_id: int
    name: str | None = None
    port: int = 1
    kit: dict | None = None   # definición del kit (ver engine/calkit.py); None = ideal


@router.post("/calibration/sol")
def calibration_sol(r: CalReq):
    sets = [dsets.load(i) for i in (r.raw_id, r.open_id, r.short_id, r.load_id)]
    f = sets[0]["f"]
    for s in sets[1:]:
        if s["f"].shape != f.shape or not np.allclose(s["f"], f, rtol=1e-9):
            raise RFInputError("Todos los conjuntos deben tener la misma rejilla de frecuencias.")
    p = r.port - 1
    gm = [s["s"][:, p, p] for s in sets]
    from ..engine.calkit import describe, standard_gamma
    kit = r.kit or {}
    g_std = [standard_gamma(k, f, kit.get(k), sets[0]["z0"][p]) for k in ("open", "short", "load")]
    terms = cal.solve_one_port(gm[1:], g_std)
    corrected = cal.apply_one_port(gm[0], terms)
    origins = {s["origin"] for s in sets}
    meta = {"calibration": f"SOL 1 puerto · {describe(kit)}", "kit": kit, "sources": [s["id"] for s in sets],
            "source_origins": sorted(origins),
            "note": "Corrección aplicada a datos " + ("medidos" if origins == {"measured"} else "no exclusivamente medidos")}
    new_id = dsets.save(r.name or f"{sets[0]['name']} (corregido SOL)", "derived", f, corrected.reshape(-1, 1, 1),
                        sets[0]["z0"][p], None, meta)
    return J({"id": new_id, "terms": terms, "meta": meta})


class SOLTReq(Model):
    raw_id: int
    short_id: int
    open_id: int
    load_id: int
    thru_id: int
    name: str | None = None
    kit: dict | None = None


@router.post("/calibration/solt")
def calibration_solt(r: SOLTReq):
    ids = (r.raw_id, r.short_id, r.open_id, r.load_id, r.thru_id)
    sets = [dsets.load(i) for i in ids]
    f = sets[0]["f"]
    for s in sets:
        if s["nports"] != 2:
            raise RFInputError(f"SOLT requiere conjuntos de 2 puertos («{s['name']}» tiene {s['nports']}).")
        if s["f"].shape != f.shape or not np.allclose(s["f"], f, rtol=1e-9):
            raise RFInputError("Todos los conjuntos deben tener la misma rejilla de frecuencias.")
    z0 = sets[0]["z0"][0]
    out = cal.solt_two_port(f, *[s["s"] for s in sets], z0=z0, kit=r.kit)
    origins = sorted({s["origin"] for s in sets})
    meta = {"calibration": out["method"], "kit": r.kit, "sources": list(ids), "source_origins": origins,
            "note": "Corrección aplicada a datos " + ("medidos" if origins == ["measured"] else "no exclusivamente medidos")}
    new_id = dsets.save(r.name or f"{sets[0]['name']} (corregido SOLT)", "derived", f, out["s"], z0, None, meta)
    return J({"id": new_id, "meta": meta})

class MMReq(Model):
    dataset_id: int
    pairs: list[list[int]] = [[1, 2], [3, 4]]
    save: bool = False


@router.post("/sparams/mixed-mode")
def sp_mixed(r: MMReq):
    d = dsets.load(r.dataset_id)
    if (d["meta"].get("summary") or {}).get("port_labels"):
        raise RFInputError("Este conjunto ya está en modo mixto.")
    if len(set(d["z0"])) > 1:
        raise RFInputError("La conversión a modo mixto requiere la misma Z0 en todos los puertos.")
    pairs = [tuple(p) for p in r.pairs]
    if any(len(p) != 2 for p in pairs):
        raise RFInputError("Cada par debe tener dos puertos (positivo, negativo).")
    res = mm.se_to_mixed(d["s"], pairs)
    k, z0 = res["npairs"], d["z0"][0]
    traces = {}
    for blk, (a, b) in {"dd": ("d", "d"), "dc": ("d", "c"), "cd": ("c", "d"), "cc": ("c", "c")}.items():
        for i in range(k):
            for j in range(k):
                x = res["blocks"][blk][:, i, j]
                traces[f"S{a}{b}{i + 1}{j + 1}"] = {"x": x, "db": sp.db20(x), "deg": sp.phase_deg(x)}
    out = {"f": d["f"], "labels": res["labels"], "pairs": pairs, "traces": traces, "origin": d["origin"],
           "z_ref": {"diferencial": 2 * z0, "comun": z0 / 2},
           "note": "Par (p, n): p = terminal positivo. Sdd: diferencial puro · Scc: común puro · Sdc/Scd: conversión de modo."}
    if r.save:
        z_mm = [2 * z0 if lb[0] == "D" else z0 / 2 if lb[0] == "C" else z0 for lb in res["labels"]]
        out["dataset_id"] = dsets.save(f"{d['name']} (modo mixto)", "derived", d["f"], res["s"], z_mm, None,
                                       {"port_labels": res["labels"], "pairs": pairs, "sources": [d["id"]],
                                        "source_origins": [d["origin"]], "note": "Conversión a modo mixto"})
    return J(out)


class EMReq(Model):
    kind: str = "dipole"
    f: float | str
    length: float | str            # m, o en λ si length_unit = "lambda"
    length_unit: str = "m"
    radius: float | str = "1m"     # 1 mm
    sigma: float = 5.8e7           # cobre
    z0: float = 50.0
    vswr_threshold: float = 2.0


@router.post("/antenna/em-model")
def antenna_em_model(r: EMReq):
    from ..engine import antenna_em
    from ..engine.units import C0
    f = qty(r.f, "Frecuencia")
    ln = qty(r.length, "Longitud")
    if r.length_unit == "lambda":
        ln *= C0 / f
    res = antenna_em.wire_antenna(r.kind, f, ln, qty(r.radius, "Radio"), r.sigma, r.z0)
    sw = res["sweep"]
    ok_ = np.isfinite(sw["z"])
    an = ant.analyze_antenna(sw["f"][ok_], z=sw["z"][ok_], z0=r.z0, vswr_threshold=r.vswr_threshold)
    del res["sweep"]
    name = "Dipolo" if r.kind == "dipole" else "Monopolo"
    detail = (f"Modelo EM analítico: {name.lower()} de {ln:.4g} m ({res['L_over_lambda'] / (2 if r.kind == 'monopole' else 1):.4g} λ), "
              f"radio {qty(r.radius):.3g} m, σ = {r.sigma:.3g} S/m")
    an.update({"gamma": an["s11"], "origin": "simulated", "origin_label": ORIGIN_LABEL["simulated"], "source_detail": detail,
               "label": f"{name} {ln:.4g} m (modelo EM)", "em": res,
               "not_available": ["Efectos del entorno, plano de masa finito, cable y balun (no modelados)"]})
    return J(an)
