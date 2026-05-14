"""Exceções tipadas do módulo motor."""

from __future__ import annotations


class MotorError(Exception):
    """Base de falhas tipadas do motor."""


class MotorNotFoundError(MotorError):
    """Não há motor_model treinado para o jogo solicitado.

    Endpoint converte em HTTP 412 — não é 404 porque o jogo existe, falta
    é treinar.
    """


class MotorInferenceError(MotorError):
    """Falha ao carregar ONNX ou rodar inferência."""
