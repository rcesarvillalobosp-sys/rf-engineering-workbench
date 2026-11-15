"""Persistencia SQLite: biblioteca de componentes, mediciones/datasets y proyectos."""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from pathlib import Path

_LOCK = threading.Lock()
_CONN: sqlite3.Connection | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS components (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,            -- resistor | inductor | capacitor | varcap | transformer | tline | coax
    name TEXT NOT NULL,
    value REAL,                        -- valor nominal en unidad SI base
    unit TEXT,                         -- Ω, H, F, ...
    tolerance_pct REAL,
    q_factor REAL,
    q_freq_hz REAL,
    esr_ohm REAL,
    srf_hz REAL,
    model TEXT NOT NULL DEFAULT 'ideal', -- ideal | real
    manufacturer TEXT,
    part_number TEXT,
    source TEXT NOT NULL,              -- generico | usuario
    notes TEXT,
    extra TEXT                         -- JSON (z0, vf, atten..., min/max)
);
CREATE TABLE IF NOT EXISTS datasets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    origin TEXT NOT NULL,              -- imported | simulated | measured | derived
    filename TEXT,
    nports INTEGER NOT NULL,
    z0 TEXT NOT NULL,                  -- JSON lista por puerto
    f TEXT NOT NULL,                   -- JSON
    s_re TEXT NOT NULL,                -- JSON (N, n, n)
    s_im TEXT NOT NULL,
    meta TEXT,                         -- JSON
    created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    data TEXT NOT NULL,
    created REAL NOT NULL,
    updated REAL NOT NULL
);
"""


def data_dir() -> Path:
    d = Path(os.environ.get("RFWB_DATA_DIR") or Path(__file__).resolve().parents[1] / "data")
    d.mkdir(parents=True, exist_ok=True)
    return d


def conn() -> sqlite3.Connection:
    global _CONN
    with _LOCK:
        if _CONN is None:
            path = os.environ.get("RFWB_DB") or str(data_dir() / "workbench.sqlite3")
            _CONN = sqlite3.connect(path, check_same_thread=False)
            _CONN.row_factory = sqlite3.Row
            _CONN.executescript(SCHEMA)
            if _CONN.execute("SELECT COUNT(*) FROM components").fetchone()[0] == 0:
                from .library.seed import seed_rows
                _insert_many(_CONN, seed_rows())
            _CONN.commit()
        return _CONN


def reset_for_tests(path: str = ":memory:") -> None:
    global _CONN
    with _LOCK:
        _CONN = None
    os.environ["RFWB_DB"] = path


COMP_FIELDS = ["category", "name", "value", "unit", "tolerance_pct", "q_factor", "q_freq_hz", "esr_ohm", "srf_hz",
               "model", "manufacturer", "part_number", "source", "notes", "extra"]


def _insert_many(c, rows):
    for r in rows:
        r = dict(r)
        r["extra"] = json.dumps(r.get("extra") or {})
        c.execute(f"INSERT INTO components ({','.join(COMP_FIELDS)}) VALUES ({','.join('?' * len(COMP_FIELDS))})",
                  [r.get(k) for k in COMP_FIELDS])


def row_to_component(r: sqlite3.Row) -> dict:
    d = dict(r)
    d["extra"] = json.loads(d.get("extra") or "{}")
    return d


def now() -> float:
    return time.time()
