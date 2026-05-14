"""Fábrica de :class:`Motor`. Por enquanto, sempre ``ONNXMotor``."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import Motor


def get_motor() -> "Motor":
    from .onnx_impl import ONNXMotor

    return ONNXMotor()
