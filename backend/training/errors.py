"""Exceções tipadas do módulo training."""

from __future__ import annotations


class TrainerError(Exception):
    """Base de falhas tipadas do trainer."""


class TrainerBusyError(TrainerError):
    """``start`` chamado mas já há treino em andamento."""


class TrainerCancelledError(TrainerError):
    """O treino foi cancelado via ``cancel()`` em meio à execução."""


class TrainerDatasetError(TrainerError):
    """Dataset inválido (recording inexistente, poucos frames, etc.)."""
