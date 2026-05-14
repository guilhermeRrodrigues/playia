"""Repositório da tabela ``recording_frames``.

Insert é batched: o capture loop (M5) acumula ~30 frames/s, manda
``insert_many`` a cada batch (≈1×/s) dentro de uma transação só. Isso
mantém WAL pequeno e libera o reader da UI pra fazer polling de status.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Iterable

from ..models import RecordingFrame


def _row_to_frame(row: sqlite3.Row) -> RecordingFrame:
    return RecordingFrame(
        recording_id=int(row["recording_id"]),
        ts_ms=int(row["ts_ms"]),
        frame_path=row["frame_path"],
        keys_down=json.loads(row["keys_down_json"]),
        mouse_x=int(row["mouse_x"]) if row["mouse_x"] is not None else None,
        mouse_y=int(row["mouse_y"]) if row["mouse_y"] is not None else None,
        mouse_buttons=json.loads(row["mouse_buttons_json"]),
    )


def insert_many(
    conn: sqlite3.Connection, frames: Iterable[RecordingFrame]
) -> int:
    """Insere um batch de frames em uma única transação. Devolve quantos."""
    rows = [
        (
            f.recording_id,
            f.ts_ms,
            f.frame_path,
            json.dumps(f.keys_down),
            f.mouse_x,
            f.mouse_y,
            json.dumps(f.mouse_buttons),
        )
        for f in frames
    ]
    if not rows:
        return 0
    conn.execute("BEGIN")
    try:
        conn.executemany(
            "INSERT INTO recording_frames "
            "(recording_id, ts_ms, frame_path, keys_down_json, mouse_x, "
            " mouse_y, mouse_buttons_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        conn.execute("COMMIT")
    except sqlite3.DatabaseError:
        conn.execute("ROLLBACK")
        raise
    return len(rows)


def list_by_recording(
    conn: sqlite3.Connection,
    recording_id: int,
    *,
    limit: int | None = None,
) -> list[RecordingFrame]:
    sql = (
        "SELECT * FROM recording_frames WHERE recording_id = ? "
        "ORDER BY ts_ms ASC"
    )
    params: list[object] = [recording_id]
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    return [_row_to_frame(r) for r in rows]


def count_by_recording(
    conn: sqlite3.Connection, recording_id: int
) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM recording_frames WHERE recording_id = ?",
        (recording_id,),
    ).fetchone()
    return int(row["n"])


__all__: Iterable[str] = (
    "insert_many",
    "list_by_recording",
    "count_by_recording",
)
