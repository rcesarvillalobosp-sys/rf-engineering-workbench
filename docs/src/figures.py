"""Figuras de la documentación generadas con el motor real de la aplicación."""
from __future__ import annotations

import math

import numpy as np
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

from common import fig_image, plt, smith_axes
from rfwb.engine import antenna_em, matching as mt, reflection as rf, tdr, tline as tl
from rfwb.engine.impedance import sweep_circuit
from rfwb.engine.network import abcd_to_s, cascade_abcd
from rfwb.engine.sparams import z_to_s11
from rfwb.engine.units import C0

GREEN, BLUE, AMBER, RED, VIOLET = "#059669", "#2563eb", "#d97706", "#dc2626", "#7c3aed"


def smith_regions(width=110):
    fig, ax = plt.subplots(figsize=(5, 5))
    smith_axes(ax)
    ax.text(0, 0.62, "Inductivo\n(X > 0)", ha="center", fontsize=8, color=GREEN)
    ax.text(0, -0.70, "Capacitivo\n(X < 0)", ha="center", fontsize=8, color=AMBER)
    for (x, y, t, ha) in ((-1, 0, "Cortocircuito\nZ = 0, Γ = −1", "left"), (1, 0, "Abierto\nZ = ∞, Γ = +1", "right"), (0, 0, "Adaptado\nZ = Z0, Γ = 0", "center")):
        ax.plot(x, y, "o", color=RED, ms=5, zorder=5)
        ax.annotate(t, (x, y), xytext=(0 if ha == "center" else (8 if ha == "left" else -8), -26), textcoords="offset points", ha=ha, fontsize=7, color="#334155")
    return fig_image(fig, width, "Figura: regiones de la carta de Smith. Centro = adaptación; borde = |Γ| = 1 (reactancia pura).")


def smith_example(z=80 + 30j, z0=50, width=105):
    m = rf.reflection_metrics(z, z0)
    g = m["gamma"]
    fig, ax = plt.subplots(figsize=(5, 5))
    smith_axes(ax)
    th = np.linspace(0, 2 * np.pi, 400)
    ax.plot(abs(g) * np.cos(th), abs(g) * np.sin(th), ls="--", color=AMBER, lw=1, label=f"VSWR = {m['vswr']:.3f}")
    ax.annotate("", xy=(g.real, g.imag), xytext=(0, 0), arrowprops=dict(arrowstyle="->", color=BLUE, lw=1.4))
    ax.plot(g.real, g.imag, "o", color=GREEN, ms=7, zorder=6)
    ax.annotate(f"Z = {z.real:g}+j{z.imag:g} Ω\nΓ = {abs(g):.4f}∠{math.degrees(np.angle(g)):.2f}°", (g.real, g.imag), xytext=(-12, 14),
                textcoords="offset points", fontsize=7.5, ha="right", annotation_clip=False)
    ax.legend(loc="lower left", fontsize=7, frameon=False)
    return fig_image(fig, width, f"Figura: Z = {z.real:g} + j{z.imag:g} Ω sobre Z0 = {z0} Ω. La flecha es el vector Γ; el círculo discontinuo, los puntos con el mismo VSWR.")


def rlc_response(width=160):
    f, z = sweep_circuit("RLC_series", 10e6, 1e9, 800, R=10, L=100e-9, C=25e-12)
    fig, ax = plt.subplots(figsize=(7.5, 2.8))
    ax.loglog(f / 1e6, np.abs(z), color=GREEN, lw=1.6, label="|Z|")
    ax2 = ax.twinx()
    ax2.semilogx(f / 1e6, np.degrees(np.angle(z)), color=BLUE, lw=1.1, ls="--", label="fase")
    f0 = 1 / (2 * math.pi * math.sqrt(100e-9 * 25e-12))
    ax.axvline(f0 / 1e6, color=AMBER, lw=0.8, ls=":")
    ax.set_xlabel("Frecuencia (MHz)", fontsize=8)
    ax.set_ylabel("|Z| (Ω)", fontsize=8)
    ax2.set_ylabel("Fase (°)", fontsize=8)
    ax.tick_params(labelsize=7)
    ax2.tick_params(labelsize=7)
    ax.grid(alpha=0.3, which="both")
    ax.text(f0 / 1e6 * 1.05, 2e3, f"f0 = {f0 / 1e6:.2f} MHz", fontsize=7, color=AMBER)
    fig.tight_layout()
    return fig_image(fig, width, "Figura: RLC serie (R = 10 Ω, L = 100 nH, C = 25 pF). En f0 la reactancia se anula, |Z| = R y la fase cruza 0°.")


def standing_wave(width=160):
    f = 145e6
    r = tl.analyze_line(50, f, 3.2, 0.66, 0.0, zl=100 + 50j)
    p = r["profile"]
    fig, ax = plt.subplots(figsize=(7.5, 2.6))
    ax.plot(p["d"], p["v_rel"], color=GREEN, lw=1.6, label="|V(d)|/|V⁺|")
    ax.plot(p["d"], p["i_rel"] * 50, color=BLUE, lw=1.1, ls="--", label="|I(d)|·Z0/|V⁺|")
    g = abs(r["gamma_load"])
    ax.axhline(1 + g, color=AMBER, lw=0.7, ls=":")
    ax.axhline(1 - g, color=AMBER, lw=0.7, ls=":")
    ax.set_xlabel("Distancia desde la carga d (m)", fontsize=8)
    ax.tick_params(labelsize=7)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=7, loc="upper right")
    ax.text(0.02, 1 + g + 0.03, f"máx = 1 + |Γ| = {1 + g:.3f}", fontsize=7, color=AMBER, transform=ax.get_yaxis_transform())
    fig.tight_layout()
    return fig_image(fig, width, f"Figura: onda estacionaria con ZL = 100 + j50 Ω, Z0 = 50 Ω, 145 MHz, vf = 0.66 (λ = {r['lambda']:.3f} m). "
                                 f"VSWR = máx/mín = {r['vswr_load']:.3f}; los máximos se repiten cada λ/2.")


def matching_example(width=160):
    res = mt.design("L", 25 - 40j, 50 + 0j, 433e6, vswr_target=2.0, span=0.5)
    s = res["solutions"][0]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(9, 4.2), gridspec_kw={"width_ratios": [1, 1.25]})
    smith_axes(a1)
    for seg, col in zip(s["trajectory"], (BLUE, AMBER)):
        g = z_to_s11(np.array(seg["z"]), 50)
        a1.plot(g.real, g.imag, color=col, lw=2.2, label=seg["label"])
    gl = rf.gamma_from_z(25 - 40j, 50)
    a1.plot(gl.real, gl.imag, "o", color=RED, ms=6)
    a1.annotate("ZL", (gl.real, gl.imag), xytext=(6, -10), textcoords="offset points", fontsize=8)
    a1.plot(0, 0, "o", color=GREEN, ms=6)
    a1.legend(fontsize=6.5, loc="lower left", frameon=False)
    sw = s["sweep"]
    a2.plot(sw["f"] / 1e6, np.maximum(sw["s11_db"], -60), color=GREEN, lw=1.6)
    bw = s["bandwidth"]
    a2.axhline(-9.54, color=AMBER, ls=":", lw=0.8)
    if bw:
        a2.axvspan(bw["f_low"] / 1e6, bw["f_high"] / 1e6, color=GREEN, alpha=0.08)
    a2.set_xlabel("Frecuencia (MHz)", fontsize=8)
    a2.set_ylabel("|Γ| (dB)", fontsize=8)
    a2.tick_params(labelsize=7)
    a2.grid(alpha=0.3)
    a2.text(0.02, 0.05, f"BW (VSWR ≤ 2) = {bw['fractional'] * 100:.1f} %\nBode–Fano ≤ {res['bode_fano']['max_fractional_bw'] * 100:.0f} %",
            transform=a2.transAxes, fontsize=7.5)
    fig.tight_layout()
    return fig_image(fig, width, "Figura: red L para ZL = 25 − j40 Ω a 433 MHz. Izquierda: trayectoria en la carta (cada elemento, un tramo). "
                                 "Derecha: |Γ| frente a frecuencia; la adaptación sólo es perfecta en f0.")


def dipole_pattern(width=150):
    fig = plt.figure(figsize=(8, 3.6))
    th = np.linspace(0, 2 * np.pi, 1441)
    for i, (L, col) in enumerate(((0.01, BLUE), (0.5, GREEN), (1.25, AMBER))):
        r = antenna_em.wire_antenna("dipole", C0, L, 1e-5)
        pat = r["pattern"]
        db = np.interp(np.degrees(th) % 360, np.concatenate([pat["theta_deg"], 360 - pat["theta_deg"][::-1]]),
                       np.concatenate([pat["db"], pat["db"][::-1]]))
        ax = fig.add_subplot(1, 3, i + 1, projection="polar")
        ax.set_theta_zero_location("N")
        ax.set_theta_direction(-1)
        ax.plot(th, np.maximum(db, -30) + 30, color=col, lw=1.6)
        ax.set_yticklabels([])
        ax.tick_params(labelsize=6)
        ax.set_title(f"L = {L:g} λ · D = {r['directivity_dbi']:.2f} dBi", fontsize=8)
    fig.tight_layout()
    return fig_image(fig, width, "Figura: diagramas de campo (plano E, escala 30 dB) del modelo de hilo delgado. "
                                 "Dipolo corto (1.76 dBi), media onda (2.15 dBi) y 1.25λ (5.16 dBi, aparecen lóbulos).")


def tdr_example(width=160):
    f = np.arange(1, 801) * 5e6
    els = [{"kind": "series", "part": "L", "value": 100e-9}, {"kind": "shunt", "part": "C", "value": 40e-12},
           {"kind": "series", "part": "L", "value": 100e-9}]
    s11 = abcd_to_s(cascade_abcd(f, els), 50)[:, 0, 0]
    r = tdr.tdr(f, s11, 50, 1.0, "lowpass")
    fig, ax = plt.subplots(figsize=(7.5, 2.4))
    ax.plot(r["t"] * 1e9, r["z"], color=GREEN, lw=1.5)
    ax.axhline(50, color="#94a3b8", lw=0.7, ls=":")
    ax.set_xlim(-0.5, 20)
    ax.set_ylim(0, 160)
    ax.set_xlabel("Tiempo de ida y vuelta (ns)", fontsize=8)
    ax.set_ylabel("Z(t) (Ω)", fontsize=8)
    ax.tick_params(labelsize=7)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    return fig_image(fig, width, "Figura: TDR low-pass de un filtro L–C–L terminado en 50 Ω: la bobina de entrada aparece como alta impedancia, "
                                 "el condensador como baja, y la respuesta se estabiliza en 50 Ω (S11(0) = 0).")


def architecture(width=165):
    fig, ax = plt.subplots(figsize=(9, 4.6))
    ax.axis("off")
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 52)

    def blk(x, y, w, h, t, sub, col):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.4,rounding_size=1.5", fc=col + "18", ec=col, lw=1.3))
        ax.text(x + w / 2, y + h - 3.2, t, ha="center", va="top", fontsize=9, weight="bold", color="#0f172a")
        ax.text(x + w / 2, y + h - 7.5, sub, ha="center", va="top", fontsize=6.6, color="#334155", linespacing=1.35)

    def arr(x1, y1, x2, y2, t=""):
        ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=11, color="#475569", lw=1))
        if t:
            ax.text((x1 + x2) / 2 + 0.8, (y1 + y2) / 2 + 0.8, t, fontsize=6.3, color="#475569")

    blk(2, 30, 28, 20, "Interfaz (React)", "12 módulos · carta de Smith SVG\nPlotly · temas claro/oscuro\nmodo educativo · exportación", BLUE)
    blk(36, 30, 28, 20, "API (FastAPI)", "routes_rf · routes_data\nroutes_sys · serialización\nde complejos e infinitos", VIOLET)
    blk(70, 30, 28, 20, "Motor RF (Python)", "reflection · impedance · network\ntline · matching · sparams\nstability · antenna_em · tdr…", GREEN)
    blk(2, 3, 28, 20, "Electron", "ventana de escritorio\narranca/detiene el motor\nactualizaciones (GitHub)", "#334155")
    blk(36, 3, 28, 20, "Datos (SQLite)", "biblioteca · conjuntos S\n(con su ORIGEN) · proyectos", AMBER)
    blk(70, 3, 28, 20, "E/S e instrumentos", "Touchstone v1/v2 · PDF/CSV\ndrivers VNA: NanoVNA,\nLibreVNA, SCPI/VISA", RED)
    arr(30, 41, 36, 41, "HTTP/JSON")
    arr(64, 41, 70, 41)
    arr(50, 30, 50, 23)
    arr(84, 30, 84, 23)
    arr(16, 23, 16, 30)
    fig.tight_layout()
    return fig_image(fig, width, "Figura: arquitectura. Todas las fórmulas viven en el motor; la interfaz sólo presenta resultados.")
