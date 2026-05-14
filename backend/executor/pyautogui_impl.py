"""Executor default — usa pyautogui (cross-platform)."""

from __future__ import annotations

import sys
import time

import pyautogui

from .errors import ExecutorBlockedError, ExecutorPermissionError

# Failsafe é sagrado: mover o mouse para um dos cantos da tela aborta
# qualquer ação sintética. Documente isso para o usuário.
pyautogui.FAILSAFE = True
# Controlamos o delay entre ações no SessionEngine — não deixe o pyautogui
# inserir pausas extras.
pyautogui.PAUSE = 0


# Mapeia o vocabulário "DOM-like" (estilo KeyboardEvent.key) para o
# vocabulário do pyautogui. Mantemos as chaves do schema iguais ao que
# uma VLM produziria naturalmente.
_DOM_TO_PYAG: dict[str, str] = {
    "ArrowUp": "up",
    "ArrowDown": "down",
    "ArrowLeft": "left",
    "ArrowRight": "right",
    "Space": "space",
    " ": "space",
    "Enter": "enter",
    "Return": "enter",
    "Escape": "escape",
    "Esc": "escape",
    "Tab": "tab",
    "Backspace": "backspace",
    "Delete": "delete",
    "Shift": "shift",
    "Control": "ctrl",
    "Ctrl": "ctrl",
    "Alt": "alt",
    "Meta": "command" if sys.platform == "darwin" else "win",
}


def _translate_key(key: str) -> str:
    if key in _DOM_TO_PYAG:
        return _DOM_TO_PYAG[key]
    # Tecla alfanumérica solta (ex: "a", "Z", "7") — pyautogui aceita em minúsculas.
    if len(key) == 1 and (key.isalnum() or key in {"-", "=", "[", "]", ",", "."}):
        return key.lower()
    # F1..F24
    if (
        len(key) >= 2
        and key[0].lower() == "f"
        and key[1:].isdigit()
        and 1 <= int(key[1:]) <= 24
    ):
        return key.lower()
    raise ValueError(
        f"Tecla desconhecida: {key!r}. "
        "Use nomes estilo DOM (ex: 'ArrowUp', 'Space', 'Enter', 'a')."
    )


def _wrap_oserror(action_label: str, e: Exception) -> ExecutorPermissionError:
    if sys.platform == "darwin":
        msg = (
            f"{action_label} bloqueado pelo macOS. "
            "Conceda Accessibility ao Terminal ou ao app Tauri em "
            "System Settings → Privacy & Security → Accessibility "
            "(e Screen Recording se ainda não concedeu). "
            f"Detalhe: {e}"
        )
    else:
        msg = f"{action_label} falhou: {e}"
    return ExecutorPermissionError(msg)


class PyAutoGuiExecutor:
    """Implementação default — funciona em macOS/Linux/Windows."""

    def key_tap(self, key: str) -> None:
        pyag_key = _translate_key(key)
        try:
            pyautogui.press(pyag_key)
        except pyautogui.FailSafeException as e:
            raise ExecutorBlockedError(
                "Failsafe acionado: mouse foi para um canto da tela e abortou. "
                "Reinicie a sessão para continuar."
            ) from e
        except (OSError, PermissionError) as e:
            raise _wrap_oserror(f"key_tap({key!r})", e) from e

    def click(self, x: int, y: int) -> None:
        try:
            pyautogui.click(x=x, y=y)
        except pyautogui.FailSafeException as e:
            raise ExecutorBlockedError(
                "Failsafe acionado: mouse foi para um canto da tela e abortou."
            ) from e
        except (OSError, PermissionError) as e:
            raise _wrap_oserror(f"click({x},{y})", e) from e

    def wait(self, ms: int) -> None:
        time.sleep(max(0, ms) / 1000.0)
