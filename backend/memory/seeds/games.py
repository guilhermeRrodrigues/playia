"""Catálogo inicial de jogos. Inserido idempotentemente no startup.

Editado livremente pelo usuário via ``/games`` (UI ou API) — entradas
adicionadas pelo usuário sobrevivem, pois ``apply_seeds`` só insere ids
inéditos. Para adicionar um jogo NOVO ao seed (que apareça para
instalações futuras), basta acrescentar aqui.
"""

from __future__ import annotations

from ..models import AntiCheat, Game, Tempo

GAMES_SEED: list[Game] = [
    Game(
        id="2048",
        name="2048",
        url="https://play2048.co/",
        tempo=Tempo.TURN_BASED,
        anti_cheat=AntiCheat.NONE,
        allowed_keys=["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"],
        goal=(
            "Você está jogando 2048. Combine peças iguais movendo todas as "
            "peças com setas (ArrowUp/Down/Left/Right). Maximize o número "
            "da maior peça. Termine (action stop) se aparecer 'Game over' "
            "ou se nenhuma jogada movimentar peças."
        ),
    ),
    Game(
        id="chrome-dino",
        name="Chrome Dino",
        url="chrome://dino",
        tempo=Tempo.FAST_REALTIME,
        anti_cheat=AntiCheat.NONE,
        allowed_keys=["Space", "ArrowDown"],
        goal=(
            "Sobreviva o máximo possível ao corredor infinito. "
            "Pule cactos (Space) e abaixe das aves (ArrowDown). "
            "Não morra."
        ),
    ),
    Game(
        id="99-nights-in-the-forest",
        name="99 Nights in the Forest",
        url="https://www.roblox.com/",
        tempo=Tempo.FAST_REALTIME,
        anti_cheat=AntiCheat.HYPERION,
        allowed_keys=[
            "W",
            "A",
            "S",
            "D",
            "Space",
            "LShift",
            "1",
            "2",
            "3",
            "MouseLeft",
            "MouseRight",
        ],
        goal=(
            "Sobreviva noites coletando recursos e construindo abrigo. "
            "Foco no objetivo atual."
        ),
        notes=(
            "JOGO COM HYPERION. v0.1 só roda em Roblox Studio Play Solo. "
            "Em servidor real = ban."
        ),
    ),
]
