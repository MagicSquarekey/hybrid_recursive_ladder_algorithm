# -*- coding: utf-8 -*-
"""Test helpers (importable because pytest adds this directory to sys.path)."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from hybrid_ladder import MemorySource

TZ = ZoneInfo("Asia/Shanghai")


def ms(*args: int) -> int:
    """Local (Asia/Shanghai) datetime -> epoch milliseconds."""
    return round(datetime(*args, tzinfo=TZ).timestamp() * 1000)


def build_source(
    *,
    days: int = 10,
    step_ms: int = 900_000,
    entity: str = "dev-1",
    key: str = "energy",
    start: int | None = None,
) -> tuple[MemorySource, int, int]:
    """A deterministic source: values cycle 1,2,3,4 on a 15-minute grid."""
    start = start if start is not None else ms(2026, 1, 1)
    end = start + days * 86_400_000
    points = []
    ts = start
    index = 0
    while ts < end:
        points.append((ts, float(1 + index % 4)))
        ts += step_ms
        index += 1
    source = MemorySource()
    source.add(entity, key, points)
    return source, start, end
