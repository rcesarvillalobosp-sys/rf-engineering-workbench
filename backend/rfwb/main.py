"""Aplicación FastAPI: motor RF + API + servidor estático del frontend compilado."""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .api import routes_data, routes_rf, routes_sys
from .engine.units import RFInputError
from .vna.base import VNAError

VERSION = "1.0.0"

app = FastAPI(title="RF Engineering Workbench API", version=VERSION)
app.add_middleware(CORSMiddleware, allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
                   allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(RFInputError)
async def rf_error(_: Request, exc: RFInputError):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(VNAError)
async def vna_error(_: Request, exc: VNAError):
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(ValueError)
async def value_error(_: Request, exc: ValueError):
    return JSONResponse(status_code=422, content={"detail": f"Valor no válido: {exc}"})


@app.exception_handler(ZeroDivisionError)
async def zero_div(_: Request, exc: ZeroDivisionError):
    return JSONResponse(status_code=422, content={"detail": "División por cero: revise los valores (¿componente nulo?)."})


@app.get("/api/health")
def health():
    import numpy, scipy, skrf
    return {"status": "ok", "version": VERSION, "numpy": numpy.__version__, "scipy": scipy.__version__,
            "skrf": skrf.__version__}


app.include_router(routes_rf.router)
app.include_router(routes_data.router)
app.include_router(routes_sys.router)

_dist = Path(os.environ.get("RFWB_UI_DIST") or Path(__file__).resolve().parents[2] / "frontend" / "dist")
if _dist.is_dir():
    app.mount("/", StaticFiles(directory=_dist, html=True), name="ui")
