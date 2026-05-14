"""Schema de ações produzidas pelo planner e consumidas pelo executor."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, model_validator

from .errors import PlannerParseError

ActionKind = Literal["key", "click", "wait", "stop"]


class Action(BaseModel):
    """Uma decisão atômica do planner.

    - ``kind="key"``  exige ``key`` (nome estilo DOM: ``"ArrowUp"``, ``"Space"``).
    - ``kind="click"`` exige ``x`` e ``y`` (coordenadas absolutas em pixels).
    - ``kind="wait"`` exige ``duration_ms``.
    - ``kind="stop"`` encerra a sessão (fim do jogo, sem jogada útil etc).
    """

    kind: ActionKind
    key: str | None = None
    x: int | None = None
    y: int | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    reason: str = ""

    @model_validator(mode="after")
    def _validate_fields_for_kind(self) -> Action:
        if self.kind == "key" and not self.key:
            raise ValueError("Action.kind='key' exige 'key' não-vazio")
        if self.kind == "click" and (self.x is None or self.y is None):
            raise ValueError("Action.kind='click' exige 'x' e 'y'")
        if self.kind == "wait" and self.duration_ms is None:
            raise ValueError("Action.kind='wait' exige 'duration_ms'")
        return self


# Regex extrai o primeiro bloco {...} balanceado de uma string.
# Suporta JSON em uma linha ou multi-linha (DOTALL).
_JSON_OBJECT_RE = re.compile(r"\{[^{}]*\}", re.DOTALL)


def parse_action_json(raw: str) -> Action:
    """Extrai um JSON ``{...}`` da resposta da VLM e valida como ``Action``.

    A VLM frequentemente embrulha o JSON em prefácio ("Aqui está: {...}") ou
    em fences markdown. Esta função procura o primeiro objeto JSON balanceado
    e tenta validar; levanta ``PlannerParseError`` se nenhum candidato for
    válido.
    """
    if not raw or not raw.strip():
        raise PlannerParseError("resposta da VLM veio vazia")

    candidates: list[str] = []
    # 1ª tentativa: regex simples (objeto JSON sem aninhamento).
    candidates.extend(_JSON_OBJECT_RE.findall(raw))
    # 2ª tentativa: scanner manual (suporta `{...}` aninhado).
    nested = _extract_balanced_json(raw)
    if nested and nested not in candidates:
        candidates.append(nested)

    last_err: Exception | None = None
    for candidate in candidates:
        try:
            return Action.model_validate_json(candidate)
        except (ValidationError, ValueError) as e:
            last_err = e
            continue

    msg = (
        f"nenhum JSON válido encontrado na resposta da VLM: {raw!r}"
        if not candidates
        else f"JSON encontrado mas inválido: {last_err}"
    )
    raise PlannerParseError(msg)


def _extract_balanced_json(raw: str) -> str | None:
    """Acha o primeiro ``{...}`` com chaves balanceadas (suporta aninhamento)."""
    depth = 0
    start: int | None = None
    for i, ch in enumerate(raw):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth == 0:
                continue
            depth -= 1
            if depth == 0 and start is not None:
                return raw[start : i + 1]
    return None
