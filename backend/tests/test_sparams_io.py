"""Parámetros S, estabilidad, Touchstone, TDR, calibración, antenas y tolerancias."""
import math

import numpy as np
import pytest
import skrf

from rfwb.engine import antenna, calibration, sparams as sp, stability, tdr, tolerance
from rfwb.engine.units import C0, RFInputError
from rfwb.io.touchstone import parse_touchstone, skrf_crosscheck, write_touchstone


def rand_s(n, nf=5, seed=0):
    rng = np.random.default_rng(seed)
    return 0.4 * (rng.normal(size=(nf, n, n)) + 1j * rng.normal(size=(nf, n, n)))


@pytest.mark.parametrize("n", [1, 2, 3, 4])
def test_s_z_roundtrip_vs_skrf(n):
    s = rand_s(n)
    z = sp.s_to_z(s, 50)
    assert np.allclose(z, skrf.network.s2z(s, 50), rtol=1e-9)
    assert np.allclose(sp.z_to_s(z, 50), s, atol=1e-12)


def test_s11_z_one_port():
    assert sp.s11_to_z(np.array([1 / 3]), 50)[0] == pytest.approx(100)
    assert sp.z_to_s11(np.array([80 + 30j]), 50)[0] == pytest.approx((30 + 30j) / (130 + 30j))


def test_abcd_conversion_vs_skrf():
    s = rand_s(2, seed=3)
    assert np.allclose(sp.s2_to_abcd(s, 50), skrf.network.s2a(s, 50), rtol=1e-9)


def test_gamma_in_matched_load():
    s = rand_s(2, seed=4)
    assert np.allclose(sp.gamma_in(s, np.zeros(5)), s[:, 0, 0])


def test_bands_and_minima():
    f = np.linspace(1e9, 2e9, 1001)
    y = 20 * np.log10(np.abs((f - 1.5e9) / 0.2e9) + 0.01)  # mínimo en 1.5 GHz
    b = sp.find_bands(f, y, -10)
    assert len(b) == 1
    # |x| + 0.01 ≤ 10^(-0.5) → |x| ≤ 0.30623 → Δ = 0.30623·0.2 GHz
    assert b[0]["f_low"] == pytest.approx(1.5e9 - (10 ** -0.5 - 0.01) * 0.2e9, rel=1e-4)
    m = sp.find_minima(f, y)
    assert m[0]["f"] == pytest.approx(1.5e9, rel=1e-4)


def test_group_delay_of_line():
    f = np.linspace(1e9, 2e9, 201)
    tau = 2.5e-9
    x = np.exp(-2j * np.pi * f * tau)
    assert np.allclose(sp.group_delay(f, x), tau, rtol=1e-6)


# ── Estabilidad ──
def test_stability_vs_skrf():
    s = np.array([[[0.6 * np.exp(-1j * 2.8), 0.05 * np.exp(1j * 0.5)],
                   [2.0 * np.exp(1j * 1.2), 0.5 * np.exp(-1j * 0.7)]]])
    st = stability.stability(s)
    ntw = skrf.Network(frequency=skrf.Frequency(1, 1, 1, unit="GHz"), s=s, z0=50)
    assert st["k"][0] == pytest.approx(ntw.stability[0], rel=1e-9)
    assert st["mu"][0] > 0


def test_stability_circle_is_gamma_in_unit_circle():
    s2 = np.array([[0.894 * np.exp(-1j * math.radians(60.6)), 0.020 * np.exp(1j * math.radians(62.4))],
                   [3.122 * np.exp(1j * math.radians(123.6)), 0.781 * np.exp(-1j * math.radians(27.6))]])
    c = stability.stability_circles(s2)["load"]
    # Puntos sobre el círculo deben dar |Γin| = 1
    for th in np.linspace(0, 2 * np.pi, 7):
        gl = c["center"] + c["radius"] * np.exp(1j * th)
        gin = s2[0, 0] + s2[0, 1] * s2[1, 0] * gl / (1 - s2[1, 1] * gl)
        assert abs(gin) == pytest.approx(1.0, abs=1e-9)


# ── Touchstone ──
S1P_RI = """! ejemplo
# MHz S RI R 50
100 0.1 0.2
200 0.3 -0.1
300 -0.2 0.05
"""

S2P_DB = """! 2 puertos en dB
# GHz S DB R 50
1.0 -10 30 -20 -45 -21 -44 -12 25
2.0 -11 35 -19 -50 -22 -49 -13 20
"""

S3P_MA = """# Hz S MA R 75
1e9 0.1 10 0.2 20 0.3 30
    0.4 40 0.5 50 0.6 60
    0.7 70 0.8 80 0.9 90
2e9 0.11 11 0.21 21 0.31 31
    0.41 41 0.51 51 0.61 61
    0.71 71 0.81 81 0.91 91
"""

S2P_V2 = """[Version] 2.0
# GHz S RI R 50
[Number of Ports] 2
[Two-Port Data Order] 12_21
[Number of Frequencies] 2
[Reference] 50 50
[Network Data]
1 0.1 0.0 0.2 0.1 0.3 0.2 0.4 0.3
2 0.2 0.1 0.3 0.2 0.4 0.3 0.5 0.4
[End]
"""

S1P_Z = """# MHz Z RI R 50
100 2 1
200 1 -1
"""


@pytest.mark.parametrize("text,name", [(S1P_RI, "a.s1p"), (S2P_DB, "b.s2p"), (S3P_MA, "c.s3p"), (S1P_Z, "z.s1p")])
def test_touchstone_vs_skrf(text, name):
    d = parse_touchstone(text, name)
    chk = skrf_crosscheck(text, name, d)
    assert chk["ok"], chk


def test_touchstone_2port_order_v1():
    d = parse_touchstone(S2P_DB, "b.s2p")
    # v1: S11 S21 S12 S22 → S21 = -20 dB
    assert 20 * np.log10(abs(d.s[0, 1, 0])) == pytest.approx(-20)
    assert 20 * np.log10(abs(d.s[0, 0, 1])) == pytest.approx(-21)


def test_touchstone_v2_order_12_21():
    d = parse_touchstone(S2P_V2, "v2.s2p")
    assert d.s[0, 0, 1] == pytest.approx(0.2 + 0.1j)  # S12
    assert d.s[0, 1, 0] == pytest.approx(0.3 + 0.2j)  # S21
    assert d.version == "2.0"


def test_touchstone_z_normalized_v1():
    d = parse_touchstone(S1P_Z, "z.s1p")
    z = sp.s11_to_z(d.s[:, 0, 0], 50)
    assert z[0] == pytest.approx(100 + 50j)


def test_touchstone_4port_roundtrip():
    s = rand_s(4, nf=3, seed=9)
    f = np.array([1e9, 2e9, 3e9])
    txt = write_touchstone(f, s, 50, "MA", "GHZ")
    d = parse_touchstone(txt, "x.s4p")
    assert np.allclose(d.s, s, atol=1e-10)
    assert skrf_crosscheck(txt, "x.s4p", d)["ok"]


@pytest.mark.parametrize("fmt", ["RI", "MA", "DB"])
def test_write_read_roundtrip(fmt):
    s = rand_s(2, nf=4, seed=2)
    f = np.linspace(1e9, 4e9, 4)
    d = parse_touchstone(write_touchstone(f, s, 50, fmt), "r.s2p")
    assert np.allclose(d.s, s, atol=1e-9) and np.allclose(d.f, f)


@pytest.mark.parametrize("bad,msg", [
    ("# MHz S RI R 50\n100 0.1\n", "incompletos"),
    ("# MHz S RI R 50\n200 0.1 0.1\n100 0.2 0.2\n", "crecientes"),
    ("# MHz S RI R 50\n100 0.1 abc\n", "no numérico"),
    ("# MHz G RI R 50\n100 0.1 0.1\n", "2 puertos"),
    ("", "vacío"),
    ("# MHz S XX R 50\n100 0.1 0.1\n", "desconocido"),
])
def test_touchstone_errors(bad, msg):
    with pytest.raises(RFInputError, match=msg):
        parse_touchstone(bad, "bad.s1p")


def test_touchstone_needs_port_count():
    with pytest.raises(RFInputError):
        parse_touchstone(S1P_RI, "noext.txt")


def test_touchstone_noise_block_v1():
    txt = S2P_DB + "1.0 1.5 0.3 45 0.2\n2.0 1.8 0.35 50 0.25\n"
    d = parse_touchstone(txt, "n.s2p")
    assert d.f.size == 2 and d.noise and len(d.noise) == 2


# ── TDR ──
def test_tdr_open_line_location():
    df = 10e6
    f = np.arange(1, 801) * df
    length, vf = 1.5, 0.8
    beta = 2 * np.pi * f / (vf * C0)
    s11 = np.exp(-2j * beta * length)  # línea sin pérdidas abierta
    r = tdr.tdr(f, s11, vf=vf, mode="lowpass")
    d, step = r["distance"], r["step"]
    k = np.argmax(step > 0.5)
    assert d[k] == pytest.approx(length, abs=2 * r["resolution_m"])
    assert step[-1] == pytest.approx(1.0, abs=0.05)


def test_tdr_lowpass_filter_settles_to_dc_value():
    """Filtro LC paso bajo terminado en 50 Ω: S11(0) = 0 → el escalón debe estabilizarse en ρ = 0 (Z = 50 Ω),
    y empezar con ρ > 0 (bobina serie a la entrada = alta impedancia instantánea)."""
    from rfwb.engine.network import abcd_to_s, cascade_abcd
    f = np.arange(1, 801) * 5e6
    els = [{"kind": "series", "part": "L", "value": 100e-9}, {"kind": "shunt", "part": "C", "value": 40e-12},
           {"kind": "series", "part": "L", "value": 100e-9}]
    s11 = abcd_to_s(cascade_abcd(f, els), 50)[:, 0, 0]
    r = tdr.tdr(f, s11, 50, 1.0, "lowpass")
    assert r["step"][-1] == pytest.approx(0.0, abs=0.02)
    assert r["z"][-1] == pytest.approx(50, abs=2)
    assert r["step"][np.argmin(np.abs(r["t"] - 0.3e-9))] > 0.3


def test_tdr_bandpass_peak():
    f = np.linspace(1e9, 3e9, 801)
    s11 = 0.3 * np.exp(-2j * 2 * np.pi * f * 2.0 / C0)
    r = tdr.tdr(f, s11, mode="bandpass")
    assert r["distance"][np.argmax(r["impulse_mag"])] == pytest.approx(2.0, abs=r["resolution_m"])


def test_tdr_lowpass_requires_harmonic():
    with pytest.raises(RFInputError):
        tdr.tdr(np.linspace(1.03e9, 2e9, 100), np.zeros(100), mode="lowpass")


# ── Calibración SOL ──
def test_one_port_sol_recovers_dut():
    rng = np.random.default_rng(5)
    n = 11
    e00 = 0.1 * (rng.normal(size=n) + 1j * rng.normal(size=n))
    e11 = 0.1 * (rng.normal(size=n) + 1j * rng.normal(size=n))
    er = 0.9 * np.exp(1j * rng.uniform(0, 6, size=n))
    meas = lambda g: e00 + er * g / (1 - e11 * g)
    dut = 0.4 * np.exp(1j * np.linspace(0, 3, n))
    terms = calibration.solve_one_port([meas(1), meas(-1), meas(0)])
    assert np.allclose(calibration.apply_one_port(meas(dut), terms), dut, atol=1e-12)


def test_one_port_vs_skrf():
    freq = skrf.Frequency(1, 2, 5, unit="GHz")
    rng = np.random.default_rng(1)
    e00 = 0.05 + 0.02j
    e11 = 0.1 - 0.05j
    er = 0.8 + 0.1j
    mk = lambda g: e00 + er * g / (1 - e11 * g)
    ideals = [skrf.Network(frequency=freq, s=np.full((5, 1, 1), g)) for g in (1, -1, 0)]
    measured = [skrf.Network(frequency=freq, s=np.full((5, 1, 1), mk(g))) for g in (1, -1, 0)]
    cal = skrf.calibration.OnePort(ideals=ideals, measured=measured)
    dut = skrf.Network(frequency=freq, s=np.full((5, 1, 1), mk(0.3 - 0.2j)))
    ref = cal.apply_cal(dut).s[:, 0, 0]
    terms = calibration.solve_one_port([m.s[:, 0, 0] for m in measured])
    assert np.allclose(calibration.apply_one_port(dut.s[:, 0, 0], terms), ref, atol=1e-12)


# ── Antenas ──
def test_antenna_series_rlc_model():
    f = np.linspace(400e6, 600e6, 2001)
    z = antenna.equivalent_model("series_rlc", 500e6, 50, 10, f)
    r = antenna.analyze_antenna(f, z=z, z0=50)
    assert r["best"]["f"] == pytest.approx(500e6, rel=1e-4)
    assert r["best"]["q_z"] == pytest.approx(10, rel=0.01)
    assert r["reactance_zero_crossings"][0]["f"] == pytest.approx(500e6, rel=1e-5)
    # VSWR 2:1 para RLC serie adaptada: FBW = (s−1)/(Q√s)
    b = r["bands"][0]
    assert b["fractional"] == pytest.approx(1 / (10 * math.sqrt(2)), rel=0.02)
    assert "Ganancia" in r["not_available"]


# ── Tolerancias ──
def test_monte_carlo_zero_tolerance():
    from rfwb.engine import matching as mt
    res = mt.design("L", 100 + 50j, 50 + 0j, 1e9)
    els = res["solutions"][0]["elements"]
    f = np.linspace(0.9e9, 1.1e9, 21)
    mc = tolerance.monte_carlo(els, np.full(f.shape, 100 + 50j), 50 + 0j, f, 1e9, 0, 0, 0, n=20)
    assert mc["yield_f0"] == 1.0 and mc["vswr_f0"]["max"] == pytest.approx(1.0, abs=1e-6)


def test_monte_carlo_spread():
    from rfwb.engine import matching as mt
    res = mt.design("L", 10 + 0j, 50 + 0j, 1e9)
    els = res["solutions"][0]["elements"]
    f = np.linspace(0.9e9, 1.1e9, 21)
    mc = tolerance.monte_carlo(els, np.full(f.shape, 10 + 0j), 50 + 0j, f, 1e9, 10, 10, 0, n=300)
    assert mc["vswr_f0"]["max"] > 1.05 and mc["yield_f0"] <= 1.0


# ── Calibración SOLT de 2 puertos ──
def test_solt_two_port_recovers_dut():
    import skrf
    from rfwb.engine.calibration import solt_two_port
    rng = np.random.default_rng(7)
    f = np.linspace(1e9, 3e9, 11)
    freq = skrf.Frequency.from_f(f, unit="Hz")
    n = f.size

    def rnd2(scale_t=0.9, scale_r=0.15):
        s = scale_r * (rng.normal(size=(n, 2, 2)) + 1j * rng.normal(size=(n, 2, 2)))
        s[:, 0, 1] = scale_t * np.exp(1j * rng.uniform(0, 6, n))
        s[:, 1, 0] = scale_t * np.exp(1j * rng.uniform(0, 6, n))
        return skrf.Network(frequency=freq, s=s, z0=50)

    A, B = rnd2(), rnd2()
    def refl(g):
        s = np.zeros((n, 2, 2), dtype=complex); s[:, 0, 0] = s[:, 1, 1] = g
        return skrf.Network(frequency=freq, s=s, z0=50)
    thru = np.zeros((n, 2, 2), dtype=complex); thru[:, 0, 1] = thru[:, 1, 0] = 1
    dut = rnd2(0.5, 0.3)
    meas = lambda x: (A ** x ** B).s
    out = solt_two_port(f, meas(dut), meas(refl(-1)), meas(refl(1)), meas(refl(0)),
                        meas(skrf.Network(frequency=freq, s=thru, z0=50)))
    assert np.allclose(out["s"], dut.s, atol=1e-9)


def test_solt_rejects_missing_params():
    from rfwb.engine.calibration import solt_two_port
    f = np.linspace(1e9, 2e9, 3)
    bad = np.full((3, 2, 2), np.nan + 0j)
    ok = np.zeros((3, 2, 2), dtype=complex)
    with pytest.raises(RFInputError, match="NaN"):
        solt_two_port(f, ok, bad, ok, ok, ok)


# ── Parámetros híbridos H/G ──
def test_h_g_to_s_vs_skrf():
    s = rand_s(2, seed=11)
    h = np.array([np.linalg.inv(x) for x in sp.s_to_z(s, 50)])  # cualquier matriz válida sirve
    h = h * np.array([[50, 1], [1, 1 / 50]])
    assert np.allclose(sp.h_to_s(h, 50), skrf.network.h2s(h, 50), atol=1e-12)
    g = np.linalg.inv(h)
    assert np.allclose(sp.g_to_s(g, 50), skrf.network.g2s(g, 50), atol=1e-12)


def test_h_from_s_roundtrip():
    s = rand_s(2, seed=12)
    h = skrf.network.s2h(s, 50)
    assert np.allclose(sp.h_to_s(h, 50), s, atol=1e-12)


def test_touchstone_h_v2_and_v1_normalized():
    s = rand_s(2, nf=2, seed=13)
    h = skrf.network.s2h(s, 50)
    f = np.array([1e9, 2e9])
    rows_v2, rows_v1 = [], []
    for k in range(2):
        v2 = [h[k, 0, 0], h[k, 0, 1], h[k, 1, 0], h[k, 1, 1]]  # orden 12_21
        hn = h[k] * np.array([[1 / 50, 1], [1, 50]])               # normalizado (v1)
        v1 = [hn[0, 0], hn[1, 0], hn[0, 1], hn[1, 1]]              # orden v1 11 21 12 22
        rows_v2.append(f"{f[k] / 1e9:g} " + " ".join(f"{x.real:.15g} {x.imag:.15g}" for x in v2))
        rows_v1.append(f"{f[k] / 1e9:g} " + " ".join(f"{x.real:.15g} {x.imag:.15g}" for x in v1))
    txt2 = "[Version] 2.0\n# GHz H RI R 50\n[Number of Ports] 2\n[Two-Port Data Order] 12_21\n[Number of Frequencies] 2\n[Network Data]\n" + "\n".join(rows_v2) + "\n[End]\n"
    txt1 = "# GHz H RI R 50\n" + "\n".join(rows_v1) + "\n"
    assert np.allclose(parse_touchstone(txt2, "h.s2p").s, s, atol=1e-9)
    assert np.allclose(parse_touchstone(txt1, "h.s2p").s, s, atol=1e-9)


# ── Microstrip completa y atenuación de cables ──
def test_microstrip_dispersive_matches_quasistatic_at_low_f():
    from rfwb.engine import tline as tl
    qs = tl.line_from_geometry("microstrip", W=3.06e-3, h=1.6e-3, er=4.4)
    full = tl.microstrip_dispersive(3.06e-3, 1.6e-3, 4.4, 1e6, t=0, tand=0, rho=0, f_er=1e6)
    assert full["z0"] == pytest.approx(qs["z0"], rel=5e-3)
    assert full["eps_eff"] == pytest.approx(qs["eps_eff"], rel=5e-3)
    assert full["atten_db_per_m"] == pytest.approx(0, abs=1e-9)


def test_microstrip_dispersion_and_losses():
    from rfwb.engine import tline as tl
    lo = tl.microstrip_dispersive(3e-3, 1.6e-3, 4.4, 1e9, t=35e-6, tand=0, rho=1.68e-8)
    hi = tl.microstrip_dispersive(3e-3, 1.6e-3, 4.4, 10e9, t=35e-6, tand=0, rho=1.68e-8)
    assert hi["eps_eff"] > lo["eps_eff"]                 # dispersión: εeff crece con f
    assert hi["alpha_c_db_m"] > lo["alpha_c_db_m"] > 0  # efecto pelicular
    lossy = tl.microstrip_dispersive(3e-3, 1.6e-3, 4.4, 1e9, t=35e-6, tand=0.02, rho=1.68e-8)
    assert lossy["alpha_d_db_m"] > 0


def test_scaled_cable_attenuation():
    from rfwb.engine import tline as tl
    assert tl.scaled_attenuation(0.2, 100e6, 400e6) == pytest.approx(0.4)
    r = tl.analyze_line(50, 400e6, 10, 0.66, 0.2, zl=50 + 0j, atten_ref_hz=100e6)
    assert r["atten_db_per_m"] == pytest.approx(0.4)
    assert r["p_load"] == pytest.approx(r["p_inc"] * 10 ** (-0.4 * 10 / 10))

def test_touchstone_v1_y_h_g_series_resistor_analytic():
    """Resistencia serie de 25 Ω entre puertos de 50 Ω: S11 = 25/125 = 0.2, S21 = 100/125 = 0.8 (analítico).
    Y = [[1/25, −1/25], [−1/25, 1/25]] → normalizada ×50 ;  H = [[25, 1], [−1, 0]] → h11/50, h22·50 ;
    G = H⁻¹ = [[0, −1], [1, 25]] → g11·50, g22/50.  Orden v1: 11 21 12 22."""
    y = "# GHz Y RI R 50\n1 2 0 -2 0 -2 0 2 0\n"
    h = "# GHz H RI R 50\n1 0.5 0 -1 0 1 0 0 0\n"
    g = "# GHz G RI R 50\n1 0 0 1 0 -1 0 0.5 0\n"
    for txt in (y, h, g):
        d = parse_touchstone(txt, "r.s2p")
        assert d.s[0, 0, 0] == pytest.approx(0.2) and d.s[0, 1, 0] == pytest.approx(0.8)
        assert d.s[0, 0, 1] == pytest.approx(0.8) and d.s[0, 1, 1] == pytest.approx(0.2)
        chk = skrf_crosscheck(txt, "r.s2p", d)
        assert chk.get("skipped") is True

# ── Kits de calibración no ideales ──
def test_calkit_standard_gamma_analytic():
    from rfwb.engine.calkit import standard_gamma
    f = np.array([1e9, 3e9])
    w = 2 * np.pi * f
    zc = 1 / (1j * w * 50e-15)
    assert np.allclose(standard_gamma("open", f, {"C0": 50}), (zc - 50) / (zc + 50))
    zl = 1j * w * 20e-12
    assert np.allclose(standard_gamma("short", f, {"L0": 20}), (zl - 50) / (zl + 50))
    tau = 30e-12  # open ideal con offset sin pérdidas: Γ = e^{-j2ωτ}
    assert np.allclose(standard_gamma("open", f, {"offset_delay": tau}), np.exp(-2j * w * tau))
    assert np.allclose(standard_gamma("load", f, {}), 0)


def _kit():
    return {"open": {"C0": 49.4, "C1": -310, "C2": 23.2, "C3": -0.16, "offset_delay": 29.2e-12, "offset_loss": 2.2e9},
            "short": {"L0": 2.08, "L1": -140, "L2": 4.7, "L3": -0.05, "offset_delay": 31.8e-12, "offset_loss": 2.4e9},
            "load": {"load_r": 50.5},
            "thru": {"offset_delay": 40e-12, "offset_loss": 1e9}}  # valores de prueba, no de un kit comercial


def test_sol_with_kit_recovers_dut():
    from rfwb.engine.calkit import standard_gamma
    f = np.linspace(1e9, 6e9, 21)
    kit = _kit()
    e00, e11, er = 0.08 - 0.03j, 0.12 + 0.05j, 0.85 * np.exp(-1j * f / 1e9)
    meas = lambda g: e00 + er * g / (1 - e11 * g)
    g_std = [standard_gamma(k, f, kit[k]) for k in ("open", "short", "load")]
    dut = 0.3 * np.exp(1j * np.linspace(0, 4, f.size))
    terms = calibration.solve_one_port([meas(g) for g in g_std], g_std)
    assert np.allclose(calibration.apply_one_port(meas(dut), terms), dut, atol=1e-10)
    ideal = calibration.solve_one_port([meas(g) for g in g_std])  # suponer ideales introduce error apreciable
    assert np.max(np.abs(calibration.apply_one_port(meas(dut), ideal) - dut)) > 1e-2


def test_solt_with_kit_recovers_dut():
    import skrf
    from rfwb.engine.calibration import solt_two_port
    from rfwb.engine.calkit import standard_gamma, thru_s
    rng = np.random.default_rng(3)
    f = np.linspace(1e9, 6e9, 11)
    n = f.size
    freq = skrf.Frequency.from_f(f, unit="Hz")
    kit = _kit()

    def rnd2(st=0.9, sr=0.12):
        s = sr * (rng.normal(size=(n, 2, 2)) + 1j * rng.normal(size=(n, 2, 2)))
        s[:, 0, 1] = st * np.exp(1j * rng.uniform(0, 6, n)); s[:, 1, 0] = st * np.exp(1j * rng.uniform(0, 6, n))
        return skrf.Network(frequency=freq, s=s, z0=50)

    A, B = rnd2(), rnd2()
    def refl(g):
        s = np.zeros((n, 2, 2), dtype=complex); s[:, 0, 0] = s[:, 1, 1] = g
        return skrf.Network(frequency=freq, s=s, z0=50)
    meas = lambda x: (A ** x ** B).s
    dut = rnd2(0.6, 0.3)
    stds = [refl(standard_gamma(k, f, kit[k])) for k in ("short", "open", "load")]
    th = skrf.Network(frequency=freq, s=thru_s(f, kit["thru"]), z0=50)
    out = solt_two_port(f, meas(dut), *[meas(x) for x in stds], meas(th), kit=kit)
    assert np.allclose(out["s"], dut.s, atol=1e-8)
    assert "Kit definido" in out["method"]

# ── Modo mixto ──
def test_mixed_mode_vs_skrf_and_roundtrip():
    from rfwb.engine import mixedmode as mm
    s = rand_s(4, nf=3, seed=21)
    n = skrf.Network(frequency=skrf.Frequency(1, 3, 3, unit="GHz"), s=s.copy(), z0=50)
    n.se2gmm(p=2)
    r = mm.se_to_mixed(s, [(1, 2), (3, 4)])
    assert np.allclose(r["s"], n.s, atol=1e-14)
    assert r["labels"] == ["D1", "D2", "C1", "C2"]
    assert np.allclose(mm.mixed_to_se(r["s"], 4, [(1, 2), (3, 4)]), s, atol=1e-14)


def test_mixed_mode_ideal_differential_thru():
    """Dos líneas idénticas sin acoplo (1→3, 2→4) excitadas como par: Sdd21 = S31, sin conversión de modo."""
    from rfwb.engine import mixedmode as mm
    t = np.exp(-1j * np.linspace(0, 2, 5))
    s = np.zeros((5, 4, 4), dtype=complex)
    s[:, 2, 0] = s[:, 0, 2] = s[:, 3, 1] = s[:, 1, 3] = t
    r = mm.se_to_mixed(s, [(1, 2), (3, 4)])
    assert np.allclose(r["blocks"]["dd"][:, 1, 0], t) and np.allclose(r["blocks"]["cc"][:, 1, 0], t)
    assert np.allclose(r["blocks"]["dc"], 0) and np.allclose(r["blocks"]["cd"], 0)


def test_mixed_mode_errors():
    from rfwb.engine import mixedmode as mm
    with pytest.raises(RFInputError):
        mm.se_to_mixed(rand_s(4), [(1, 2), (2, 3)])


def test_touchstone_mixed_mode_order():
    s = rand_s(4, nf=2, seed=22)
    rows = []
    for k, f in enumerate((1, 2)):
        vals = s[k].reshape(-1)
        rows.append(f"{f} " + " ".join(f"{v.real:.15g} {v.imag:.15g}" for v in vals))
    txt = ("[Version] 2.0\n# GHz S RI R 50\n[Number of Ports] 4\n[Number of Frequencies] 2\n"
           "[Mixed-Mode Order] D1,2 D3,4 C1,2 C3,4\n[Network Data]\n" + "\n".join(rows) + "\n[End]\n")
    d = parse_touchstone(txt, "mm.s4p")
    assert np.allclose(d.s, s) and d.port_labels == ["D1,2", "D3,4", "C1,2", "C3,4"]
    assert list(d.z0) == [100, 100, 25, 25]
    assert skrf_crosscheck(txt, "mm.s4p", d)["skipped"]
    with pytest.raises(RFInputError, match="Mixed-Mode"):
        parse_touchstone(txt.replace("C3,4\n", "\n"), "mm.s4p")

# ── Modelo EM analítico de antenas de hilo (valores de Balanis) ──
@pytest.mark.parametrize("kind,L,z_re,z_im,d_dbi", [
    ("dipole", 0.5, 73.08, 42.5, 2.15),     # dipolo λ/2
    ("monopole", 0.25, 36.54, 21.25, 5.16),  # monopolo λ/4 sobre masa perfecta
])
def test_wire_antenna_textbook(kind, L, z_re, z_im, d_dbi):
    from rfwb.engine.antenna_em import wire_antenna
    r = wire_antenna(kind, C0, L, 1e-5)  # f tal que λ = 1 m
    assert r["z_in"].real == pytest.approx(z_re, abs=0.05)
    assert r["z_in"].imag == pytest.approx(z_im, abs=0.1)
    assert r["directivity_dbi"] == pytest.approx(d_dbi, abs=0.01)


def test_short_dipole_and_long_dipole():
    from rfwb.engine.antenna_em import wire_antenna
    s = wire_antenna("dipole", C0, 0.01, 1e-6)
    assert s["directivity"] == pytest.approx(1.5, abs=0.002)
    assert s["z_in"].real == pytest.approx(20 * math.pi ** 2 * 0.01 ** 2, rel=0.01)
    assert wire_antenna("dipole", C0, 1.25, 1e-5)["directivity"] == pytest.approx(3.28, abs=0.01)


def test_wire_antenna_losses_and_errors():
    from rfwb.engine.antenna_em import wire_antenna
    thick = wire_antenna("dipole", 433e6, 0.33, 1e-3)
    thin = wire_antenna("dipole", 433e6, 0.33, 1e-5)
    assert 0.98 < thick["efficiency"] < 1 and thin["efficiency"] < thick["efficiency"]
    assert thick["gain"] == pytest.approx(thick["efficiency"] * thick["directivity"])
    with pytest.raises(RFInputError):
        wire_antenna("dipole", C0, 1.0, 1e-5)  # corriente nula en la alimentación