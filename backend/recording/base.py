"""Protocol e tipos do módulo recording."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable


@dataclass
class RecordingStatus:
    """Snapshot serializável do estado atual da gravação.

    Quando ``running`` é ``False`` mas ``recording_id`` está preenchido,
    significa "última gravação finalizada" — a UI usa pra mostrar o
    resumo (frame_count, fps real) sem precisar refetchar.
    """

    running: bool = False
    recording_id: int | None = None
    game_id: str | None = None
    fps_target: int = 0
    fps_real: float = 0.0
    frames_captured: int = 0
    started_at: datetime | None = None
    finished_at: datetime | None = None
    region: tuple[int, int, int, int] | None = None
    error: str | None = None


@runtime_checkable
class Recorder(Protocol):
    """Interface de uma gravação watch-me-play.

    Contrato:
    - ``start`` cria uma row em ``recordings`` e dispara a thread de
      captura; levanta :class:`RecorderBusyError` se já há gravação ativa
      e :class:`RecorderPermissionError` se o SO bloqueia o listener
      global (macOS Input Monitoring).
    - ``stop`` é idempotente: chamar com gravação parada devolve o
      status atual sem mexer.
    - ``status`` nunca levanta; pode ser chamado a qualquer momento.
    """

    def start(
        self,
        *,
        game_id: str,
        fps: int,
        region: tuple[int, int, int, int] | None,
    ) -> RecordingStatus: ...

    def stop(self) -> RecordingStatus: ...

    def status(self) -> RecordingStatus: ...
