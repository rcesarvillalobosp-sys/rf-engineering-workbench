"""Modelos de estándares de calibración (convención de definición de kits de los VNA comerciales).

Cada estándar = línea de offset (Z0_off, retardo τ, pérdidas en GΩ/s) + terminación:
  Open : C(f) = C0 + C1·f + C2·f² + C3·f³   (C0 en fF, C1 en 1e-27 F/Hz, C2 en 1e-36 F/Hz², C3 en 1e-45 F/Hz³)
  Short: L(f) = L0 + L1·f + L2·f² + L3·f³   (L0 en pH, L1 en 1e-24 H/Hz, L2 en 1e-33 H/Hz², L3 en 1e-42 H/Hz³)
  Load : impedancia fija (por defecto Z0 del sistema)
  Thru : línea de offset de 2 puertos.

Línea de offset con pérdidas (modelo estándar de definición de kits):
  α·l = (pérdida·τ)/(2·Z0_off) · √(f/1 GHz)          [Np]
  β·l = 2π·f·τ + α·l                                    [rad]
  Zc  = Z0_off + (1 − j)·(pérdida/(4π·f))·√(f/1 GHz)
No se incluyen coeficientes de kits comerciales: deben copiarse de la documentación del kit que se use.
"""
from __future__ import annotations

import numpy as np

from .units import RFInputError

IDEAL = {"open": {}, "short": {}, "load": {}, "thru": {}}


def _offset(f: np.ndarray, p: dict):
    z0o = float(p.get("offset_z0", 50.0))
    tau = float(p.get("offset_delay", 0.0))       # s
    loss = float(p.get("offset_loss", 0.0))       # Ω/s (GΩ/s × 1e9)
    if z0o <= 0 or tau < 0 or loss < 0:
        raise RFInputError("Kit: Z0 de offset > 0, retardo ≥ 0 y pérdidas ≥ 0.")
    if np.any(f <= 0):
        raise RFInputError("Kit: las frecuencias deben ser positivas.")
    root = np.sqrt(f / 1e9)
    al = loss * tau / (2 * z0o) * root
    bl = 2 * np.pi * f * tau + al
    zc = z0o + (1 - 1j) * (loss / (4 * np.pi * f)) * root
    return zc, al + 1j * bl


def _terminal_z(kind: str, f: np.ndarray, p: dict, z0: float) -> np.ndarray:
    w = 2 * np.pi * f
    if kind == "open":
        c = (p.get("C0", 0) * 1e-15 + p.get("C1", 0) * 1e-27 * f + p.get("C2", 0) * 1e-36 * f ** 2
             + p.get("C3", 0) * 1e-45 * f ** 3)
        c = np.asarray(c, dtype=float) * np.ones_like(f)
        with np.errstate(divide="ignore"):
            return np.where(c > 0, 1 / (1j * w * np.where(c > 0, c, 1)), np.inf + 0j)
    if kind == "short":
        L = (p.get("L0", 0) * 1e-12 + p.get("L1", 0) * 1e-24 * f + p.get("L2", 0) * 1e-33 * f ** 2
             + p.get("L3", 0) * 1e-42 * f ** 3)
        return 1j * w * np.asarray(L, dtype=float) * np.ones_like(f)
    if kind == "load":
        r = complex(p.get("load_r", z0), p.get("load_x", 0.0))
        return np.full(f.shape, r)
    raise RFInputError(f"Estándar desconocido: {kind}")


def standard_gamma(kind: str, f, p: dict | None, z0: float = 50.0) -> np.ndarray:
    """Γ real del estándar de reflexión (open/short/load) referido a Z0 del sistema."""
    f = np.atleast_1d(np.asarray(f, dtype=float))
    p = p or {}
    zt = _terminal_z(kind, f, p, z0)
    zc, gl = _offset(f, p)
    t = np.tanh(gl)
    with np.errstate(divide="ignore", invalid="ignore"):
        zin = np.where(np.isinf(zt), zc / np.where(t == 0, 1e-300, t), zc * (zt + zc * t) / (zc + zt * t))
        g = np.where(np.isinf(zin), 1 + 0j, (zin - z0) / (zin + z0))
    return g


def thru_s(f, p: dict | None, z0: float = 50.0) -> np.ndarray:
    """S (N,2,2) del thru definido como línea de offset."""
    from .network import abcd_to_s
    f = np.atleast_1d(np.asarray(f, dtype=float))
    p = p or {}
    zc, gl = _offset(f, p)
    abcd = np.empty((f.size, 2, 2), dtype=complex)
    abcd[:, 0, 0] = np.cosh(gl)
    abcd[:, 0, 1] = zc * np.sinh(gl)
    abcd[:, 1, 0] = np.sinh(gl) / zc
    abcd[:, 1, 1] = np.cosh(gl)
    return abcd_to_s(abcd, z0)


def is_ideal(kit: dict | None) -> bool:
    if not kit:
        return True
    return all(not any(abs(float(v)) > 0 for k, v in (kit.get(s) or {}).items() if k not in ("offset_z0", "load_r"))
               and float((kit.get(s) or {}).get("load_r", 50) or 50) == 50 for s in ("open", "short", "load", "thru"))


def describe(kit: dict | None) -> str:
    return "Estándares ideales" if is_ideal(kit) else "Kit definido por el usuario (offset + C(f)/L(f) + carga)"


