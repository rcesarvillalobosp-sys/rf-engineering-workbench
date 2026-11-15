"""Almacenamiento de conjuntos de datos de parámetros S con su ORIGEN obligatorio."""
from __future__ import annotations

import json

import numpy as np

from . import db
from .engine.units import RFInputError

ORIGINS = ("imported", "simulated", "measured", "derived")


def save(name: str, origin: str, f: np.ndarray, s: np.ndarray, z0, filename: str | None = None,
         meta: dict | None = None) -> int:
    if origin not in ORIGINS:
        raise RFInputError(f"Origen de datos no válido: {origin}")
    s = np.asarray(s, dtype=complex)
    z0 = [float(v) for v in np.atleast_1d(z0)]
    if len(z0) == 1:
        z0 = z0 * s.shape[1]
    c = db.conn()
    cur = c.execute(
        "INSERT INTO datasets (name, origin, filename, nports, z0, f, s_re, s_im, meta, created) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (name, origin, filename, int(s.shape[1]), json.dumps(z0), json.dumps(np.asarray(f, float).tolist()),
         json.dumps(s.real.tolist()), json.dumps(s.imag.tolist()), json.dumps(meta or {}), db.now()))
    c.commit()
    return int(cur.lastrowid)


def load(ds_id: int) -> dict:
    r = db.conn().execute("SELECT * FROM datasets WHERE id = ?", (ds_id,)).fetchone()
    if not r:
        raise RFInputError(f"No existe el conjunto de datos {ds_id}.")
    d = dict(r)
    d["f"] = np.asarray(json.loads(d["f"]), dtype=float)
    d["s"] = np.asarray(json.loads(d["s_re"])) + 1j * np.asarray(json.loads(d["s_im"]))
    d["z0"] = json.loads(d["z0"])
    d["meta"] = json.loads(d["meta"] or "{}")
    del d["s_re"], d["s_im"]
    return d


def listing() -> list[dict]:
    rows = db.conn().execute("SELECT id, name, origin, filename, nports, f, meta, created FROM datasets ORDER BY created DESC").fetchall()
    out = []
    for r in rows:
        f = json.loads(r["f"])
        out.append({"id": r["id"], "name": r["name"], "origin": r["origin"], "filename": r["filename"],
                    "nports": r["nports"], "points": len(f), "f_start": f[0] if f else None, "f_stop": f[-1] if f else None,
                    "created": r["created"], "meta": json.loads(r["meta"] or "{}")})
    return out


def delete(ds_id: int) -> None:
    c = db.conn()
    c.execute("DELETE FROM datasets WHERE id = ?", (ds_id,))
    c.commit()
