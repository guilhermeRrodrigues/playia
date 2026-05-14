from __future__ import annotations

from typing import Protocol, runtime_checkable

Region = tuple[int, int, int, int]
"""(x, y, width, height) em pixels do monitor primário."""


@runtime_checkable
class ScreenCapture(Protocol):
    """Interface mínima para uma captura de tela.

    Retorna PNG bytes prontos para serem servidos via HTTP ou
    enviados a um VLM.

    Se ``region`` for ``None`` (default), captura a tela inteira do
    monitor primário. Caso contrário, recorta a região especificada.
    """

    def grab(self, region: Region | None = None) -> bytes: ...
