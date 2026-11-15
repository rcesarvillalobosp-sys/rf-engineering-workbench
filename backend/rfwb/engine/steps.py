"""Traza educativa: cada cálculo registra fórmula, sustitución, resultado e interpretación."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class Step:
    title: str
    formula: str
    substitution: str = ""
    result: str = ""
    unit: str = ""
    note: str = ""


@dataclass
class Trace:
    steps: list[Step] = field(default_factory=list)

    def add(self, title: str, formula: str, substitution: str = "", result: str = "",
            unit: str = "", note: str = "") -> None:
        self.steps.append(Step(title, formula, substitution, result, unit, note))

    def extend(self, other: "Trace") -> None:
        self.steps.extend(other.steps)

    def to_list(self) -> list[dict]:
        return [asdict(s) for s in self.steps]
