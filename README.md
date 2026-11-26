# RF Engineering Workbench

**Documento de presentación (PDF):** [docs/Presentacion-RF-Engineering-Workbench.pdf](docs/Presentacion-RF-Engineering-Workbench.pdf)

Plataforma de escritorio para análisis, simulación y diseño de sistemas de radiofrecuencia: carta de Smith, impedancias,
adaptación, líneas de transmisión, parámetros S, antenas, Touchstone, preparación para VNA e informes técnicos.

Funciona **sin instrumento**: todos los resultados proceden del motor matemático, de modelos o de archivos importados,
y cada dato indica su origen (calculado · simulado · importado · medido · derivado).

Documentación técnica completa (arquitectura, API, validación, publicación): [`docs/RF_Engineering_Workbench_Documentacion_Tecnica.pdf`](docs/RF_Engineering_Workbench_Documentacion_Tecnica.pdf). Se regenera con `docs/build_docs.ps1`.

## Requisitos

- Windows 10/11 (también funciona en Linux/macOS desde el código fuente)
- Python 3.11+ (probado con 3.13)
- Node.js 20+ (probado con 26)

## Instalación (una vez)

```powershell
python -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
npm install
npm --prefix frontend install
```

> **Electron con Node 26.** El extractor de zip que usa el instalador de Electron se detiene tras la primera entrada en
> Node muy recientes y deja `node_modules/electron/dist` incompleto. Si `npm run app` dice que Electron no está instalado,
> extraiga a mano el zip oficial que ya está en caché (`%LOCALAPPDATA%\electron\Cache\…\electron-v33.2.0-win32-x64.zip`,
> verificando su SHA-256 contra `node_modules/electron/checksums.json`) en `node_modules/electron/dist` y cree
> `node_modules/electron/path.txt` con el contenido `electron.exe`.

## Ejecución

| Comando | Qué hace |
|---|---|
| `npm start` | Compila la interfaz y abre la aplicación de escritorio |
| `npm run app` | Abre la aplicación (interfaz ya compilada) |
| `npm run dev` | Desarrollo: Vite con recarga en caliente + Electron (motor en el puerto 47615) |
| `npm run test:engine` | Batería de validación del motor (165 pruebas) |

## Instalador de Windows

```powershell
backend\.venv\Scripts\python.exe -m pip install pyinstaller
npm run dist
```

`npm run dist` compila la interfaz, compila el motor con PyInstaller (`scripts/build_engine.ps1`, que ejecuta después
`scripts/smoke_engine.ps1` contra el ejecutable) y genera `release/RF-Engineering-Workbench-Setup-1.0.0.exe` con
electron-builder (NSIS, por usuario, carpeta elegible, accesos directos). El equipo de destino **no necesita Python ni Node**.

- El instalador no está firmado digitalmente: Windows SmartScreen mostrará «Editor desconocido» la primera vez.
- Si electron-builder falla con «Cannot create symbolic link» al extraer `winCodeSign`, extraiga ese `.7z` de la caché
  (`%LOCALAPPDATA%\electron-builder\Cache\winCodeSign`) en la subcarpeta `winCodeSign-2.6.0` excluyendo
  `libcrypto.dylib` y `libssl.dylib` (enlaces de macOS que no se usan en Windows), o active el Modo de desarrollador.

## Versiones y actualizaciones automáticas

- Código: repositorio **privado** `rcesarvillalobosp-sys/rf-engineering-workbench`.
- Instaladores: repositorio **público** `rcesarvillalobosp-sys/rf-engineering-workbench-releases` (sólo Releases;
  así la aplicación se actualiza sin incrustar ningún token).
- La app instalada comprueba al arrancar si hay una versión nueva y **pregunta** antes de descargar y antes de instalar.
  También hay un botón «Buscar actualizaciones» en el Dashboard. Registro: `%APPDATA%\rf-engineering-workbench\updater.log`.

Publicar una versión nueva (requiere GitHub CLI con sesión iniciada):

```powershell
npm version patch --no-git-tag-version
git commit -am "Versión X.Y.Z"
npm run release
```

`scripts/release.ps1` se niega a publicar con cambios sin confirmar, fuera de `main` o si la versión ya existe; ejecuta
las pruebas, compila todo, sube el instalador y `latest.yml` a las Releases públicas y etiqueta la versión en el repo de código.

Electron arranca el motor Python en un puerto libre asignado por el sistema y lo detiene al cerrar.
Los datos (biblioteca, mediciones, proyectos) se guardan en SQLite en `%APPDATA%\rf-engineering-workbench\data`.

## Arquitectura

```
backend/rfwb/
  engine/        Motor matemático puro (sin interfaz): units, reflection, impedance, network (ABCD),
                 tline, matching, sparams, stability, antenna, tdr, tolerance, calibration, selftest
  io/            Touchstone v1/v2 (lector propio contrastado con scikit-rf, escritor RI/MA/DB)
  library/       Contenido genérico inicial de la biblioteca
  vna/           Drivers: NanoVNA (serie), LibreVNA (SCPI/TCP), SCPI genérico (VISA) + gestor
  reports/       PDF (reportlab + matplotlib, fuentes DejaVu con Γ Ω ∠) y CSV
  api/           FastAPI: rutas por módulo; serialización segura de complejos e infinitos
  db.py, datasets.py
frontend/src/    React + TypeScript + Tailwind + Motion + Plotly; carta de Smith en SVG
electron/        Proceso principal (arranque/parada del motor)
```

Todas las fórmulas de ingeniería viven en `backend/rfwb/engine`. El frontend sólo contiene la geometría de dibujo de
la carta de Smith (`frontend/src/lib/smith.ts`), usada para pintar la rejilla y para la lectura instantánea del cursor.

### Convenciones

- Dependencia temporal e^{+jωt}: X_L = +ωL (mitad superior de la carta), X_C = −1/(ωC).
- Γ = (Z − Z0)/(Z + Z0) con Z0 real; con fuente compleja se usa la onda de potencia Γ = (ZL − Zs*)/(ZL + Zs).
- Return Loss positivo (RL = −20·log10|Γ|); |S11| dB = −RL.
- Líneas: d se mide desde la carga hacia el generador.
- Las entradas aceptan prefijos SI: `10n`, `4.7p`, `433MHz`, `2.4G`.

## Validación

`backend/tests` (165 pruebas) cubre: cargas resistivas, inductivas, capacitivas, abiertas y en cortocircuito; Γ, VSWR,
RL y mismatch loss; circuitos RLC; transformación por líneas (λ/4, λ/2, λ/8, con pérdidas vs scikit-rf); microstrip;
redes L (ejemplo 5.1 de Pozar), Pi, T, λ/4, stub simple (ej. 5.2) y doble stub (ej. 5.4); límite de Bode–Fano; conversión
S↔Z/ABCD vs scikit-rf; estabilidad K vs scikit-rf; círculos de estabilidad; Touchstone 1–4 puertos (RI/MA/DB, Z normalizada,
v2, orden 12_21, ruido, errores) vs scikit-rf; TDR; calibración SOL vs scikit-rf y SOLT de 2 puertos con cajas de error aleatorias; parámetros H/G (Frickey vs scikit-rf y casos analíticos); microstrip dispersiva con pérdidas; atenuación de cables escalada; kits de calibración no ideales (SOL y SOLT recuperan el DUT); modo mixto vs scikit-rf `se2gmm`; antenas de hilo frente a Balanis (dipolo λ/2: 73.08 + j42.5 Ω y 2.15 dBi; monopolo λ/4: 36.54 + j21.26 Ω y 5.16 dBi; dipolo corto D = 1.5); antenas; Monte Carlo; y la API completa.
El Dashboard incluye una autoverificación ejecutable desde la aplicación.

## Limitaciones conocidas / pendiente

- **Drivers VNA sin verificar con hardware real.** Siguen la documentación pública de cada fabricante; nunca se simula una
  conexión. El barrido continuo y la calibración SOL/SOLT están implementados y probados sin instrumento (con datos
  sintéticos y un driver de prueba que sólo existe en los tests).
- **Kits de calibración:** se admite la definición completa (offset, C(f), L(f), carga), pero no se incluyen coeficientes de kits comerciales: deben copiarse de su documentación.
- **Antenas:** la radiación (diagrama, directividad, eficiencia, ganancia) sólo se calcula para dipolos y monopolos delgados con un modelo analítico (corriente sinusoidal, plano de masa infinito). Otras geometrías requieren medidas o simulación EM numérica (MoM/FDTD/FEM).
- **Biblioteca:** sin datos de fabricantes precargados; la atenuación de cada cable se introduce desde su hoja de datos
  y se escala con √f (pérdidas de conductor; las dieléctricas, ∝ f, se desprecian).
- **Touchstone:** los archivos con `[Mixed-Mode Order]` se conservan en modo mixto (no se reconvierten a terminación simple). Para Y/H/G en v1 se omite el contraste con scikit-rf 2.2, que desnormaliza
  multiplicando todos los elementos por R (sólo correcto para Z); la lectura propia se valida con casos analíticos.
- **Distribución:** instalador NSIS sin firma de código y sin auto-actualización.
