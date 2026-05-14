"""Exceções tipadas do módulo recording.

Cada uma vira um HTTP status no endpoint:
- :class:`RecorderBusyError`        → 409
- :class:`RecorderPermissionError`  → 403 com mensagem prescritiva
- :class:`RecorderError` (genérica) → 500 (último recurso)
"""

from __future__ import annotations


class RecorderError(Exception):
    """Base de falhas tipadas do recorder."""


class RecorderBusyError(RecorderError):
    """``start`` chamado mas já existe gravação em andamento."""


class RecorderPermissionError(RecorderError):
    """O SO bloqueou o listener global (macOS Input Monitoring, p.ex.).

    A mensagem sempre carrega instrução acionável em pt-br dizendo
    exatamente onde habilitar a permissão.
    """
