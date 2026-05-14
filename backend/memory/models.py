"""Schemas pydantic dos registros persistidos no SQLite.

Estes são modelos de **dados** (representação Pythonica das linhas).
Schemas de **request/response** dos endpoints HTTP ficam em ``main.py``
(eles compõem estes modelos com validações específicas).

Convenção de serialização: colunas JSON do DB têm sufixo ``_json``
(ex.: ``allowed_keys_json``); os campos pydantic equivalentes expõem
listas/dicts (ex.: ``allowed_keys: list[str]``). A conversão acontece
no repositório, **não** no schema, pra não vazar SQLite pra fora.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class Tempo(StrEnum):
    """Como o jogo se move no tempo — determina qual modo de play roda.

    - ``TURN_BASED``: VLM-no-loop é suficiente (M3). Ex.: 2048, xadrez.
    - ``SLOW_REALTIME``: VLM-no-loop com cadência 1-2 Hz pode jogar (M7).
    - ``FAST_REALTIME``: exige loop hierárquico VLM+motor (M7). Ex.: Dino,
      99 Nights, plataformers, FPS.
    """

    TURN_BASED = "turn_based"
    SLOW_REALTIME = "slow_realtime"
    FAST_REALTIME = "fast_realtime"


class AntiCheat(StrEnum):
    """Anti-cheat conhecido do jogo.

    Qualquer valor != ``NONE`` faz a UI bloquear sessão por padrão
    (RISCO REAL de ban — ver CLAUDE.md → Segurança e ética).
    """

    NONE = "none"
    UNKNOWN = "unknown"
    HYPERION = "hyperion"
    EAC = "eac"
    BATTLEYE = "battleye"
    VANGUARD = "vanguard"
    OTHER = "other"


class Game(BaseModel):
    """Perfil de um jogo conhecido pelo PlayIA."""

    id: str
    name: str
    url: str
    tempo: Tempo
    anti_cheat: AntiCheat
    allowed_keys: list[str] = Field(default_factory=list)
    goal: str
    notes: str | None = None
    created_at: datetime | None = None


class Recording(BaseModel):
    """Sessão de watch-me-play. Materializada em M5."""

    id: int | None = None
    game_id: str
    started_at: datetime | None = None
    ended_at: datetime | None = None
    fps: int
    frame_count: int = 0
    notes: str | None = None


class RecordingFrame(BaseModel):
    """Frame único de uma gravação (sem o PNG; ``frame_path`` aponta pra ele)."""

    recording_id: int
    ts_ms: int
    frame_path: str
    keys_down: list[str] = Field(default_factory=list)
    mouse_x: int | None = None
    mouse_y: int | None = None
    mouse_buttons: list[str] = Field(default_factory=list)


class MotorModel(BaseModel):
    """Motor model ONNX treinado por behavioral cloning (M6)."""

    id: int | None = None
    game_id: str
    recording_id: int
    onnx_path: str
    accuracy: float
    trained_at: datetime | None = None
    version: int = 1


class Episode(BaseModel):
    """Evento individual de play (estado → ação → recompensa)."""

    id: int | None = None
    game_id: str
    ts: datetime | None = None
    state_text: str
    action_json: str
    reward: float | None = None
    screenshot_path: str | None = None


class Skill(BaseModel):
    """Sequência de ações nomeada, invocável diretamente pelo VLM (M8)."""

    id: int | None = None
    game_id: str
    name: str
    description: str
    action_sequence_json: str
    success_rate: float = 0.0
    times_used: int = 0
    embedding: bytes | None = None
    created_at: datetime | None = None


class Knowledge(BaseModel):
    """Fato semântico aprendido sobre um jogo (M8)."""

    id: int | None = None
    game_id: str
    fact: str
    source: str | None = None
    embedding: bytes | None = None
    created_at: datetime | None = None
