"""Conexão SQLite por-thread, com extensão ``sqlite-vec`` carregada.

Por que thread-local: o FastAPI executa endpoints síncronos no threadpool
do uvicorn. SQLite proíbe por padrão que uma ``Connection`` seja usada em
threads diferentes da que a criou. Em vez de passar ``check_same_thread=
False`` (que esconde race conditions sob WAL writes), mantemos **uma
conexão por thread**: cada thread chama :func:`get_connection` e recebe a
sua. Como o uvicorn reusa threads do pool, o custo de abrir é amortizado.

Side-effects ao abrir uma conexão:
- ``foreign_keys=ON`` (sem isso o SQLite ignora FKs silenciosamente).
- ``journal_mode=WAL`` (writers não bloqueiam readers — essencial pra UI
  fazer polling de status enquanto gravação/treino rodam).
- ``synchronous=NORMAL`` (durabilidade boa o suficiente; ``FULL`` lentifica
  o batch insert de frames).
- Carrega a extensão ``vec0`` via ``sqlite_vec.load``.

As migrations e seeds rodam no startup do FastAPI (lifespan; M4.2) usando
a conexão do main thread.
"""

from __future__ import annotations

import logging
import sqlite3
import threading

import sqlite_vec

from .paths import db_path

log = logging.getLogger("playia.memory.connection")

_local = threading.local()


class SQLiteExtensionsUnsupportedError(RuntimeError):
    """Build do Python não suporta ``enable_load_extension``."""


def _open() -> sqlite3.Connection:
    path = db_path()
    # isolation_level=None deixa o sqlite3 em autocommit — transações
    # ficam explícitas via ``BEGIN``/``COMMIT`` nos repos e migrations.
    conn = sqlite3.connect(path, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")

    if not hasattr(conn, "enable_load_extension"):
        conn.close()
        raise SQLiteExtensionsUnsupportedError(
            "Este build do Python foi compilado sem suporte a load_extension. "
            "Instale Python via uv (`uv python install 3.12`) ou pyenv."
        )

    conn.enable_load_extension(True)
    try:
        sqlite_vec.load(conn)
    finally:
        conn.enable_load_extension(False)

    log.info("sqlite conectado em %s (sqlite-vec carregado)", path)
    return conn


def get_connection() -> sqlite3.Connection:
    """Devolve a conexão SQLite da thread atual, criando se necessário."""
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = _open()
        _local.conn = conn
    return conn


def close_thread_connection() -> None:
    """Fecha a conexão da thread atual, se existir. Útil em testes."""
    conn = getattr(_local, "conn", None)
    if conn is not None:
        conn.close()
        _local.conn = None
