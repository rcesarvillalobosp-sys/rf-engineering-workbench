"""Arquitectura de drivers VNA. Cada driver habla el protocolo REAL del instrumento.
No existe ningún driver "simulado": sin instrumento, la aplicación trabaja en modo simulación
con datos calculados o importados, claramente etiquetados.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field

import numpy as np


class VNAError(RuntimeError):
    pass


@dataclass
class DriverInfo:
    key: str
    name: str
    vendor_family: str
    interfaces: list[str]
    protocol: str
    ports: int
    params: list[str]
    max_points: int | None
    calibration: list[str]
    verified_with_hardware: bool = False
    notes: str = ""
    address_hint: str = ""

    def to_dict(self):
        return asdict(self)


@dataclass
class SweepConfig:
    start_hz: float
    stop_hz: float
    points: int
    ifbw_hz: float | None = None
    power_dbm: float | None = None


@dataclass
class Capture:
    f: np.ndarray
    s: dict[str, np.ndarray]  # "S11" -> complejo
    idn: str
    sweep: SweepConfig
    instrument_cal_active: bool | None = None
    meta: dict = field(default_factory=dict)


class VNADriver(ABC):
    info: DriverInfo

    def __init__(self, address: str):
        self.address = address
        self.idn = ""
        self.sweep: SweepConfig | None = None

    @abstractmethod
    def connect(self) -> str: ...

    @abstractmethod
    def disconnect(self) -> None: ...

    @abstractmethod
    def configure_sweep(self, cfg: SweepConfig) -> None: ...

    @abstractmethod
    def capture(self, params: list[str]) -> Capture: ...

    def validate_sweep(self, cfg: SweepConfig):
        if cfg.stop_hz <= cfg.start_hz:
            raise VNAError("La frecuencia final debe ser mayor que la inicial.")
        if cfg.points < 2:
            raise VNAError("Se requieren al menos 2 puntos.")
        if self.info.max_points and cfg.points > self.info.max_points:
            raise VNAError(f"Este instrumento admite como máximo {self.info.max_points} puntos.")
