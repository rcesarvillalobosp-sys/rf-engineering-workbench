"""Genera la guía personal en LaTeX (XeLaTeX).

1. Calcula con el motor de la aplicación todos los valores numéricos de los ejemplos y los escribe como
   macros LaTeX en docs/guia/generado/valores.tex (y tablas en generado/*.tex).
2. Exporta las figuras (matplotlib, PDF vectorial) a docs/guia/generado/.
3. Compila docs/guia/guia.tex con XeLaTeX (tres pasadas) y copia el PDF al destino indicado.
"""
from __future__ import annotations

import cmath
import math
import pathlib
import shutil
import subprocess
import sys

import figures as F
from common import ROOT, version
from rfwb.engine import antenna_em, matching as mt, reflection as rf, stability as stb, tline as tl
from rfwb.engine.impedance import analyze_circuit
from rfwb.engine.network import describe
from rfwb.engine.units import C0

GUIA = ROOT / "docs" / "guia"
GEN = GUIA / "generado"


# ───────────── formato ─────────────
def n(x, d=4):
    """Número con d cifras significativas, signo menos tipográfico."""
    s = f"{x:.{d}g}"
    if "e" in s:
        m, e = s.split("e")
        s = rf"{m}\times 10^{{{int(e)}}}"
    return s.replace("-", "-")


def cx(z, d=4):
    z = complex(z)
    sg = "+" if z.imag >= 0 else "-"
    return rf"{n(z.real, d)} {sg} j\,{n(abs(z.imag), d)}"


def polar(z, d=4):
    z = complex(z)
    return rf"{n(abs(z), d)}\,\angle\,{n(math.degrees(cmath.phase(z)), d)}^\circ"


MACROS: dict[str, str] = {}


def mac(name, value):
    MACROS[name] = value


# ───────────── valores ─────────────
def compute():
    mac("Version", version())
    z = 80 + 30j
    mac("ZejMod", n(abs(z), 6))
    mac("ZejArg", n(math.degrees(cmath.phase(z)), 6))
    mac("ZejInv", cx(1 / z, 5))

    r = analyze_circuit("RLC_series", 100e6, R=10, L=100e-9, C=25e-12, v_rms=1.0)
    mac("RlcW", n(r["omega"], 6))
    mac("RlcXl", n(r["xl"], 6))
    mac("RlcXc", n(r["xc"], 6))
    mac("RlcZ", cx(r["z"], 6))
    mac("RlcZmag", n(r["z_mag"], 6))
    mac("RlcZdeg", n(r["z_deg"], 5))
    mac("RlcY", cx(r["y"], 5))
    mac("RlcFz", n(r["f0"] / 1e6, 6))
    mac("RlcQ", n(r["q_factor"], 5))
    mac("RlcBw", n(r["bw_3db"] / 1e6, 5))
    mac("RlcI", n(abs(r["i"]), 5))
    mac("RlcP", n(r["p"], 5))
    mac("RlcQr", n(r["q"], 5))
    mac("RlcS", n(r["s"], 5))
    mac("RlcPf", n(r["pf"], 5))

    m = rf.reflection_metrics(80 + 30j, 50)
    mac("GejRect", cx(m["gamma"], 6))
    mac("GejPol", polar(m["gamma"], 6))
    mac("GejMag", n(m["gamma_mag"], 6))
    mac("GejVswr", n(m["vswr"], 5))
    mac("GejRl", n(m["return_loss_db"], 5))
    mac("GejMl", n(m["mismatch_loss_db"], 4))
    mac("GejRefl", n(m["reflected_pct"], 5))
    mac("GejZn", cx(m["z_norm"], 4))

    lam = 0.66 * C0 / 145e6
    rl = tl.analyze_line(50, 145e6, 3.2, 0.66, 0.0, zl=100 + 50j)
    mac("LnLam", n(lam, 5))
    mac("LnBeta", n(rl["beta"], 5))
    mac("LnTheta", n(rl["theta_deg"], 6))
    mac("LnLenLam", n(rl["length_lambda"], 5))
    mac("LnGl", polar(rl["gamma_load"], 5))
    mac("LnVswr", n(rl["vswr_load"], 5))
    mac("LnZin", cx(rl["zin"], 5))
    mac("LnVmax", n(1 + abs(rl["gamma_load"]), 4))
    mac("LnVmin", n(1 - abs(rl["gamma_load"]), 4))

    rows = []
    for s in (1.1, 1.2, 1.5, 2.0, 3.0, 5.0, 10.0):
        g = rf.gamma_from_vswr(s)
        rows.append(rf"{n(s, 3)} & {g:.4f} & {rf.return_loss_db(g):.2f} & {100 * g * g:.2f} & {100 * (1 - g * g):.2f} & {rf.mismatch_loss_db(g):.3f} \\")
    (GEN / "tabla_vswr.tex").write_text("\n".join(rows), encoding="utf-8")

    res = mt.design("L", 25 - 40j, 50 + 0j, 433e6, vswr_target=2.0)
    mac("MtGb", n(abs(res["gamma_before"]), 4))
    mac("MtVb", n(res["vswr_before"], 4))
    sol_rows = []
    for i, s in enumerate(res["solutions"], 1):
        els = r" \newline ".join(describe(e).replace("µ", r"\textmu ") for e in s["elements"])
        bw = s["bandwidth"]
        sol_rows.append(rf"{i} & {s['topology']} & {els} & {100 * bw['fractional']:.1f}\,\% \\" if bw else rf"{i} & {s['topology']} & {els} & --- \\")
    (GEN / "tabla_red_l.tex").write_text("\n".join(sol_rows), encoding="utf-8")
    mac("MtBf", n(100 * res["bode_fano"]["max_fractional_bw"], 4))
    mac("MtQl", n(res["bode_fano"]["q_load"], 4))

    p51 = mt.design("L", 200 - 100j, 100 + 0j, 500e6, z0=100)
    sol = next(s for s in p51["solutions"] if {(e["kind"], e["part"]) for e in s["elements"]} == {("shunt", "C"), ("series", "L")})
    mac("PozC", n(next(e["value"] for e in sol["elements"] if e["part"] == "C") * 1e12, 4))
    mac("PozL", n(next(e["value"] for e in sol["elements"] if e["part"] == "L") * 1e9, 4))
    st = sorted((s["d_lambda"], s["l_lambda"]) for s in mt.design("STUB1", 60 - 80j, 50 + 0j, 2e9, stub="short")["solutions"])
    mac("StD", n(st[0][0], 3))
    mac("StL", n(st[0][1], 3))
    mac("StDb", n(st[1][0], 3))
    mac("StLb", n(st[1][1], 3))

    import numpy as np
    s2 = np.array([[0.894 * np.exp(-1j * math.radians(60.6)), 0.020 * np.exp(1j * math.radians(62.4))],
                   [3.122 * np.exp(1j * math.radians(123.6)), 0.781 * np.exp(-1j * math.radians(27.6))]])
    sb = stb.stability(s2[None])
    mac("StbK", n(sb["k"][0], 4))
    mac("StbD", n(abs(sb["delta"][0]), 4))
    mac("StbMu", n(sb["mu"][0], 4))

    d = antenna_em.wire_antenna("dipole", C0, 0.5, 1e-5)
    mac("DpZ", cx(d["z_in"], 5))
    mac("DpD", n(d["directivity"], 4))
    mac("DpDdbi", n(d["directivity_dbi"], 4))
    mac("DpRr", n(d["rr_max"], 5))
    mo = antenna_em.wire_antenna("monopole", C0, 0.25, 1e-5)
    mac("MpZ", cx(mo["z_in"], 5))
    mac("MpDdbi", n(mo["directivity_dbi"], 4))
    sh = antenna_em.wire_antenna("dipole", C0, 0.01, 1e-6)
    mac("ShD", n(sh["directivity"], 4))
    mac("ShR", n(sh["z_in"].real, 3))
    mac("ShRth", n(20 * math.pi ** 2 * 0.01 ** 2, 3))

    mu0, sigma, f = 4e-7 * math.pi, 5.8e7, 1e9
    mac("SkinDelta", n(1 / math.sqrt(math.pi * f * mu0 * sigma) * 1e6, 4))
    ms = tl.line_from_geometry("microstrip", W=3.06e-3, h=1.6e-3, er=4.4)
    mac("MsZ", n(ms["z0"], 4))
    mac("MsEeff", n(ms["eps_eff"], 4))
    mac("MsVf", n(ms["vf"], 4))
    mac("CoaxZ", n(60 / 1.5 * math.log(2.95 / 0.9), 4))

    lines = [rf"\newcommand{{\{k}}}{{{v}}}" for k, v in MACROS.items()]
    (GEN / "valores.tex").write_text("% Generado automáticamente por docs/src/guia_latex.py — no editar\n" + "\n".join(lines) + "\n", encoding="utf-8")


# ───────────── figuras ─────────────
def figures():
    saved = {}

    def saver(name):
        def _save(fig, width_mm=150, caption=None):
            path = GEN / f"{name}.pdf"
            fig.savefig(path, bbox_inches="tight")
            F.plt.close(fig)
            saved[name] = path
            return path
        return _save

    for name, fn in (("smith_regiones", F.smith_regions), ("smith_ejemplo", F.smith_example), ("rlc", F.rlc_response),
                     ("onda_estacionaria", F.standing_wave), ("red_l", F.matching_example), ("dipolos", F.dipole_pattern),
                     ("tdr", F.tdr_example), ("arquitectura", F.architecture)):
        F.fig_image = saver(name)
        fn()
    return saved


def compile_pdf(out_pdf: pathlib.Path):
    # XeLaTeX directo (latexmk requiere Perl): 3 pasadas para el índice y las referencias.
    cmd = ["xelatex", "-interaction=nonstopmode", "-halt-on-error", "-file-line-error", "guia.tex"]
    for _ in range(3):
        r = subprocess.run(cmd, cwd=str(GUIA), capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            break
    pdf = GUIA / "guia.pdf"
    if r.returncode != 0 or not pdf.exists():
        log = (GUIA / "guia.log").read_text(encoding="utf-8", errors="replace") if (GUIA / "guia.log").exists() else r.stdout
        errs = [l for l in log.splitlines() if l.startswith("!") or ".tex:" in l][:25]
        raise SystemExit("Error de compilación LaTeX:\n" + "\n".join(errs))
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(pdf, out_pdf)
    return out_pdf


if __name__ == "__main__":
    GEN.mkdir(parents=True, exist_ok=True)
    compute()
    figures()
    print("PDF:", compile_pdf(pathlib.Path(sys.argv[1])))
