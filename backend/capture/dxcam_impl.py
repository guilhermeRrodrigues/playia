# TODO(windows-only): validar em Windows real quando o CI estiver no ar (M8).
"""Captura via dxcam — Windows-only, alta performance (DXGI).

Import opcional: `dxcam` não instala em macOS/Linux, então a importação
fica protegida e a classe levanta erro claro se for instanciada fora do
Windows. O `factory` só escolhe esta implementação se `sys.platform == 'win32'`.
"""

from __future__ import annotations

import sys
from io import BytesIO

try:
    import dxcam  # type: ignore[import-not-found]
except ImportError:
    dxcam = None  # type: ignore[assignment]


class DxCamCapture:
    def __init__(self) -> None:
        if sys.platform != "win32" or dxcam is None:
            raise NotImplementedError(
                "DxCamCapture só funciona em Windows. "
                "No Mac/Linux o factory usa MssCapture."
            )
        # `output_color="RGB"` devolve frame RGB pronto para PIL.
        self._camera = dxcam.create(output_color="RGB")

    def grab(self) -> bytes:
        from PIL import Image  # import tardio: evita custo no Mac

        frame = self._camera.grab()
        if frame is None:
            # dxcam devolve None se o frame ainda não mudou; tentar de novo.
            frame = self._camera.grab()
        if frame is None:
            raise RuntimeError("dxcam não retornou frame (timeout)")
        img = Image.fromarray(frame)
        buf = BytesIO()
        img.save(buf, format="PNG", compress_level=3)
        return buf.getvalue()
