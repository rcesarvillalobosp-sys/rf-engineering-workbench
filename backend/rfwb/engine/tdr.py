"""Dominio del tiempo (TDR) a partir de S11(f).

Low-pass: requiere una rejilla armónica f_n = n·Δf (se extrapola DC). Da respuesta al escalón → Z(t).
Band-pass: cualquier rejilla uniforme; sólo magnitud de la respuesta al impulso (localización de discontinuidades).
Resolución ≈ vf·c / (2·Δf_span). Alcance sin aliasing = vf·c / (2·Δf).
"""
from __future__ import annotations

import numpy as np

from .units import C0, RFInputError


def _uniform(f, x):
    f = np.asarray(f, dtype=float)
    x = np.asarray(x, dtype=complex)
    df = np.diff(f)
    if np.allclose(df, df.mean(), rtol=1e-4):
        return f, x, False
    fu = np.linspace(f[0], f[-1], len(f))
    xu = np.interp(fu, f, x.real) + 1j * np.interp(fu, f, x.imag)
    return fu, xu, True


def _window(n, kind, beta):
    if kind == "none":
        return np.ones(n)
    if kind == "hann":
        return np.hanning(2 * n + 1)[n:-1] / np.hanning(2 * n + 1)[n]
    return np.kaiser(2 * n - 1, beta)[n - 1:]


def tdr(f, s11, z0=50.0, vf=1.0, mode="lowpass", window="kaiser", beta=6.0, pad=8) -> dict:
    f = np.asarray(f, dtype=float)
    if f.size < 16:
        raise RFInputError("Se necesitan al menos 16 puntos de frecuencia para TDR.")
    fu, x, resampled = _uniform(f, s11)
    df = fu[1] - fu[0]
    warnings = []
    if resampled:
        warnings.append("Rejilla no uniforme: se interpoló a paso constante.")
    if mode == "lowpass":
        k = fu[0] / df
        if k > 10.5:
            raise RFInputError("Low-pass requiere datos que empiecen cerca de DC (f_inicial ≤ 10·Δf). Use modo band-pass.")
        if abs(k - round(k)) > 1e-6 or round(k) < 1:
            # Re-muestreo a una rejilla armónica exacta f_n = n·Δf' dentro del rango medido
            n_hi = int(np.floor(fu[-1] / df))
            df = fu[-1] / n_hi
            n_lo = int(np.ceil(fu[0] / df - 1e-9))
            fh = np.arange(n_lo, n_hi + 1) * df
            x = np.interp(fh, fu, x.real) + 1j * np.interp(fh, fu, x.imag)
            fu = fh
            k = n_lo
            warnings.append("Rejilla no armónica: se re-muestreó a f_n = n·Δf por interpolación lineal.")
        k = int(round(k))
        # Extrapolación de DC (real) y relleno de armónicos faltantes por interpolación lineal
        # DC: extrapolación lineal de |S| y de la fase desenrollada (primeros puntos) hasta f = 0
        m = min(6, x.size)
        idx = np.arange(m) + k
        pm = np.polyfit(idx, np.abs(x[:m]), 1)
        pp = np.polyfit(idx, np.unwrap(np.angle(x[:m])), 1)
        dc = float(np.polyval(pm, 0) * np.cos(np.polyval(pp, 0)))
        if k > 1:
            warnings.append(f"Faltan {k - 1} armónicos bajos: se interpolaron desde DC.")
        lo = np.linspace(dc, x[0], k + 1)[:-1]
        spec = np.concatenate([[dc], lo[1:], x])
        n = spec.size
        w = _window(n, window, beta)
        nfft = int(2 ** np.ceil(np.log2(2 * n * pad)))
        h = np.fft.irfft(spec * w, n=nfft)
        dt = 1 / (nfft * df)
        # El pulso en t = 0 (ensanchado por la ventana) tiene una mitad en t < 0, que la FFT coloca al final
        # del periodo. Se centra el eje temporal (−T/2 … T/2) ANTES de integrar para no perder esa mitad.
        h = np.roll(h, nfft // 2)
        t = (np.arange(nfft) - nfft // 2) * dt
        step = np.cumsum(h)
        t_res = 1 / (2 * (fu[-1]))  # ≈ resolución temporal (ida y vuelta)
        keep = (t >= -4 * t_res) & (t <= 1 / (2 * df))
        t, h, step = t[keep], h[keep], step[keep]
        rho = np.clip(step, -0.999999, 0.999999)
        z = z0 * (1 + rho) / (1 - rho)
        out = {"t": t, "impulse": h, "step": step, "z": z}
    elif mode == "bandpass":
        n = x.size
        w = np.kaiser(n, beta) if window == "kaiser" else (np.hanning(n) if window == "hann" else np.ones(n))
        nfft = int(2 ** np.ceil(np.log2(n * pad)))
        h = np.fft.ifft(x * w, n=nfft) * nfft / np.sum(w)
        dt = 1 / (nfft * df)
        t = np.arange(nfft) * dt
        keep = t <= 1 / df
        out = {"t": t[keep], "impulse_mag": np.abs(h[keep]), "impulse_db": 20 * np.log10(np.abs(h[keep]) + 1e-15)}
    else:
        raise RFInputError("Modo TDR desconocido (lowpass | bandpass).")
    span = fu[-1] - (0 if mode == "lowpass" else fu[0])
    out["distance"] = out["t"] * vf * C0 / 2
    out["resolution_m"] = vf * C0 / (2 * span)
    out["range_m"] = vf * C0 / (2 * df)
    out["warnings"] = warnings
    return out
