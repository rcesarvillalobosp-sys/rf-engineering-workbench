"""Validación del motor: casos analíticos conocidos y contraste con scikit-rf."""
import cmath
import math

import numpy as np
import pytest
import skrf

from rfwb.engine import impedance as imp
from rfwb.engine import reflection as rf
from rfwb.engine.units import RFInputError, parse_complex, parse_quantity


# ── Parseo y unidades ──
@pytest.mark.parametrize("txt,val", [
    ("80+j30", 80 + 30j), ("80 - j30 Ω", 80 - 30j), ("j25", 25j), ("-j10", -10j), ("50", 50),
    ("30-12j", 30 - 12j), ("1e2+j1e1", 100 + 10j), ("0.5-j0.25", 0.5 - 0.25j), ("-20+j5", -20 + 5j),
])
def test_parse_complex(txt, val):
    assert parse_complex(txt) == pytest.approx(val)


def test_parse_complex_polar():
    assert parse_complex("100∠90") == pytest.approx(100j, abs=1e-9)


@pytest.mark.parametrize("bad", ["abc", "80+j", "++3", ""])
def test_parse_complex_invalid(bad):
    with pytest.raises(RFInputError):
        parse_complex(bad)


@pytest.mark.parametrize("txt,val", [("10nH", 1e-8), ("4.7p", 4.7e-12), ("2.4 GHz", 2.4e9), ("100k", 1e5), ("33u", 33e-6)])
def test_parse_quantity(txt, val):
    assert parse_quantity(txt) == pytest.approx(val)


# ── Reflexión ──
def test_matched_load():
    m = rf.reflection_metrics(50 + 0j, 50)
    assert m["gamma"] == 0 and m["vswr"] == 1 and math.isinf(m["return_loss_db"])


def test_resistive_100_ohm():
    m = rf.reflection_metrics(100 + 0j, 50)
    assert m["gamma"] == pytest.approx(1 / 3)
    assert m["vswr"] == pytest.approx(2.0)
    assert m["return_loss_db"] == pytest.approx(9.5424, abs=1e-4)
    assert m["mismatch_loss_db"] == pytest.approx(0.5115, abs=1e-4)
    assert m["reflected_pct"] == pytest.approx(100 / 9)


def test_open_and_short():
    assert rf.gamma_from_z(complex(math.inf, 0), 50) == 1
    assert rf.gamma_from_z(0j, 50) == -1
    assert math.isinf(rf.vswr(1.0))
    assert rf.return_loss_db(1.0) == pytest.approx(0.0)


def test_inductive_and_capacitive_sign():
    g_ind = rf.gamma_from_z(50 + 50j, 50)
    g_cap = rf.gamma_from_z(50 - 50j, 50)
    assert g_ind.imag > 0 and g_cap.imag < 0  # mitad superior inductiva, inferior capacitiva


@pytest.mark.parametrize("z", [80 + 30j, 10 - 70j, 200 + 0j, 1 + 1j, 49.9 + 0.1j])
@pytest.mark.parametrize("z0", [50.0, 75.0, 300.0])
def test_gamma_vs_skrf_and_roundtrip(z, z0):
    g = rf.gamma_from_z(z, z0)
    g_skrf = complex(skrf.network.z2s(np.array([[[z]]]), z0)[0, 0, 0])
    assert g == pytest.approx(g_skrf, abs=1e-12)
    assert rf.z_from_gamma(g, z0) == pytest.approx(z, rel=1e-12)


def test_power_wave_gamma_reduces_to_voltage_for_real_source():
    assert rf.power_wave_gamma(80 + 30j, 50 + 0j) == pytest.approx(rf.gamma_from_z(80 + 30j, 50))
    # carga conjugada de la fuente → Γp = 0
    assert abs(rf.power_wave_gamma(30 - 40j, 30 + 40j)) < 1e-15


def test_z0_must_be_positive():
    with pytest.raises(RFInputError):
        rf.gamma_from_z(50, 0)


# ── Reactancias e impedancias ──
def test_reactances():
    assert imp.reactance_l(100e6, 10e-9) == pytest.approx(6.283185307, rel=1e-9)
    assert imp.reactance_c(100e6, 10e-12) == pytest.approx(-159.1549431, rel=1e-9)


def test_rlc_series_resonance():
    L, C, R = 100e-9, 25.33e-12, 10.0
    f0 = 1 / (2 * math.pi * math.sqrt(L * C))
    r = imp.analyze_circuit("RLC_series", f0, R=R, L=L, C=C)
    assert r["z"] == pytest.approx(complex(R, 0), abs=1e-9)
    assert r["f0"] == pytest.approx(f0)
    assert r["q_factor"] == pytest.approx(math.sqrt(L / C) / R)
    assert r["p"] == pytest.approx(1 / R)  # 1 V rms


def test_rlc_parallel_resonance_and_q():
    L, C, R = 1e-6, 1e-9, 1000.0
    f0 = 1 / (2 * math.pi * math.sqrt(L * C))
    r = imp.analyze_circuit("RLC_parallel", f0, R=R, L=L, C=C)
    assert r["z"] == pytest.approx(complex(R, 0), rel=1e-9)
    assert r["q_factor"] == pytest.approx(R * math.sqrt(C / L))


def test_lc_parallel_ideal_resonance_is_open():
    L, C = 1e-6, 1e-9
    f0 = 1 / (2 * math.pi * math.sqrt(L * C))
    r = imp.analyze_circuit("LC_parallel", f0 * (1 + 1e-12), L=L, C=C)
    assert abs(r["z"]) > 1e6


@pytest.mark.parametrize("topo,R,L,C,expected", [
    ("RL_series", 50, 10e-9, 0, 50 + 2j * math.pi * 1e9 * 10e-9),
    ("RC_series", 50, 0, 1e-12, 50 - 1j / (2 * math.pi * 1e9 * 1e-12)),
    ("RL_parallel", 50, 10e-9, 0, 1 / (1 / 50 + 1 / (2j * math.pi * 1e9 * 10e-9))),
    ("RC_parallel", 50, 0, 1e-12, 1 / (1 / 50 + 2j * math.pi * 1e9 * 1e-12)),
])
def test_topologies(topo, R, L, C, expected):
    assert imp.analyze_circuit(topo, 1e9, R=R, L=L, C=C)["z"] == pytest.approx(expected, rel=1e-12)


def test_power_triangle():
    r = imp.analyze_circuit("RL_series", 50, R=3, L=4 / (2 * math.pi * 50), v_rms=10)
    # Z = 3 + j4 → |Z| = 5, I = 2 A, P = 12 W, Q = 16 var, S = 20 VA
    assert r["p"] == pytest.approx(12) and r["q"] == pytest.approx(16) and r["s"] == pytest.approx(20)


def test_network_expression():
    node = imp.parse_network("R(50) + (L(10n) || C(4.7p))")
    f = 1e9
    zl, zc = 2j * math.pi * f * 10e-9, 1 / (2j * math.pi * f * 4.7e-12)
    assert imp.network_z(node, f)[0] == pytest.approx(50 + zl * zc / (zl + zc))


def test_network_expression_errors():
    with pytest.raises(RFInputError):
        imp.parse_network("R(50) + (L(10n)")
    with pytest.raises(RFInputError):
        imp.parse_network("X(5)")


def test_component_real_model_srf():
    m = imp.ComponentModel("L", 100e-9, srf=500e6)
    z_low = m.z(10e6)
    z_srf = m.z(500e6 * (1 + 1e-9))
    assert z_low.imag == pytest.approx(2 * math.pi * 10e6 * 100e-9, rel=1e-3)
    assert abs(z_srf) > 1e6  # autorresonancia paralelo


def test_component_q():
    m = imp.ComponentModel("L", 100e-9, q=50)
    z = m.z(100e6)
    assert z.imag / z.real == pytest.approx(50)
