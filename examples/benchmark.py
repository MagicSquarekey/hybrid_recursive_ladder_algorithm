# -*- coding: utf-8 -*-
"""Count segments and source requests without a server.

Run::

    python examples/benchmark.py
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo

from hybrid_ladder import LadderEngine, MemorySource

TZ = ZoneInfo("Asia/Shanghai")


def ms(*args: int) -> int:
    return round(datetime(*args, tzinfo=TZ).timestamp() * 1000)


class CountingSource:
    """Wrap a source and count interval/raw calls."""

    def __init__(self, inner: MemorySource) -> None:
        self.inner = inner
        self.calls: Counter[str] = Counter()

    def interval_agg(self, ref, start_ms, end_ms, bucket_ms, agg="SUM"):
        self.calls["interval_agg"] += 1
        return self.inner.interval_agg(ref, start_ms, end_ms, bucket_ms, agg)

    def raw_series(self, ref, start_ms, end_ms, limit=10_000):
        self.calls["raw_series"] += 1
        return self.inner.raw_series(ref, start_ms, end_ms, limit)


def fill(source: MemorySource, start: int, end: int, step_ms: int) -> None:
    points = []
    ts = start
    index = 0
    while ts < end:
        points.append((ts, float(1 + index % 4)))
        ts += step_ms
        index += 1
    source.add("bench", "energy", points)


def run(label: str, start: int, end: int, step_ms: int, finest: str) -> None:
    source = MemorySource()
    fill(source, start, end, step_ms)
    counting = CountingSource(source)
    engine = LadderEngine(counting)
    result = engine.sum([("bench", "energy")], start, end, finest=finest)
    print(
        f"{label:<28} {result.rows[0].segments_count:>8} "
        f"{counting.calls['interval_agg']:>13} "
        f"{counting.calls['raw_series']:>12}"
    )


def main() -> None:
    print(f"{'range':<28} {'segments':>8} {'agg_requests':>13} {'raw_requests':>12}")
    print("-" * 65)
    run("2 days, minute", ms(2026, 10, 19, 6, 30), ms(2026, 10, 21, 7, 45), 60_000, "minute")
    run("10 months, mixed levels", ms(2026, 1, 1), ms(2026, 10, 21, 18, 49, 59), 60_000, "minute")
    run("1 year, day level", ms(2025, 1, 20), ms(2026, 1, 25), 86_400_000, "day")


if __name__ == "__main__":
    main()
