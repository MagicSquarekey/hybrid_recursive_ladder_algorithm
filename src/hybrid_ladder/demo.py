# -*- coding: utf-8 -*-
"""Deterministic demo data so the CLI and HTTP API work with zero setup."""

from __future__ import annotations

import math
from datetime import datetime
from zoneinfo import ZoneInfo

from .models import SeriesRef
from .sources.memory import MemorySource

__all__ = ["DEMO_SERIES", "build_demo_source", "demo_info", "demo_range"]

_TZ = ZoneInfo("Asia/Shanghai")
DEMO_START_MS = round(datetime(2026, 1, 1, tzinfo=_TZ).timestamp() * 1000)
DEMO_DAYS = 120
DEMO_STEP_MS = 15 * 60 * 1000
DEMO_SERIES = (
    SeriesRef("demo-chiller-1", "energy", "Chiller 1 energy"),
    SeriesRef("demo-chiller-2", "energy", "Chiller 2 energy"),
)


def demo_range() -> tuple[int, int]:
    """The full time range covered by the demo data."""
    return DEMO_START_MS, DEMO_START_MS + DEMO_DAYS * 86_400_000


def demo_info() -> dict:
    """A ready-to-use description of the demo data."""
    start, end = demo_range()
    return {
        "start_ts": start,
        "end_ts": end,
        "series": [ref.as_dict() for ref in DEMO_SERIES],
        "hint": "POST /v1/ladder/sum?sync=true with these series and range",
    }


def build_demo_source(days: int = DEMO_DAYS, step_ms: int = DEMO_STEP_MS) -> MemorySource:
    """Two 15-minute series over ``days`` days, with a deliberate gap."""
    source = MemorySource()
    end = DEMO_START_MS + days * 86_400_000
    for series_index, ref in enumerate(DEMO_SERIES):
        points = []
        index = 0
        ts = DEMO_START_MS
        while ts < end:
            # A smooth daily wave plus a small deterministic ripple.
            phase = 2 * math.pi * (index * step_ms / 86_400_000)
            value = 2.5 + 1.4 * math.sin(phase) + 0.2 * ((index * 37) % 11)
            value += 0.6 * series_index
            # Series 2 has a one-day outage to exercise empty segments.
            if not (series_index == 1 and 30 <= index * step_ms // 86_400_000 < 31):
                points.append((ts, round(value, 3)))
            ts += step_ms
            index += 1
        source.add(ref.entity, ref.key, points)
    return source
