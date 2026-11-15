"""Parámetros S en modo mixto (diferencial / común) a partir de S de terminación simple.

Para cada par (p, n) — p = terminal positivo, n = negativo:
    a_d = (a_p − a_n)/√2      a_c = (a_p + a_n)/√2
    Smm = M · S · Mᵀ   (M ortonormal)
Referencias resultantes con Z0 real común: Z_dif = 2·Z0, Z_común = Z0/2.
Orden de salida: [D1 … Dk, C1 … Ck, S(puertos sin pareja)].
"""
from __future__ import annotations

import numpy as np

from .units import RFInputError


def mm_matrix(nports: int, pairs: list[tuple[int, int]]) -> tuple[np.ndarray, list[str]]:
    used = [p for pr in pairs for p in pr]
    if not pairs:
        raise RFInputError("Defina al menos un par diferencial.")
    if len(set(used)) != len(used) or any(not (1 <= p <= nports) for p in used):
        raise RFInputError(f"Pares no válidos para {nports} puertos: cada puerto sólo puede pertenecer a un par.")
    singles = [p for p in range(1, nports + 1) if p not in used]
    m = np.zeros((nports, nports))
    labels = []
    r = 0
    for k, (p, n) in enumerate(pairs, start=1):
        m[r, p - 1], m[r, n - 1] = 1 / np.sqrt(2), -1 / np.sqrt(2)
        labels.append(f"D{k}")
        r += 1
    for k, (p, n) in enumerate(pairs, start=1):
        m[r, p - 1], m[r, n - 1] = 1 / np.sqrt(2), 1 / np.sqrt(2)
        labels.append(f"C{k}")
        r += 1
    for p in singles:
        m[r, p - 1] = 1
        labels.append(f"S{p}")
        r += 1
    return m, labels


def se_to_mixed(s: np.ndarray, pairs: list[tuple[int, int]]) -> dict:
    s = np.asarray(s, dtype=complex)
    n = s.shape[1]
    m, labels = mm_matrix(n, pairs)
    smm = m @ s @ m.T
    k = len(pairs)
    blocks = {"dd": smm[:, :k, :k], "dc": smm[:, :k, k:2 * k], "cd": smm[:, k:2 * k, :k], "cc": smm[:, k:2 * k, k:2 * k]}
    return {"s": smm, "labels": labels, "blocks": blocks, "npairs": k}


def mixed_to_se(smm: np.ndarray, nports: int, pairs: list[tuple[int, int]]) -> np.ndarray:
    m, _ = mm_matrix(nports, pairs)
    return m.T @ np.asarray(smm, dtype=complex) @ m
