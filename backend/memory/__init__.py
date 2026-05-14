"""Memória persistente do PlayIA — SQLite + sqlite-vec.

Submódulos:
- ``paths``       — diretórios persistentes via ``platformdirs``.
- ``connection``  — conexão SQLite por-thread, com extensão ``vec0`` carregada.
- ``migrations``  — schema versionado e aplicado no startup do sidecar (M4.2).
- ``models``      — schemas pydantic dos registros do DB (M4.3).
- ``repos``       — repositórios (Game, Recording, …) (M4.3+).
- ``seeds``       — inserção idempotente de perfis de jogo padrão (M4.4).
"""
