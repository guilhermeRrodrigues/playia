"""Repositório da tabela ``recordings``."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Iterable

from ..models import Recording


def _row_to_recording(row: sqlite3.Row) -> Recording:
    return Recording(
        id=int(row["id"]),
        game_id=row["game_id"],
        started_at=datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
        ended_at=datetime.fromisoformat(row["ended_at"]) if row["ended_at"] else None,
        fps=int(row["fps"]),
        frame_count=int(row["frame_count"]),
        notes=row["notes"],
    )


def create(
    conn: sqlite3.Connection,
    *,
    game_id: str,
    fps: int,
    notes: str | None = None,
) -> Recording:
    """Cria uma nova gravação. ``id`` e ``started_at`` são preenchidos pelo DB."""
    cur = conn.execute(
        "INSERT INTO recordings (game_id, fps, frame_count, notes) "
        "VALUES (?, ?, 0, ?)",
        (game_id, fps, notes),
    )
    rec = get(conn, int(cur.lastrowid))
    assert rec is not None
    return rec


def get(conn: sqlite3.Connection, recording_id: int) -> Recording | None:
    row = conn.execute(
        "SELECT * FROM recordings WHERE id = ?", (recording_id,)
    ).fetchone()
    return _row_to_recording(row) if row else None


def list_all(
    conn: sqlite3.Connection, *, game_id: str | None = None
) -> list[Recording]:
    """Lista as gravações em ordem cronológica decrescente."""
    if game_id is None:
        rows = conn.execute(
            "SELECT * FROM recordings ORDER BY started_at DESC"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM recordings WHERE game_id = ? ORDER BY started_at DESC",
            (game_id,),
        ).fetchall()
    return [_row_to_recording(r) for r in rows]


def list_by_game(conn: sqlite3.Connection, game_id: str) -> list[Recording]:
    """Atalho para :func:`list_all` filtrando por jogo."""
    return list_all(conn, game_id=game_id)


def end(
    conn: sqlite3.Connection, recording_id: int, *, frame_count: int
) -> Recording:
    """Marca a gravação como finalizada — preenche ``ended_at`` e ``frame_count``."""
    conn.execute(
        "UPDATE recordings SET ended_at = datetime('now'), frame_count = ? "
        "WHERE id = ?",
        (frame_count, recording_id),
    )
    rec = get(conn, recording_id)
    if rec is None:
        raise LookupError(f"recordings.end: id desconhecido {recording_id}")
    return rec


def update_notes(
    conn: sqlite3.Connection, recording_id: int, notes: str | None
) -> Recording:
    conn.execute(
        "UPDATE recordings SET notes = ? WHERE id = ?",
        (notes, recording_id),
    )
    rec = get(conn, recording_id)
    if rec is None:
        raise LookupError(f"recordings.update_notes: id desconhecido {recording_id}")
    return rec


def delete(conn: sqlite3.Connection, recording_id: int) -> None:
    """Apaga a gravação. Recording_frames vão junto por ON DELETE CASCADE."""
    conn.execute("DELETE FROM recordings WHERE id = ?", (recording_id,))


def has_motor_models(conn: sqlite3.Connection, recording_id: int) -> bool:
    """``True`` se há motor_models treinados em cima dessa gravação."""
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM motor_models WHERE recording_id = ?",
        (recording_id,),
    ).fetchone()
    return int(row["n"]) > 0


__all__: Iterable[str] = (
    "create",
    "get",
    "list_all",
    "list_by_game",
    "end",
    "update_notes",
    "delete",
    "has_motor_models",
)
