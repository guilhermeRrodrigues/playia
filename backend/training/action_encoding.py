"""Codificação/decodificação do vetor de ação.

Formato (ordenado por convenção, mesmo no train e no inference):

  [is_key_0, is_key_1, …, is_key_{N-1},   # binárias (BCE)
   mouse_dx_norm, mouse_dy_norm,          # contínuas (MSE)
   click_left, click_right]               # binárias (BCE)

onde ``allowed_keys`` define N e a ordem. ``mouse_dx_norm`` é
``clip(dx / MOUSE_NORM, -1, 1)``; defina ``MOUSE_NORM`` conforme a
escala típica do jogo (200 px/frame suporta mira rápida sem saturar).
"""

from __future__ import annotations

import numpy as np

MOUSE_NORM = 200.0


def action_dim(allowed_keys: list[str]) -> int:
    """Tamanho do vetor de ação para ``allowed_keys`` dado."""
    return len(allowed_keys) + 4  # +dx +dy +click_left +click_right


def encode(
    *,
    allowed_keys: list[str],
    keys_down: list[str],
    mouse_dx: int,
    mouse_dy: int,
    mouse_buttons: list[str],
) -> np.ndarray:
    n = len(allowed_keys)
    out = np.zeros(n + 4, dtype=np.float32)
    keys_set = set(keys_down)
    for i, k in enumerate(allowed_keys):
        if k in keys_set:
            out[i] = 1.0
    out[n] = float(np.clip(mouse_dx / MOUSE_NORM, -1.0, 1.0))
    out[n + 1] = float(np.clip(mouse_dy / MOUSE_NORM, -1.0, 1.0))
    mbtns = set(mouse_buttons)
    out[n + 2] = 1.0 if "MouseLeft" in mbtns else 0.0
    out[n + 3] = 1.0 if "MouseRight" in mbtns else 0.0
    return out


def decode_keys(
    logits: np.ndarray, allowed_keys: list[str], *, threshold: float = 0.5
) -> list[str]:
    """Aplica sigmoid e devolve as teclas cuja probabilidade ≥ threshold."""
    n = len(allowed_keys)
    probs = 1.0 / (1.0 + np.exp(-logits[:n]))
    return [k for k, p in zip(allowed_keys, probs.tolist(), strict=False) if p >= threshold]


def decode_mouse(
    logits: np.ndarray, allowed_keys: list[str], *, click_threshold: float = 0.5
) -> tuple[int, int, bool, bool]:
    """Decodifica ``(dx, dy, click_left, click_right)`` do vetor de ação."""
    n = len(allowed_keys)
    dx = float(logits[n]) * MOUSE_NORM
    dy = float(logits[n + 1]) * MOUSE_NORM
    cl_p = 1.0 / (1.0 + np.exp(-float(logits[n + 2])))
    cr_p = 1.0 / (1.0 + np.exp(-float(logits[n + 3])))
    return int(dx), int(dy), cl_p >= click_threshold, cr_p >= click_threshold
