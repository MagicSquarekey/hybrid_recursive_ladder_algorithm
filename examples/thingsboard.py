# -*- coding: utf-8 -*-
"""ThingsBoard source example.

Required environment::

    HL_TB_URL=https://tb.example.com
    HL_TB_TOKEN=...            # or HL_TB_USERNAME / HL_TB_PASSWORD

Optional::

    HL_PG_DSN=postgresql://user:pass@127.0.0.1:5432/telemetry

Run::

    python examples/thingsboard.py <device_id> <key> <start> <end>
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from hybrid_ladder import LadderConfig, LadderEngine
from hybrid_ladder.sources.thingsboard import ThingsBoardSource

TZ = ZoneInfo(os.getenv("HL_TIMEZONE", "Asia/Shanghai"))


def parse_time(value: str) -> int:
    text = value.strip()
    if text.isdigit():
        return int(text)
    dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ)
    return round(dt.timestamp() * 1000)


def main() -> int:
    if len(sys.argv) != 5:
        print(__doc__)
        return 2
    device_id, key, start_text, end_text = sys.argv[1:]
    base_url = os.getenv("HL_TB_URL")
    if not base_url:
        print("HL_TB_URL is required")
        return 2

    source = ThingsBoardSource(
        base_url,
        token=os.getenv("HL_TB_TOKEN"),
        username=os.getenv("HL_TB_USERNAME"),
        password=os.getenv("HL_TB_PASSWORD"),
    )
    store = None
    dsn = os.getenv("HL_PG_DSN")
    if dsn:
        from hybrid_ladder.stores.postgres import PostgresStore

        store = PostgresStore(
            dsn,
            namespace=os.getenv("HL_NAMESPACE", "default"),
            timezone=os.getenv("HL_TIMEZONE", "Asia/Shanghai"),
        )

    engine = LadderEngine(source, store, LadderConfig())
    start, end = parse_time(start_text), parse_time(end_text)
    result = engine.sum_mixed([(device_id, key)], start, end) if store else engine.sum(
        [(device_id, key)], start, end
    )
    print(f"total: {result.grand_total}")
    print(f"source: {result.source} {result.source_counts}")
    print(f"segments: {result.rows[0].segments_count} empty: {result.rows[0].empty_count}")
    if result.rows[0].tb_ranges:
        print(f"missing locally: {result.rows[0].tb_ranges}")
    source.close()
    if store:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
