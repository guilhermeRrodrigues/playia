"""Protocol e tipos do módulo vision (VLM)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class VLMStatus:
    """Estado atual do VLM, usado pelo endpoint /vlm/status.

    `ready=False` SEMPRE carrega `issue` com uma frase prescritiva em
    pt-br que diz ao usuário o que fazer (ex.: "Inicie com: ollama serve").
    """

    ready: bool
    model: str
    issue: str | None


@runtime_checkable
class VLMProvider(Protocol):
    """Interface mínima de um provider de descrição visual.

    Contrato:
    - `image_png`: bytes PNG da tela (mesmo formato devolvido por
      `ScreenCapture.grab()`).
    - `prompt`: instrução em pt-br. A descrição também deve ser em pt-br
      por padrão.
    - Retorno de `describe`: texto puro (sem envelopamento markdown).
    - `describe` pode levantar `VLMUnavailableError`, `VLMModelMissingError`
      ou `VLMTimeoutError` (definidos em `vision.errors`).
    - `status` nunca levanta: devolve `VLMStatus(ready=False, issue=...)`
      quando algo está errado, para o endpoint de health-check renderizar.

    Atributo público obrigatório `model: str` permite o endpoint anunciar
    qual modelo está respondendo sem conhecer a impl concreta.
    """

    model: str

    async def describe(self, image_png: bytes, prompt: str) -> str: ...
    async def status(self) -> VLMStatus: ...
