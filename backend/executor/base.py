"""Interface do executor de input — abstrai pyautogui/pydirectinput."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class InputExecutor(Protocol):
    """Executa ações de teclado e mouse no SO.

    Todas as operações são síncronas (rodam fora do event loop via
    ``asyncio.to_thread`` no engine). Erros tipados estão em
    :mod:`executor.errors`.

    Semântica:
    - ``key_tap`` — press + release imediato (usado pelo loop turn-based,
      M3).
    - ``key_press`` / ``key_release`` — mantém a tecla pressionada até a
      release; usado pelo loop hierárquico (M7) pra segurar Space ou
      direções enquanto o motor model prediz o estado contínuo.
    - ``click`` — clique único na posição absoluta.
    - ``mouse_move_rel`` — desloca o cursor por (dx, dy) pixels do ponto
      atual. Usado por jogos com mira (futuro M7+).
    - ``wait`` — sleep síncrono em milissegundos.
    """

    def key_tap(self, key: str) -> None: ...

    def key_press(self, key: str) -> None: ...

    def key_release(self, key: str) -> None: ...

    def click(self, x: int, y: int) -> None: ...

    def mouse_move_rel(self, dx: int, dy: int) -> None: ...

    def wait(self, ms: int) -> None: ...
