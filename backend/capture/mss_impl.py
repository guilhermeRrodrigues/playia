"""Captura via mss — usado em macOS/Linux (e como fallback no Windows)."""

from __future__ import annotations

from io import BytesIO

import mss
from PIL import Image


class MssCapture:
    """Captura o monitor primário e devolve PNG bytes.

    Reuso da instância de `mss.mss()` é seguro entre chamadas e
    evita o custo de re-inicializar o backend a cada captura.
    """

    def __init__(self) -> None:
        self._sct = mss.mss()

    def grab(self) -> bytes:
        # mss numera monitores a partir de 1; índice 0 = "todos juntos".
        monitor = self._sct.monitors[1]
        shot = self._sct.grab(monitor)
        img = Image.frombytes("RGB", shot.size, shot.rgb)
        buf = BytesIO()
        img.save(buf, format="PNG", compress_level=3)
        return buf.getvalue()
