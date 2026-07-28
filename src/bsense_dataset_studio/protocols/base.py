from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Step:
    name: str
    duration_s: float | None
    instruction: str
    marker: str


@dataclass(frozen=True)
class Protocol:
    task: str
    display_name: str
    category: str
    version: str
    steps: tuple[Step, ...]
