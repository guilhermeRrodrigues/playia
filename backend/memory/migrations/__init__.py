"""Aplicação de migrations SQL versionadas do PlayIA.

Cada arquivo nesta pasta tem nome ``NNN_descricao.sql`` (3 dígitos,
zero-padded). :func:`apply_pending` aplica os arquivos cujo número é
maior que a versão atual registrada em ``schema_version``, e é idempotente
— rodar duas vezes no mesmo DB não duplica nada.

Limitação conhecida: ``sqlite3.executescript`` faz auto-commit entre
statements, então uma migration que falhar no meio pode deixar o DB em
estado parcial. Para M4 (greenfield) isto é aceitável; quando houver
deploys em produção, dividimos cada migration em um único ``BEGIN…COMMIT``
manual.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from datetime import datetime
from pathlib import Path

log = logging.getLogger("playia.memory.migrations")

MIGRATIONS_DIR = Path(__file__).parent
_VERSION_RE = re.compile(r"^(\d{3})_.+\.sql$")


def _bootstrap(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_version ("
        "  version    INTEGER PRIMARY KEY,"
        "  applied_at TEXT NOT NULL"
        ")"
    )


def current_version(conn: sqlite3.Connection) -> int:
    """Versão de schema atualmente aplicada (0 se nada aplicado)."""
    _bootstrap(conn)
    row = conn.execute("SELECT MAX(version) AS v FROM schema_version").fetchone()
    return int(row["v"] or 0)


def _discover() -> list[tuple[int, Path]]:
    out: list[tuple[int, Path]] = []
    for path in MIGRATIONS_DIR.iterdir():
        m = _VERSION_RE.match(path.name)
        if not m:
            continue
        out.append((int(m.group(1)), path))
    out.sort(key=lambda t: t[0])
    return out


def apply_pending(conn: sqlite3.Connection) -> list[int]:
    """Aplica migrations cujo versionamento é maior que :func:`current_version`.

    Retorna a lista das versões efetivamente aplicadas (vazia se já atual).
    """
    _bootstrap(conn)
    applied: list[int] = []
    have = current_version(conn)
    for version, path in _discover():
        if version <= have:
            continue
        sql = path.read_text(encoding="utf-8")
        log.info("aplicando migration %03d (%s)", version, path.name)
        try:
            conn.executescript(sql)
            conn.execute(
                "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                (version, datetime.now().isoformat(timespec="seconds")),
            )
        except sqlite3.DatabaseError:
            log.exception(
                "migration %03d falhou — DB pode estar em estado parcial",
                version,
            )
            raise
        applied.append(version)
    if applied:
        log.info("migrations aplicadas: %s", applied)
    else:
        log.info("schema já está na versão %d", have)
    return applied
