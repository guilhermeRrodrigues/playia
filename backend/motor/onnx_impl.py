"""Inferência ONNX em CPU via onnxruntime.

Cache: ``load_for_game`` mantém uma única ``InferenceSession`` por
processo, substituída quando outro jogo é solicitado. Preprocess +
postprocess espelham o que ``training.action_encoding`` e
``training.dataset`` fazem — qualquer mudança lá tem que vir aqui.
"""

from __future__ import annotations

import io
import logging
import time
from pathlib import Path

import numpy as np
import onnxruntime as ort
from PIL import Image

from memory.connection import get_connection
from memory.repos import games_repo, motor_models_repo
from training.action_encoding import decode_keys, decode_mouse

from .base import MotorAction, MotorMeta
from .errors import MotorInferenceError, MotorNotFoundError

log = logging.getLogger("playia.motor")


class ONNXMotor:
    def __init__(self) -> None:
        self._session: ort.InferenceSession | None = None
        self._meta: MotorMeta | None = None
        self._input_name: str = "frame"

    def is_loaded(self) -> bool:
        return self._session is not None

    def loaded_metadata(self) -> MotorMeta | None:
        return self._meta

    def load_for_game(self, game_id: str) -> MotorMeta:
        conn = get_connection()
        game = games_repo.get(conn, game_id)
        if game is None:
            raise MotorNotFoundError(f"jogo {game_id!r} não existe no catálogo")

        motor = motor_models_repo.get_latest_for_game(conn, game_id)
        if motor is None:
            raise MotorNotFoundError(
                f"nenhum motor_model treinado para {game_id!r}. "
                f"Grave uma sessão em /record e treine em /train antes."
            )

        onnx_path = Path(motor.onnx_path)
        if not onnx_path.exists():
            raise MotorNotFoundError(
                f"motor_model #{motor.id} aponta para {onnx_path}, "
                f"mas o arquivo não existe em disco."
            )

        try:
            self._session = ort.InferenceSession(
                str(onnx_path),
                providers=["CPUExecutionProvider"],
            )
        except Exception as e:  # noqa: BLE001
            raise MotorInferenceError(f"falha ao carregar ONNX {onnx_path}: {e}") from e

        self._input_name = self._session.get_inputs()[0].name
        # tenta inferir img_size do shape de entrada; default 128.
        try:
            shape = self._session.get_inputs()[0].shape  # [B, 3, H, W]
            h = shape[2]
            img_size = int(h) if isinstance(h, int) and h > 0 else 128
        except Exception:  # noqa: BLE001
            img_size = 128

        self._meta = MotorMeta(
            motor_model_id=int(motor.id),
            game_id=game.id,
            onnx_path=str(onnx_path),
            accuracy=float(motor.accuracy),
            allowed_keys=list(game.allowed_keys),
            img_size=img_size,
        )
        log.info(
            "motor carregado motor_id=%d game=%s img_size=%d allowed_keys=%d",
            motor.id, game.id, img_size, len(game.allowed_keys),
        )
        return self._meta

    def predict(self, frame_png: bytes) -> MotorAction:
        if self._session is None or self._meta is None:
            raise MotorInferenceError(
                "motor não carregado; chame load_for_game(game_id) antes."
            )

        t0 = time.monotonic()
        with Image.open(io.BytesIO(frame_png)) as raw:
            img = raw.convert("RGB").resize(
                (self._meta.img_size, self._meta.img_size), Image.BILINEAR
            )
        arr = np.asarray(img, dtype=np.float32) / 255.0
        arr = arr.transpose(2, 0, 1)  # C, H, W
        arr = np.expand_dims(arr, 0)  # 1, C, H, W

        try:
            outputs = self._session.run(None, {self._input_name: arr})
        except Exception as e:  # noqa: BLE001
            raise MotorInferenceError(f"inferência ONNX falhou: {e}") from e

        logits = outputs[0][0]  # remove batch
        keys = decode_keys(logits, self._meta.allowed_keys)
        dx, dy, cl, cr = decode_mouse(logits, self._meta.allowed_keys)
        return MotorAction(
            keys_down=keys,
            mouse_dx=dx,
            mouse_dy=dy,
            click_left=cl,
            click_right=cr,
            raw_logits=logits.tolist(),
            latency_ms=(time.monotonic() - t0) * 1000.0,
        )
