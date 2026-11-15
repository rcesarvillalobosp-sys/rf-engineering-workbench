"""Autoverificación del motor ejecutable desde la aplicación (subconjunto de la batería de pytest)."""
from __future__ import annotations

import math

import numpy as np

from . import matching as mt
from . import reflection as rf
from . import sparams as sp
from . import tline as tl
from .units import C0


def _case(name, expected, got, tol, ref):
    ok = abs(complex(got) - complex(expected)) <= tol * max(1.0, abs(complex(expected)))
    return {"name": name, "expected": str(expected), "got": str(got), "ok": bool(ok), "reference": ref}


def run() -> dict:
    cases = []
    cases.append(_case("Γ de carga 50 Ω (Z0 = 50 Ω)", 0, rf.gamma_from_z(50, 50), 1e-12, "Analítico"))
    cases.append(_case("VSWR de 100 Ω en 50 Ω", 2.0, rf.vswr(abs(rf.gamma_from_z(100, 50))), 1e-12, "Analítico"))
    cases.append(_case("Return Loss de 100 Ω en 50 Ω (dB)", 9.542425094, rf.return_loss_db(1 / 3), 1e-9, "Analítico"))
    cases.append(_case("Γ circuito abierto", 1, rf.gamma_from_z(complex(math.inf, 0), 50), 0, "Analítico"))
    cases.append(_case("Γ cortocircuito", -1, rf.gamma_from_z(0, 50), 0, "Analítico"))
    lam = C0 / 1e9
    cases.append(_case("Zin λ/4 con ZL = 100 Ω, Z0 = 50 Ω", 25, tl.analyze_line(50, 1e9, lam / 4, zl=100 + 0j)["zin"], 1e-9,
                       "Z0²/ZL"))
    cases.append(_case("Zin stub en corto λ/8", 50j, tl.analyze_line(50, 1e9, lam / 8, load="short")["zin"], 1e-9, "jZ0·tan(π/4)"))
    r = mt.design("L", 200 - 100j, 100 + 0j, 500e6, z0=100)
    sol = next(s for s in r["solutions"] if {(e["kind"], e["part"]) for e in s["elements"]} == {("shunt", "C"), ("series", "L")})
    c = next(e["value"] for e in sol["elements"] if e["part"] == "C")
    cases.append(_case("Pozar ej. 5.1: C paralelo (pF)", 0.92, round(c * 1e12, 2), 0.011, "Pozar, Microwave Engineering"))
    s = mt.design("STUB1", 60 - 80j, 50 + 0j, 2e9, stub="short")["solutions"]
    d = sorted(x["d_lambda"] for x in s)[0]
    cases.append(_case("Pozar ej. 5.2: posición del stub d (λ)", 0.110, round(d, 3), 0.01, "Pozar, Microwave Engineering"))
    try:
        import skrf
        rng = np.random.default_rng(0)
        S = 0.4 * (rng.normal(size=(3, 2, 2)) + 1j * rng.normal(size=(3, 2, 2)))
        diff = float(np.max(np.abs(sp.s_to_z(S, 50) - skrf.network.s2z(S, 50))))
        cases.append(_case("Conversión S→Z vs scikit-rf (máx. dif.)", 0, diff, 1e-9, f"scikit-rf {skrf.__version__}"))
    except Exception as e:  # noqa: BLE001
        cases.append({"name": "Contraste con scikit-rf", "ok": False, "expected": "-", "got": str(e), "reference": "scikit-rf"})
    return {"passed": sum(c["ok"] for c in cases), "total": len(cases), "cases": cases}
