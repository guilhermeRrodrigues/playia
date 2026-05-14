"""Interface do executor de input — abstrai pyautogui/pydirectinput."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class InputExecutor(Protocol):
    """Executa ações de teclado e mouse no SO.

    Todas as operações são síncronas (rodam fora do event loop via
    ``asyncio.to_thread`` no ``SessionEngine``). Erros tipados estão em
    :mod:`executor.errors`.
    """

    def key_tap(self, key: str) -> None: ...

    def click(self, x: int, y: int) -> None: ...

    def wait(self, ms: int) -> None: ...
