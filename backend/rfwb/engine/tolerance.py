"""Análisis Monte Carlo de tolerancias sobre una red de adaptación."""
from __future__ import annotations

import numpy as np

from .network import zin_cascade
from .reflection import vswr_arr
from .units import RFInputError


def monte_carlo(elements: list[dict], zl_f: np.ndarray, zs: complex, f: np.ndarray, f0: float,
                tol_l_pct: float = 5.0, tol_c_pct: float = 5.0, tol_len_pct: float = 1.0,
                n: int = 500, dist: str = "uniform", vswr_target: float = 2.0, seed: int | None = 1) -> dict:
    if not (10 <= n <= 20000):
        raise RFInputError("Número de iteraciones entre 10 y 20000.")
    rng = np.random.default_rng(seed)
    i0 = int(np.argmin(np.abs(f - f0)))
    curves = np.empty((n, f.size))
    v0 = np.empty(n)
    for k in range(n):
        pert = []
        for e in elements:
            e2 = dict(e)
            if e.get("part") == "L":
                tol, key = tol_l_pct, "value"
            elif e.get("part") == "C":
                tol, key = tol_c_pct, "value"
            elif "length_m" in e:
                tol, key = tol_len_pct, "length_m"
            else:
                tol, key = 0.0, None
            if key and tol > 0:
                if dist == "gaussian":
                    d = rng.normal(0, tol / 3 / 100)  # tolerancia = 3σ
                else:
                    d = rng.uniform(-tol / 100, tol / 100)
                e2[key] = e[key] * (1 + d)
            pert.append(e2)
        zin = zin_cascade(f, pert, zl_f)
        g = np.abs((zin - np.conj(zs)) / (zin + zs))
        vs = vswr_arr(np.minimum(g, 1.0))
        curves[k] = vs
        v0[k] = vs[i0]
    finite = np.where(np.isfinite(curves), curves, 1e6)
    pct = {p: np.percentile(finite, p, axis=0) for p in (5, 50, 95)}
    hist, edges = np.histogram(np.clip(v0, 1, 10), bins=40)
    return {
        "n": n, "dist": dist, "f": f,
        "vswr_f0": {"mean": float(np.mean(v0)), "std": float(np.std(v0)), "p50": float(np.median(v0)),
                    "p95": float(np.percentile(v0, 95)), "max": float(np.max(v0)), "min": float(np.min(v0))},
        "yield_f0": float(np.mean(v0 <= vswr_target)),
        "envelope": {"p5": pct[5], "p50": pct[50], "p95": pct[95]},
        "hist": {"counts": hist, "edges": edges},
    }
