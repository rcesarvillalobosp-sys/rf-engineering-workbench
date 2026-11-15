"""Generador de informes técnicos (PDF y CSV).

Cada elemento del informe procede de un módulo e indica SIEMPRE el origen de sus datos.
Estructura de un item:
  {title, module, origin, created, inputs: [[k, v]], results: [[k, v]], steps: [{title, formula, substitution, result, unit, note}],
   smith: {z0, points: [{re, im, label}], traces: [{name, re: [], im: []}]},
   plots: [{title, xlabel, ylabel, x: [], series: [{name, y: []}]}], tables: [{title, header: [], rows: [[]]}], notes: [str]}
"""
from __future__ import annotations

import csv
import datetime as dt
import io

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from reportlab.lib import colors  # noqa: E402
from reportlab.lib.enums import TA_LEFT  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # noqa: E402
from reportlab.lib.units import mm  # noqa: E402
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,  # noqa: E402
                                TableStyle)

ORIGIN_LABELS = {
    "calculated": "Calculado — motor matemático (sin medición)",
    "simulated": "Simulado — modelo de circuito / línea",
    "imported": "Datos importados desde Touchstone",
    "measured": "Medición real — VNA conectado",
    "derived": "Derivado por procesado (p. ej. calibración) de otros datos",
}
ACCENT = colors.HexColor("#0f9d58")


def _register_fonts() -> tuple[str, str]:
    """Fuentes TrueType con Γ, Ω, ∠, −, ∞ (las Type1 estándar de PDF no los contienen).
    DejaVu se distribuye con matplotlib, que ya es dependencia del proyecto."""
    from pathlib import Path

    from reportlab.lib.fonts import addMapping
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    d = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
    try:
        for name, file in (("DejaVu", "DejaVuSans.ttf"), ("DejaVu-Bold", "DejaVuSans-Bold.ttf"),
                           ("DejaVu-Oblique", "DejaVuSans-Oblique.ttf"), ("DejaVu-BoldOblique", "DejaVuSans-BoldOblique.ttf"),
                           ("DejaVuMono", "DejaVuSansMono.ttf"), ("DejaVuMono-Bold", "DejaVuSansMono-Bold.ttf")):
            pdfmetrics.registerFont(TTFont(name, str(d / file)))
        addMapping("DejaVu", 0, 0, "DejaVu")
        addMapping("DejaVu", 1, 0, "DejaVu-Bold")
        addMapping("DejaVu", 0, 1, "DejaVu-Oblique")
        addMapping("DejaVu", 1, 1, "DejaVu-BoldOblique")
        addMapping("DejaVuMono", 0, 0, "DejaVuMono")
        addMapping("DejaVuMono", 1, 0, "DejaVuMono-Bold")
        addMapping("DejaVuMono", 0, 1, "DejaVuMono")
        addMapping("DejaVuMono", 1, 1, "DejaVuMono-Bold")
        return "DejaVu", "DejaVuMono"
    except Exception:  # noqa: BLE001
        return "Helvetica", "Courier"


SANS, MONO = _register_fonts()


def _esc(s) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def smith_figure(smith: dict, size=4.2):
    fig, ax = plt.subplots(figsize=(size, size), dpi=150)
    ax.set_aspect("equal")
    ax.axis("off")
    th = np.linspace(0, 2 * np.pi, 400)
    ax.plot(np.cos(th), np.sin(th), color="#222", lw=1.0)
    for r in (0.2, 0.5, 1, 2, 5):
        c, rad = r / (1 + r), 1 / (1 + r)
        ax.plot(c + rad * np.cos(th), rad * np.sin(th), color="#9a9a9a", lw=0.5)
    for x in (0.2, 0.5, 1, 2, 5):
        for sgn in (1, -1):
            xx = sgn * x
            pts = 1 + (1 / xx) * 1j + (1 / x) * np.exp(1j * np.linspace(0, 2 * np.pi, 1200))
            pts[np.abs(pts) > 1.0001] = np.nan  # se corta fuera de la carta
            ax.plot(pts.real, pts.imag, color="#9a9a9a", lw=0.5)
    ax.plot([-1, 1], [0, 0], color="#9a9a9a", lw=0.5)
    palette = ["#0f9d58", "#1565c0", "#c62828", "#ef6c00", "#6a1b9a", "#00838f"]
    for i, tr in enumerate(smith.get("traces", [])):
        ax.plot(tr["re"], tr["im"], color=palette[i % len(palette)], lw=1.3, label=tr.get("name"))
    for i, p in enumerate(smith.get("points", [])):
        ax.plot(p["re"], p["im"], "o", color=palette[(i + 2) % len(palette)], ms=5)
        if p.get("label"):
            ax.annotate(p["label"], (p["re"], p["im"]), textcoords="offset points", xytext=(5, 5), fontsize=7)
    if smith.get("traces"):
        ax.legend(fontsize=6, loc="lower left", frameon=False)
    ax.set_xlim(-1.08, 1.08)
    ax.set_ylim(-1.08, 1.08)
    ax.set_title(f"Carta de Smith (Z0 = {smith.get('z0', 50):g} Ω)", fontsize=8)
    return fig


def plot_figure(p: dict):
    fig, ax = plt.subplots(figsize=(6.4, 2.8), dpi=150)
    x = np.asarray(p["x"], dtype=float)
    scale, unit = 1.0, ""
    if p.get("x_is_freq", True) and x.size and np.nanmax(x) > 1e3:
        mx = np.nanmax(x)
        scale, unit = (1e9, "GHz") if mx >= 1e9 else (1e6, "MHz") if mx >= 1e6 else (1e3, "kHz")
    db_axis = "dB" in (p.get("ylabel") or "")
    clipped = False
    for s in p["series"]:
        y = np.asarray([np.nan if v is None else v for v in s["y"]], dtype=float)
        if db_axis and "VSWR" not in (s.get("name") or "") and np.nanmin(y, initial=0) < -80:
            y = np.maximum(y, -80)  # sólo presentación: una adaptación exacta da |Γ| → 0 (−∞ dB)
            clipped = True
        ax.plot(x / scale, y, lw=1.1, label=s.get("name"))
    if clipped:
        ax.text(0.99, 0.02, "Valores < −80 dB recortados en la gráfica", transform=ax.transAxes, ha="right", fontsize=6, color="#777")
    ax.set_xlabel(p.get("xlabel") or (f"Frecuencia ({unit})" if unit else ""), fontsize=7)
    ax.set_ylabel(p.get("ylabel", ""), fontsize=7)
    ax.set_title(p.get("title", ""), fontsize=8)
    ax.tick_params(labelsize=6)
    ax.grid(alpha=0.3)
    if len(p["series"]) > 1:
        ax.legend(fontsize=6)
    fig.tight_layout()
    return fig


def _fig_image(fig, width_mm):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    img = Image(buf)
    ratio = img.imageHeight / img.imageWidth
    img.drawWidth = width_mm * mm
    img.drawHeight = width_mm * mm * ratio
    return img


def _kv_table(rows, styles):
    data = [[Paragraph(_esc(k), styles["cell"]), Paragraph(_esc(v), styles["cellmono"])] for k, v in rows]
    t = Table(data, colWidths=[62 * mm, 108 * mm])
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#bbbbbb")),
                           ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f2f5f3")),
                           ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    return t


def build_pdf(report: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm,
                            bottomMargin=16 * mm, title=report.get("title", "Informe RF"),
                            author=report.get("author", ""))
    ss = getSampleStyleSheet()
    styles = {
        "h1": ParagraphStyle("h1", parent=ss["Title"], fontName=SANS + "-Bold", fontSize=18, textColor=colors.HexColor("#0b3d2a"), alignment=TA_LEFT),
        "h2": ParagraphStyle("h2", parent=ss["Heading2"], fontName=SANS + "-Bold", fontSize=12.5, textColor=colors.HexColor("#0b3d2a"), spaceBefore=8),
        "h3": ParagraphStyle("h3", parent=ss["Heading3"], fontName=SANS + "-Bold", fontSize=10, spaceBefore=6),
        "body": ParagraphStyle("body", parent=ss["BodyText"], fontName=SANS, fontSize=8.6, leading=11.5),
        "cell": ParagraphStyle("cell", parent=ss["BodyText"], fontName=SANS, fontSize=7.8, leading=9.6),
        "cellmono": ParagraphStyle("cellmono", parent=ss["BodyText"], fontName=MONO, fontSize=7.6, leading=9.6),
        "origin": ParagraphStyle("origin", parent=ss["BodyText"], fontName=SANS, fontSize=8.4, textColor=colors.white,
                                 backColor=ACCENT, borderPadding=(3, 5, 3, 5), spaceBefore=2, spaceAfter=6),
        "note": ParagraphStyle("note", parent=ss["BodyText"], fontName=SANS, fontSize=7.6, textColor=colors.HexColor("#555555"), leading=9.5),
    }
    story = []
    created = report.get("created") or dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    story.append(Paragraph(_esc(report.get("title", "Informe técnico RF")), styles["h1"]))
    meta = [["Generado", created], ["Software", "RF Engineering Workbench"]]
    if report.get("author"):
        meta.insert(0, ["Autor", report["author"]])
    if report.get("project"):
        meta.insert(0, ["Proyecto", report["project"]])
    story.append(_kv_table(meta, styles))
    items = report.get("items", [])
    origins = sorted({it.get("origin", "calculated") for it in items})
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("Procedencia de los datos", styles["h2"]))
    story.append(_kv_table([[ORIGIN_LABELS.get(o, o), ", ".join(it["title"] for it in items if it.get("origin") == o)]
                            for o in origins] or [["—", "Informe vacío"]], styles))
    story.append(Paragraph(
        "Los resultados calculados o simulados proceden de modelos matemáticos y no constituyen mediciones. "
        "Los datos importados reflejan el contenido del archivo Touchstone indicado; su validez depende de cómo se midieron.",
        styles["note"]))
    for n, it in enumerate(items, start=1):
        story.append(PageBreak())
        story.append(Paragraph(f"{n}. {_esc(it.get('title', 'Resultado'))}", styles["h2"]))
        story.append(Paragraph(f"Origen: {_esc(ORIGIN_LABELS.get(it.get('origin'), it.get('origin')))}"
                               f" · Módulo: {_esc(it.get('module', ''))}"
                               + (f" · {_esc(it['created'])}" if it.get("created") else ""), styles["origin"]))
        if it.get("source_detail"):
            story.append(Paragraph(_esc(it["source_detail"]), styles["note"]))
        if it.get("inputs"):
            story.append(Paragraph("Datos de entrada", styles["h3"]))
            story.append(_kv_table(it["inputs"], styles))
        if it.get("results"):
            story.append(Paragraph("Resultados", styles["h3"]))
            story.append(_kv_table(it["results"], styles))
        for tb in it.get("tables", []):
            story.append(Paragraph(_esc(tb.get("title", "")), styles["h3"]))
            data = [[Paragraph(_esc(h), styles["cell"]) for h in tb["header"]]] + \
                   [[Paragraph(_esc(c), styles["cellmono"]) for c in row] for row in tb["rows"]]
            t = Table(data, repeatRows=1)
            t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#bbbbbb")),
                                   ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e3efe8"))]))
            story.append(t)
        if it.get("smith"):
            story.append(Spacer(1, 3 * mm))
            story.append(_fig_image(smith_figure(it["smith"]), 100))
        for p in it.get("plots", []):
            story.append(KeepTogether([_fig_image(plot_figure(p), 170)]))
        if it.get("steps"):
            story.append(Paragraph("Procedimiento matemático", styles["h3"]))
            for k, s in enumerate(it["steps"], start=1):
                txt = f"<b>{k}. {_esc(s.get('title', ''))}</b><br/><font face='{MONO}'>{_esc(s.get('formula', ''))}</font>"
                if s.get("substitution"):
                    txt += f"<br/><font face='{MONO}' color='#444444'>{_esc(s['substitution'])}</font>"
                if s.get("result"):
                    txt += f"<br/>= <font face='{MONO}'><b>{_esc(s['result'])}</b></font> {_esc(s.get('unit', ''))}"
                if s.get("note"):
                    txt += f"<br/><font color='#555555'><i>{_esc(s['note'])}</i></font>"
                story.append(Paragraph(txt, styles["body"]))
                story.append(Spacer(1, 1.5 * mm))
        for note in it.get("notes", []):
            story.append(Paragraph("• " + _esc(note), styles["note"]))

    def footer(canvas, d):
        canvas.saveState()
        canvas.setFont(SANS, 7)
        canvas.setFillColor(colors.HexColor("#777777"))
        canvas.drawString(18 * mm, 9 * mm, "RF Engineering Workbench — informe técnico")
        canvas.drawRightString(A4[0] - 18 * mm, 9 * mm, f"Página {d.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()


def build_csv(report: dict) -> str:
    out = io.StringIO()
    w = csv.writer(out, delimiter=";")
    w.writerow(["Informe", report.get("title", "")])
    w.writerow(["Generado", report.get("created") or dt.datetime.now().isoformat(timespec="seconds")])
    for it in report.get("items", []):
        w.writerow([])
        w.writerow(["# Elemento", it.get("title", "")])
        w.writerow(["Origen", ORIGIN_LABELS.get(it.get("origin"), it.get("origin"))])
        w.writerow(["Módulo", it.get("module", "")])
        for sec, key in (("Entrada", "inputs"), ("Resultado", "results")):
            for k, v in it.get(key, []):
                w.writerow([sec, k, v])
        for tb in it.get("tables", []):
            w.writerow(["Tabla", tb.get("title", "")])
            w.writerow(tb["header"])
            w.writerows(tb["rows"])
        for p in it.get("plots", []):
            w.writerow(["Gráfica", p.get("title", "")])
            w.writerow([p.get("xlabel") or "f (Hz)"] + [s.get("name", "") for s in p["series"]])
            for i, x in enumerate(p["x"]):
                w.writerow([x] + [s["y"][i] if i < len(s["y"]) else "" for s in p["series"]])
        for s in it.get("steps", []):
            w.writerow(["Paso", s.get("title", ""), s.get("formula", ""), s.get("substitution", ""), s.get("result", ""),
                        s.get("unit", "")])
    return out.getvalue()
