"""Configuração e resultado do treinador."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Device = Literal["mps", "cuda", "cpu"]


@dataclass
class TrainConfig:
    """Hiperparâmetros do treino. Defaults sãos pra 5-10 min em Mac M-series."""

    epochs: int = 20
    batch_size: int = 32
    lr: float = 1e-3
    img_size: int = 128
    val_split: float = 0.2
    device: Device | None = None
    """``None`` faz auto-detecção (MPS > CUDA > CPU)."""

    dropout: float = 0.2
    mouse_loss_weight: float = 0.5
    """Peso do MSE de mouse_dx/dy vs BCE de keys+clicks no loss combinado."""


@dataclass
class TrainResult:
    """Devolvido ao terminar com sucesso. Persistido em ``motor_models``."""

    motor_model_id: int
    onnx_path: str
    accuracy_keys: float
    mse_mouse: float
    training_time_s: float
    loss_curve: list[float] = field(default_factory=list)
    val_loss_curve: list[float] = field(default_factory=list)
