"""Repositório da tabela ``games``."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Iterable

from ..models import AntiCheat, Game, Tempo


def _row_to_game(row: sqlite3.Row) -> Game:
    return Game(
        id=row["id"],
        name=row["name"],
        url=row["url"],
        tempo=Tempo(row["tempo"]),
        anti_cheat=AntiCheat(row["anti_cheat"]),
        allowed_keys=json.loads(row["allowed_keys_json"]),
        goal=row["goal"],
        notes=row["notes"],
        created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
    )


def list_all(
    conn: sqlite3.Connection,
    *,
    tempo: Tempo | None = None,
    anti_cheat: AntiCheat | None = None,
) -> list[Game]:
    """Lista jogos ordenados por nome, com filtros opcionais por tempo/anti-cheat."""
    sql = "SELECT * FROM games WHERE 1=1"
    params: list[str] = []
    if tempo is not None:
        sql += " AND tempo = ?"
        params.append(tempo.value)
    if anti_cheat is not None:
        sql += " AND anti_cheat = ?"
        params.append(anti_cheat.value)
    sql += " ORDER BY name"
    return [_row_to_game(r) for r in conn.execute(sql, params)]


def get(conn: sqlite3.Connection, game_id: str) -> Game | None:
    """Retorna o jogo pelo ``id`` (slug), ou ``None`` se não existir."""
    row = conn.execute("SELECT * FROM games WHERE id = ?", (game_id,)).fetchone()
    return _row_to_game(row) if row else None


def get_by_name(conn: sqlite3.Connection, name: str) -> Game | None:
    """Retorna o jogo pelo nome humano (``name``), ou ``None``."""
    row = conn.execute("SELECT * FROM games WHERE name = ?", (name,)).fetchone()
    return _row_to_game(row) if row else None


def create(conn: sqlite3.Connection, game: Game) -> Game:
    """Insere um novo jogo. Levanta ``sqlite3.IntegrityError`` se o id ou nome existir."""
    conn.execute(
        "INSERT INTO games "
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
    saved = get(conn, game.id)
    if saved is None:
        # Improvável (acabamos de inserir), mas mantém o contrato: nunca None.
        raise RuntimeError(f"games.create: falha ao reler {game.id!r}")
    return saved


def update(conn: sqlite3.Connection, game: Game) -> Game:
    """Atualiza um jogo existente. Levanta ``LookupError`` se não existir."""
    if get(conn, game.id) is None:
        raise LookupError(f"games.update: id desconhecido {game.id!r}")
    conn.execute(
        "UPDATE games SET "
        " name = ?, url = ?, tempo = ?, anti_cheat = ?, "
        " allowed_keys_json = ?, goal = ?, notes = ? "
        "WHERE id = ?",
        (
            game.name,
            game.url,
            game.tempo.value,
            game.anti_cheat.value,
            json.dumps(game.allowed_keys),
            game.goal,
            game.notes,
            game.id,
        ),
    )
    saved = get(conn, game.id)
    assert saved is not None  # acabamos de validar a existência
    return saved


def delete(conn: sqlite3.Connection, game_id: str) -> None:
    """Apaga um jogo pelo id.

    Pode levantar ``sqlite3.IntegrityError`` se houver ``recordings`` ou
    ``motor_models`` apontando pra ele (``ON DELETE RESTRICT``).
    """
    conn.execute("DELETE FROM games WHERE id = ?", (game_id,))


def has_dependents(conn: sqlite3.Connection, game_id: str) -> bool:
    """Checa se o jogo tem ``recordings`` ou ``motor_models`` ligados.

    Usado por endpoints para devolver 409 antes de tentar DELETE e
    receber ``IntegrityError`` opaco.
    """
    row = conn.execute(
        "SELECT "
        "  (SELECT COUNT(*) FROM recordings  WHERE game_id = ?) "
        "+ (SELECT COUNT(*) FROM motor_models WHERE game_id = ?) AS n",
        (game_id, game_id),
    ).fetchone()
    return int(row["n"]) > 0


__all__: Iterable[str] = (
    "list_all",
    "get",
    "get_by_name",
    "create",
    "update",
    "delete",
    "has_dependents",
)
