"""Erros tipados do planner — mapeados em HTTP no main.py."""

from __future__ import annotations


class PlannerError(Exception):
    """Base de qualquer erro do planner."""


class PlannerParseError(PlannerError):
    """A VLM não devolveu um JSON parseável dentro do limite de tentativas."""


class PlannerNoActionError(PlannerError):
    """A VLM devolveu `stop` quando o caller não esperava encerramento."""
