"""Interface do planner — recebe tela + estado e devolve uma ``Action``."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .actions import Action


@runtime_checkable
class Planner(Protocol):
    """Decide a próxima ação a partir do estado do jogo.

    Contrato:
    - ``image_png``: bytes PNG (geralmente recortados pela região do jogo).
    - ``goal``: objetivo descritivo do jogo (vem do perfil em ``session.games``).
    - ``history``: ações já executadas nesta sessão (mais recente por último).
    - ``allowed_keys``: vocabulário válido para ``Action.kind="key"`` neste jogo.

    Implementações podem levantar ``PlannerParseError`` se não conseguirem
    extrair uma ação válida dentro do limite de tentativas.
    """

    async def decide(
        self,
        image_png: bytes,
        goal: str,
        history: list[Action],
        allowed_keys: list[str],
    ) -> Action: ...
