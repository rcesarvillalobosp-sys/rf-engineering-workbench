"""Contenido inicial de la biblioteca: SÓLO componentes genéricos.

* R, L, C: valores normalizados IEC 60063 (series E12) como componentes IDEALES.
* Cables coaxiales: Z0 nominal y factor de velocidad derivado del dieléctrico declarado por la designación
  (PE sólido: εr ≈ 2.25 → vf ≈ 0.66). La atenuación NO se incluye: depende del fabricante concreto y
  debe introducirse desde la hoja de datos.
No se incluyen fabricantes ni referencias comerciales.
"""
from __future__ import annotations

E12 = [1.0, 1.2, 1.5, 1.8, 2.2, 2.7, 3.3, 3.9, 4.7, 5.6, 6.8, 8.2]


def _fmt(v, unit):
    from ..engine.units import fmt_si
    return fmt_si(v, unit, 3).replace(" ", "")


def seed_rows() -> list[dict]:
    rows = []
    common = {"model": "ideal", "source": "generico", "manufacturer": None, "part_number": None}
    for dec in (1, 10, 100, 1000):
        for m in E12:
            v = round(m * dec, 6)
            rows.append({**common, "category": "resistor", "name": f"R {_fmt(v, 'Ω')} (E12, ideal)", "value": v,
                         "unit": "Ω", "tolerance_pct": 5.0, "notes": "Genérico ideal. Serie E12 (IEC 60063)."})
    for dec in (1e-9, 10e-9, 100e-9):
        for m in E12:
            v = m * dec
            rows.append({**common, "category": "inductor", "name": f"L {_fmt(v, 'H')} (E12, ideal)", "value": v,
                         "unit": "H", "tolerance_pct": 5.0, "notes": "Genérico ideal. Sin Q ni SRF: añada datos reales si los dispone."})
    for dec in (1e-12, 10e-12, 100e-12, 1e-9):
        for m in E12:
            v = m * dec
            rows.append({**common, "category": "capacitor", "name": f"C {_fmt(v, 'F')} (E12, ideal)", "value": v,
                         "unit": "F", "tolerance_pct": 5.0, "notes": "Genérico ideal. Sin ESR ni SRF."})
    rows.append({**common, "category": "varcap", "name": "Condensador variable genérico 5–50 pF", "value": 25e-12,
                 "unit": "F", "tolerance_pct": None, "notes": "Rango ajustable genérico.",
                 "extra": {"min": 5e-12, "max": 50e-12}})
    rows.append({**common, "category": "transformer", "name": "Transformador ideal 1:4 (impedancia)", "value": 4.0,
                 "unit": "", "notes": "Relación de impedancias 4 (vueltas 1:2). Ideal: sin pérdidas ni límites de banda.",
                 "extra": {"impedance_ratio": 4.0}})
    rows.append({**common, "category": "transformer", "name": "Transformador ideal 1:9 (impedancia)", "value": 9.0,
                 "unit": "", "notes": "Relación de impedancias 9 (vueltas 1:3). Ideal.", "extra": {"impedance_ratio": 9.0}})
    for name, z0, vf, diel in (("RG-58 (genérico)", 50.0, 0.66, "PE sólido"), ("RG-213 (genérico)", 50.0, 0.66, "PE sólido"),
                               ("RG-174 (genérico)", 50.0, 0.66, "PE sólido"), ("RG-59 (genérico, PE sólido)", 75.0, 0.66, "PE sólido")):
        rows.append({**common, "category": "coax", "name": name, "value": z0, "unit": "Ω", "model": "ideal",
                     "notes": f"Z0 nominal y vf de dieléctrico {diel}. Atenuación no incluida: introdúzcala desde la hoja de datos del fabricante.",
                     "extra": {"z0": z0, "vf": vf, "atten_db_per_100m": None, "atten_ref_hz": None, "dielectric": diel}})
    rows.append({**common, "category": "tline", "name": "Línea ideal 50 Ω (aire)", "value": 50.0, "unit": "Ω",
                 "notes": "Línea TEM ideal sin pérdidas, vf = 1.", "extra": {"z0": 50.0, "vf": 1.0}})
    return rows
