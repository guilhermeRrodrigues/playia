from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class ScreenCapture(Protocol):
    """Interface mínima para uma captura de tela.

    Retorna PNG bytes prontos para serem servidos via HTTP ou
    enviados a um VLM.
    """

    def grab(self) -> bytes: ...
