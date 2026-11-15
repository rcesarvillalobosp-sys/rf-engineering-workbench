"""Gestor de instrumento: detección, conexión única y etiquetado del modo de datos."""
from __future__ import annotations

import socket
import threading

from .base import SweepConfig, VNAError
from .drivers import DRIVERS, SCPI_PROFILES, NanoVNADriver

LABEL_SIM = "Sin instrumento conectado — Modo de simulación"
LABEL_REAL = "Medición real — VNA conectado"


class VNAManager:
    def __init__(self):
        self.driver = None
        self.last = None  # última captura (para guardar desde el modo continuo)
        self.lock = threading.Lock()

    def status(self) -> dict:
        if self.driver is None:
            return {"connected": False, "mode": "simulation", "label": LABEL_SIM}
        d = self.driver
        return {"connected": True, "mode": "measured", "label": LABEL_REAL, "driver": d.info.key,
                "driver_name": d.info.name, "address": d.address, "idn": d.idn,
                "sweep": vars(d.sweep) if d.sweep else None}

    def drivers(self) -> dict:
        return {"drivers": [cls.info.to_dict() for cls in DRIVERS.values()],
                "scpi_profiles": {k: v["name"] for k, v in SCPI_PROFILES.items()}}

    def scan(self) -> dict:
        found, notes = [], []
        try:
            from serial.tools import list_ports
            for p in list_ports.comports():
                is_nano = (p.vid, p.pid) in NanoVNADriver.USB_IDS
                found.append({"interface": "serial", "address": p.device, "description": p.description,
                              "vid_pid": f"{p.vid:04X}:{p.pid:04X}" if p.vid else None,
                              "suggested_driver": "nanovna" if is_nano else None})
        except Exception as e:  # noqa: BLE001
            notes.append(f"No se pudieron enumerar puertos serie: {e}")
        try:
            s = socket.create_connection(("127.0.0.1", 19542), timeout=0.3)
            s.close()
            found.append({"interface": "tcp", "address": "127.0.0.1:19542", "description": "Servidor SCPI de LibreVNA-GUI",
                          "suggested_driver": "librevna"})
        except OSError:
            notes.append("LibreVNA-GUI no detectado en 127.0.0.1:19542.")
        try:
            import pyvisa
            rm = pyvisa.ResourceManager()
            for r in rm.list_resources():
                found.append({"interface": "visa", "address": r, "description": "Recurso VISA", "suggested_driver": "scpi"})
        except Exception as e:  # noqa: BLE001
            notes.append(f"VISA no disponible: {type(e).__name__}. Instale NI-VISA / Keysight IO Libraries o pyvisa-py para LAN/USB-TMC.")
        return {"devices": found, "notes": notes}

    def connect(self, driver: str, address: str, profile: str | None = None) -> dict:
        with self.lock:
            if self.driver is not None:
                raise VNAError("Ya hay un instrumento conectado. Desconéctelo primero.")
            if driver not in DRIVERS:
                raise VNAError(f"Driver desconocido: {driver}")
            d = DRIVERS[driver](address, profile) if driver == "scpi" else DRIVERS[driver](address)
            d.connect()
            self.driver = d
        return self.status()

    def disconnect(self) -> dict:
        with self.lock:
            if self.driver:
                self.driver.disconnect()
            self.driver = None
            self.last = None
        return self.status()

    def configure(self, cfg: SweepConfig) -> dict:
        if not self.driver:
            raise VNAError(LABEL_SIM + ": no se puede configurar un barrido.")
        self.driver.configure_sweep(cfg)
        return self.status()

    def capture(self, params: list[str]):
        if not self.driver:
            raise VNAError(LABEL_SIM + ": no hay datos de instrumento que capturar.")
        bad = [p for p in params if p not in self.driver.info.params]
        if bad:
            raise VNAError(f"Este instrumento no mide {', '.join(bad)}.")
        with self.lock:  # un único barrido a la vez sobre el instrumento
            cap = self.driver.capture(params)
        self.last = cap
        return cap


MANAGER = VNAManager()
