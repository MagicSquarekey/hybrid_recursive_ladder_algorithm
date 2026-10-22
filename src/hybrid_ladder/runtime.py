# -*- coding: utf-8 -*-
"""Build an engine from ``HL_*`` environment variables.

Kept separate from the HTTP layer so the CLI and the MCP server can use it
without installing FastAPI.
"""

from __future__ import annotations

import os
from typing import Any

from .demo import build_demo_source
from .engine import LadderEngine
from .errors import ConfigurationError
from .models import LadderConfig

__all__ = ["config_from_env", "engine_from_env"]


def config_from_env() -> LadderConfig:
    return LadderConfig(
        finest=os.getenv("HL_FINEST", "minute"),
        timezone=os.getenv("HL_TIMEZONE", "Asia/Shanghai"),
        max_intervals=int(os.getenv("HL_MAX_INTERVALS", "500")),
        max_points=int(os.getenv("HL_MAX_POINTS", "10000")),
        materialize_grace_ms=int(os.getenv("HL_MATERIALIZE_GRACE_MS", "300000")),
        concurrency=int(os.getenv("HL_CONCURRENCY", "8")),
    )


def engine_from_env() -> LadderEngine:
    """Build an engine from environment variables.

    * ``HL_SOURCE``: ``memory`` (default, demo data) or ``thingsboard``.
    * ``HL_TB_URL`` / ``HL_TB_TOKEN`` or ``HL_TB_USERNAME`` + ``HL_TB_PASSWORD``.
    * ``HL_PG_DSN``: enables the local store (mixed/local modes).
    * ``HL_NAMESPACE`` / ``HL_TABLE_PREFIX``: PostgreSQL namespace and tables.
    """
    config = config_from_env()
    source_name = os.getenv("HL_SOURCE", "memory").strip().lower()
    if source_name == "memory":
        source: Any = build_demo_source()
    elif source_name == "thingsboard":
        from .sources.thingsboard import ThingsBoardSource

        base_url = os.getenv("HL_TB_URL")
        if not base_url:
            raise ConfigurationError("HL_TB_URL is required when HL_SOURCE=thingsboard")
        source = ThingsBoardSource(
            base_url,
            token=os.getenv("HL_TB_TOKEN"),
            username=os.getenv("HL_TB_USERNAME"),
            password=os.getenv("HL_TB_PASSWORD"),
            max_intervals=config.max_intervals,
            max_points=config.max_points,
        )
    else:
        raise ConfigurationError(f"unknown HL_SOURCE: {source_name!r}")

    store = None
    dsn = os.getenv("HL_PG_DSN")
    if dsn:
        from .stores.postgres import PostgresStore

        store = PostgresStore(
            dsn,
            namespace=os.getenv("HL_NAMESPACE", "default"),
            table_prefix=os.getenv("HL_TABLE_PREFIX", "hl_"),
            timezone=config.timezone,
        )
    return LadderEngine(source, store, config)
