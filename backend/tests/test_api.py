"""Prueba de integración de la API completa (base de datos en memoria)."""
import pytest
from fastapi.testclient import TestClient

from rfwb import db

db.reset_for_tests(":memory:")
from rfwb.main import app  # noqa: E402

client = TestClient(app)
S2P = """! test
# GHz S RI R 50
1.0 0.2 0.1 0.8 -0.2 0.01 0.0 0.3 -0.1
1.5 0.1 0.05 0.85 -0.1 0.01 0.0 0.25 -0.05
2.0 0.15 -0.1 0.7 -0.3 0.01 0.0 0.2 0.1
2.5 0.2 -0.2 0.6 -0.4 0.01 0.01 0.3 0.1
"""


def ok(r):
    assert r.status_code == 200, r.text
    return r.json()


def test_health_and_selftest():
    assert ok(client.get("/api/health"))["status"] == "ok"
    st = ok(client.get("/api/selftest"))
    assert st["passed"] == st["total"], st


def test_reflection_and_rotate():
    r = ok(client.post("/api/rf/reflection", json={"z": "80+j30", "z0": 50, "f": "100MHz"}))
    assert r["vswr"] > 1 and r["equivalent"]["series"]["kind"] == "L"
    assert len(r["trace"]) >= 5
    r = ok(client.post("/api/rf/reflection", json={"z": "0", "z0": 50}))
    assert r["vswr"] == "inf"
    r = ok(client.post("/api/rf/line-rotate", json={"z": "100", "z0": 50, "length_lambda": 0.25}))
    assert r["z_end"]["re"] == pytest.approx(25)
    assert client.post("/api/rf/reflection", json={"z": "abc"}).status_code == 422


def test_circuit_and_network():
    r = ok(client.post("/api/circuit/analyze", json={"topology": "RLC_series", "f": "100MHz", "R": 10, "L": "100n", "C": "25p",
                                                      "sweep": {"start": "10MHz", "stop": "1GHz", "n": 101}}))
    assert "f0" in r and len(r["sweep"]["f"]) == 101
    r = ok(client.post("/api/circuit/network", json={"expr": "R(50) + (L(10n) || C(4.7p))", "f": "1GHz",
                                                      "sweep": {"start": "100MHz", "stop": "3GHz", "n": 51}}))
    assert r["reflection"]["vswr"] > 1
    assert client.post("/api/circuit/analyze", json={"topology": "RLC_series", "f": 0, "R": 1, "L": 1, "C": 1}).status_code == 422


def test_component_model():
    r = ok(client.post("/api/component/impedance", json={"kind": "C", "value": "10p", "srf": "1.2GHz", "esr": 0.2}))
    assert len(r["real"]["z"]["re"]) == 601


def test_tline():
    r = ok(client.post("/api/tline/analyze", json={"z0": 50, "f": "1GHz", "length": 0.25, "length_unit": "lambda", "zl": "100"}))
    assert r["zin"]["re"] == pytest.approx(25, abs=1e-6)
    g = ok(client.post("/api/tline/geometry", json={"kind": "microstrip", "W": 3.06e-3, "h": 1.6e-3, "er": 4.4}))
    assert 49 < g["z0"] < 51


@pytest.mark.parametrize("method", ["L", "PI", "T", "QWT", "STUB1", "STUB2"])
def test_match(method):
    r = ok(client.post("/api/match/design", json={"method": method, "zl": "25-j40", "zs": "50", "f0": "433MHz",
                                                   "q_net": 4, "snap": "E24", "d1_lambda": 0.05}))
    assert r["solutions"]
    s = r["solutions"][0]
    assert s["vswr_after"] == pytest.approx(1, abs=1e-4)
    assert s["trajectory_gamma"]
    tol = ok(client.post("/api/match/tolerance", json={"elements": s["elements"], "zl": "25-j40", "zs": "50",
                                                       "f0": "433MHz", "n": 50}))
    assert 0 <= tol["yield_f0"] <= 1


def test_match_library_snap():
    r = ok(client.post("/api/match/design", json={"method": "L", "zl": "10+j5", "zs": "50", "f0": "145MHz", "snap": "library"}))
    assert any("snapped" in s for s in r["solutions"])


def test_touchstone_dataset_flow():
    r = ok(client.post("/api/touchstone/parse", json={"filename": "amp.s2p", "text": S2P, "save": True}))
    assert r["skrf_check"]["ok"] and r["summary"]["nports"] == 2
    ds = r["dataset_id"]
    assert any(d["id"] == ds for d in ok(client.get("/api/datasets")))
    a = ok(client.post("/api/sparams/analyze", json={"dataset_id": ds, "marker_f": "1.7GHz"}))
    assert "stability" in a and "S21" in a["marker"]["values"]
    c = ok(client.post("/api/sparams/circles", json={"dataset_id": ds, "f": "2GHz", "gains_db": [0, 3]}))
    assert "k" in c
    assert ok(client.get(f"/api/datasets/{ds}"))["origin"] == "imported"
    ex = client.get(f"/api/datasets/{ds}/export?kind=touchstone&fmt=MA")
    assert ex.status_code == 200 and "# GHz S MA R 50" in ex.text
    assert client.get(f"/api/datasets/{ds}/export?kind=csv").status_code == 200
    bad = client.post("/api/touchstone/parse", json={"filename": "x.s2p", "text": "# GHz S RI R 50\n1 0.1 0.1\n"})
    assert bad.status_code == 422 and "incompletos" in bad.json()["detail"]


def test_simulated_dataset_tdr_antenna_cal():
    sim = ok(client.post("/api/datasets/simulated", json={"name": "línea", "kind": "oneport", "expr": "R(50)+L(20n)",
                                                          "f_start": "10MHz", "f_stop": "4GHz", "n": 400}))
    t = ok(client.post("/api/sparams/tdr", json={"dataset_id": sim["id"], "mode": "lowpass"}))
    assert len(t["z"]) > 10
    a = ok(client.post("/api/antenna/analyze", json={"source": "model", "model": {"kind": "series_rlc", "f0": "433MHz", "R": 50, "Q": 12,
                                                                                    "f_start": "380MHz", "f_stop": "480MHz"}}))
    assert a["origin"] == "simulated" and "Ganancia" in a["not_available"]
    a2 = ok(client.post("/api/antenna/analyze", json={"source": "dataset", "dataset_id": sim["id"]}))
    assert a2["origin"] == "simulated"
    two = ok(client.post("/api/datasets/simulated", json={"name": "LPF", "elements": [
        {"kind": "series", "part": "L", "value": 10e-9}, {"kind": "shunt", "part": "C", "value": 4e-12}],
        "f_start": "100MHz", "f_stop": "3GHz", "n": 101}))
    assert ok(client.post("/api/sparams/analyze", json={"dataset_id": two["id"]}))["nports"] == 2
    ids = []
    for expr in ("R(50)+L(5n)", "R(1e9)", "R(1e-6)", "R(50)"):
        ids.append(ok(client.post("/api/datasets/simulated", json={"name": expr, "kind": "oneport", "expr": expr,
                                                                    "f_start": "100MHz", "f_stop": "1GHz", "n": 11}))["id"])
    c = ok(client.post("/api/calibration/sol", json={"raw_id": ids[0], "open_id": ids[1], "short_id": ids[2], "load_id": ids[3]}))
    assert ok(client.get(f"/api/datasets/{c['id']}"))["origin"] == "derived"


def test_library_and_projects():
    lib = ok(client.get("/api/library?category=coax"))
    assert lib["items"] and all(i["source"] == "generico" for i in lib["items"])
    new = ok(client.post("/api/library", json={"category": "inductor", "name": "L prueba", "value": "12n", "unit": "H",
                                               "q_factor": 40, "srf_hz": "2GHz"}))
    items = ok(client.get("/api/library?q=prueba"))["items"]
    assert items[0]["model"] == "real" and items[0]["source"] == "usuario"
    ok(client.delete(f"/api/library/{new['id']}"))
    p = ok(client.post("/api/projects", json={"name": "P1", "data": {"a": 1}}))
    ok(client.put(f"/api/projects/{p['id']}", json={"name": "P1b", "data": {"a": 2}}))
    assert ok(client.get(f"/api/projects/{p['id']}"))["data"]["a"] == 2


def test_vna_simulation_mode():
    st = ok(client.get("/api/vna/status"))
    assert st["connected"] is False and st["label"] == "Sin instrumento conectado — Modo de simulación"
    assert len(ok(client.get("/api/vna/drivers"))["drivers"]) == 3
    r = client.post("/api/vna/capture", json={"params": ["S11"]})
    assert r.status_code == 409
    r = client.post("/api/vna/connect", json={"driver": "librevna", "address": "127.0.0.1:1"})
    assert r.status_code == 409  # sin instrumento: error real, nunca conexión simulada
    assert ok(client.get("/api/vna/status"))["connected"] is False


def test_reports():
    rep = {"title": "Prueba", "items": [{"title": "Z", "module": "Smith", "origin": "calculated",
                                         "inputs": [["Z", "80+j30"]], "results": [["VSWR", "1.9"]],
                                         "steps": [{"title": "Γ", "formula": "Γ=(Z−Z0)/(Z+Z0)", "result": "0.3"}],
                                         "smith": {"z0": 50, "points": [{"re": 0.3, "im": 0.2, "label": "Z"}], "traces": []},
                                         "plots": [{"title": "S11", "x": [1e9, 2e9], "series": [{"name": "S11", "y": [-10, -12]}]}]}]}
    r = client.post("/api/reports/pdf", json=rep)
    assert r.status_code == 200 and r.content[:4] == b"%PDF"
    assert "Origen" in client.post("/api/reports/csv", json=rep).text


def test_vna_live_and_save_with_test_double():
    """Driver de prueba SÓLO para tests: verifica el flujo de barrido continuo y guardado sin hardware."""
    import numpy as np
    from rfwb.vna.base import Capture, SweepConfig, VNADriver
    from rfwb.vna.drivers import NanoVNADriver
    from rfwb.vna.manager import MANAGER

    class FakeDriver(VNADriver):
        info = NanoVNADriver.info
        def connect(self): return "TEST"
        def disconnect(self): pass
        def configure_sweep(self, cfg): self.sweep = cfg
        def capture(self, params):
            f = np.linspace(self.sweep.start_hz, self.sweep.stop_hz, self.sweep.points)
            return Capture(f, {p: np.full(f.size, 0.1 + 0.05j) for p in params}, "TEST", self.sweep)

    d = FakeDriver("test"); d.idn = "TEST"
    MANAGER.driver = d
    try:
        assert ok(client.get("/api/vna/status"))["label"] == "Medición real — VNA conectado"
        ok(client.post("/api/vna/sweep", json={"start": "1MHz", "stop": "10MHz", "points": 11}))
        live = ok(client.post("/api/vna/live", json={"params": ["S11", "S21"]}))
        assert live["origin"] == "measured" and len(live["f"]) == 11 and "S21" in live["db"]
        n_before = len(ok(client.get("/api/datasets")))
        saved = ok(client.post("/api/vna/save-last", json={"params": ["S11"], "name": "live"}))
        assert len(ok(client.get("/api/datasets"))) == n_before + 1
        assert ok(client.get(f"/api/datasets/{saved['id']}"))["origin"] == "measured"
        assert client.post("/api/vna/live", json={"params": ["S22"]}).status_code == 409  # NanoVNA no mide S22
    finally:
        MANAGER.driver = None
        MANAGER.last = None
    assert client.post("/api/vna/save-last", json={"params": ["S11"]}).status_code == 409


def test_solt_endpoint():
    ids = []
    for expr in ("R(50)+L(5n)", "R(1e-6)", "R(1e9)", "R(50)"):
        ids.append(ok(client.post("/api/datasets/simulated", json={"name": expr, "kind": "twoport",
            "elements": [{"kind": "series", "part": "R", "value": "1"}], "f_start": "100MHz", "f_stop": "1GHz", "n": 11}))["id"])
    r = client.post("/api/calibration/solt", json={"raw_id": ids[0], "short_id": ids[1], "open_id": ids[2], "load_id": ids[3], "thru_id": ids[0]})
    # estándares idénticos (no independientes): debe rechazarse con un error claro, nunca guardar basura
    assert r.status_code == 422 and "singular" in r.json()["detail"], r.text


def test_library_cable_attenuation_flow():
    new = ok(client.post("/api/library", json={"category": "coax", "name": "Cable prueba", "extra": {"z0": "50", "vf": "0.66",
                                                "atten_db_per_100m": "20", "atten_ref_hz": "100M"}}))
    item = next(i for i in ok(client.get("/api/library?category=coax"))["items"] if i["id"] == new["id"])
    assert item["extra"]["atten_ref_hz"] == 1e8 and item["value"] == 50
    bad = client.post("/api/library", json={"category": "coax", "name": "x", "extra": {"z0": "50", "vf": "1.5"}})
    assert bad.status_code == 422
    r = ok(client.post("/api/tline/analyze", json={"z0": 50, "f": "400MHz", "length": 10, "vf": 0.66, "atten_db_per_m": 0.2,
                                                   "atten_ref_hz": "100MHz", "load": "matched"}))
    assert r["atten_db_per_m"] == pytest.approx(0.4)
    g = ok(client.post("/api/tline/geometry", json={"kind": "microstrip", "W": "3m", "h": "1.6m", "er": 4.4, "f": "2.4GHz", "t": "35u", "tand": 0.02}))
    assert g["atten_db_per_m"] > 0 and "quasi_static" in g
import numpy as np

def test_mixed_mode_endpoint():
    s4 = "# GHz S RI R 50\n" + "\n".join(
        f"{f} " + " ".join("0.1 0.0" if i == j else ("0.9 0.0" if abs(i - j) == 2 else "0 0") for i in range(4) for j in range(4))
        for f in (1, 2, 3)) + "\n"
    ds = ok(client.post("/api/touchstone/parse", json={"filename": "par.s4p", "text": s4, "save": True}))["dataset_id"]
    r = ok(client.post("/api/sparams/mixed-mode", json={"dataset_id": ds, "pairs": [[1, 2], [3, 4]], "save": True}))
    assert r["traces"]["Sdd21"]["db"][0] == pytest.approx(20 * np.log10(0.9))
    assert r["z_ref"]["diferencial"] == 100
    a = ok(client.post("/api/sparams/analyze", json={"dataset_id": r["dataset_id"]}))
    assert a["labels"]["S21"] == "S[D2,D1]" and a["origin"] == "derived"
    assert client.post("/api/sparams/mixed-mode", json={"dataset_id": r["dataset_id"]}).status_code == 422

def test_antenna_em_endpoint():
    r = ok(client.post("/api/antenna/em-model", json={"kind": "dipole", "f": "433MHz", "length": 0.48, "length_unit": "lambda", "radius": "1m"}))
    assert r["origin"] == "simulated" and 2.0 < r["em"]["directivity_dbi"] < 2.3
    assert abs(r["best"]["f"] - 433e6) < 40e6  # resonancia cerca de f con L ≈ 0.48λ
    assert len(r["em"]["pattern"]["db"]) > 100

def test_circuit_builder():
    # Red L de Pozar ej. 5.1 construida desde la carga: C paralelo 0.92 pF y L serie 38.8 nH -> Zin ≈ 100 Ω
    from rfwb.engine import matching as mt
    sol = next(s for s in mt.design("L", 200 - 100j, 100 + 0j, 500e6, z0=100)["solutions"]
               if {(e["kind"], e["part"]) for e in s["elements"]} == {("shunt", "C"), ("series", "L")})
    c = next(e["value"] for e in sol["elements"] if e["part"] == "C")
    lv = next(e["value"] for e in sol["elements"] if e["part"] == "L")
    r = ok(client.post("/api/circuit/builder", json={"zl": "200-j100", "z0": 100, "f0": "500MHz", "elements": [
        {"kind": "shunt", "part": "C", "value": c}, {"kind": "series", "part": "L", "value": lv}]}))
    assert r["zin"]["re"] == pytest.approx(100, rel=1e-9) and abs(r["zin"]["im"]) < 1e-6
    assert len(r["nodes"]) == 3 and len(r["segments"]) == 2 and len(r["trace"]) >= 4
    # λ/4 de 50 Ω sobre 100 Ω -> 25 Ω ; stub en corto λ/8 en paralelo
    r2 = ok(client.post("/api/circuit/builder", json={"zl": "100", "f0": "1GHz", "elements": [
        {"kind": "line", "part": "line", "z0": "50", "length": 0.25, "unit": "lambda"}]}))
    assert r2["zin"]["re"] == pytest.approx(25, rel=1e-6)
    r3 = ok(client.post("/api/circuit/builder", json={"zl": "50", "f0": "1GHz", "elements": [
        {"kind": "shunt", "part": "stub_short", "z0": "50", "length": 0.125, "unit": "lambda"}]}))
    assert r3["zin"]["re"] == pytest.approx(25, rel=1e-6) and r3["zin"]["im"] == pytest.approx(25, rel=1e-6)  # 50 ‖ j50
    assert client.post("/api/circuit/builder", json={"zl": "50", "f0": "1GHz", "elements": [{"kind": "series", "part": "L", "value": "-1n"}]}).status_code == 422
