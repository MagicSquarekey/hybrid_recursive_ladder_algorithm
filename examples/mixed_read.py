# -*- coding: utf-8 -*-
"""Materialize, mixed read, verify and repair with an in-memory store.

Run::

    python examples/mixed_read.py
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from hybrid_ladder import LadderEngine, MemorySource, MemoryStore, SeriesRef

TZ = ZoneInfo("Asia/Shanghai")


def ms(*args: int) -> int:
    return round(datetime(*args, tzinfo=TZ).timestamp() * 1000)


def main() -> None:
    start, end = ms(2026, 1, 1), ms(2026, 1, 11)
    source = MemorySource()
    points = []
    ts = start
    index = 0
    while ts < end:
        points.append((ts, float(1 + index % 4)))
        ts += 900_000
        index += 1
    source.add("chiller-1", "energy", points)

    store = MemoryStore()
    engine = LadderEngine(source, store, clock=lambda: ms(2030, 1, 1))

    pure = engine.sum([("chiller-1", "energy")], start, end)
    print("source-only:", pure.grand_total)

    half = start + 5 * 86_400_000 + 12 * 3_600_000
    print("materialized:", engine.materialize([("chiller-1", "energy")], start, half))

    mixed = engine.sum_mixed([("chiller-1", "energy")], start, end)
    print("mixed:", mixed.grand_total, "source:", mixed.source)
    print("segments by source:", mixed.source_counts)
    print("still missing locally:", mixed.rows[0].tb_ranges)

    report = engine.verify([("chiller-1", "energy")], start, half)
    print("verify:", report["diff_segments"], "differences")

    # Tamper with one point, verify again, then repair.
    ref = SeriesRef("chiller-1", "energy")
    store.upsert_points(ref, [(start + 3_600_000, 999.0)])
    print("after tamper:", engine.verify([ref], start, half)["diff_segments"], "differences")
    print("repair:", engine.repair([ref], start, half))
    print("after repair:", engine.verify([ref], start, half)["diff_segments"], "differences")


if __name__ == "__main__":
    main()
