"""Estado público da sessão — exposto via /session/status."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from planner.actions import Action

SessionStatus = Literal["idle", "running", "paused", "stopped", "error"]
StopReason = Literal[
    "user", "max_actions", "max_duration", "game_over", "error", "vlm_unavailable"
]


@dataclass
class SessionState:
    """Snapshot mutável da sessão atual.

    Lido pelo endpoint /session/status; cópia rasa é feita pelo engine
    para evitar mutações concorrentes durante a serialização HTTP.
    """

    status: SessionStatus = "idle"
    game: str | None = None
    region: tuple[int, int, int, int] | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    actions_taken: int = 0
    last_action: Action | None = None
    last_reason: str | None = None
    history: list[Action] = field(default_factory=list)
    last_screenshot_b64: str | None = None
    stop_reason: StopReason | None = None
    error: str | None = None

    def reset(self) -> None:
        """Volta ao estado idle, mantendo o objeto referenciado pelo engine."""
        self.status = "idle"
        self.game = None
        self.region = None
        self.started_at = None
        self.finished_at = None
        self.actions_taken = 0
        self.last_action = None
        self.last_reason = None
        self.history = []
        self.last_screenshot_b64 = None
        self.stop_reason = None
        self.error = None
