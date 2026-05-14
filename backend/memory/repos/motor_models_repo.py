"""Repositório da tabela ``motor_models``."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Iterable

from ..models import MotorModel


def _row_to_motor(row: sqlite3.Row) -> MotorModel:
    return MotorModel(
        id=int(row["id"]),
        game_id=row["game_id"],
        recording_id=int(row["recording_id"]),
        onnx_path=row["onnx_path"],
        accuracy=float(row["accuracy"]),
        trained_at=datetime.fromisoformat(row["trained_at"]) if row["trained_at"] else None,
        version=int(row["version"]),
    )


def create(
    conn: sqlite3.Connection,
    *,
    game_id: str,
    recording_id: int,
    onnx_path: str,
    accuracy: float,
    version: int = 1,
) -> MotorModel:
    """Cria um motor model. ``id`` e ``trained_at`` preenchidos pelo DB."""
    cur = conn.execute(
        "INSERT INTO motor_models (game_id, recording_id, onnx_path, accuracy, version) "
        "VALUES (?, ?, ?, ?, ?)",
        (game_id, recording_id, onnx_path, accuracy, version),
    )
    m = get(conn, int(cur.lastrowid))
    assert m is not None
    return m


def get(conn: sqlite3.Connection, motor_id: int) -> MotorModel | None:
    row = conn.execute(
        "SELECT * FROM motor_models WHERE id = ?", (motor_id,)
    ).fetchone()
    return _row_to_motor(row) if row else None


def list_by_game(conn: sqlite3.Connection, game_id: str) -> list[MotorModel]:
    rows = conn.execute(
        "SELECT * FROM motor_models WHERE game_id = ? ORDER BY trained_at DESC",
        (game_id,),
    ).fetchall()
    return [_row_to_motor(r) for r in rows]


def list_all(conn: sqlite3.Connection) -> list[MotorModel]:
    rows = conn.execute(
        "SELECT * FROM motor_models ORDER BY trained_at DESC"
    ).fetchall()
    return [_row_to_motor(r) for r in rows]


def get_latest_for_game(
    conn: sqlite3.Connection, game_id: str
) -> MotorModel | None:
    """Devolve o motor model mais recente do jogo (por trained_at), ou ``None``."""
    row = conn.execute(
        "SELECT * FROM motor_models WHERE game_id = ? "
        "ORDER BY trained_at DESC LIMIT 1",
        (game_id,),
    ).fetchone()
    return _row_to_motor(row) if row else None


def delete(conn: sqlite3.Connection, motor_id: int) -> None:
    """Apaga o motor model. O arquivo ONNX em disco deve ser apagado pelo caller."""
    conn.execute("DELETE FROM motor_models WHERE id = ?", (motor_id,))


__all__: Iterable[str] = (
    "create",
    "get",
    "list_by_game",
    "list_all",
    "get_latest_for_game",
    "delete",
)
