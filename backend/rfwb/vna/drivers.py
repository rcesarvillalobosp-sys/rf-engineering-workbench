"""Drivers concretos: NanoVNA (serie USB-CDC), LibreVNA (SCPI por TCP vía LibreVNA-GUI) y SCPI/VISA genérico.

Estado de verificación: ninguno se ha probado todavía contra hardware real en este proyecto
(verified_with_hardware = False). Los comandos siguen la documentación pública de cada fabricante;
cualquier discrepancia se informa como error del instrumento, nunca se sustituye por datos ficticios.
"""
from __future__ import annotations

import re
import socket
import time

import numpy as np

from .base import Capture, DriverInfo, SweepConfig, VNADriver, VNAError


# ───────────────────────── NanoVNA ─────────────────────────
class NanoVNADriver(VNADriver):
    info = DriverInfo(
        key="nanovna", name="NanoVNA / NanoVNA-H / H4", vendor_family="NanoVNA (hugen79, DiSlord y derivados)",
        interfaces=["USB (CDC serie)"], protocol="Shell de texto propio (no SCPI): sweep, scan, data, frequencies",
        ports=2, params=["S11", "S21"], max_points=401,
        calibration=["SOLT de 1.5 puertos interna del instrumento (se usa la calibración activa del equipo)"],
        notes="S21 es una medida de transmisión de 1.5 puertos (sin S12/S22). Máx. puntos depende del firmware (101 o 401).",
        address_hint="COM3  (Windows)  ·  /dev/ttyACM0 (Linux)")
    USB_IDS = {(0x0483, 0x5740)}

    def __init__(self, address):
        super().__init__(address)
        self.ser = None

    def _cmd(self, cmd: str, timeout=5.0) -> list[str]:
        self.ser.reset_input_buffer()
        self.ser.write((cmd + "\r").encode())
        buf = b""
        t0 = time.time()
        while b"ch> " not in buf:
            chunk = self.ser.read(self.ser.in_waiting or 1)
            buf += chunk
            if time.time() - t0 > timeout:
                raise VNAError(f"Tiempo de espera agotado en el comando '{cmd}'.")
        lines = buf.decode(errors="replace").replace("\r", "").split("\n")
        return [ln for ln in lines if ln and not ln.startswith(cmd) and not ln.startswith("ch>")]

    def connect(self):
        try:
            import serial
        except ImportError as e:
            raise VNAError("pyserial no está instalado.") from e
        try:
            self.ser = serial.Serial(self.address, 115200, timeout=0.2)
        except Exception as e:  # noqa: BLE001
            raise VNAError(f"No se pudo abrir {self.address}: {e}") from e
        info = self._cmd("info", 3.0)
        if not info:
            self.disconnect()
            raise VNAError("El dispositivo no respondió al comando 'info': ¿es un NanoVNA?")
        self.idn = " | ".join(info[:3])
        return self.idn

    def disconnect(self):
        if self.ser:
            try:
                self.ser.close()
            finally:
                self.ser = None

    def configure_sweep(self, cfg: SweepConfig):
        self.validate_sweep(cfg)
        self._cmd(f"sweep {int(cfg.start_hz)} {int(cfg.stop_hz)} {int(cfg.points)}")
        self.sweep = cfg

    def capture(self, params):
        if not self.sweep:
            raise VNAError("Configure el barrido antes de capturar.")
        cfg = self.sweep
        rows = self._cmd(f"scan {int(cfg.start_hz)} {int(cfg.stop_hz)} {int(cfg.points)} 7", timeout=60)
        f, s11, s21 = [], [], []
        for r in rows:
            p = r.split()
            if len(p) == 5:
                f.append(float(p[0]))
                s11.append(complex(float(p[1]), float(p[2])))
                s21.append(complex(float(p[3]), float(p[4])))
        if len(f) != cfg.points:
            raise VNAError(f"Respuesta incompleta del NanoVNA: {len(f)} de {cfg.points} puntos.")
        data = {"S11": np.array(s11), "S21": np.array(s21)}
        return Capture(np.array(f), {k: v for k, v in data.items() if k in params}, self.idn, cfg)


# ───────────────────────── LibreVNA ─────────────────────────
class LibreVNADriver(VNADriver):
    info = DriverInfo(
        key="librevna", name="LibreVNA", vendor_family="LibreVNA (jankae)",
        interfaces=["USB (a través de LibreVNA-GUI)", "TCP/SCPI (servidor de LibreVNA-GUI, puerto 19542)"],
        protocol="SCPI sobre TCP", ports=2, params=["S11", "S21", "S12", "S22"], max_points=4501,
        calibration=["SOLT, TRL y otras gestionadas por LibreVNA-GUI (se usa la calibración activa)"],
        notes="Requiere LibreVNA-GUI en ejecución con el servidor SCPI habilitado.",
        address_hint="127.0.0.1:19542")

    def __init__(self, address):
        super().__init__(address or "127.0.0.1:19542")
        self.sock = None

    def _send(self, cmd):
        self.sock.sendall((cmd + "\n").encode())

    def _query(self, cmd, timeout=10.0):
        self._send(cmd)
        self.sock.settimeout(timeout)
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = self.sock.recv(65536)
            if not chunk:
                raise VNAError("Conexión cerrada por LibreVNA-GUI.")
            buf += chunk
        return buf.decode().strip()

    def connect(self):
        host, _, port = self.address.partition(":")
        try:
            self.sock = socket.create_connection((host, int(port or 19542)), timeout=3)
        except OSError as e:
            raise VNAError(f"No se pudo conectar con LibreVNA-GUI en {self.address}: {e}") from e
        self.idn = self._query("*IDN?")
        dev = self._query(":DEV:CONN?")
        if not dev or "not" in dev.lower():
            self.disconnect()
            raise VNAError("LibreVNA-GUI responde, pero no hay ningún LibreVNA conectado a la GUI.")
        self.idn += f" | dispositivo {dev}"
        return self.idn

    def disconnect(self):
        if self.sock:
            try:
                self.sock.close()
            finally:
                self.sock = None

    def configure_sweep(self, cfg):
        self.validate_sweep(cfg)
        self._send(":DEV:MODE VNA")
        self._send(":VNA:SWEEP FREQUENCY")
        self._send(f":VNA:FREQuency:START {cfg.start_hz:.0f}")
        self._send(f":VNA:FREQuency:STOP {cfg.stop_hz:.0f}")
        self._send(f":VNA:ACQuisition:POINTS {cfg.points}")
        if cfg.ifbw_hz:
            self._send(f":VNA:ACQuisition:IFBW {cfg.ifbw_hz:.0f}")
        if cfg.power_dbm is not None:
            self._send(f":VNA:STIMulus:LVL {cfg.power_dbm:.1f}")
        self.sweep = cfg

    def capture(self, params):
        if not self.sweep:
            raise VNAError("Configure el barrido antes de capturar.")
        t0 = time.time()
        while self._query(":VNA:ACQuisition:FINished?").upper() != "TRUE":
            if time.time() - t0 > 120:
                raise VNAError("El barrido no terminó en 120 s.")
            time.sleep(0.2)
        out, f = {}, None
        for p in params:
            raw = self._query(f":VNA:TRACe:DATA? {p}", timeout=30)
            tri = re.findall(r"\[([^\]]+)\]", raw)
            if not tri:
                raise VNAError(f"Respuesta no válida para {p}: {raw[:80]}")
            arr = np.array([[float(v) for v in t.split(",")] for t in tri])
            f = arr[:, 0]
            out[p] = arr[:, 1] + 1j * arr[:, 2]
        cal = self._query(":VNA:CALibration:ACTive?")
        return Capture(f, out, self.idn, self.sweep, instrument_cal_active=bool(cal and cal.lower() not in ("", "none")),
                       meta={"calibration": cal})


# ───────────────────────── SCPI genérico (VISA) ─────────────────────────
SCPI_PROFILES = {
    "keysight_ena": {
        "name": "Keysight ENA (E5061B/E5063A/E5071C)",
        "setup": ["SENS1:FREQ:STAR {start}", "SENS1:FREQ:STOP {stop}", "SENS1:SWE:POIN {points}"],
        "define": "CALC1:PAR1:DEF {param}", "select": "CALC1:PAR1:SEL", "trigger": ["INIT1:CONT OFF", "INIT1:IMM", "*OPC?"],
        "data": "CALC1:DATA:SDAT?", "freq": "SENS1:FREQ:DATA?"},
    "rs_znb": {
        "name": "Rohde & Schwarz ZNB/ZNA/ZNL",
        "setup": ["SENS1:FREQ:STAR {start}", "SENS1:FREQ:STOP {stop}", "SENS1:SWE:POIN {points}"],
        "define": "CALC1:PAR:SDEF 'RFWB_{param}','{param}'", "select": "CALC1:PAR:SEL 'RFWB_{param}'",
        "trigger": ["INIT1:CONT OFF", "INIT1:IMM", "*OPC?"], "data": "CALC1:DATA? SDAT", "freq": "CALC1:DATA:STIM?"},
    "coppermountain": {
        "name": "Copper Mountain (S2VNA/S4VNA, TCP 5025)",
        "setup": ["SENS1:FREQ:STAR {start}", "SENS1:FREQ:STOP {stop}", "SENS1:SWE:POIN {points}"],
        "define": "CALC1:PAR1:DEF {param}", "select": "CALC1:PAR1:SEL", "trigger": ["TRIG:SOUR BUS", "TRIG:SING", "*OPC?"],
        "data": "CALC1:DATA:SDAT?", "freq": "SENS1:FREQ:DATA?"},
}


class SCPIVisaDriver(VNADriver):
    info = DriverInfo(
        key="scpi", name="SCPI genérico (VISA)", vendor_family="Keysight / Rohde & Schwarz / Copper Mountain",
        interfaces=["LAN (TCPIP::host::INSTR / SOCKET)", "USB-TMC", "GPIB"], protocol="SCPI vía PyVISA",
        ports=4, params=["S11", "S21", "S12", "S22"], max_points=None,
        calibration=["Calibración del propio instrumento (SOLT, TRL, ECal…) — se informa su estado"],
        notes="Requiere un backend VISA (NI-VISA, Keysight IO Libraries o pyvisa-py). Perfil de comandos por familia.",
        address_hint="TCPIP0::192.168.1.50::inst0::INSTR  ·  TCPIP0::192.168.1.60::5025::SOCKET")

    def __init__(self, address, profile="keysight_ena"):
        super().__init__(address)
        if profile not in SCPI_PROFILES:
            raise VNAError(f"Perfil SCPI desconocido: {profile}")
        self.profile = SCPI_PROFILES[profile]
        self.inst = None

    def connect(self):
        try:
            import pyvisa
        except ImportError as e:
            raise VNAError("PyVISA no está instalado.") from e
        try:
            rm = pyvisa.ResourceManager()
        except Exception:  # noqa: BLE001
            try:
                rm = pyvisa.ResourceManager("@py")
            except Exception as e:  # noqa: BLE001
                raise VNAError("No hay backend VISA disponible (instale NI-VISA o pyvisa-py).") from e
        try:
            self.inst = rm.open_resource(self.address)
            self.inst.timeout = 20000
            if self.address.upper().endswith("SOCKET"):
                self.inst.read_termination = "\n"
                self.inst.write_termination = "\n"
            self.idn = self.inst.query("*IDN?").strip()
        except Exception as e:  # noqa: BLE001
            self.inst = None
            raise VNAError(f"No se pudo abrir {self.address}: {e}") from e
        return self.idn

    def disconnect(self):
        if self.inst:
            try:
                self.inst.close()
            finally:
                self.inst = None

    def configure_sweep(self, cfg):
        self.validate_sweep(cfg)
        for c in self.profile["setup"]:
            self.inst.write(c.format(start=f"{cfg.start_hz:.0f}", stop=f"{cfg.stop_hz:.0f}", points=cfg.points))
        self.sweep = cfg

    def capture(self, params):
        if not self.sweep:
            raise VNAError("Configure el barrido antes de capturar.")
        p = self.profile
        out = {}
        for c in p["trigger"]:
            (self.inst.query if c.endswith("?") else self.inst.write)(c)
        for prm in params:
            self.inst.write(p["define"].format(param=prm))
            self.inst.write(p["select"].format(param=prm))
            vals = np.array([float(v) for v in self.inst.query(p["data"]).strip().split(",")])
            out[prm] = vals[0::2] + 1j * vals[1::2]
        f = np.array([float(v) for v in self.inst.query(p["freq"]).strip().split(",")])
        err = self.inst.query("SYST:ERR?").strip()
        if not err.startswith(("+0", "0")):
            raise VNAError(f"El instrumento devolvió un error: {err}")
        return Capture(f, out, self.idn, self.sweep)


DRIVERS = {"nanovna": NanoVNADriver, "librevna": LibreVNADriver, "scpi": SCPIVisaDriver}
