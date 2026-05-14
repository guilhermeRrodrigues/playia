"""Caminhos persistentes do PlayIA.

Usa ``platformdirs.user_data_dir("PlayIA")`` como raiz para que dados de
runtime fiquem fora do diretório do app:

- macOS:   ``~/Library/Application Support/PlayIA/``
- Windows: ``%APPDATA%/PlayIA/``
- Linux:   ``~/.local/share/PlayIA/``

Toda escrita de runtime (DB, frames PNG, motor models ONNX) vive sob essa
raiz. Os getters criam o diretório se não existir — chamáveis sem ordem.
"""

from __future__ import annotations

from pathlib import Path

from platformdirs import user_data_dir

APP_NAME = "PlayIA"


def data_dir() -> Path:
    """Raiz de dados persistentes do app. Cria se não existir."""
    d = Path(user_data_dir(APP_NAME))
    d.mkdir(parents=True, exist_ok=True)
    return d


def db_path() -> Path:
    """Arquivo SQLite único do PlayIA (``<data_dir>/playia.db``)."""
    return data_dir() / "playia.db"


def recordings_dir() -> Path:
    """Raiz das gravações de watch-me-play (M5)."""
    d = data_dir() / "data" / "recordings"
    d.mkdir(parents=True, exist_ok=True)
    return d


def motor_models_dir() -> Path:
    """Raiz dos motor models ONNX treinados (M6)."""
    d = data_dir() / "data" / "motor_models"
    d.mkdir(parents=True, exist_ok=True)
    return d
