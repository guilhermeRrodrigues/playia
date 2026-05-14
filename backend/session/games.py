"""Perfis de jogo conhecidos pelo PlayIA.

Cada perfil define o *objetivo* (que vai pro prompt da VLM), a URL onde o
usuário deve abrir o jogo, e o vocabulário de teclas permitido. Estrutura
aberta para expansão depois do M3 — por enquanto só ``2048``.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class GameProfile(BaseModel):
    name: str
    url: str
    goal: str
    allowed_keys: list[str] = Field(default_factory=list)


GAMES: dict[str, GameProfile] = {
    "2048": GameProfile(
        name="2048",
        url="https://play2048.co/",
        goal=(
            "Você está jogando 2048. Combine peças iguais movendo todas as "
            "peças com setas (ArrowUp/Down/Left/Right). Maximize o número "
            "da maior peça. Termine (action stop) se aparecer 'Game over' "
            "ou se nenhuma jogada movimentar peças."
        ),
        allowed_keys=["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"],
    ),
}


def get_profile(name: str) -> GameProfile:
    """Devolve o perfil ou levanta ``KeyError`` se o nome for desconhecido."""
    return GAMES[name]
