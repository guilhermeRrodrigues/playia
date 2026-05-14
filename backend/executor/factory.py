"""Seleciona a implementação de InputExecutor adequada ao SO."""

from __future__ import annotations

from .base import InputExecutor


def get_executor() -> InputExecutor:
    # Hoje pyautogui cobre Mac/Linux/Windows. No futuro (M+), Windows
    # pode trocar para pydirectinput em jogos com DirectInput.
    from .pyautogui_impl import PyAutoGuiExecutor

    return PyAutoGuiExecutor()
