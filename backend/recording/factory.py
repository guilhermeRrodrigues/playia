"""Fábrica de :class:`Recorder`. Por enquanto, sempre ``PynputRecorder``."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from capture.base import ScreenCapture

    from .base import Recorder


def get_recorder(capture: "ScreenCapture") -> "Recorder":
    # TODO(M+): suportar backends alternativos (XInput no Linux,
    # SendInput-only no Windows quando pynput tiver problemas).
    from .pynput_impl import PynputRecorder

    return PynputRecorder(capture)
