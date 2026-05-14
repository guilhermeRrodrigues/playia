"""Planner que delega a decisão para um ``VLMProvider``.

Estratégia: instrui a VLM a devolver SÓ um JSON no schema de ``Action``.
Faz parse robusto (a função ``parse_action_json`` extrai o primeiro ``{...}``
mesmo com preâmbulo). Se a resposta for inválida ou usar uma tecla fora do
vocabulário, tenta de novo uma vez com mensagem corretiva; se ainda falhar,
levanta ``PlannerParseError``.
"""

from __future__ import annotations

import logging

from vision.base import VLMProvider

from .actions import Action, parse_action_json
from .errors import PlannerParseError

log = logging.getLogger("playia.planner.vlm")


_SYSTEM_RULES = (
    "Você é o cérebro de um agente que joga jogos simples no navegador.\n"
    "A cada turno você vê um print da tela do jogo e deve escolher UMA ação.\n"
    "RESPONDA APENAS com um JSON válido — sem comentários, sem markdown, "
    "sem texto antes ou depois.\n"
    "Schema do JSON:\n"
    '  {"kind": "key" | "stop", "key": "<tecla>" | null, '
    '"reason": "<por que esta ação faz sentido>"}\n'
    'Use "stop" SOMENTE se o jogo claramente terminou ("Game over", '
    "tela final) ou se nenhuma das teclas disponíveis adianta.\n"
)

_FEW_SHOTS = (
    "Exemplos:\n"
    '1) Tabuleiro com peças "2" e "4" alinhadas em coluna; melhor jogada é '
    "juntar para baixo:\n"
    '   {"kind": "key", "key": "ArrowDown", "reason": "junta o par de 2s na '
    'coluna direita"}\n'
    "2) Tela mostra mensagem 'Game over!':\n"
    '   {"kind": "stop", "key": null, "reason": "jogo encerrou, sem jogadas '
    'restantes"}\n'
)


def _summarize_history(history: list[Action], limit: int = 5) -> str:
    if not history:
        return "(nenhuma ação ainda)"
    tail = history[-limit:]
    lines: list[str] = []
    for i, a in enumerate(tail, start=max(1, len(history) - len(tail) + 1)):
        if a.kind == "key":
            lines.append(f"{i}. {a.kind}:{a.key} — {a.reason or '(sem motivo)'}")
        elif a.kind == "click":
            lines.append(f"{i}. click({a.x},{a.y}) — {a.reason}")
        elif a.kind == "wait":
            lines.append(f"{i}. wait({a.duration_ms}ms) — {a.reason}")
        else:
            lines.append(f"{i}. stop — {a.reason}")
    return "\n".join(lines)


def _build_prompt(
    goal: str,
    history: list[Action],
    allowed_keys: list[str],
    correction: str | None = None,
) -> str:
    parts: list[str] = [
        _SYSTEM_RULES,
        "",
        f"OBJETIVO DO JOGO:\n{goal}",
        "",
        f"TECLAS DISPONÍVEIS: {allowed_keys}",
        "",
        "Histórico recente:",
        _summarize_history(history),
        "",
        _FEW_SHOTS,
    ]
    if correction:
        parts.append("")
        parts.append(f"ATENÇÃO: {correction}")
    parts.append("")
    parts.append("Agora analise a imagem e devolva o JSON da próxima ação.")
    return "\n".join(parts)


class VLMPlanner:
    """Implementação default: delega para um ``VLMProvider``."""

    def __init__(self, vlm: VLMProvider, max_retries: int = 1) -> None:
        self._vlm = vlm
        self._max_retries = max(0, max_retries)

    async def decide(
        self,
        image_png: bytes,
        goal: str,
        history: list[Action],
        allowed_keys: list[str],
    ) -> Action:
        correction: str | None = None
        last_err: Exception | None = None
        attempts = self._max_retries + 1

        for attempt in range(1, attempts + 1):
            prompt = _build_prompt(goal, history, allowed_keys, correction)
            raw = await self._vlm.describe(image_png, prompt)
            log.debug("vlm raw (attempt=%d): %s", attempt, raw)
            try:
                action = parse_action_json(raw)
            except PlannerParseError as e:
                last_err = e
                correction = (
                    f"Sua última resposta não foi JSON válido ({e}). "
                    "Devolva APENAS o JSON do schema, sem nenhum outro texto."
                )
                continue

            # Validação extra: kind=key precisa estar dentro do vocabulário
            # permitido para este jogo. Falha trata como parse inválido (retry).
            if action.kind == "key" and action.key not in allowed_keys:
                correction = (
                    f"Tecla {action.key!r} não está disponível neste jogo. "
                    f"Escolha uma de: {allowed_keys}."
                )
                last_err = PlannerParseError(
                    f"tecla {action.key!r} fora do vocabulário"
                )
                continue

            return action

        raise PlannerParseError(
            f"VLM não devolveu Action válida em {attempts} tentativas: {last_err}"
        )
