from __future__ import annotations

import sys

from .base import ScreenCapture


def get_capture() -> ScreenCapture:
    if sys.platform == "win32":
        from .dxcam_impl import DxCamCapture

        return DxCamCapture()
    from .mss_impl import MssCapture

    return MssCapture()
