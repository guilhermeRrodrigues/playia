"""Protocol e tipos do módulo motor."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class MotorMeta:
    """Metadados do motor model carregado em memória."""

    motor_model_id: int
    game_id: str
    onnx_path: str
    accuracy: float
    allowed_keys: list[str]
    img_size: int


@dataclass
class MotorAction:
    """Ação prevista pelo motor model a partir de um frame.

    Os campos binários (``keys_down``, ``click_*``) são decodificados via
    sigmoid + threshold; ``mouse_dx/dy`` são valores absolutos em pixels
    (já desnormalizados pela escala MOUSE_NORM do training.action_encoding).
    """

    keys_down: list[str]
    mouse_dx: int
    mouse_dy: int
    click_left: bool
    click_right: bool
    raw_logits: list[float] = field(default_factory=list)
    latency_ms: float = 0.0


@runtime_checkable
class Motor(Protocol):
    """Inferência de motor model treinado por behavioral cloning."""

    def load_for_game(self, game_id: str) -> MotorMeta: ...

    def predict(self, frame_png: bytes) -> MotorAction: ...

    def is_loaded(self) -> bool: ...

    def loaded_metadata(self) -> MotorMeta | None: ...
