"""Seleciona a implementação de Planner. Hoje sempre ``VLMPlanner``."""

from __future__ import annotations

from vision.factory import get_vlm

from .base import Planner
from .vlm_planner import VLMPlanner


def get_planner() -> Planner:
    return VLMPlanner(get_vlm())
