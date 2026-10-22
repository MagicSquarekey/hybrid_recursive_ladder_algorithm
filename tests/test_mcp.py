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


@pytest.fixture(autouse=True)
def _fresh_engine():
    reset_engine()
    yield
    reset_engine()


def test_tools_registered():
    server = build_server()
    tools = _resolve(server.list_tools())
    names = {tool.name for tool in tools}
    assert names == {"ladder_meta", "ladder_decompose", "ladder_sum", "ladder_verify"}


def test_decompose_tool():
    server = build_server()
    result = _resolve(
        server.call_tool(
            "ladder_decompose",
            {"start": "2026-01-01", "end": "2026-10-21T18:49:59"},
        )
    )
    payload = json.loads(result.content[0].text)
    assert payload["count"] == 97
    assert payload["by_level"] == {"month": 9, "day": 20, "hour": 18, "minute": 50}


def test_sum_tool_with_demo_data():
    server = build_server()
    result = _resolve(
        server.call_tool(
            "ladder_sum",
            {
                "series": [{"entity": "demo-chiller-1", "key": "energy"}],
                "start": "2026-01-01",
                "end": "2026-02-01",
            },
        )
    )
    payload = json.loads(result.content[0].text)
    assert payload["grand_total"] is not None
    assert payload["rows"][0]["segments_count"] == 1
