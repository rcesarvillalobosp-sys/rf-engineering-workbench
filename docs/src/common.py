"""Base común de los documentos PDF de RF Engineering Workbench.

Estilos, fuentes con Γ Ω ∠ (DejaVu), ecuaciones renderizadas con mathtext de matplotlib, figuras,
cuadros de definición/ejemplo/nota, portada y pie de página. Los valores numéricos de los ejemplos
se calculan con el propio motor (backend/rfwb) para que coincidan exactamente con la aplicación.
"""
from __future__ import annotations

import io
import pathlib
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from reportlab.lib import colors  # noqa: E402
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.styles import ParagraphStyle  # noqa: E402
from reportlab.lib.units import mm  # noqa: E402
from reportlab.platypus import (BaseDocTemplate, Frame, Image, KeepTogether, NextPageTemplate, PageBreak,  # noqa: E402
                                PageTemplate, Paragraph, Spacer, Table, TableStyle)
from reportlab.platypus.tableofcontents import TableOfContents  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from rfwb.reports.generator import MONO, SANS  # noqa: E402  (registra DejaVu)

AUTHOR = "Ricardo Villalobos Perez"
GITHUB = "rcesarvillalobosp-sys"
APP = "RF Engineering Workbench"

INK = colors.HexColor("#0f172a")
DIM = colors.HexColor("#475569")
ACC = colors.HexColor("#059669")
ACC_D = colors.HexColor("#064e3b")
ACC_L = colors.HexColor("#ecfdf5")
INFO_L = colors.HexColor("#eff6ff")
WARN_L = colors.HexColor("#fffbeb")
LINE = colors.HexColor("#d7dee6")
BAND = colors.HexColor("#0b1220")

S = {
    "title": ParagraphStyle("title", fontName=SANS + "-Bold", fontSize=26, leading=31, textColor=colors.white),
    "subtitle": ParagraphStyle("subtitle", fontName=SANS, fontSize=13, leading=18, textColor=colors.HexColor("#a7f3d0")),
    "h1": ParagraphStyle("h1", fontName=SANS + "-Bold", fontSize=18, leading=23, textColor=ACC_D, spaceBefore=10, spaceAfter=8, keepWithNext=1),
    "h2": ParagraphStyle("h2", fontName=SANS + "-Bold", fontSize=13.2, leading=17, textColor=ACC_D, spaceBefore=10, spaceAfter=4, keepWithNext=1),
    "h3": ParagraphStyle("h3", fontName=SANS + "-Bold", fontSize=10.8, leading=14, textColor=INK, spaceBefore=7, spaceAfter=2, keepWithNext=1),
    "body": ParagraphStyle("body", fontName=SANS, fontSize=9.6, leading=14, textColor=INK, alignment=TA_JUSTIFY, spaceAfter=5),
    "bullet": ParagraphStyle("bullet", fontName=SANS, fontSize=9.6, leading=13.6, textColor=INK, leftIndent=12, bulletIndent=2, spaceAfter=2),
    "small": ParagraphStyle("small", fontName=SANS, fontSize=8, leading=10.5, textColor=DIM),
    "caption": ParagraphStyle("caption", fontName=SANS, fontSize=8.2, leading=10.5, textColor=DIM, alignment=TA_CENTER, spaceAfter=8),
    "box": ParagraphStyle("box", fontName=SANS, fontSize=9.2, leading=13.2, textColor=INK, alignment=TA_LEFT),
    "boxt": ParagraphStyle("boxt", fontName=SANS + "-Bold", fontSize=9.4, leading=13, textColor=ACC_D),
    "cell": ParagraphStyle("cell", fontName=SANS, fontSize=8.4, leading=11, textColor=INK),
    "cellb": ParagraphStyle("cellb", fontName=SANS + "-Bold", fontSize=8.4, leading=11, textColor=colors.white),
    "mono": ParagraphStyle("mono", fontName=MONO, fontSize=8.2, leading=11, textColor=INK),
    "toc1": ParagraphStyle("toc1", fontName=SANS + "-Bold", fontSize=10.5, leading=15, textColor=INK, leftIndent=0),
    "toc2": ParagraphStyle("toc2", fontName=SANS, fontSize=9.2, leading=12.5, textColor=DIM, leftIndent=14),
}


def P(text, style="body"):
    return Paragraph(text, S[style])


def bullets(items, style="bullet"):
    return [Paragraph(t, S[style], bulletText="•") for t in items]


def numbered(items):
    return [Paragraph(t, S["bullet"], bulletText=f"{i}.") for i, t in enumerate(items, 1)]


# ───────────── Ecuaciones (mathtext) ─────────────
def eq(tex: str, size: float = 13, width_mm: float | None = None, label: str | None = None):
    """Ecuación renderizada con mathtext de matplotlib (sin LaTeX instalado)."""
    fig = plt.figure(figsize=(0.01, 0.01))
    fig.text(0, 0, f"${tex}$", fontsize=size, color="#0f172a")
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=300, bbox_inches="tight", pad_inches=0.04, transparent=True)
    plt.close(fig)
    buf.seek(0)
    img = Image(buf)
    w = img.imageWidth / 300 * 72
    h = img.imageHeight / 300 * 72
    if width_mm and w > width_mm * mm:
        h *= width_mm * mm / w
        w = width_mm * mm
    img.drawWidth, img.drawHeight = w, h
    cells = [[img, Paragraph(f"({label})", S["small"]) if label else ""]]
    t = Table(cells, colWidths=[160 * mm, 14 * mm])
    t.setStyle(TableStyle([("ALIGN", (0, 0), (0, 0), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                           ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    return t


# ───────────── Figuras ─────────────
def fig_image(fig, width_mm=150, caption: str | None = None):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    img = Image(buf)
    r = img.imageHeight / img.imageWidth
    img.drawWidth = width_mm * mm
    img.drawHeight = width_mm * mm * r
    cell = [img] + ([Paragraph(caption, S["caption"])] if caption else [])
    t = Table([[cell]], colWidths=[170 * mm])  # una sola fila: no se parte y se mantiene con su título
    t.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                           ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 2)]))
    return t


def smith_axes(ax, z0=50, admittance=False):
    """Carta de Smith dibujada con las mismas ecuaciones que la aplicación."""
    ax.set_aspect("equal")
    ax.axis("off")
    th = np.linspace(0, 2 * np.pi, 600)
    ax.fill(np.cos(th), np.sin(th), color="#f8fafc", zorder=0)
    for r in (0.2, 0.5, 1, 2, 5):
        c, rad = r / (1 + r), 1 / (1 + r)
        ax.plot(c + rad * np.cos(th), rad * np.sin(th), color="#059669" if r == 1 else "#cbd5e1", lw=0.8 if r == 1 else 0.6, zorder=1)
        ax.text((r - 1) / (r + 1) + 0.01, 0.015, f"{r:g}", fontsize=6, color="#64748b", rotation=90, va="bottom")
    for x in (0.2, 0.5, 1, 2, 5):
        for sg in (1, -1):
            p = 1 + 1j / (sg * x) + np.exp(1j * np.linspace(0, 2 * np.pi, 1500)) / x
            p[np.abs(p) > 1.0005] = np.nan
            ax.plot(p.real, p.imag, color="#059669" if x == 1 else "#cbd5e1", lw=0.8 if x == 1 else 0.6, zorder=1)
            gz = ((1j * sg * x) - 1) / ((1j * sg * x) + 1)
            ax.text(gz.real * 1.07, gz.imag * 1.07, f"{'+' if sg > 0 else '−'}j{x:g}", fontsize=6, color="#64748b", ha="center", va="center")
    if admittance:
        for g in (0.5, 1, 2):
            c, rad = g / (1 + g), 1 / (1 + g)
            ax.plot(-c + rad * np.cos(th), rad * np.sin(th), color="#93c5fd", lw=0.6, ls="--", zorder=1)
    ax.plot([-1, 1], [0, 0], color="#94a3b8", lw=0.6, zorder=1)
    ax.plot(np.cos(th), np.sin(th), color="#334155", lw=1.2, zorder=2)
    ax.set_xlim(-1.15, 1.15)
    ax.set_ylim(-1.15, 1.15)


def gamma_of(z, z0=50):
    return (z - z0) / (z + z0)


def table(rows, header=None, widths=None, zebra=True, font="cell"):
    data = []
    if header:
        data.append([Paragraph(h, S["cellb"]) for h in header])
    data += [[c if not isinstance(c, str) else Paragraph(c, S[font]) for c in r] for r in rows]
    t = Table(data, colWidths=[w * mm for w in widths] if widths else None, repeatRows=1 if header else 0)
    st = [("GRID", (0, 0), (-1, -1), 0.3, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
          ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    if header:
        st.append(("BACKGROUND", (0, 0), (-1, 0), ACC_D))
    if zebra:
        for i in range(1 if header else 0, len(data)):
            if i % 2 == 0:
                st.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#f8fafc")))
    t.setStyle(TableStyle(st))
    return t


def box(kind: str, title: str, content):
    """Cuadro de color: kind ∈ def (definición), ej (ejemplo), nota, app (en la aplicación)."""
    bg, bar = {"def": (ACC_L, ACC), "ej": (INFO_L, colors.HexColor("#2563eb")), "nota": (WARN_L, colors.HexColor("#d97706")),
               "app": (colors.HexColor("#f1f5f9"), colors.HexColor("#334155"))}[kind]
    inner = [Paragraph(title, S["boxt"])]
    for c in (content if isinstance(content, list) else [content]):
        inner.append(Paragraph(c, S["box"]) if isinstance(c, str) else c)
    t = Table([[inner]], colWidths=[170 * mm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), bg), ("LINEBEFORE", (0, 0), (0, -1), 3, bar),
                           ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                           ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
    return KeepTogether([t, Spacer(1, 6)])


# ───────────── Documento ─────────────
class Doc(BaseDocTemplate):
    """Documento con portada propia, índice automático, cabecera y pie."""

    def __init__(self, path, title, subtitle, kind_label, **kw):
        super().__init__(str(path), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=20 * mm,
                         bottomMargin=18 * mm, title=title, author=AUTHOR, subject=subtitle, creator=APP, **kw)
        self.doc_title, self.subtitle, self.kind_label = title, subtitle, kind_label
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="f")
        self.addPageTemplates([PageTemplate("cover", [frame], onPage=self._cover),
                               PageTemplate("body", [frame], onPage=self._page)])

    def afterFlowable(self, f):
        if isinstance(f, Paragraph) and f.style.name in ("h1", "h2"):
            lvl = 0 if f.style.name == "h1" else 1
            text = f.getPlainText()
            key = f"h{id(f)}"
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(text, key, level=lvl, closed=lvl > 0)
            self.notify("TOCEntry", (lvl, text, self.page, key))

    def _cover(self, c, d):
        w, h = A4
        c.saveState()
        c.setFillColor(BAND)
        c.rect(0, h * 0.42, w, h * 0.58, stroke=0, fill=1)
        c.setStrokeColor(colors.HexColor("#34d399"))
        cx, cy, R = w - 50 * mm, h - 52 * mm, 30 * mm
        c.setLineWidth(2.2)
        c.circle(cx, cy, R)
        c.setLineWidth(0.8)
        for r in (0.5, 1, 3):
            rr = R / (1 + r)
            c.circle(cx + R - rr, cy, rr)
        c.line(cx - R, cy, cx + R, cy)
        c.setFillColor(colors.HexColor("#34d399"))
        c.setFont(MONO, 9)
        c.drawString(20 * mm, h - 25 * mm, self.kind_label.upper())
        c.setFillColor(colors.HexColor("#94a3b8"))
        c.setFont(SANS, 9)
        c.drawString(20 * mm, h * 0.42 + 12 * mm, f"Autor: {AUTHOR}")
        c.drawString(20 * mm, h * 0.42 + 7 * mm, f"GitHub: {GITHUB}  ·  Versión de la aplicación: {version()}")
        c.restoreState()

    def _page(self, c, d):
        w, h = A4
        c.saveState()
        c.setStrokeColor(LINE)
        c.setLineWidth(0.5)
        c.line(20 * mm, h - 13 * mm, w - 20 * mm, h - 13 * mm)
        c.setFont(SANS, 7.5)
        c.setFillColor(DIM)
        c.drawString(20 * mm, h - 11 * mm, f"{APP} — {self.doc_title}")
        c.drawRightString(w - 20 * mm, h - 11 * mm, f"Versión {version()}")  # el autor sólo figura en la portada
        c.line(20 * mm, 12 * mm, w - 20 * mm, 12 * mm)
        c.drawString(20 * mm, 8 * mm, self.kind_label)
        c.drawRightString(w - 20 * mm, 8 * mm, f"Página {d.page}")
        c.restoreState()


def cover_flowables(title, subtitle, abstract):
    return [Spacer(1, 92 * mm), Paragraph(title, S["title"]), Spacer(1, 4 * mm), Paragraph(subtitle, S["subtitle"]),
            Spacer(1, 52 * mm), Paragraph(abstract, ParagraphStyle("abs", parent=S["body"], fontSize=10.2, leading=15)),
            NextPageTemplate("body"), PageBreak()]


def toc():
    t = TableOfContents()
    t.levelStyles = [S["toc1"], S["toc2"]]
    return [Paragraph("Contenido", S["h1"].clone("tocH")), t, PageBreak()]


def version():
    import json
    return json.loads((ROOT / "package.json").read_text(encoding="utf-8"))["version"]


__all__ = ["P", "S", "eq", "fig_image", "smith_axes", "gamma_of", "table", "box", "bullets", "numbered", "Doc",
           "cover_flowables", "toc", "version", "plt", "np", "mm", "Spacer", "PageBreak", "KeepTogether", "AUTHOR",
           "GITHUB", "APP", "ROOT"]
