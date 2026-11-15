"""Reactancias, impedancias de componentes (ideales y con modelo real) y análisis de circuitos RLC."""
from __future__ import annotations

import cmath
import math
from dataclasses import dataclass

import numpy as np

from .steps import Trace
from .units import RFInputError, fmt_complex, fmt_si, require_nonneg, require_positive

TWO_PI = 2 * math.pi


# ───────────────────────── Reactancias básicas ─────────────────────────
def omega(f: float) -> float:
    return TWO_PI * require_positive("Frecuencia", f)


def reactance_l(f: float, L: float) -> float:
    """X_L = ωL  (positiva)."""
    return omega(f) * require_nonneg("Inductancia", L)


def reactance_c(f: float, C: float) -> float:
    """X_C = −1/(ωC)  (negativa, convención e^{+jωt})."""
    C = require_positive("Capacitancia", C)
    return -1.0 / (omega(f) * C)


def series(*zs: complex) -> complex:
    total = 0j
    for z in zs:
        if cmath.isinf(z):
            return complex(math.inf, 0)
        total += z
    return total


def parallel(*zs: complex) -> complex:
    y = 0j
    for z in zs:
        if z == 0:
            return 0j
        if cmath.isinf(z):
            continue
        y += 1 / z
    if y == 0:
        return complex(math.inf, 0)
    return 1 / y


def admittance(z: complex) -> complex:
    if z == 0:
        raise RFInputError("Admitancia infinita (cortocircuito).")
    if cmath.isinf(z):
        return 0j
    return 1 / z


# ───────────────────────── Modelos de componentes ─────────────────────────
@dataclass
class ComponentModel:
    """Modelo de componente. kind ∈ {R, L, C}.

    Modelo real (opcional):
      L: R_s en serie (ESR o derivada de Q a f_Q) ‖ C_p de autorresonancia (SRF).
      C: R_s (ESR o derivada de Q) + L_s (ESL derivada de SRF), todo en serie.
      R: ideal salvo L_s / C_p opcionales.
    """
    kind: str
    value: float
    q: float | None = None
    q_freq: float | None = None
    esr: float | None = None
    srf: float | None = None
    ls: float | None = None
    cp: float | None = None

    def is_ideal(self) -> bool:
        return not any((self.q, self.esr, self.srf, self.ls, self.cp))

    def z(self, f: float | np.ndarray) -> complex | np.ndarray:
        f = np.asarray(f, dtype=float)
        w = TWO_PI * f
        k = self.kind.upper()
        if k == "R":
            z = np.full_like(w, self.value, dtype=complex)
            if self.ls:
                z = z + 1j * w * self.ls
            if self.cp:
                z = 1 / (1 / z + 1j * w * self.cp)
        elif k == "L":
            rs = self._series_r(w, lambda ww: ww * self.value)
            z = rs + 1j * w * self.value
            if self.srf:
                cp = 1 / ((TWO_PI * self.srf) ** 2 * self.value)
                z = 1 / (1 / z + 1j * w * cp)
        elif k == "C":
            rs = self._series_r(w, lambda ww: 1 / (ww * self.value))
            with np.errstate(divide="ignore"):
                z = rs + 1 / (1j * w * self.value)
            if self.srf:
                esl = 1 / ((TWO_PI * self.srf) ** 2 * self.value)
                z = z + 1j * w * esl
        else:
            raise RFInputError(f"Tipo de componente desconocido: {self.kind}")
        z = np.asarray(z)
        return complex(z) if z.ndim == 0 else z

    def _series_r(self, w, xfun):
        if self.esr is not None and self.esr > 0:
            return self.esr
        if self.q and self.q > 0:
            # Q especificado a q_freq (o a la frecuencia de uso si no se especifica): R = |X|/Q.
            if self.q_freq:
                return xfun(TWO_PI * self.q_freq) / self.q
            return xfun(w) / self.q
        return 0.0


# ───────────────────────── Circuitos predefinidos ─────────────────────────
TOPOLOGIES = {
    "R": "Resistencia pura",
    "L": "Inductancia pura",
    "C": "Capacitancia pura",
    "RL_series": "RL serie", "RL_parallel": "RL paralelo",
    "RC_series": "RC serie", "RC_parallel": "RC paralelo",
    "LC_series": "LC serie", "LC_parallel": "LC paralelo",
    "RLC_series": "RLC serie", "RLC_parallel": "RLC paralelo",
}


def _topology_z(topo: str, f, R, L, C):
    scalar = np.ndim(f) == 0
    w = TWO_PI * np.atleast_1d(np.asarray(f, dtype=float))
    base = topo.split("_")[0]
    with np.errstate(divide="ignore", invalid="ignore"):
        if topo == "R":
            z = np.full(w.shape, R, dtype=complex)
        elif topo == "L":
            z = 1j * w * L
        elif topo == "C":
            z = 1 / (1j * w * C)
        elif topo.endswith("_series"):
            z = np.zeros(w.shape, dtype=complex)
            if "R" in base:
                z = z + R
            if "L" in base:
                z = z + 1j * w * L
            if "C" in base:
                z = z + 1 / (1j * w * C)
        else:
            y = np.zeros(w.shape, dtype=complex)
            if "R" in base:
                y = y + 1 / R
            if "L" in base:
                y = y + 1 / (1j * w * L)
            if "C" in base:
                y = y + 1j * w * C
            z = np.where(np.abs(y) < 1e-300, complex(np.inf, 0), 1 / np.where(y == 0, 1, y))
    return complex(z[0]) if scalar else z

def analyze_circuit(topology: str, f: float, R: float = 0.0, L: float = 0.0, C: float = 0.0,
                    z0: float = 50.0, v_rms: float = 1.0) -> dict:
    """Análisis completo de un circuito R/L/C con traza paso a paso."""
    if topology not in TOPOLOGIES:
        raise RFInputError(f"Topología no soportada: {topology}")
    f = require_positive("Frecuencia", f)
    z0 = require_positive("Z0", z0)
    v_rms = require_positive("Tensión", v_rms)
    uses = set(topology.split("_")[0])
    if "R" in uses:
        R = require_positive("R", R) if "parallel" in topology else require_nonneg("R", R)
    if "L" in uses:
        L = require_positive("L", L)
    if "C" in uses:
        C = require_positive("C", C)
    t = Trace()
    w = TWO_PI * f
    t.add("Frecuencia angular", "ω = 2πf", f"ω = 2π · {fmt_si(f, 'Hz')}", f"{w:.6g}", "rad/s")
    xl = xc = None
    if "L" in uses:
        xl = w * L
        t.add("Reactancia inductiva", "X_L = ωL", f"X_L = {w:.6g} · {fmt_si(L, 'H')}", f"+{xl:.6g}", "Ω",
              "Positiva: la tensión adelanta 90° a la corriente.")
    if "C" in uses:
        xc = -1 / (w * C)
        t.add("Reactancia capacitiva", "X_C = −1 / (ωC)", f"X_C = −1 / ({w:.6g} · {fmt_si(C, 'F')})",
              f"{xc:.6g}", "Ω", "Negativa (convención e^{+jωt}): la corriente adelanta 90° a la tensión.")
    z = complex(_topology_z(topology, f, R, L, C))
    if topology.endswith("_series"):
        terms = " + ".join([s for s, used in (("R", "R" in uses), ("jX_L", "L" in uses), ("jX_C", "C" in uses)) if used])
        t.add("Impedancia serie", f"Z = {terms}", "Las impedancias en serie se suman.", fmt_complex(z), "Ω")
    elif topology.endswith("_parallel"):
        terms = " + ".join([s for s, used in (("1/R", "R" in uses), ("1/(jX_L)", "L" in uses), ("1/(jX_C)", "C" in uses)) if used])
        y = 1 / z if z != 0 and not cmath.isinf(z) else 0j
        t.add("Admitancia paralelo", f"Y = {terms}", "Las admitancias en paralelo se suman.", fmt_complex(y, "S"), "S")
        t.add("Impedancia equivalente", "Z = 1 / Y", "", fmt_complex(z), "Ω")
    else:
        t.add("Impedancia", "Z = R | jωL | 1/(jωC)", "", fmt_complex(z), "Ω")

    res: dict = {"topology": topology, "topology_name": TOPOLOGIES[topology], "f": f, "omega": w,
                 "xl": xl, "xc": xc, "z": z}
    if cmath.isinf(z):
        res.update({"z_mag": math.inf, "z_deg": 0.0, "y": 0j, "g": 0.0, "b": 0.0})
        t.add("Resultado", "Z → ∞", "", "Circuito abierto (resonancia paralelo ideal)", "",
              "Un LC paralelo ideal en resonancia presenta impedancia infinita.")
    else:
        zmag, zdeg = abs(z), math.degrees(cmath.phase(z))
        t.add("Forma polar", "|Z| = √(R² + X²) ;  φ = atan2(X, R)",
              f"|Z| = √({z.real:.6g}² + {z.imag:.6g}²)", f"{zmag:.6g} Ω ∠ {zdeg:.4f}°", "",
              "φ > 0: carácter inductivo · φ < 0: capacitivo · φ = 0: resistivo.")
        y = 1 / z if z != 0 else complex(math.inf, 0)
        if z != 0:
            t.add("Admitancia", "Y = 1/Z = G + jB", f"Y = 1 / ({fmt_complex(z)})", fmt_complex(y, "S"), "S",
                  "G = conductancia, B = susceptancia (B > 0 capacitiva, B < 0 inductiva).")
        # Potencias con fuente de tensión ideal V_rms
        if z != 0:
            i = v_rms / z
            s = v_rms * i.conjugate()
            t.add("Corriente", "I = V / Z", f"I = {v_rms:g} V / ({fmt_complex(z)})",
                  f"{abs(i):.6g} A ∠ {math.degrees(cmath.phase(i)):.3f}°", "A rms",
                  "Hipótesis: fuente ideal de tensión senoidal, valores eficaces.")
            t.add("Potencia compleja", "S = V · I* = P + jQ", f"S = {v_rms:g} · ({fmt_complex(i.conjugate(), 'A')})",
                  f"P = {s.real:.6g} W ; Q = {s.imag:.6g} var ; |S| = {abs(s):.6g} VA", "",
                  "Q > 0 consume reactiva inductiva; Q < 0 la entrega (capacitiva). FP = cos φ.")
            res.update({"i": i, "p": s.real, "q": s.imag, "s": abs(s), "pf": s.real / abs(s) if abs(s) else 1.0})
        res.update({"z_mag": zmag, "z_deg": zdeg, "y": y, "g": y.real if z != 0 else math.inf,
                    "b": y.imag if z != 0 else 0.0})

    # Resonancia y Q
    if "L" in uses and "C" in uses:
        f0 = 1 / (TWO_PI * math.sqrt(L * C))
        t.add("Frecuencia de resonancia", "f0 = 1 / (2π√(LC))",
              f"f0 = 1 / (2π√({fmt_si(L, 'H')} · {fmt_si(C, 'F')}))", fmt_si(f0, "Hz"), "",
              "En f0 se anulan las reactancias (serie) o susceptancias (paralelo).")
        res["f0"] = f0
        if topology == "RLC_series" and R > 0:
            q = math.sqrt(L / C) / R
            t.add("Factor de calidad (serie)", "Q = (1/R)·√(L/C)", f"Q = (1/{R:g})·√({L:.4g}/{C:.4g})", f"{q:.5g}", "")
            t.add("Ancho de banda (−3 dB)", "BW = f0 / Q", f"BW = {fmt_si(f0, 'Hz')} / {q:.5g}", fmt_si(f0 / q, "Hz"))
            res.update({"q_factor": q, "bw_3db": f0 / q})
        elif topology == "RLC_parallel":
            q = R * math.sqrt(C / L)
            t.add("Factor de calidad (paralelo)", "Q = R·√(C/L)", f"Q = {R:g}·√({C:.4g}/{L:.4g})", f"{q:.5g}", "")
            t.add("Ancho de banda (−3 dB)", "BW = f0 / Q", f"BW = {fmt_si(f0, 'Hz')} / {q:.5g}", fmt_si(f0 / q, "Hz"))
            res.update({"q_factor": q, "bw_3db": f0 / q})
    res["character"] = ("abierto" if cmath.isinf(z) else "resistivo" if abs(z.imag) < 1e-9 * max(1, abs(z))
                        else "inductivo" if z.imag > 0 else "capacitivo")
    res["trace"] = t
    return res


def sweep_circuit(topology: str, f_start: float, f_stop: float, n: int, R=0.0, L=0.0, C=0.0, log=True):
    if f_stop <= f_start:
        raise RFInputError("La frecuencia final debe ser mayor que la inicial.")
    n = int(max(2, min(n, 20001)))
    f = np.geomspace(f_start, f_stop, n) if log else np.linspace(f_start, f_stop, n)
    return f, np.asarray(_topology_z(topology, f, R, L, C), dtype=complex)


# ───────────────────────── Redes arbitrarias (expresión) ─────────────────────────
class _Parser:
    """Gramática:  expr := term ('+' term)* ;  term := factor ('||' factor)* ;
    factor := '(' expr ')' | R(val) | L(val) | C(val) | Z(re,im)
    '+' = serie, '||' = paralelo.  Ej.: R(50) + (L(10n) || C(4.7p))
    """

    def __init__(self, text: str):
        self.s = text.replace(" ", "")
        self.i = 0

    def parse(self):
        node = self.expr()
        if self.i != len(self.s):
            raise RFInputError(f"Expresión no válida cerca de '{self.s[self.i:]}'.")
        return node

    def expr(self):
        nodes = [self.term()]
        while self.s.startswith("+", self.i):
            self.i += 1
            nodes.append(self.term())
        return nodes[0] if len(nodes) == 1 else {"type": "series", "children": nodes}

    def term(self):
        nodes = [self.factor()]
        while self.s.startswith("||", self.i):
            self.i += 2
            nodes.append(self.factor())
        return nodes[0] if len(nodes) == 1 else {"type": "parallel", "children": nodes}

    def factor(self):
        from .units import parse_quantity
        if self.s.startswith("(", self.i):
            self.i += 1
            n = self.expr()
            if not self.s.startswith(")", self.i):
                raise RFInputError("Falta ')' en la expresión.")
            self.i += 1
            return n
        if self.i >= len(self.s):
            raise RFInputError("Expresión incompleta.")
        k = self.s[self.i].upper()
        if k not in "RLCZ" or not self.s.startswith("(", self.i + 1):
            raise RFInputError(f"Se esperaba R(...), L(...), C(...) o Z(re,im) en la posición {self.i + 1}.")
        j = self.s.find(")", self.i)
        if j < 0:
            raise RFInputError("Falta ')' tras el valor del componente.")
        arg = self.s[self.i + 2:j]
        self.i = j + 1
        if k == "Z":
            parts = arg.split(";") if ";" in arg else arg.split(",")
            if len(parts) != 2:
                raise RFInputError("Z(re,im) requiere dos valores.")
            return {"type": "Z", "re": float(parts[0]), "im": float(parts[1])}
        v = parse_quantity(arg)
        if v <= 0:
            raise RFInputError(f"{k}: el valor debe ser positivo.")
        return {"type": k, "value": v}


def parse_network(expr: str) -> dict:
    return _Parser(expr).parse()


def network_z(node: dict, f) -> np.ndarray:
    f = np.atleast_1d(np.asarray(f, dtype=float))
    w = TWO_PI * f
    t = node["type"]
    with np.errstate(divide="ignore", invalid="ignore"):
        if t == "R":
            return np.full(f.shape, node["value"], dtype=complex)
        if t == "L":
            return 1j * w * node["value"]
        if t == "C":
            return 1 / (1j * w * node["value"])
        if t == "Z":
            return np.full(f.shape, complex(node["re"], node["im"]))
        kids = [network_z(c, f) for c in node["children"]]
        if t == "series":
            return np.sum(kids, axis=0)
        y = np.sum([np.where(k == 0, np.inf, 1 / k) for k in kids], axis=0)
        return np.where(y == 0, np.inf, 1 / y)


def network_to_text(node: dict) -> str:
    t = node["type"]
    if t in "RLC":
        unit = {"R": "Ω", "L": "H", "C": "F"}[t]
        return f"{t}({fmt_si(node['value'], unit)})"
    if t == "Z":
        return f"Z({node['re']:g}{node['im']:+g}j)"
    sep = " + " if t == "series" else " ‖ "
    return "(" + sep.join(network_to_text(c) for c in node["children"]) + ")"
