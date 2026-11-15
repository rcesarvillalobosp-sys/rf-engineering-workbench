"""Endpoints: biblioteca de componentes, proyectos, VNA, informes y autoverificación."""
from __future__ import annotations

import json

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse, Response

from .. import datasets as dsets
from .. import db
from ..engine import selftest
from ..engine.units import RFInputError
from ..reports.generator import build_csv, build_pdf
from ..vna.base import SweepConfig, VNAError
from ..vna.manager import MANAGER
from .common import J, Model, qty

router = APIRouter(prefix="/api")
CATEGORIES = {"resistor": "Resistencias", "inductor": "Inductores", "capacitor": "Capacitores",
              "varcap": "Condensadores variables", "transformer": "Transformadores", "tline": "Líneas de transmisión",
              "coax": "Cables coaxiales"}


# ───────────── Biblioteca ─────────────
class CompIn(Model):
    category: str
    name: str
    value: float | str | None = None
    unit: str | None = None
    tolerance_pct: float | None = None
    q_factor: float | None = None
    q_freq_hz: float | str | None = None
    esr_ohm: float | None = None
    srf_hz: float | str | None = None
    model: str = "ideal"
    manufacturer: str | None = None
    part_number: str | None = None
    notes: str | None = None
    extra: dict | None = None


def _clean(c: CompIn) -> dict:
    if c.category not in CATEGORIES:
        raise RFInputError(f"Categoría no válida: {c.category}")
    if not c.name.strip():
        raise RFInputError("El nombre es obligatorio.")
    d = c.model_dump()
    for k in ("value", "q_freq_hz", "srf_hz"):
        if d[k] not in (None, ""):
            d[k] = qty(d[k], k)
        else:
            d[k] = None
    for k in ("value", "tolerance_pct", "q_factor", "esr_ohm", "srf_hz"):
        if d[k] is not None and d[k] < 0:
            raise RFInputError(f"{k} no puede ser negativo.")
    if c.category in ("coax", "tline"):
        ex = dict(d.get("extra") or {})
        num = lambda k: (qty(ex[k], k) if ex.get(k) not in (None, "") else None)
        z0, vf = num("z0"), num("vf")
        att, fref = num("atten_db_per_100m"), num("atten_ref_hz")
        if not z0 or z0 <= 0:
            raise RFInputError("Cable/línea: Z0 debe ser positivo.")
        if not vf or not (0 < vf <= 1):
            raise RFInputError("Cable/línea: el factor de velocidad debe estar en (0, 1].")
        if att is not None and att < 0:
            raise RFInputError("La atenuación no puede ser negativa.")
        if fref is not None and fref <= 0:
            raise RFInputError("La frecuencia de referencia de la atenuación debe ser positiva.")
        ex.update({"z0": z0, "vf": vf, "atten_db_per_100m": att, "atten_ref_hz": fref})
        d["extra"], d["value"], d["unit"] = ex, z0, "Ω"
    has_real = any(d[k] for k in ("q_factor", "esr_ohm", "srf_hz"))
    d["model"] = "real" if has_real else "ideal"
    d["source"] = "usuario"
    return d


@router.get("/library")
def lib_list(category: str | None = None, q: str | None = None):
    sql, args = "SELECT * FROM components WHERE 1=1", []
    if category:
        sql += " AND category = ?"
        args.append(category)
    if q:
        sql += " AND (name LIKE ? OR manufacturer LIKE ? OR part_number LIKE ? OR notes LIKE ?)"
        args += [f"%{q}%"] * 4
    sql += " ORDER BY category, value"
    rows = [db.row_to_component(r) for r in db.conn().execute(sql, args).fetchall()]
    return J({"categories": CATEGORIES, "items": rows})


@router.post("/library")
def lib_add(c: CompIn):
    d = _clean(c)
    con = db.conn()
    cur = con.execute(f"INSERT INTO components ({','.join(db.COMP_FIELDS)}) VALUES ({','.join('?' * len(db.COMP_FIELDS))})",
                      [json.dumps(d.get("extra") or {}) if k == "extra" else d.get(k) for k in db.COMP_FIELDS])
    con.commit()
    return {"id": cur.lastrowid}


@router.put("/library/{cid}")
def lib_update(cid: int, c: CompIn):
    d = _clean(c)
    con = db.conn()
    con.execute(f"UPDATE components SET {', '.join(k + ' = ?' for k in db.COMP_FIELDS)} WHERE id = ?",
                [json.dumps(d.get("extra") or {}) if k == "extra" else d.get(k) for k in db.COMP_FIELDS] + [cid])
    con.commit()
    return {"ok": True}


@router.delete("/library/{cid}")
def lib_delete(cid: int):
    con = db.conn()
    con.execute("DELETE FROM components WHERE id = ?", (cid,))
    con.commit()
    return {"ok": True}


def library_values(ids: list[int] | None = None) -> dict:
    sql = "SELECT * FROM components WHERE category IN ('inductor','capacitor') AND value > 0"
    args: list = []
    if ids:
        sql += f" AND id IN ({','.join('?' * len(ids))})"
        args = list(ids)
    out = {"L": [], "C": []}
    for r in db.conn().execute(sql, args).fetchall():
        key = "L" if r["category"] == "inductor" else "C"
        out[key].append({"id": r["id"], "name": r["name"], "value": r["value"], "q": r["q_factor"]})
    return out


# ───────────── Proyectos ─────────────
class ProjIn(Model):
    name: str
    data: dict


@router.get("/projects")
def proj_list():
    rows = db.conn().execute("SELECT id, name, created, updated FROM projects ORDER BY updated DESC").fetchall()
    return [dict(r) for r in rows]


@router.post("/projects")
def proj_create(p: ProjIn):
    if not p.name.strip():
        raise RFInputError("El proyecto necesita un nombre.")
    con = db.conn()
    t = db.now()
    cur = con.execute("INSERT INTO projects (name, data, created, updated) VALUES (?,?,?,?)", (p.name, json.dumps(p.data), t, t))
    con.commit()
    return {"id": cur.lastrowid}


@router.put("/projects/{pid}")
def proj_update(pid: int, p: ProjIn):
    con = db.conn()
    con.execute("UPDATE projects SET name = ?, data = ?, updated = ? WHERE id = ?", (p.name, json.dumps(p.data), db.now(), pid))
    con.commit()
    return {"ok": True}


@router.get("/projects/{pid}")
def proj_get(pid: int):
    r = db.conn().execute("SELECT * FROM projects WHERE id = ?", (pid,)).fetchone()
    if not r:
        raise RFInputError("Proyecto no encontrado.")
    d = dict(r)
    d["data"] = json.loads(d["data"])
    return d


@router.delete("/projects/{pid}")
def proj_delete(pid: int):
    con = db.conn()
    con.execute("DELETE FROM projects WHERE id = ?", (pid,))
    con.commit()
    return {"ok": True}


# ───────────── VNA ─────────────
@router.get("/vna/status")
def vna_status():
    return MANAGER.status()


@router.get("/vna/drivers")
def vna_drivers():
    return MANAGER.drivers()


@router.post("/vna/scan")
def vna_scan():
    return MANAGER.scan()


class ConnIn(Model):
    driver: str
    address: str
    profile: str | None = None


@router.post("/vna/connect")
def vna_connect(c: ConnIn):
    return MANAGER.connect(c.driver, c.address, c.profile)


@router.post("/vna/disconnect")
def vna_disconnect():
    return MANAGER.disconnect()


class SweepIn(Model):
    start: float | str
    stop: float | str
    points: int = 201
    ifbw: float | None = None
    power_dbm: float | None = None


@router.post("/vna/sweep")
def vna_sweep(s: SweepIn):
    return MANAGER.configure(SweepConfig(qty(s.start), qty(s.stop), s.points, s.ifbw, s.power_dbm))


class CapIn(Model):
    params: list[str] = ["S11"]
    name: str | None = None


def _save_capture(cap, name: str | None) -> dict:
    import numpy as np
    n = 2 if any(p != "S11" for p in cap.s) else 1
    s = np.full((cap.f.size, n, n), np.nan + 0j)
    for p, v in cap.s.items():
        s[:, int(p[1]) - 1, int(p[2]) - 1] = v
    meta = {"idn": cap.idn, "sweep": vars(cap.sweep), "params_measured": list(cap.s),
            "instrument_cal_active": cap.instrument_cal_active, **cap.meta}
    if n == 2:
        meta["note"] = "Parámetros no medidos se guardan como NaN (no se rellenan)."
    ds_id = dsets.save(name or f"Captura {cap.idn[:30]}", "measured", cap.f, s, 50.0, None, meta)
    return {"id": ds_id, "points": int(cap.f.size), "params": list(cap.s)}


@router.post("/vna/capture")
def vna_capture(c: CapIn):
    return _save_capture(MANAGER.capture(c.params), c.name)


@router.post("/vna/live")
def vna_live(c: CapIn):
    """Barrido continuo: mide y devuelve los datos SIN guardarlos (el cliente repite la llamada)."""
    from ..engine import sparams as sp
    cap = MANAGER.capture(c.params)
    return J({"f": cap.f, "params": cap.s, "db": {k: sp.db20(v) for k, v in cap.s.items()}, "idn": cap.idn,
              "origin": "measured", "label": "Medición real — VNA conectado"})


@router.post("/vna/save-last")
def vna_save_last(c: CapIn):
    if MANAGER.last is None:
        raise VNAError("No hay ninguna captura que guardar.")
    return _save_capture(MANAGER.last, c.name)

# ───────────── Informes ─────────────
@router.post("/reports/pdf")
def report_pdf(report: dict):
    if not report.get("items"):
        raise RFInputError("El informe no contiene elementos.")
    return Response(build_pdf(report), media_type="application/pdf",
                    headers={"Content-Disposition": 'attachment; filename="informe_rf.pdf"'})


@router.post("/reports/csv")
def report_csv(report: dict):
    if not report.get("items"):
        raise RFInputError("El informe no contiene elementos.")
    return PlainTextResponse(build_csv(report), headers={"Content-Disposition": 'attachment; filename="informe_rf.csv"'})


# ───────────── Sistema ─────────────
@router.get("/selftest")
def run_selftest():
    return J(selftest.run())


__all__ = ["router", "library_values", "VNAError"]
