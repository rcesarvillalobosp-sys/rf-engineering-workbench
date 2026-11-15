"""Calibración: 1 puerto SOL (3 términos, implementación propia) y 2 puertos SOLT (12 términos, scikit-rf).

    Γm = e00 + e10e01·Γa / (1 − e11·Γa)
Linealizando con Δe = e00·e11 − e10e01:   Γm = e00 + Γa·Γm·e11 − Γa·Δe
Con tres estándares conocidos (Γa) y sus medidas (Γm) se resuelve un sistema 3×3 por frecuencia.
Por defecto estándares ideales: Open Γ=+1, Short Γ=−1, Load Γ=0.
"""
from __future__ import annotations

import numpy as np

from .units import RFInputError


def solve_one_port(m_std: list[np.ndarray], g_std: list[np.ndarray] | None = None) -> dict:
    if len(m_std) != 3:
        raise RFInputError("Se requieren exactamente 3 estándares (Open, Short, Load).")
    m = [np.asarray(x, dtype=complex) for x in m_std]
    n = m[0].size
    if any(x.size != n for x in m):
        raise RFInputError("Los estándares deben tener el mismo número de puntos de frecuencia.")
    if g_std is None:
        g = [np.full(n, 1 + 0j), np.full(n, -1 + 0j), np.zeros(n, dtype=complex)]
    else:
        g = [np.broadcast_to(np.asarray(x, dtype=complex), (n,)) for x in g_std]
    e00 = np.empty(n, dtype=complex)
    e11 = np.empty(n, dtype=complex)
    er = np.empty(n, dtype=complex)
    for k in range(n):
        a = np.array([[1, g[i][k] * m[i][k], -g[i][k]] for i in range(3)])
        b = np.array([m[i][k] for i in range(3)])
        try:
            x = np.linalg.solve(a, b)
        except np.linalg.LinAlgError:
            raise RFInputError(f"Sistema de calibración singular en el punto {k}: estándares no independientes.")
        e00[k], e11[k] = x[0], x[1]
        er[k] = x[0] * x[1] - x[2]
    return {"e00": e00, "e11": e11, "e10e01": er}


def apply_one_port(gm: np.ndarray, terms: dict) -> np.ndarray:
    gm = np.asarray(gm, dtype=complex)
    d = gm - terms["e00"]
    return d / (terms["e10e01"] + terms["e11"] * d)


# ───────────────────────── SOLT de 2 puertos (12 términos) ─────────────────────────
def solt_two_port(f: np.ndarray, raw: np.ndarray, short: np.ndarray, open_: np.ndarray, load: np.ndarray,
                  thru: np.ndarray, z0: float = 50.0, kit: dict | None = None) -> dict:
    """Calibración SOLT completa de 2 puertos (modelo de 12 términos) con estándares IDEALES
    (Short Γ=−1, Open Γ=+1, Load Γ=0 en ambos puertos; Thru de longitud nula).

    Cada estándar es una medida de 2 puertos (N, 2, 2) con el estándar conectado en AMBOS puertos
    (como lo exportan los VNA); 'thru' es la medida con los puertos unidos. Se resuelve con
    scikit-rf (skrf.calibration.SOLT) y se devuelve el DUT corregido y los términos de error.
    """
    import skrf

    f = np.asarray(f, dtype=float)
    arrays = {"medida": raw, "short": short, "open": open_, "load": load, "thru": thru}
    for k, a in arrays.items():
        a = np.asarray(a)
        if a.shape != (f.size, 2, 2):
            raise RFInputError(f"SOLT: '{k}' debe ser un conjunto de 2 puertos con {f.size} puntos (forma {a.shape}).")
        if np.isnan(a).any():
            raise RFInputError(f"SOLT: '{k}' contiene parámetros no medidos (NaN). Se requieren los cuatro Sij.")
    freq = skrf.Frequency.from_f(f, unit="Hz")
    net = lambda s: skrf.Network(frequency=freq, s=np.asarray(s, dtype=complex), z0=z0)
    n = f.size

    from .calkit import describe, standard_gamma, thru_s
    kit = kit or {}

    def reflect2(g):
        s = np.zeros((n, 2, 2), dtype=complex)
        s[:, 0, 0] = g
        s[:, 1, 1] = g
        return net(s)

    ideals = [reflect2(standard_gamma("short", f, kit.get("short"), z0)), reflect2(standard_gamma("open", f, kit.get("open"), z0)),
              reflect2(standard_gamma("load", f, kit.get("load"), z0)), net(thru_s(f, kit.get("thru"), z0))]
    measured = [net(short), net(open_), net(load), net(thru)]
    import warnings
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            cal = skrf.calibration.SOLT(measured=measured, ideals=ideals)
            cal.run()
            corrected = cal.apply_cal(net(raw)).s
    except Exception as e:  # noqa: BLE001
        raise RFInputError(f"SOLT: no se pudo resolver la calibración ({e}).") from None
    singular = [str(w.message) for w in caught if "singular" in str(w.message).lower()]
    if singular:
        raise RFInputError(f"SOLT: sistema singular en {len(singular)} frecuencias: los estándares medidos no son "
                           "independientes (¿archivos intercambiados o estándar mal conectado?). No se genera resultado.")
    if not np.all(np.isfinite(corrected)):
        raise RFInputError("SOLT: la corrección produjo valores no finitos; revise las medidas de los estándares.")
    terms = {k: np.asarray(v) for k, v in cal.coefs.items() if np.ndim(v) == 1}
    return {"s": corrected, "terms": terms, "method": f"SOLT 12 términos (scikit-rf) · {describe(kit)}"}