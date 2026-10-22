# -*- coding: utf-8 -*-
"""PostgreSQL integration tests.

Skipped unless ``HL_TEST_PG_DSN`` points at a disposable database::

    HL_TEST_PG_DSN='postgresql://user:pass@127.0.0.1:5432/testdb' pytest -m integration
"""

from __future__ import annotations

import os
import uuid

import pytest
from helpers import ms

from hybrid_ladder import SeriesRef
from hybrid_ladder.stores.postgres import PostgresStore

DSN = os.getenv("HL_TEST_PG_DSN")
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not DSN, reason="HL_TEST_PG_DSN is not set"),
]


@pytest.fixture
def store():
    pytest.importorskip("psycopg")
    namespace = f"test-{uuid.uuid4().hex[:12]}"
    prefix = "hl_test_"
    store = PostgresStore(
        DSN,
        namespace=namespace,
        table_prefix=prefix,
        timezone="Asia/Shanghai",
    )
    yield store
    try:
        import psycopg

        with psycopg.connect(DSN) as conn:
            conn.execute(f'DELETE FROM {prefix}readings WHERE namespace=%s', (namespace,))
            conn.execute(f'DELETE FROM {prefix}coverage WHERE namespace=%s', (namespace,))
    finally:
        store.close()


def test_upsert_sum_and_idempotency(store):
    ref = SeriesRef("device-1", "energy", "Chiller 1")
    start = ms(2026, 1, 1)
    points = [(start, 1.0), (start + 60_000, 2.0), (start + 120_000, 3.0)]
    assert store.upsert_points(ref, points, at_ms=ms(2030, 1, 1)) == 3
    # Writing the same timestamps again must not duplicate rows.
    assert store.upsert_points(ref, [(start, 10.0)], at_ms=ms(2030, 1, 1)) == 1

    sums = store.sum_ranges(ref, [(start, start + 180_000)])
    assert sums[start] == (15.0, 3)  # 10 + 2 + 3

    series = store.series(ref, start, start + 180_000)
    assert [row["ts"] for row in series] == [start, start + 60_000, start + 120_000]
    assert series[0]["value"] == 10.0


def test_coverage_lifecycle(store):
    ref = SeriesRef("device-1", "energy")
    start = ms(2026, 1, 1)
    end = start + 3_600_000
    assert store.coverage(ref) == []
    store.mark_covered(ref, start, end, 60, ms(2030, 1, 1))
    assert store.coverage(ref) == [(start, end, ms(2030, 1, 1))]
    assert store.clear_coverage(ref, start + 1_800_000, end + 1) == 1
    assert store.coverage(ref) == []


def test_delete_and_replace(store):
    ref = SeriesRef("device-1", "energy")
    start = ms(2026, 1, 1)
    store.upsert_points(
        ref,
        [(start, 1.0), (start + 60_000, 2.0), (start + 120_000, 3.0)],
        at_ms=ms(2030, 1, 1),
    )
    assert store.delete_range(ref, start + 60_000, start + 120_000) == 1
    assert store.sum_ranges(ref, [(start, start + 180_000)])[start] == (4.0, 2)

    result = store.replace_range(
        ref,
        start,
        start + 180_000,
        [(start + 30_000, 7.0), (start + 90_000, 8.0)],
        at_ms=ms(2030, 1, 1),
    )
    assert result == {"deleted": 2, "inserted": 2}
    assert store.sum_ranges(ref, [(start, start + 180_000)])[start] == (15.0, 2)


def test_empty_range_returns_none(store):
    ref = SeriesRef("device-1", "energy")
    start = ms(2026, 1, 1)
    assert store.sum_ranges(ref, [(start, start + 60_000)])[start] == (None, 0)


def test_partitions_are_created_across_months(store):
    ref = SeriesRef("device-1", "energy")
    start = ms(2026, 1, 31, 23, 0)
    points = [(start, 1.0), (start + 3_600_000, 2.0), (start + 7_200_000, 3.0)]
    store.upsert_points(ref, points, at_ms=ms(2030, 1, 1))
    assert store.sum_ranges(ref, [(start, start + 7_200_001)])[start] == (6.0, 3)
