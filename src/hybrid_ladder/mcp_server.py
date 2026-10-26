# -*- coding: utf-8 -*-
"""MCP (Model Context Protocol) server over stdio.

Run::

    pip install -e ".[mcp]"   # from a source checkout
    hybrid-ladder mcp

Configure the source with the same ``HL_*`` environment variables as the HTTP
API (``HL_SOURCE``, ``HL_TB_URL``, ``HL_PG_DSN``, ...).  With no configuration
the server exposes deterministic demo data, so every tool works out of the box.
"""

from __future__ import annotations

import re
from dataclasses import asdict
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from . import __version__
from .demo import DEMO_SERIES, demo_info
from .engine import LadderEngine
from .models import LEVELS, SeriesRef, coerce_refs
from .runtime import engine_from_env

__all__ = ["build_server", "run"]

_ENGINE: LadderEngine | None = None


def _engine() -> LadderEngine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = engine_from_env()
    return _ENGINE


def reset_engine() -> None:
    """Drop the cached engine (useful in tests after changing env vars)."""
    global _ENGINE
    _ENGINE = None


def _parse_time(value: str, timezone: str) -> int:
    text = str(value).strip()
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(
            f"invalid time {value!r}; use ISO-8601 or epoch milliseconds"
        ) from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo(timezone))
    return round(dt.timestamp() * 1000)


def _refs(series: list[dict[str, Any]] | None) -> list[SeriesRef]:
    if not series:
        return list(DEMO_SERIES)
    return coerce_refs(series)


def build_server():
    """Create the MCP server.  Importing ``mcp`` is deferred.

    Supports both the 1.x ``FastMCP`` name and the 2.x ``MCPServer`` name.
    """
    try:
        try:
            from mcp.server.fastmcp import FastMCP as _Server  # mcp 1.x
        except ImportError:
            from mcp.server.mcpserver import MCPServer as _Server  # mcp 2.x
        from mcp.types import ToolAnnotations
    except ImportError as exc:  # pragma: no cover - dependency error path
        raise ImportError(
            "the MCP server needs the mcp package; install with "
            "'pip install -e \".[mcp]\" (source checkout)'"
        ) from exc

    server = _Server("hybrid-recursive-ladder")

    # Clients use these hints to decide whether to ask for confirmation and
    # whether calls can be batched.  Nothing here deletes data: the only write
    # path is materialization, which replaces a range and is safe to repeat.
    local_only = ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    reads_source = ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
    writes_local = ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )

    @server.tool(title="Ladder metadata", annotations=local_only)
    def ladder_meta() -> dict[str, Any]:
        """Return version, configuration, source/store type and demo range."""
        engine = _engine()
        return {
            "version": __version__,
            "levels": list(LEVELS),
            "config": asdict(engine.config),
            "source": type(engine.source).__name__,
            "store": type(engine.store).__name__ if engine.store is not None else None,
            "demo": demo_info(),
        }

    @server.tool(title="Decompose a time range", annotations=local_only)
    def ladder_decompose(
        start: str,
        end: str,
        finest: str = "minute",
        timezone: str = "Asia/Shanghai",
    ) -> dict[str, Any]:
        """Decompose [start, end) into month/day/hour/minute ladder segments.

        Times accept ISO-8601 (``2026-01-01T00:00:00``) or epoch milliseconds.
        """
        start_ms = _parse_time(start, timezone)
        end_ms = _parse_time(end, timezone)
        segments = _engine().decompose(start_ms, end_ms, finest)
        by_level: dict[str, int] = {}
        for segment in segments:
            by_level[segment.level] = by_level.get(segment.level, 0) + 1
        return {
            "count": len(segments),
            "by_level": by_level,
            "segments": [segment.as_dict() for segment in segments],
        }

    @server.tool(title="Sum time series", annotations=writes_local)
    def ladder_sum(
        series: list[dict[str, Any]],
        start: str,
        end: str,
        finest: str = "minute",
        mode: str = "tb",
        materialize: bool = False,
    ) -> dict[str, Any]:
        """Sum time series over a range.

        ``series`` items use ``{"entity": "...", "key": "...", "name": "..."}``
        (``device_id``/``device_name`` are accepted as aliases).  ``mode`` is
        ``tb`` (source only), ``mixed`` (local first) or ``local`` (offline).
        With no series, the built-in demo series are used.
        """
        engine = _engine()
        refs = _refs(series)
        start_ms = _parse_time(start, engine.config.timezone)
        end_ms = _parse_time(end, engine.config.timezone)
        if mode not in ("tb", "mixed", "local"):
            raise ValueError("mode must be tb, mixed or local")
        if mode == "tb":
            result = engine.sum(refs, start_ms, end_ms, finest=finest)
        elif mode == "local":
            result = engine.sum_local(refs, start_ms, end_ms, finest=finest)
        else:
            result = engine.sum_mixed(refs, start_ms, end_ms, finest=finest)

        if materialize and engine.store is not None:
            items = (
                [(ref, [(start_ms, end_ms)]) for ref in refs]
                if mode == "tb"
                else [(row.ref, row.tb_ranges) for row in result.rows if row.tb_ranges]
            )
            if items:
                result.materialized = engine.materialize_ranges(items)
        return result.as_dict()

    @server.tool(title="Verify against source", annotations=reads_source)
    def ladder_verify(
        series: list[dict[str, Any]],
        start: str,
        end: str,
        finest: str = "minute",
        drill_limit: int = 50,
    ) -> dict[str, Any]:
        """Compare the authoritative source with the local store.

        Returns per-segment differences and, for the first ``drill_limit``
        differing segments, point-level added/removed/changed counts.
        """
        engine = _engine()
        if engine.store is None:
            raise ValueError("verify needs a local store; set HL_PG_DSN")
        refs = _refs(series)
        start_ms = _parse_time(start, engine.config.timezone)
        end_ms = _parse_time(end, engine.config.timezone)
        return engine.verify(
            refs, start_ms, end_ms, finest=finest, drill_limit=drill_limit
        )

    return server


def run() -> None:
    """Run the MCP server over stdio."""
    build_server().run()


if __name__ == "__main__":  # pragma: no cover
    run()
