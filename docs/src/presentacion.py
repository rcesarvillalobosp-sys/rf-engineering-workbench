"""PDF 1 — Presentación de RF Engineering Workbench (para mostrar la herramienta)."""
from __future__ import annotations

import math
import subprocess
import sys

import figures as F
from common import (APP, AUTHOR, GITHUB, ROOT, Doc, P, PageBreak, Spacer, box, bullets, cover_flowables, mm, table,
                    toc, version)
from rfwb.engine import antenna_em, matching as mt, reflection as rf, tline as tl
from rfwb.engine.units import C0


def test_count() -> int:
    out = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", str(ROOT / "backend" / "tests")],
                         capture_output=True, text=True, cwd=str(ROOT / "backend")).stdout
    for line in out.splitlines()[::-1]:
        if "test" in line and "collected" not in line and line.split()[0].isdigit():
            return int(line.split()[0])
    return sum(1 for l in out.splitlines() if "::" in l)


def validation_rows():
    rows = []
    m = rf.reflection_metrics(100 + 0j, 50)
    rows.append(["Carga 100 Ω en 50 Ω", "Γ = 1/3, VSWR = 2, RL = 9.542 dB", f"Γ = {m['gamma'].real:.5f}, VSWR = {m['vswr']:.4f}, RL = {m['return_loss_db']:.4f} dB"])
    lam = C0 / 1e9
    r = tl.analyze_line(50, 1e9, lam / 4, zl=100 + 0j)
    rows.append(["Transformador λ/4 (Z0 = 50 Ω, ZL = 100 Ω)", "Zin = Z0²/ZL = 25 Ω", f"Zin = {r['zin'].real:.6f} Ω"])
    res = mt.design("L", 200 - 100j, 100 + 0j, 500e6, z0=100)
    sol = next(s for s in res["solutions"] if {(e["kind"], e["part"]) for e in s["elements"]} == {("shunt", "C"), ("series", "L")})
    c = next(e["value"] for e in sol["elements"] if e["part"] == "C")
    l = next(e["value"] for e in sol["elements"] if e["part"] == "L")
    rows.append(["Pozar, ej. 5.1 (red L)", "C = 0.92 pF, L = 38.8 nH", f"C = {c * 1e12:.3f} pF, L = {l * 1e9:.2f} nH"])
    st = sorted((round(s["d_lambda"], 3), round(s["l_lambda"], 3)) for s in mt.design("STUB1", 60 - 80j, 50 + 0j, 2e9, stub="short")["solutions"])
    rows.append(["Pozar, ej. 5.2 (stub en corto)", "d = 0.110λ, ℓ = 0.095λ", f"d = {st[0][0]:.3f}λ, ℓ = {st[0][1]:.3f}λ"])
    d = antenna_em.wire_antenna("dipole", C0, 0.5, 1e-5)
    rows.append(["Dipolo λ/2 (Balanis)", "Z = 73.1 + j42.5 Ω, D = 2.15 dBi", f"Z = {d['z_in'].real:.2f} + j{d['z_in'].imag:.2f} Ω, D = {d['directivity_dbi']:.3f} dBi"])
    mo = antenna_em.wire_antenna("monopole", C0, 0.25, 1e-5)
    rows.append(["Monopolo λ/4 (Balanis)", "Z = 36.5 + j21.3 Ω, D = 5.16 dBi", f"Z = {mo['z_in'].real:.2f} + j{mo['z_in'].imag:.2f} Ω, D = {mo['directivity_dbi']:.3f} dBi"])
    return rows


def build(out_path):
    n_tests = test_count()
    doc = Doc(out_path, "Presentación de la herramienta", "Plataforma de análisis, simulación y diseño de sistemas RF", "Presentación")
    st = cover_flowables(
        APP, "Plataforma profesional de análisis, simulación y diseño de sistemas de radiofrecuencia",
        f"Herramienta de escritorio desarrollada por <b>{AUTHOR}</b> para el cálculo de impedancias, la carta de Smith, el diseño de "
        "redes de adaptación, el análisis de líneas de transmisión, parámetros S y antenas, y la importación de mediciones reales. "
        "Funciona sin instrumentos y está preparada para conectarse a analizadores vectoriales de redes (VNA).")
    st += toc()

    st += [P("1. Qué es RF Engineering Workbench", "h1"),
           P(f"<b>{APP}</b> es una aplicación de escritorio para Windows, concebida y dirigida por <b>{AUTHOR}</b>, que reúne en un único entorno "
             "las herramientas que un estudiante, técnico o ingeniero de telecomunicaciones necesita para trabajar con circuitos de radiofrecuencia: "
             "desde el cálculo de una reactancia hasta el diseño de una red de adaptación, el análisis de un archivo Touchstone medido en laboratorio "
             "o la estimación del diagrama de radiación de un dipolo."),
           P("No es una calculadora con fórmulas sueltas: cada módulo está construido sobre un <b>motor matemático único</b>, validado con casos de libro "
             "y contrastado con la biblioteca científica scikit-rf, y cada resultado indica explícitamente de dónde procede."),
           box("def", "Objetivo", ["Ofrecer una herramienta técnica fiable, didáctica y útil incluso sin hardware, con una arquitectura preparada para evolucionar "
                                   "hacia un sistema de medida integrado con instrumentos reales."]),
           P("2. Principios de diseño", "h1"),
           *bullets([
               "<b>Precisión antes que apariencia.</b> Todas las fórmulas residen en un motor central; la interfaz nunca recalcula magnitudes de ingeniería.",
               f"<b>Resultados verificables.</b> {n_tests} pruebas automáticas comparan el motor con resultados analíticos, ejemplos de Pozar y Balanis y con scikit-rf.",
               "<b>Procedencia explícita.</b> Cada dato se etiqueta como <i>Calculado</i>, <i>Simulado</i>, <i>Importado desde Touchstone</i>, <i>Medición real</i> o <i>Derivado</i>. Nunca se mezclan.",
               "<b>Honestidad técnica.</b> Una adaptación sólo es exacta a su frecuencia de diseño; la aplicación muestra el ancho de banda real y el límite teórico de Bode–Fano. Del S11 no se deducen magnitudes de radiación.",
               "<b>Sin conexiones simuladas.</b> Sin instrumento, la aplicación lo indica («Sin instrumento conectado — Modo de simulación») y trabaja con modelos o archivos.",
               "<b>Didáctica.</b> El modo educativo muestra fórmula, sustitución, resultado e interpretación física de cada cálculo.",
           ]),
           P("3. Arquitectura", "h1"),
           P("La aplicación separa estrictamente cálculo, datos e interfaz. Electron aloja la ventana de escritorio y arranca el motor Python "
             "como un proceso interno; la interfaz se comunica con él mediante una API HTTP local."),
           F.architecture(),
           P("4. Módulos", "h1"),
           table([
               ["Dashboard", "Estado del sistema, autoverificación del motor, datos recientes y conceptos fundamentales."],
               ["Smith Chart", "Carta exacta e interactiva: impedancia/admitancia, Γ, VSWR, RL, comparación de puntos, desplazamiento por línea, zoom y exportación SVG/PNG 4000 px."],
               ["Circuit Builder", "Construcción del circuito elemento a elemento (L, C, R, líneas, stubs) con la trayectoria en vivo sobre la carta de Smith."],
               ["Impedance Analyzer", "Circuitos R, L, C serie/paralelo y redes arbitrarias por expresión; potencias, resonancia, Q y barridos."],
               ["Matching Designer", "Redes L, Pi, T, λ/4, stub simple y doble; ancho de banda, Bode–Fano, valores normalizados, Q finito y Monte Carlo de tolerancias."],
               ["Transmission Lines", "Coaxial, microstrip (con dispersión y pérdidas), bifilar y cables; Zin, Γ(d), onda estacionaria y balance de potencia."],
               ["S-Parameters", "Magnitud, fase, Smith, VSWR, RL, retardo de grupo, marcadores, bandas, comparación, estabilidad K/μ, círculos de ganancia, TDR y modo mixto."],
               ["Antenna Analyzer", "Resonancia, ancho de banda y Q desde S11/Z; modelo EM analítico de dipolo y monopolo (diagrama, directividad, eficiencia, ganancia)."],
               ["Component Library", "Componentes ideales y reales (Q, ESR, SRF), cables con atenuación; sin datos inventados de fabricantes."],
               ["Touchstone Importer", "Lectura validada de .s1p–.s4p (v1/v2, RI/MA/DB, S/Y/Z/H/G, modo mixto) y exportación."],
               ["VNA Integration", "Drivers NanoVNA, LibreVNA y SCPI/VISA, barrido continuo, calibración SOL/SOLT con kits definibles."],
               ["Reports", "Informes PDF y CSV con datos de entrada, resultados, carta, gráficas, procedimiento y procedencia."],
           ], header=["Módulo", "Función"], widths=[38, 132]),
           Spacer(1, 6),
           P("5. Algunas capacidades en imágenes", "h1"),
           F.smith_example(width=92),
           F.matching_example(),
           F.dipole_pattern(),
           P("6. Validación", "h1"),
           P(f"La batería de pruebas automáticas ({n_tests} pruebas en la versión {version()}) se ejecuta antes de cada publicación; si una sola falla, "
             "la versión no se publica. La tabla muestra algunos casos de referencia con el valor que calcula la aplicación en el momento de generar este documento."),
           table(validation_rows(), header=["Caso", "Referencia", "Resultado de la aplicación"], widths=[48, 52, 70]),
           P("Los valores de Pozar proceden de la lectura sobre la carta de Smith y están redondeados (por ejemplo, x = 1.22 en lugar de 1.2247); "
             "la aplicación da el valor exacto de la solución analítica.", "small"),
           Spacer(1, 6),
           P("Además se contrastan con scikit-rf las conversiones S↔Z/ABCD, el factor de estabilidad K, la lectura de archivos Touchstone, "
             "la calibración de un puerto, la conversión a modo mixto y las líneas con pérdidas."),
           P("7. Tecnologías", "h1"),
           table([["Motor de cálculo", "Python 3.13 · NumPy · SciPy · scikit-rf · pandas"],
                  ["API", "FastAPI · Uvicorn · Pydantic"],
                  ["Interfaz", "React · TypeScript · Tailwind CSS · Motion · Plotly · SVG propio para la carta de Smith"],
                  ["Escritorio", "Electron · electron-builder (instalador NSIS) · electron-updater"],
                  ["Persistencia e informes", "SQLite · ReportLab · Matplotlib"],
                  ["Instrumentación", "pyserial · PyVISA · SCPI sobre TCP"]], header=["Capa", "Tecnologías"], widths=[45, 125]),
           P("8. Distribución y actualizaciones", "h1"),
           P("La aplicación se distribuye como instalador de Windows que incluye el motor compilado: el equipo de destino no necesita Python ni Node. "
             "Cada versión se publica en GitHub Releases y la aplicación instalada avisa de las nuevas versiones, pidiendo confirmación antes de descargar e instalar."),
           P("9. Estado y evolución", "h1"),
           *bullets(["Pendiente: verificación de los drivers con instrumentos físicos.",
                     "Pendiente: firma digital del instalador.",
                     "Evolución prevista: más geometrías de antena mediante simulación numérica y kits de calibración con datos medidos."]),
           Spacer(1, 10),
           box("app", "Autor", [f"<b>{AUTHOR}</b> · GitHub: {GITHUB}", f"{APP} · versión {version()}"]),
           ]
    doc.multiBuild(st)


if __name__ == "__main__":
    build(sys.argv[1])
