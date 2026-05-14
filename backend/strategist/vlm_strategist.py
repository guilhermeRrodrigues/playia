"""Estrategista VLM — placeholder M7.1.

Esta versão devolve uma intenção genérica ("observar o jogo") sem chamar
o VLM. O M7.2 substitui por uma chamada real ao
:mod:`vision.ollama_impl` com prompt focado em intenção de alto nível.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .base import Intention

if TYPE_CHECKING:
    from vision.base import VLMProvider

log = logging.getLogger("playia.strategist.vlm")


class VLMStrategist:
    def __init__(self, vlm: "VLMProvider") -> None:
        self._vlm = vlm

    async def decide(
        self,
        frame_png: bytes,
        goal: str,
        history: list[Intention],
    ) -> Intention:
        # TODO(M7.2): chamar self._vlm.describe(...) com prompt focado em
        # INTENÇÃO de alto nível em pt-br + few-shots; parsear JSON
        # {text, ttl_s}.
        _ = (frame_png, goal, history)
        return Intention(
            text="observar o jogo (VLM ainda não plugado — placeholder M7.1)",
            ttl_s=10.0,
        )
