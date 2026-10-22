# -*- coding: utf-8 -*-
"""Minimal library example — no store, no network.

Run::

    python examples/quickstart.py
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from hybrid_ladder import LadderEngine, MemorySource

TZ = ZoneInfo("Asia/Shanghai")


def ms(*args: int) -> int:
    return round(datetime(*args, tzinfo=TZ).timestamp() * 1000)


def main() -> None:
    start = ms(2026, 1, 1)
    end = ms(2026, 1, 2)
    source = MemorySource()
    source.add("chiller-1", "energy", [(ts, 1.0) for ts in range(start, end, 60_000)])

    engine = LadderEngine(source)
    result = engine.sum([("chiller-1", "energy")], start, end)

    print("segments:", result.rows[0].segments_count)
    print("total:", result.grand_total)
    for segment in result.rows[0].segments:
        print(f"  {segment.label:<18} {segment.level:<6} {segment.value}")


if __name__ == "__main__":
    main()
