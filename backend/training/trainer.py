"""Loop de treino + ONNX export.

Concorrência: ``Trainer.start`` cria uma ``asyncio.Task`` que delega o
trabalho pesado a ``asyncio.to_thread``. Status é publicado em
``_Status`` (protegido por ``threading.Lock``) e lido por
``/training/status``. Cancelamento via ``threading.Event``.

Detecção de dispositivo: tenta MPS (Mac) → CUDA → CPU. Um probe
sintético no startup detecta se o backend está OK; falha do MPS faz
fallback automático pra CPU com warning. Para a release Windows isto
seleciona CUDA quando disponível.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, random_split

from memory.connection import close_thread_connection, get_connection
from memory.paths import motor_models_dir
from memory.repos import motor_models_repo, recordings_repo

from .action_encoding import action_dim as _action_dim
from .base import Device, TrainConfig, TrainResult
from .dataset import RecordingDataset
from .errors import TrainerBusyError, TrainerCancelledError, TrainerError
from .model import PolicyNet
from .onnx_export import export_onnx

log = logging.getLogger("playia.training.trainer")


def _detect_device(prefer: Device | None) -> Device:
    if prefer is not None:
        return prefer
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def _probe_device(device: Device, img_size: int) -> Device:
    """Faz um forward sintético; se MPS quebrar, retorna 'cpu'."""
    try:
        m = PolicyNet(action_dim=4).to(device)
        with torch.no_grad():
            m(torch.zeros(1, 3, img_size, img_size, device=device))
        return device
    except Exception:  # noqa: BLE001
        if device == "mps":
            log.warning(
                "MPS probe falhou; fallback pra CPU (treino será mais lento)"
            )
            return "cpu"
        raise


class _Status:
    """Estado compartilhado entre o thread de treino e o endpoint de status."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.running = False
        self.recording_id: int | None = None
        self.game_id: str | None = None
        self.epoch = 0
        self.epochs_total = 0
        self.train_loss = 0.0
        self.val_loss = 0.0
        self.accuracy_keys = 0.0
        self.mse_mouse = 0.0
        self.eta_s = 0.0
        self.error: str | None = None
        self.cancelled = threading.Event()
        self.result: TrainResult | None = None
        self.loss_curve: list[float] = []
        self.val_loss_curve: list[float] = []


class Trainer:
    """Singleton do treinador. ``main.py`` segura uma instância."""

    def __init__(self) -> None:
        self._status = _Status()
        self._task: asyncio.Task[None] | None = None

    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    def status_snapshot(self) -> dict:
        s = self._status
        with s.lock:
            return {
                "running": s.running,
                "recording_id": s.recording_id,
                "game_id": s.game_id,
                "epoch": s.epoch,
                "epochs_total": s.epochs_total,
                "train_loss": s.train_loss,
                "val_loss": s.val_loss,
                "accuracy_keys": s.accuracy_keys,
                "mse_mouse": s.mse_mouse,
                "eta_s": s.eta_s,
                "error": s.error,
                "loss_curve": list(s.loss_curve),
                "val_loss_curve": list(s.val_loss_curve),
                "result": (
                    {
                        "motor_model_id": s.result.motor_model_id,
                        "onnx_path": s.result.onnx_path,
                        "accuracy_keys": s.result.accuracy_keys,
                        "mse_mouse": s.result.mse_mouse,
                        "training_time_s": s.result.training_time_s,
                    }
                    if s.result is not None
                    else None
                ),
            }

    async def start(
        self, recording_id: int, config: TrainConfig | None = None
    ) -> dict:
        if self.is_running():
            raise TrainerBusyError(
                "Já existe um treino em andamento. Cancele ou espere terminar."
            )
        cfg = config or TrainConfig()
        # reset
        new_status = _Status()
        new_status.running = True
        new_status.recording_id = recording_id
        new_status.epochs_total = cfg.epochs
        self._status = new_status
        self._task = asyncio.create_task(
            self._supervise(recording_id, cfg), name=f"trainer-{recording_id}"
        )
        return self.status_snapshot()

    async def cancel(self) -> dict:
        if self.is_running():
            self._status.cancelled.set()
        return self.status_snapshot()

    async def _supervise(self, recording_id: int, cfg: TrainConfig) -> None:
        try:
            result = await asyncio.to_thread(
                _train_blocking, recording_id, cfg, self._status
            )
        except TrainerCancelledError:
            log.info("treino cancelado rec_id=%d", recording_id)
            with self._status.lock:
                self._status.running = False
                self._status.error = "cancelado"
        except TrainerError as e:
            log.exception("treino falhou rec_id=%d", recording_id)
            with self._status.lock:
                self._status.running = False
                self._status.error = str(e)
        except Exception as e:  # noqa: BLE001
            log.exception("treino: erro inesperado rec_id=%d", recording_id)
            with self._status.lock:
                self._status.running = False
                self._status.error = f"inesperado: {e}"
        else:
            with self._status.lock:
                self._status.running = False
                self._status.result = result
        finally:
            close_thread_connection()


def _train_blocking(
    recording_id: int, cfg: TrainConfig, status: _Status
) -> TrainResult:
    """Roda dentro de asyncio.to_thread — pode levar minutos."""
    t0 = time.monotonic()

    conn = get_connection()
    rec = recordings_repo.get(conn, recording_id)
    if rec is None:
        raise TrainerError(f"recording {recording_id} não existe")
    with status.lock:
        status.game_id = rec.game_id

    dataset = RecordingDataset(recording_id, img_size=cfg.img_size)
    n_keys = len(dataset.allowed_keys)
    a_dim = dataset.action_dim

    # split
    n = len(dataset)
    val_size = max(1, int(n * cfg.val_split))
    train_size = n - val_size
    train_ds, val_ds = random_split(
        dataset,
        [train_size, val_size],
        generator=torch.Generator().manual_seed(42),
    )
    train_loader = DataLoader(
        train_ds, batch_size=cfg.batch_size, shuffle=True, num_workers=0
    )
    val_loader = DataLoader(
        val_ds, batch_size=cfg.batch_size, shuffle=False, num_workers=0
    )

    device = _probe_device(_detect_device(cfg.device), cfg.img_size)
    log.info(
        "treino rec_id=%d game=%s frames=%d action_dim=%d device=%s epochs=%d",
        recording_id, rec.game_id, n, a_dim, device, cfg.epochs,
    )

    model = PolicyNet(action_dim=a_dim, dropout=cfg.dropout).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=cfg.lr)

    def split_target(t: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        # devolve (bin, mouse, _) — onde bin é [keys + 2 clicks] e mouse é [dx, dy]
        keys = t[:, :n_keys]
        mouse = t[:, n_keys : n_keys + 2]
        clicks = t[:, n_keys + 2 : n_keys + 4]
        bin_ = torch.cat([keys, clicks], dim=1)
        return bin_, mouse, clicks  # clicks redundant; keep for clarity

    def compute_loss(logits: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        bin_t, mouse_t, _ = split_target(target)
        bin_l, mouse_l, _ = split_target(logits)
        bce = nn.functional.binary_cross_entropy_with_logits(bin_l, bin_t)
        mse = nn.functional.mse_loss(mouse_l, mouse_t)
        return bce + cfg.mouse_loss_weight * mse

    accuracy_keys = 0.0
    mse_mouse = 0.0

    for epoch in range(cfg.epochs):
        if status.cancelled.is_set():
            raise TrainerCancelledError()

        model.train()
        train_loss_acc = 0.0
        train_count = 0
        for frames, actions in train_loader:
            if status.cancelled.is_set():
                raise TrainerCancelledError()
            frames = frames.to(device)
            actions = actions.to(device)
            optimizer.zero_grad()
            logits = model(frames)
            loss = compute_loss(logits, actions)
            loss.backward()
            optimizer.step()
            bs = frames.size(0)
            train_loss_acc += loss.item() * bs
            train_count += bs

        model.eval()
        val_loss_acc = 0.0
        val_count = 0
        acc_keys_acc = 0.0
        mse_mouse_acc = 0.0
        with torch.no_grad():
            for frames, actions in val_loader:
                frames = frames.to(device)
                actions = actions.to(device)
                logits = model(frames)
                bs = frames.size(0)
                val_loss_acc += compute_loss(logits, actions).item() * bs
                val_count += bs
                key_probs = torch.sigmoid(logits[:, :n_keys])
                key_pred = (key_probs >= 0.5).float()
                acc_keys_acc += (key_pred == actions[:, :n_keys]).float().mean().item() * bs
                mouse_l = logits[:, n_keys : n_keys + 2]
                mouse_t = actions[:, n_keys : n_keys + 2]
                mse_mouse_acc += nn.functional.mse_loss(mouse_l, mouse_t).item() * bs

        train_loss = train_loss_acc / max(train_count, 1)
        val_loss = val_loss_acc / max(val_count, 1)
        accuracy_keys = acc_keys_acc / max(val_count, 1)
        mse_mouse = mse_mouse_acc / max(val_count, 1)
        elapsed = time.monotonic() - t0
        eta_s = elapsed / (epoch + 1) * (cfg.epochs - epoch - 1)

        with status.lock:
            status.epoch = epoch + 1
            status.train_loss = train_loss
            status.val_loss = val_loss
            status.accuracy_keys = accuracy_keys
            status.mse_mouse = mse_mouse
            status.eta_s = eta_s
            status.loss_curve.append(train_loss)
            status.val_loss_curve.append(val_loss)

        log.info(
            "epoch %d/%d train=%.4f val=%.4f acc_keys=%.3f mse_mouse=%.4f eta=%.1fs",
            epoch + 1, cfg.epochs, train_loss, val_loss, accuracy_keys, mse_mouse, eta_s,
        )

    # export ONNX
    motor_dir: Path = motor_models_dir() / rec.game_id
    motor_dir.mkdir(parents=True, exist_ok=True)
    onnx_path = motor_dir / f"{recording_id}_{int(time.time())}.onnx"
    try:
        export_onnx(model, onnx_path, img_size=cfg.img_size)
    except Exception as e:  # noqa: BLE001
        raise TrainerError(f"falha ao exportar ONNX: {e}") from e

    motor = motor_models_repo.create(
        get_connection(),
        game_id=rec.game_id,
        recording_id=recording_id,
        onnx_path=str(onnx_path),
        accuracy=accuracy_keys,
    )
    log.info(
        "treino concluído rec_id=%d motor_id=%s onnx=%s",
        recording_id, motor.id, onnx_path,
    )

    return TrainResult(
        motor_model_id=int(motor.id),
        onnx_path=str(onnx_path),
        accuracy_keys=accuracy_keys,
        mse_mouse=mse_mouse,
        training_time_s=time.monotonic() - t0,
    )
