"""Líneas de transmisión y adaptación: ejemplos de Pozar (Microwave Engineering, 4ª ed.) y scikit-rf."""
import cmath
import math

import numpy as np
import pytest
import skrf

from rfwb.engine import matching as mt
from rfwb.engine import tline as tl
from rfwb.engine.network import cascade_abcd, abcd_to_s, zin_cascade
from rfwb.engine.units import C0, RFInputError


def lam(f, vf=1.0):
    return vf * C0 / f


# ── Líneas ──
def test_quarter_wave_inverts():
    f = 1e9
    r = tl.analyze_line(50, f, lam(f) / 4, load="arbitrary", zl=100 + 0j)
    assert r["zin"] == pytest.approx(25 + 0j, abs=1e-6)


def test_half_wave_repeats():
    r = tl.analyze_line(50, 1e9, lam(1e9) / 2, zl=30 - 20j)
    assert r["zin"] == pytest.approx(30 - 20j, abs=1e-6)


def test_short_and_open_eighth_wave():
    s = tl.analyze_line(50, 1e9, lam(1e9) / 8, load="short")
    o = tl.analyze_line(50, 1e9, lam(1e9) / 8, load="open")
    assert s["zin"] == pytest.approx(50j, abs=1e-6)
    assert o["zin"] == pytest.approx(-50j, abs=1e-6)


def test_matched_line():
    r = tl.analyze_line(75, 433e6, 3.7, vf=0.66, load="matched", atten_db_per_m=0.2)
    assert r["zin"] == pytest.approx(75 + 0j, abs=1e-9)
    assert r["vswr_in"] == pytest.approx(1.0)


def test_lossy_line_vs_skrf():
    f, z0, vf, a_db, length, zl = 1e9, 50.0, 0.7, 0.5, 2.3, 20 + 35j
    r = tl.analyze_line(z0, f, length, vf=vf, atten_db_per_m=a_db, zl=zl)
    freq = skrf.Frequency(f, f, 1, unit="Hz")
    alpha = a_db / (20 / math.log(10))
    beta = 2 * math.pi * f / (vf * C0)
    media = skrf.media.DefinedGammaZ0(freq, z0=z0, gamma=alpha + 1j * beta)
    ntw = media.line(length, unit="m") ** media.load(complex(skrf.network.z2s(np.array([[[zl]]]), z0)[0, 0, 0]))
    assert r["zin"] == pytest.approx(complex(ntw.z[0, 0, 0]), rel=1e-9)
    # pérdidas: |Γin| = |ΓL|·e^{-2αℓ}
    assert abs(r["gamma_in"]) == pytest.approx(abs(r["gamma_load"]) * math.exp(-2 * alpha * length))
    # balance de potencia consistente
    assert r["p_reflected"] + r["p_load"] + r["p_line_loss"] == pytest.approx(r["p_inc"])


def test_coax_geometry_rg58_like():
    g = tl.line_from_geometry("coax", D=2.95e-3, d=0.9e-3, er=2.25)
    assert g["z0"] == pytest.approx(60 / 1.5 * math.log(2.95 / 0.9))
    assert g["vf"] == pytest.approx(1 / 1.5)


def test_microstrip_fr4_50_ohm():
    # FR4 εr=4.4, h=1.6 mm: W≈3.06 mm da ~50 Ω (valor de referencia de calculadoras estándar)
    g = tl.line_from_geometry("microstrip", W=3.06e-3, h=1.6e-3, er=4.4)
    assert g["z0"] == pytest.approx(50, abs=1.0)
    assert 3.2 < g["eps_eff"] < 3.5


def test_abcd_line_vs_skrf():
    f = np.linspace(0.5e9, 2e9, 7)
    el = {"kind": "line", "z0": 50, "length_m": 0.1, "vf": 1.0}
    s = abcd_to_s(cascade_abcd(f, [el]), 50)
    media = skrf.media.DefinedGammaZ0(skrf.Frequency.from_f(f, unit="Hz"), z0=50, gamma=2j * np.pi * f / C0)
    ref = media.line(0.1, unit="m").s
    assert np.allclose(s, ref, atol=1e-12)


# ── Adaptación ──
def _assert_matched(res, tol=1e-6):
    assert res["solutions"], "sin soluciones"
    for s in res["solutions"]:
        assert abs(s["gamma_after"]) < tol
        assert s["vswr_after"] == pytest.approx(1.0, abs=1e-5)


def test_pozar_example_5_1_l_network():
    """ZL = 200 − j100 Ω, Z0 = 100 Ω, f = 500 MHz.
    Sol. 1: C paralelo 0.92 pF, L serie 38.8 nH ; Sol. 2: L paralelo 46.1 nH, C serie 2.61 pF."""
    res = mt.design("L", 200 - 100j, 100 + 0j, 500e6, z0=100)
    _assert_matched(res)
    combos = []
    for s in res["solutions"]:
        combos.append({(e["kind"], e["part"]): e["value"] for e in s["elements"]})
    sol1 = next(c for c in combos if ("shunt", "C") in c and ("series", "L") in c)
    sol2 = next(c for c in combos if ("shunt", "L") in c and ("series", "C") in c)
    assert sol1[("shunt", "C")] == pytest.approx(0.92e-12, rel=0.01)
    assert sol1[("series", "L")] == pytest.approx(38.8e-9, rel=0.01)
    assert sol2[("shunt", "L")] == pytest.approx(46.1e-9, rel=0.01)
    assert sol2[("series", "C")] == pytest.approx(2.61e-12, rel=0.01)


@pytest.mark.parametrize("zl", [100 + 50j, 10 - 5j, 25 + 0j, 300 - 200j, 50 + 80j])
@pytest.mark.parametrize("zs", [50 + 0j, 25 + 10j])
def test_l_network_general(zl, zs):
    _assert_matched(mt.design("L", zl, zs, 1e9))


@pytest.mark.parametrize("method", ["PI", "T"])
def test_pi_t(method):
    res = mt.design(method, 10 + 5j, 50 + 0j, 145e6, q_net=5)
    _assert_matched(res)
    assert all(len(s["elements"]) == 3 for s in res["solutions"])


def test_pi_q_too_low():
    with pytest.raises(RFInputError):
        mt.design("PI", 10 + 0j, 50 + 0j, 145e6, q_net=1)


def test_quarter_wave_real_and_complex():
    r = mt.design("QWT", 100 + 0j, 50 + 0j, 1e9)
    _assert_matched(r)
    assert r["solutions"][0]["z1"] == pytest.approx(math.sqrt(5000))
    _assert_matched(mt.design("QWT", 60 - 80j, 50 + 0j, 1e9))


def test_pozar_example_5_2_single_stub():
    """ZL = 60 − j80 Ω, Z0 = 50 Ω, 2 GHz: d1 = 0.110λ, ℓ1 = 0.095λ ; d2 = 0.260λ, ℓ2 = 0.405λ (stub en corto).
    Con stub abierto: d1 = 0.110λ → ℓ = 0.345λ ; d2 = 0.260λ → ℓ = 0.155λ."""
    res = mt.design("STUB1", 60 - 80j, 50 + 0j, 2e9, z0=50, stub="short")
    _assert_matched(res)
    got = sorted((round(s["d_lambda"], 3), round(s["l_lambda"], 3)) for s in res["solutions"])
    assert got[0][0] == pytest.approx(0.110, abs=0.002) and got[0][1] == pytest.approx(0.095, abs=0.002)
    assert got[1][0] == pytest.approx(0.260, abs=0.002) and got[1][1] == pytest.approx(0.405, abs=0.002)


def test_single_stub_open():
    res = mt.design("STUB1", 60 - 80j, 50 + 0j, 2e9, stub="open")
    _assert_matched(res)
    got = sorted((round(s["d_lambda"], 3), round(s["l_lambda"], 3)) for s in res["solutions"])
    assert got == [pytest.approx((0.110, 0.345), abs=0.002), pytest.approx((0.260, 0.155), abs=0.002)]


def test_pozar_example_5_4_double_stub():
    """ZL = 60 − j80 Ω, 2 GHz, stubs abiertos, separación λ/8, primer stub en la carga:
    ℓ1 = 0.146λ, ℓ2 = 0.204λ  y  ℓ1 = 0.482λ, ℓ2 = 0.350λ."""
    res = mt.design("STUB2", 60 - 80j, 50 + 0j, 2e9, stub="open", d1_lambda=0.0, spacing_lambda=0.125)
    _assert_matched(res)
    got = sorted((round(s["l1_lambda"], 3), round(s["l2_lambda"], 3)) for s in res["solutions"])
    assert got[0] == pytest.approx((0.146, 0.204), abs=0.002)
    assert got[1] == pytest.approx((0.482, 0.350), abs=0.002)


def test_matching_is_narrowband():
    res = mt.design("L", 10 - 30j, 50 + 0j, 1e9, vswr_target=2.0, span=0.5)
    s = res["solutions"][0]
    bw = s["bandwidth"]
    assert bw is not None and 0 < bw["fractional"] < 1
    v = s["sweep"]["vswr"]
    assert v[0] > 1.5 and v[-1] > 1.5  # fuera de f0 se desadapta


def test_bode_fano():
    bf = mt.bode_fano(50 - 100j, 1e9, 2.0)
    assert bf["q_load"] == pytest.approx(2.0)
    assert bf["max_fractional_bw"] == pytest.approx(math.pi / (2 * math.log(3)))


def test_lossless_transducer_gain_unity():
    res = mt.design("L", 100 + 50j, 50 + 0j, 1e9)
    assert res["solutions"][0]["transducer_gain_db_f0"] == pytest.approx(0, abs=1e-9)


def test_finite_q_reduces_gain():
    res = mt.design("L", 10 + 0j, 50 + 0j, 1e9, comp_q=30)
    assert res["solutions"][0]["transducer_gain_db_f0"] < -0.05


def test_e_series_snap():
    assert mt.nearest_e_value(4.6e-9, "E12") == pytest.approx(4.7e-9)
    assert mt.nearest_e_value(9.6e-12, "E24") == pytest.approx(9.1e-12) or mt.nearest_e_value(9.6e-12, "E24") == pytest.approx(10e-12)
