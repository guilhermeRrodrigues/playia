"""Exceções tipadas do módulo strategist."""

from __future__ import annotations


class StrategistError(Exception):
    """Base de falhas tipadas do loop hierárquico."""


class HSessionAlreadyRunningError(StrategistError):
    """``start`` chamado mas já existe sessão hierárquica ativa."""


class MotorNotTrainedError(StrategistError):
    """Jogo não tem motor_model treinado — loop hierárquico não pode rodar.

    Endpoint converte em HTTP 412 com mensagem sugerindo /train.
    """
