"""Seeds idempotentes para o SQLite do PlayIA.

``apply_seeds(conn)`` é chamado no startup (após :func:`memory.migrations
.apply_pending`). Usa ``INSERT OR IGNORE`` por linha — primeiro boot
preenche tudo, boots subsequentes pulam o que já existe e adicionam o
que for novo no seed. Edições feitas pelo usuário via ``/games`` CRUD
não são afetadas (entradas customizadas têm ids diferentes do seed).
"""

from __future__ import annotations

import json
import logging
import sqlite3
from typing import Iterable

from ..models import Game
from .games import GAMES_SEED

log = logging.getLogger("playia.memory.seeds")


def apply_seeds(conn: sqlite3.Connection) -> list[str]:
    """Insere os games do seed que ainda não existem. Retorna os ids inseridos."""
    inserted: list[str] = []
    for game in GAMES_SEED:
        cur = conn.execute(
            "INSERT OR IGNORE INTO games "
            "(id, name, url, tempo, anti_cheat, allowed_keys_json, goal, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                game.id,
                game.name,
                game.url,
                game.tempo.value,
                game.anti_cheat.value,
                json.dumps(game.allowed_keys),
                game.goal,
                game.notes,
            ),
        )
        if cur.rowcount == 1:
            inserted.append(game.id)
    if inserted:
        log.info("seeds aplicadas: games %s", inserted)
    return inserted


__all__: Iterable[str] = ("apply_seeds", "GAMES_SEED")
