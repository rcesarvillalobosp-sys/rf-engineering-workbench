"""Utilidades comunes de la API: serialización JSON segura y parseo de entradas."""
from __future__ import annotations

import math
from typing import Any

import numpy as np
from pydantic import BaseModel

from ..engine.steps import Trace
from ..engine.units import RFInputError, parse_complex, parse_quantity


def _num(v: float):
    if v is None:
        return None
    v = float(v)
    if math.isnan(v):
        return None
    if math.isinf(v):
        return "inf" if v > 0 else "-inf"
    return v


def J(obj: Any) -> Any:
    """Convierte resultados del motor (complejos, ndarray, Trace, inf) a JSON."""
    if isinstance(obj, Trace):
        return obj.to_list()
    if isinstance(obj, dict):
        return {str(k): J(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [J(v) for v in obj]
    if isinstance(obj, np.ndarray):
        if np.iscomplexobj(obj):
            re_, im_ = np.real(obj).astype(float), np.imag(obj).astype(float)
            bad = ~(np.isfinite(re_) & np.isfinite(im_))
            return {"re": _tolist(np.where(bad, np.nan, re_)), "im": _tolist(np.where(bad, np.nan, im_))}
        if obj.dtype == bool:
            return obj.tolist()
        return _tolist(obj.astype(float))
    if isinstance(obj, (complex, np.complexfloating)):
        z = complex(obj)
        if not (math.isfinite(z.real) and math.isfinite(z.imag)):
            return {"re": None, "im": None, "inf": True}
        return {"re": z.real, "im": z.imag}
    if isinstance(obj, (bool, np.bool_)):
        return bool(obj)
    if isinstance(obj, (int, np.integer)):
        return int(obj)
    if isinstance(obj, (float, np.floating)):
        return _num(obj)
    return obj


def _tolist(a: np.ndarray):
    o = a.astype(object)
    o[~np.isfinite(a)] = None
    return o.tolist()


def cplx(v: Any, name: str = "Impedancia") -> complex:
    if isinstance(v, dict):
        if v.get("inf"):
            return complex(math.inf, 0)
        return complex(float(v["re"]), float(v["im"]))
    try:
        return parse_complex(v)
    except RFInputError as e:
        raise RFInputError(f"{name}: {e}") from None


def qty(v: Any, name: str = "Valor") -> float:
    try:
        return float(v) if isinstance(v, (int, float)) else parse_quantity(v)
    except RFInputError as e:
        raise RFInputError(f"{name}: {e}") from None


class Model(BaseModel):
    model_config = {"extra": "ignore"}
