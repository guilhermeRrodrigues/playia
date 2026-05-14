"""Erros tipados do executor — mapeados em HTTP no main.py."""

from __future__ import annotations


class ExecutorError(Exception):
    """Base de qualquer erro do executor."""


class ExecutorPermissionError(ExecutorError):
    """O SO recusou o input sintético (no macOS, falta Accessibility)."""


class ExecutorBlockedError(ExecutorError):
    """Algo bloqueou a execução: failsafe do pyautogui ou anti-cheat (TODO M+)."""
