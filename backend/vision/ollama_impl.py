"""Provider VLM via Ollama (HTTP local em :11434).

Comunica com o endpoint `/api/generate` do Ollama enviando a tela em
PNG-base64 no campo `images`. Modelo padrão: `qwen2.5vl:3b` (cabe inteiro
na GPU em Apple Silicon 16GB; o 7b spilla pro CPU e fica inviável).
"""

from __future__ import annotations

import base64
import logging

import httpx

from .base import VLMStatus
from .errors import (
    VLMModelMissingError,
    VLMTimeoutError,
    VLMUnavailableError,
)

log = logging.getLogger("playia.vision.ollama")


class OllamaProvider:
    """Implementação de `VLMProvider` que fala com um daemon Ollama local."""

    def __init__(
        self,
        model: str = "qwen2.5vl:3b",
        host: str = "http://127.0.0.1:11434",
        timeout_s: float = 60.0,
    ) -> None:
        self.model = model
        self.host = host.rstrip("/")
        self._timeout = httpx.Timeout(timeout_s, connect=3.0)
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def describe(self, image_png: bytes, prompt: str) -> str:
        client = self._get_client()
        payload = {
            "model": self.model,
            "prompt": prompt,
            "images": [base64.b64encode(image_png).decode("ascii")],
            "stream": False,
        }
        try:
            resp = await client.post(f"{self.host}/api/generate", json=payload)
        except (httpx.ConnectError, httpx.ConnectTimeout) as e:
            raise VLMUnavailableError(
                f"Não consegui conectar ao Ollama em {self.host}"
            ) from e
        except httpx.ReadTimeout as e:
            raise VLMTimeoutError(
                f"Ollama não respondeu dentro de {self._timeout.read}s"
            ) from e

        if resp.status_code == 404:
            # 404 do Ollama quando o modelo não está baixado:
            # body costuma ser {"error":"model 'qwen2.5vl:3b' not found, try ..."}
            body = _safe_json(resp)
            err = (body.get("error") or "").lower() if isinstance(body, dict) else ""
            if "model" in err or "not found" in err:
                raise VLMModelMissingError(
                    f"Modelo {self.model} não encontrado no Ollama"
                )
        resp.raise_for_status()
        body = resp.json()
        return str(body.get("response", "")).strip()

    async def status(self) -> VLMStatus:
        """Confere daemon + presença do modelo. Nunca levanta."""
        client = self._get_client()
        try:
            resp = await client.get(f"{self.host}/api/tags", timeout=3.0)
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout):
            return VLMStatus(
                ready=False,
                model=self.model,
                issue="Ollama não está rodando. Inicie com: ollama serve",
            )
        except Exception as e:  # noqa: BLE001 — status() não pode propagar
            log.warning("status() falhou inesperadamente: %r", e)
            return VLMStatus(
                ready=False,
                model=self.model,
                issue=f"Erro inesperado consultando Ollama: {e}",
            )

        if resp.status_code != 200:
            return VLMStatus(
                ready=False,
                model=self.model,
                issue=f"Ollama respondeu HTTP {resp.status_code} em /api/tags",
            )

        body = _safe_json(resp)
        models = body.get("models", []) if isinstance(body, dict) else []
        names = {m.get("name") for m in models if isinstance(m, dict)}
        if self.model not in names:
            return VLMStatus(
                ready=False,
                model=self.model,
                issue=(
                    f"Modelo {self.model} não encontrado. "
                    f"Rode: ollama pull {self.model}"
                ),
            )
        return VLMStatus(ready=True, model=self.model, issue=None)

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None


def _safe_json(resp: httpx.Response) -> dict:
    try:
        data = resp.json()
        return data if isinstance(data, dict) else {}
    except ValueError:
        return {}
