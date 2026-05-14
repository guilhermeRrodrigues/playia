"""Estrategista VLM — pede ao Ollama uma INTENÇÃO de alto nível em pt-br.

Reusa ``VLMProvider`` (vision/) com prompt diferente do planner do M3:
- Saída esperada é só ``{"text": "<intenção>", "ttl_s": <segundos>}``.
- Não há lista de teclas — a intenção é estratégica, o motor traduz pra
  tecla.
- Few-shots cobrem cenas comuns de Chrome Dino e Roblox-style survival
  pra ajudar o modelo a calibrar a saída.

Parsing é tolerante: se o VLM devolver com preâmbulo, extrai o primeiro
``{...}`` válido. Falha ainda assim → ``Intention`` com texto de fallback
e ``ttl_s=5`` (re-tenta logo).
"""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING

from .base import Intention

if TYPE_CHECKING:
    from vision.base import VLMProvider

log = logging.getLogger("playia.strategist.vlm")

_JSON_RE = re.compile(r"\{[^{}]*\}")


_SYSTEM_RULES = (
    "Você é o estrategista de um agente que joga videogame em tempo real.\n"
    "A cada chamada você vê um print da tela e deve definir UMA INTENÇÃO\n"
    "de alto nível em pt-br pra o motor seguir nos próximos 5-15 segundos.\n"
    "NÃO escolha teclas — escolha OBJETIVOS curtos e acionáveis.\n"
    "RESPONDA APENAS com um JSON válido, sem comentários ou markdown.\n"
    "Schema:\n"
    '  {"text": "<intenção curta em pt-br>", "ttl_s": <int 3-30>}\n'
    "Mantenha ``text`` com no máximo 80 caracteres.\n"
    "Escolha ``ttl_s`` curto (3-5s) quando o estado da tela muda rápido\n"
    "(jogo de ação intenso) e mais longo (15-30s) em fases calmas\n"
    "(exploração, coleta).\n"
)

_FEW_SHOTS = (
    "Exemplos:\n"
    '1) Tela mostra um cacto se aproximando no Chrome Dino:\n'
    '   {"text": "pular o cacto à frente", "ttl_s": 3}\n'
    '2) Tela vazia, pista limpa:\n'
    '   {"text": "esperar próximo obstáculo", "ttl_s": 5}\n'
    '3) Personagem perto de uma árvore com machado equipado:\n'
    '   {"text": "coletar madeira da árvore à frente", "ttl_s": 15}\n'
    '4) Personagem cercado por lobos:\n'
    '   {"text": "fugir dos lobos rumo ao abrigo", "ttl_s": 4}\n'
)


def _summarize_history(history: list[Intention], limit: int = 3) -> str:
    if not history:
        return "(nenhuma intenção anterior)"
    tail = history[-limit:]
    return "\n".join(f"- {it.text}" for it in tail)


def _build_prompt(goal: str, history: list[Intention]) -> str:
    return "\n".join(
        [
            _SYSTEM_RULES,
            "",
            f"OBJETIVO DO JOGO:\n{goal}",
            "",
            "Intenções recentes:",
            _summarize_history(history),
            "",
            _FEW_SHOTS,
            "",
            "Analise a imagem e devolva o JSON da próxima intenção.",
        ]
    )


def _parse_intention(raw: str) -> Intention | None:
    """Extrai um ``Intention`` do output do VLM. None se não der pra parsear."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # tenta extrair o primeiro {...} do texto
        m = _JSON_RE.search(raw)
        if m is None:
            return None
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError:
            return None

    if not isinstance(data, dict):
        return None
    text = data.get("text")
    if not isinstance(text, str) or not text.strip():
        return None
    ttl_s_raw = data.get("ttl_s", 10)
    try:
        ttl_s = float(ttl_s_raw)
    except (TypeError, ValueError):
        ttl_s = 10.0
    # clamp pra evitar valores absurdos
    ttl_s = max(2.0, min(30.0, ttl_s))
    return Intention(text=text.strip()[:200], ttl_s=ttl_s)


class VLMStrategist:
    def __init__(self, vlm: "VLMProvider") -> None:
        self._vlm = vlm

    async def decide(
        self,
        frame_png: bytes,
        goal: str,
        history: list[Intention],
    ) -> Intention:
        prompt = _build_prompt(goal, history)
        raw = await self._vlm.describe(frame_png, prompt)
        log.debug("vlm strategist raw: %s", raw)
        intention = _parse_intention(raw)
        if intention is None:
            log.warning(
                "strategist VLM não devolveu JSON parseável; usando fallback. raw=%s",
                raw[:200],
            )
            return Intention(
                text="(VLM devolveu resposta não-JSON; tentando de novo)",
                ttl_s=5.0,
            )
        return intention
