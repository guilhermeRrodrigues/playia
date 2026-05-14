"""Repositórios de acesso ao SQLite.

Padrão Repository: cada arquivo expõe funções puras
``operation(conn, ...)`` que recebem a :class:`sqlite3.Connection` como
primeiro argumento e retornam modelos pydantic do :mod:`memory.models`.
A conversão entre colunas JSON do DB e listas/dicts Python acontece aqui.

Estado em M4:
- ``games_repo``            — ativo (M4)
- ``recordings_repo``       — stub (M5)
- ``recording_frames_repo`` — stub (M5)
- ``motor_models_repo``     — stub (M6)
- ``episodes_repo``         — stub (M8)
- ``skills_repo``           — stub (M8)
- ``knowledge_repo``        — stub (M8)
"""
