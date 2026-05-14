"""PyTorch ``Dataset`` que materializa um recording como pares (frame, action).

Cada amostra:
- ``frame``: tensor float32 (3, img_size, img_size) normalizado [0, 1].
- ``action``: tensor float32 ``action_dim`` (binárias + 2 contínuas).

Mouse deltas (``dx``, ``dy``) são pré-computados em ``__init__`` lendo a
sequência inteira do DB. PIL faz o resize bilinear; preferimos isso a
torchvision pra manter o pacote PyInstaller mais magro no M10.
"""

from __future__ import annotations

import logging

import numpy as np
import torch
from PIL import Image
from torch.utils.data import Dataset

from memory.connection import get_connection
from memory.repos import games_repo, recording_frames_repo, recordings_repo

from .action_encoding import action_dim, encode
from .errors import TrainerDatasetError

log = logging.getLogger("playia.training.dataset")


class RecordingDataset(Dataset):
    def __init__(self, recording_id: int, *, img_size: int = 128) -> None:
        self.recording_id = recording_id
        self.img_size = img_size

        conn = get_connection()
        rec = recordings_repo.get(conn, recording_id)
        if rec is None:
            raise TrainerDatasetError(f"recording {recording_id} não existe")
        game = games_repo.get(conn, rec.game_id)
        if game is None:
            raise TrainerDatasetError(
                f"game {rec.game_id} (da recording {recording_id}) não existe"
            )

        self.game_id = game.id
        self.allowed_keys = list(game.allowed_keys)
        self.action_dim = action_dim(self.allowed_keys)

        self.frames = recording_frames_repo.list_by_recording(conn, recording_id)
        if len(self.frames) < 2:
            raise TrainerDatasetError(
                f"recording {recording_id} tem menos de 2 frames; impossível treinar"
            )

        # pré-computa (dx, dy) por frame, primeiro frame é (0, 0)
        self._dxdys: list[tuple[int, int]] = [(0, 0)]
        for i in range(1, len(self.frames)):
            prev = self.frames[i - 1]
            cur = self.frames[i]
            dx = (cur.mouse_x or 0) - (prev.mouse_x or 0)
            dy = (cur.mouse_y or 0) - (prev.mouse_y or 0)
            self._dxdys.append((dx, dy))

        log.info(
            "dataset rec_id=%d game=%s frames=%d action_dim=%d",
            recording_id,
            game.id,
            len(self.frames),
            self.action_dim,
        )

    def __len__(self) -> int:
        return len(self.frames)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
        f = self.frames[idx]
        dx, dy = self._dxdys[idx]
        with Image.open(f.frame_path) as raw:
            img = raw.convert("RGB").resize(
                (self.img_size, self.img_size), Image.BILINEAR
            )
        arr = np.asarray(img, dtype=np.float32) / 255.0  # H, W, C
        arr = arr.transpose(2, 0, 1)  # C, H, W
        frame_tensor = torch.from_numpy(arr.copy())
        action_arr = encode(
            allowed_keys=self.allowed_keys,
            keys_down=f.keys_down,
            mouse_dx=dx,
            mouse_dy=dy,
            mouse_buttons=f.mouse_buttons,
        )
        return frame_tensor, torch.from_numpy(action_arr)
