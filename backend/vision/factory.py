"""Fábrica de `VLMProvider`. Por enquanto, sempre Ollama local."""

from __future__ import annotations

from .base import VLMProvider


def get_vlm() -> VLMProvider:
    # TODO(M7): selecionar provider a partir de ~/.playia/config.toml
    # ou da UI de Settings (Gemini / Groq / Claude / OpenAI / OpenRouter).
    from .ollama_impl import OllamaProvider

    return OllamaProvider()
