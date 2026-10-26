# -*- coding: utf-8 -*-
"""MCP server tests (skipped when the optional ``mcp`` package is absent)."""

from __future__ import annotations

import asyncio
import inspect
import json

import pytest

pytest.importorskip("mcp")

from hybrid_ladder.mcp_server import build_server, reset_engine


def _resolve(value):
    if inspect.isawaitable(value):
        return asyncio.run(value)
    return value


def _call(server, name, arguments):
    """Call a tool and return its list of content blocks.

    Newer SDK releases return ``(content, structured)``; older ones return a
    result object carrying ``.content``.
    """
    result = _resolve(server.call_tool(name, arguments))
    if isinstance(result, tuple):
        result = result[0]
    if not isinstance(result, list):
        result = result.content
    return result


@pytest.fixture(autouse=True)
def _fresh_engine():
    reset_engine()
    yield
    reset_engine()


# SDK releases disagree on the attribute spelling of ToolAnnotations fields:
# some expose readOnlyHint, others read_only_hint (with the camelCase form as
# the serialization alias).  Read whichever the installed version provides.
_HINT_ALIASES = {
    "readOnlyHint": "read_only_hint",
    "destructiveHint": "destructive_hint",
    "idempotentHint": "idempotent_hint",
    "openWorldHint": "open_world_hint",
}


def _hint(annotations, name):
    attr = name if hasattr(annotations, name) else _HINT_ALIASES[name]
    return getattr(annotations, attr)


def test_tools_registered():
    server = build_server()
    tools = _resolve(server.list_tools())
    names = {tool.name for tool in tools}
    assert names == {"ladder_meta", "ladder_decompose", "ladder_sum", "ladder_verify"}


def test_tool_annotations():
    server = build_server()
    tools = {tool.name: tool for tool in _resolve(server.list_tools())}

    # Reads only local configuration and demo data.
    for name in ("ladder_meta", "ladder_decompose"):
        annotations = tools[name].annotations
        assert _hint(annotations, "readOnlyHint") is True
        assert _hint(annotations, "openWorldHint") is False
        assert _hint(annotations, "destructiveHint") is False

    # ladder_sum can write to the local store through materialize=True, so it
    # must not be advertised as read-only.
    annotations = tools["ladder_sum"].annotations
    assert _hint(annotations, "readOnlyHint") is False
    assert _hint(annotations, "destructiveHint") is False
    assert _hint(annotations, "openWorldHint") is True

    # ladder_verify reaches the source but never writes.
    annotations = tools["ladder_verify"].annotations
    assert _hint(annotations, "readOnlyHint") is True
    assert _hint(annotations, "openWorldHint") is True


def test_decompose_tool():
    server = build_server()
    result = _call(
        server,
        "ladder_decompose",
        {"start": "2026-01-01", "end": "2026-10-21T18:49:59"},
    )
    payload = json.loads(result[0].text)
    assert payload["count"] == 97
    assert payload["by_level"] == {"month": 9, "day": 20, "hour": 18, "minute": 50}


def test_sum_tool_with_demo_data():
    server = build_server()
    result = _call(
        server,
        "ladder_sum",
        {
            "series": [{"entity": "demo-chiller-1", "key": "energy"}],
            "start": "2026-01-01",
            "end": "2026-02-01",
        },
    )
    payload = json.loads(result[0].text)
    assert payload["grand_total"] is not None
    assert payload["rows"][0]["segments_count"] == 1
