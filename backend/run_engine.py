"""Punto de entrada del motor RF empaquetado (PyInstaller).

Uso: rfwb-engine --port 51234 [--host 127.0.0.1]
Variables de entorno: RFWB_DATA_DIR (base SQLite), RFWB_UI_DIST (interfaz compilada).
"""
import argparse
import multiprocessing

import uvicorn


def main() -> None:
    p = argparse.ArgumentParser(description="RF Engineering Workbench — motor de cálculo")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=47615)
    a = p.parse_args()
    from rfwb.main import app  # import directo: PyInstaller no resuelve la cadena "rfwb.main:app"
    uvicorn.run(app, host=a.host, port=a.port, log_level="warning")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
