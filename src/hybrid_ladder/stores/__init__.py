# -*- coding: utf-8 -*-
"""Point store adapters."""

from .memory import MemoryStore

__all__ = ["MemoryStore", "PostgresStore"]


def __getattr__(name: str):
    # Import psycopg lazily so the base package has no hard dependency on it.
    if name == "PostgresStore":
        from .postgres import PostgresStore

        return PostgresStore
    raise AttributeError(name)
