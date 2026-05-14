"""Tipos compartilhados do loop hierárquico."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

HSessionStatus = Literal["idle", "running", "stopped", "error"]


@dataclass
class Intention:
    """Intenção de alto nível publicada pelo estrategista.

    O motor pode (M+) usar o ``text`` como input adicional; em v0.1 só
    fica no log e na UI.
    """

    text: str
    params: dict[str, Any] = field(default_factory=dict)
    issued_at: datetime = field(default_factory=datetime.now)
    ttl_s: float = 10.0


@dataclass
class HierarchicalState:
    """Snapshot do loop hierárquico — exposto via /hsession/status."""

    status: HSessionStatus = "idle"
    game: str | None = None
    region: tuple[int, int, int, int] | None = None
    motor_model_id: int | None = None
    motor_accuracy: float | None = None
    current_intention: Intention | None = None
    intentions_history: list[Intention] = field(default_factory=list)
    actions_per_second: float = 0.0
    total_actions: int = 0
    last_frame_b64: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    stop_reason: str | None = None
    error: str | None = None
