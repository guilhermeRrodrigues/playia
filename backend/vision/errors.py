"""Exceções tipadas do módulo vision.

O endpoint converte cada uma em um HTTP status apropriado:
- VLMUnavailableError   → 503 (daemon offline / conexão recusada)
- VLMModelMissingError  → 404 (modelo não baixado)
- VLMTimeoutError       → 504 (inferência demorou demais)
"""

from __future__ import annotations


class VLMError(Exception):
    """Base de todas as falhas tipadas do vision."""


class VLMUnavailableError(VLMError):
    """O provider está offline / não responde no host configurado."""


class VLMModelMissingError(VLMError):
    """O modelo solicitado não está disponível no provider."""


class VLMTimeoutError(VLMError):
    """O provider aceitou a requisição mas não respondeu no tempo."""
