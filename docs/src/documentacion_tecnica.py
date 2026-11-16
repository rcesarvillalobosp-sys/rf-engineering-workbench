"""PDF 3 — Documentación técnica profesional (para el repositorio de GitHub).
Las tablas de endpoints, pruebas e historial se generan a partir del propio código y del historial de git.
"""
from __future__ import annotations

import collections
import subprocess
import sys

import figures as F
from common import (APP, AUTHOR, GITHUB, ROOT, Doc, P, Spacer, box, bullets, cover_flowables, numbered, table, toc,
                    version)


def run(cmd, cwd=ROOT):
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(cwd), encoding="utf-8", errors="replace").stdout


def endpoints():
    """Rutas reales de la API, leídas del esquema OpenAPI de la aplicación."""
    from rfwb.main import app
    rows = []
    for path, ops in app.openapi()["paths"].items():
        if not path.startswith("/api"):
            continue
        for method, op in ops.items():
            desc = (op.get("description") or "").strip().split("\n")[0] or op.get("summary", "")
            rows.append([method.upper(), path, desc])
    return sorted(rows, key=lambda x: (x[1], x[0]))


def tests_by_file():
    out = run([sys.executable, "-m", "pytest", "--collect-only", "-q", "tests"], cwd=ROOT / "backend")
    cnt = collections.Counter(l.split("::")[0] for l in out.splitlines() if "::" in l)
    return [[f, str(n)] for f, n in sorted(cnt.items())], sum(cnt.values())


def changelog():
    """Para cada versión, los mensajes de todos sus commits (desde la etiqueta anterior)."""
    tags = [x for x in run(["git", "tag", "--sort=creatordate"]).split() if x.startswith("v")]
    rows, prev = [], None
    for tag in tags:
        rng = f"{prev}..{tag}" if prev else tag
        subjects = [l.strip() for l in run(["git", "log", "--format=%s", rng]).splitlines() if l.strip()]
        date = run(["git", "log", "-1", "--format=%ad", "--date=short", tag]).strip()
        rows.append([tag, date, " · ".join(reversed(subjects))])
        prev = tag
    return rows[::-1]


DESC = {
    ('GET', '/api/health'): 'Estado del motor y versiones de NumPy, SciPy y scikit-rf',
    ('GET', '/api/selftest'): 'Autoverificación del motor contra casos de referencia',
    ('POST', '/api/rf/reflection'): 'Γ, VSWR, RL, admitancia y equivalentes L/C de una impedancia',
    ('POST', '/api/rf/line-rotate'): 'Desplazamiento de una impedancia por una línea sin pérdidas',
    ('POST', '/api/circuit/analyze'): 'Análisis de circuitos R, L, C serie/paralelo con barrido',
    ('POST', '/api/circuit/network'): 'Análisis de redes definidas por expresión (serie/paralelo)',
    ('POST', '/api/circuit/builder'): 'Constructor de circuitos: nodos, trayectoria en la carta y barrido',
    ('POST', '/api/component/impedance'): '|Z(f)| de componentes ideales y con parásitos (Q, ESR, SRF)',
    ('POST', '/api/tline/geometry'): 'Z0, vf y pérdidas a partir de la geometría (coaxial, bifilar, microstrip)',
    ('POST', '/api/tline/analyze'): 'Análisis de líneas: Zin, Γ(d), onda estacionaria y potencias',
    ('POST', '/api/match/design'): 'Diseño de redes de adaptación (L, Pi, T, λ/4, stubs)',
    ('POST', '/api/match/evaluate'): 'Evaluación de una red de adaptación editada manualmente',
    ('POST', '/api/match/tolerance'): 'Análisis Monte Carlo de tolerancias',
    ('POST', '/api/touchstone/parse'): 'Lectura, validación y contraste con scikit-rf de archivos Touchstone',
    ('GET', '/api/datasets'): 'Lista de conjuntos de datos con su origen',
    ('GET', '/api/datasets/{ds_id}'): 'Conjunto de datos completo',
    ('DELETE', '/api/datasets/{ds_id}'): 'Elimina un conjunto de datos',
    ('GET', '/api/datasets/{ds_id}/export'): 'Exportación a Touchstone (RI/MA/DB) o CSV',
    ('POST', '/api/datasets/simulated'): 'Genera datos simulados a partir de un modelo',
    ('POST', '/api/sparams/analyze'): 'Métricas, marcadores, bandas, resonancias y estabilidad',
    ('POST', '/api/sparams/circles'): 'Círculos de estabilidad y de ganancia a una frecuencia',
    ('POST', '/api/sparams/tdr'): 'Respuesta en el dominio del tiempo (low-pass / band-pass)',
    ('POST', '/api/sparams/mixed-mode'): 'Conversión a parámetros S en modo mixto',
    ('POST', '/api/antenna/analyze'): 'Análisis de puerto de antenas (resonancia, BW, Q)',
    ('POST', '/api/antenna/em-model'): 'Modelo EM analítico de dipolo/monopolo',
    ('POST', '/api/calibration/sol'): 'Calibración SOL de un puerto (kit ideal o definido)',
    ('POST', '/api/calibration/solt'): 'Calibración SOLT de dos puertos (12 términos)',
    ('GET', '/api/library'): 'Consulta de la biblioteca de componentes',
    ('POST', '/api/library'): 'Añade un componente',
    ('PUT', '/api/library/{cid}'): 'Modifica un componente',
    ('DELETE', '/api/library/{cid}'): 'Elimina un componente',
    ('GET', '/api/projects'): 'Lista de proyectos',
    ('POST', '/api/projects'): 'Crea un proyecto',
    ('GET', '/api/projects/{pid}'): 'Abre un proyecto',
    ('PUT', '/api/projects/{pid}'): 'Guarda un proyecto',
    ('DELETE', '/api/projects/{pid}'): 'Elimina un proyecto',
    ('GET', '/api/vna/status'): 'Estado del instrumento (modo simulación o medición real)',
    ('GET', '/api/vna/drivers'): 'Drivers disponibles y sus capacidades',
    ('POST', '/api/vna/scan'): 'Detección de instrumentos (serie, LibreVNA, VISA)',
    ('POST', '/api/vna/connect'): 'Conexión a un instrumento',
    ('POST', '/api/vna/disconnect'): 'Desconexión del instrumento',
    ('POST', '/api/vna/sweep'): 'Configuración del barrido',
    ('POST', '/api/vna/capture'): 'Captura y guardado como medición real',
    ('POST', '/api/vna/live'): 'Barrido continuo (sin guardar)',
    ('POST', '/api/vna/save-last'): 'Guarda la última captura del barrido continuo',
    ('POST', '/api/reports/pdf'): 'Informe técnico en PDF',
    ('POST', '/api/reports/csv'): 'Informe en CSV',
}


def build(out_path):
    tb, ntests = tests_by_file()
    doc = Doc(out_path, "Documentación técnica", "Arquitectura, instalación, API, validación y publicación", "Documentación técnica")
    st = cover_flowables(
        APP, "Documentación técnica del proyecto",
        "Plataforma de escritorio para el análisis, la simulación y el diseño de sistemas de radiofrecuencia. Este documento describe la "
        "arquitectura, la instalación y compilación, la API del motor de cálculo, la estrategia de validación numérica y el proceso de publicación.")
    st += toc()
    st += [P("1. Resumen", "h1"),
           P(f"{APP} integra en una aplicación de escritorio para Windows un motor de cálculo de RF escrito en Python (NumPy, SciPy, scikit-rf), "
             "una API local FastAPI y una interfaz React. Funciona sin instrumentos y está preparada para integrarse con analizadores vectoriales "
             f"de redes. La versión actual es la <b>{version()}</b>, validada con <b>{ntests}</b> pruebas automáticas."),
           P("2. Características", "h1"),
           *bullets(["Carta de Smith exacta e interactiva con exportación vectorial y de alta resolución.",
                     "Circuit Builder: construcción de redes elemento a elemento con trayectoria en vivo sobre la carta.",
                     "Análisis de impedancias, circuitos RLC y redes arbitrarias por expresión.",
                     "Diseño de adaptación: L, Pi, T, λ/4, stub simple y doble; Bode–Fano, valores normalizados, Q finito y Monte Carlo.",
                     "Líneas de transmisión: coaxial, bifilar, microstrip con dispersión y pérdidas; onda estacionaria y balance de potencia.",
                     "Parámetros S: magnitud, fase, retardo de grupo, bandas, estabilidad K/μ, círculos de ganancia, TDR y modo mixto.",
                     "Antenas: análisis de puerto y modelo EM analítico de dipolo/monopolo (diagrama, directividad, eficiencia, ganancia).",
                     "Touchstone v1/v2 (.s1p–.sNp; RI/MA/DB; S/Y/Z/H/G; modo mixto) con contraste frente a scikit-rf.",
                     "Instrumentación: drivers NanoVNA, LibreVNA y SCPI/VISA; barrido continuo; calibración SOL/SOLT con kits definibles.",
                     "Procedencia de datos obligatoria (calculado, simulado, importado, medido, derivado) e informes PDF/CSV.",
                     "Temas claro/oscuro, modo educativo, proyectos persistentes y actualizaciones automáticas."]),
           P("3. Arquitectura", "h1"),
           F.architecture(),
           P("Principio rector: <b>una sola implementación de cada fórmula</b>, en backend/rfwb/engine. La interfaz contiene únicamente la geometría de dibujo de la carta "
             "de Smith (para la lectura instantánea del cursor). Electron arranca el motor en un puerto efímero y lo detiene al cerrar; en producción el motor es un "
             "ejecutable PyInstaller autocontenido."),
           P("4. Estructura del repositorio", "h1"),
           table([["backend/rfwb/engine", "Motor de cálculo (Python puro, sin dependencias de interfaz)"], ["backend/rfwb/api", "Endpoints FastAPI y serialización"],
                  ["backend/rfwb/io · vna · reports · library", "Touchstone, drivers de instrumentos, informes, biblioteca"], ["backend/tests", "Pruebas (pytest)"],
                  ["frontend/src", "Interfaz React + TypeScript (módulos, componentes, temas)"], ["electron", "Proceso principal, preload, actualizador"],
                  ["scripts", "build_engine.ps1, smoke_engine.ps1, release.ps1"], ["docs", "Documentación y generadores de PDF"]],
                 header=["Ruta", "Contenido"], widths=[70, 100]),
           P("5. Puesta en marcha", "h1"),
           P("Requisitos: Windows 10/11, Python 3.11+ (probado con 3.13), Node.js 20+ y Git.", "body"),
           table([["python -m venv backend\\.venv", "Entorno virtual del motor"], ["backend\\.venv\\Scripts\\python -m pip install -r backend\\requirements.txt", "Dependencias Python"],
                  ["npm install && npm --prefix frontend install", "Dependencias de Electron y de la interfaz"], ["npm run dev", "Desarrollo con recarga en caliente"],
                  ["npm run test:engine", "Batería de validación"], ["npm start", "Compilar la interfaz y abrir la aplicación"]],
                 header=["Comando", "Propósito"], widths=[100, 70], font="mono"),
           P("6. API del motor", "h1"),
           P("La API es local (127.0.0.1) y no expone servicios a la red. Los números complejos se serializan como {re, im} y los infinitos como \"inf\". "
             "Los errores de validación devuelven HTTP 422 con un mensaje legible; los errores de instrumento, HTTP 409."),
           table([[m, p, DESC.get((m, p), d)] for m, p, d in endpoints()], header=["Método", "Ruta", "Descripción"], widths=[20, 62, 88], font="cell"),
           P("7. Validación numérica", "h1"),
           P("Cada fórmula se verifica frente a resultados analíticos, ejemplos publicados (Pozar, Balanis) y la biblioteca scikit-rf. El script de publicación "
             "ejecuta toda la batería y aborta si una sola prueba falla."),
           table(tb + [["Total", str(ntests)]], header=["Archivo", "Pruebas"], widths=[130, 40]),
           Spacer(1, 4),
           table([["Reflexión y VSWR", "Analítico; scikit-rf (z2s)"], ["Líneas con pérdidas", "scikit-rf (DefinedGammaZ0)"], ["Red L, stub simple y doble", "Pozar 5.1, 5.2, 5.4"],
                  ["S ↔ Z / ABCD / H / G", "scikit-rf; casos analíticos"], ["Estabilidad K", "scikit-rf"], ["Touchstone", "scikit-rf; ida y vuelta RI/MA/DB"],
                  ["Calibración SOL / SOLT", "Cajas de error aleatorias; scikit-rf OnePort"], ["Modo mixto", "scikit-rf (se2gmm)"], ["Antenas de hilo", "Balanis (dipolo λ/2, monopolo λ/4, dipolo corto)"]],
                 header=["Área", "Referencia de contraste"], widths=[70, 100]),
           box("nota", "Discrepancia documentada con scikit-rf", ["scikit-rf 2.2 desnormaliza los parámetros Y/H/G de Touchstone v1 multiplicando todos los elementos por R (sólo correcto para Z). "
                                                                "En esos casos el contraste se omite y la lectura se valida con redes de resultado analítico conocido."]),
           P("8. Convenciones", "h1"),
           *bullets(["Dependencia temporal e<super>+jωt</super>: X_L = +ωL, X_C = −1/(ωC).", "Γ = (Z − Z0)/(Z + Z0) con Z0 real; onda de potencia para fuentes complejas.",
                     "Return Loss positivo; |S11| dB = −RL.", "Touchstone v1 de 2 puertos en orden S11 S21 S12 S22.",
                     "Modo mixto: pares consecutivos (p, n), referencias 2·Z0 y Z0/2."]),
           P("9. Compilación y publicación", "h1"),
           *numbered(["npm version patch --no-git-tag-version", "git commit -am \"Versión X.Y.Z\"",
                      "npm run release — pruebas, interfaz, motor PyInstaller (con prueba de humo), instalador NSIS, subida a GitHub Releases y etiqueta git."]),
           P("Los instaladores se publican en un repositorio público independiente de sólo releases, de modo que electron-updater funciona sin credenciales; el código permanece en un repositorio privado."),
           P("10. Seguridad y privacidad", "h1"),
           *bullets(["Sin telemetría. La única conexión saliente es la comprobación de actualizaciones contra GitHub Releases.",
                     "Electron con contextIsolation, sandbox y sin nodeIntegration; el preload expone sólo dos funciones de actualización.",
                     "Los datos (SQLite) residen en %APPDATA%\\rf-engineering-workbench."]),
           P("11. Historial de versiones", "h1"),
           table(changelog() or [["—", "—", "Sin etiquetas"]], header=["Versión", "Fecha", "Cambios"], widths=[22, 26, 122]),
           P("12. Limitaciones y hoja de ruta", "h1"),
           *bullets(["Drivers de VNA pendientes de verificación con instrumentos físicos.", "Instalador sin firma digital de código.",
                     "Radiación de antenas sólo para geometrías de hilo canónicas (sin simulación numérica MoM/FDTD)."]),
           P("13. Autoría", "h1"),
           P(f"Proyecto de <b>{AUTHOR}</b> (GitHub: {GITHUB}). Licencia: pendiente de definir por el autor."),
           ]
    doc.multiBuild(st)


if __name__ == "__main__":
    build(sys.argv[1])
