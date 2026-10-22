# -*- coding: utf-8 -*-
"""Engine tests: source-only sums, folding, tails, batches, cancellation."""

from __future__ import annotations

import pytest
from helpers import ms

from hybrid_ladder import (
    CancelledError,
    LadderConfig,
    LadderEngine,
    MemorySource,
    MemoryStore,
    SourceError,
)
from hybrid_ladder.models import SeriesRef


def _minute_source(start: int, end: int, value: float = 1.0) -> MemorySource:
    source = MemorySource()
    points = []
    ts = start
    while ts < end:
        points.append((ts, value))
        ts += 60_000
    source.add("dev", "key", points)
    return source


def test_single_level_sum(ten_days, engine):
    _, start, end = ten_days
    result = engine.sum([("dev-1", "energy")], start, end)
    # 10 days x 96 points/day, values cycle 1,2,3,4 => 240 per day
    assert result.grand_total == 2400.0
    assert result.rows[0].segments_count == 10
    assert all(segment.level == "day" for segment in result.rows[0].segments)
    assert result.rows[0].empty_count == 0


def test_multilevel_query_is_exact():
    """Regression: the original grouped segments without checking their level.

    A 97-segment range must be fetched per level; fetching the whole range at
    the coarsest level assigned whole days to the first hour and lost the rest.
    """
    start, end = ms(2026, 1, 1), ms(2026, 10, 21, 18, 49, 59)
    source = _minute_source(start, end)
    expected = len(source.points("dev", "key"))
    assert expected > 400_000

    result = LadderEngine(source).sum([("dev", "key")], start, end)
    assert result.grand_total == float(expected)
    assert result.rows[0].empty_count == 0

    segments = result.rows[0].segments
    hours = [s for s in segments if s.level == "hour"]
    minutes = [s for s in segments if s.level == "minute"]
    assert [s.value for s in hours] == [60.0] * 18
    assert [s.value for s in minutes[:3]] == [1.0, 1.0, 1.0]
    assert segments[-1].value == 1.0  # the 18:49 tail
    assert segments[-1].cnt == 1


def test_empty_vs_zero():
    start = ms(2026, 1, 1)
    source = MemorySource()
    source.add(
        "dev",
        "key",
        [
            (start + 3_600_000, 0.0),
            (start + 5_400_000, 0.0),
            (start + 7_200_000, 5.0),
        ],
    )
    result = LadderEngine(source).sum(
        [("dev", "key")], start, start + 3 * 3_600_000, finest="hour"
    )
    segments = result.rows[0].segments
    assert [s.value for s in segments] == [None, 0.0, 5.0]
    assert [s.source for s in segments] == ["empty", "tb", "tb"]
    assert result.grand_total == 5.0
    assert result.rows[0].empty_count == 1


def test_subminute_tail():
    start = ms(2026, 10, 21, 18, 49)
    source = MemorySource()
    source.add(
        "dev",
        "key",
        [(start, 1.0), (start + 30_000, 2.0), (start + 59_000, 100.0)],
    )
    result = LadderEngine(source).sum([("dev", "key")], start, start + 59_000)
    segment = result.rows[0].segments[0]
    assert segment.is_subminute_tail
    assert segment.value == 3.0  # the point exactly at end is excluded
    assert segment.cnt == 2
    assert segment.source == "tb"
    assert result.grand_total == 3.0


def test_subminute_tail_empty():
    start = ms(2026, 10, 21, 18, 49)
    source = MemorySource()
    result = LadderEngine(source).sum([("dev", "key")], start, start + 30_000)
    segment = result.rows[0].segments[0]
    assert segment.value is None
    assert segment.source == "empty"
    assert result.grand_total is None


def test_finest_hour_tail():
    start = ms(2026, 1, 1)
    end = start + 5 * 3_600_000 + 30 * 60_000
    source = _minute_source(start, end)
    result = LadderEngine(source).sum([("dev", "key")], start, end, finest="hour")
    segments = result.rows[0].segments
    assert len(segments) == 6
    assert [s.value for s in segments] == [60.0, 60.0, 60.0, 60.0, 60.0, 30.0]
    assert segments[-1].duration_ms == 30 * 60_000
    assert segments[-1].expected == 30
    assert result.grand_total == 330.0


def test_batch_preserves_order_and_reports_progress():
    start = ms(2026, 1, 1)
    source = MemorySource()
    source.add("a", "k", [(start + i * 60_000, 1.0) for i in range(60)])
    source.add("b", "k", [(start + i * 60_000, 2.0) for i in range(60)])
    seen = []
    result = LadderEngine(source).sum(
        [("a", "k"), ("b", "k")],
        start,
        start + 3_600_000,
        finest="hour",
        progress=lambda done, total, message: seen.append((done, total)),
    )
    assert [row.total for row in result.rows] == [60.0, 120.0]
    assert result.grand_total == 180.0
    assert seen[-1] == (2, 2)


def test_continue_on_error():
    start = ms(2026, 1, 1)

    class Flaky(MemorySource):
        def interval_agg(self, ref, *args, **kwargs):
            if ref.key == "bad":
                raise SourceError("boom")
            return super().interval_agg(ref, *args, **kwargs)

    source = Flaky()
    source.add("a", "good", [(start + i * 60_000, 1.0) for i in range(60)])
    source.add("a", "bad", [(start + i * 60_000, 1.0) for i in range(60)])
    engine = LadderEngine(source, config=LadderConfig(continue_on_error=True))
    result = engine.sum([("a", "good"), ("a", "bad")], start, start + 3_600_000)
    assert result.rows[0].total == 60.0
    assert result.rows[1].total is None
    assert "boom" in (result.rows[1].error or "")
    assert len(result.errors) == 1


def test_failure_propagates_by_default():
    start = ms(2026, 1, 1)

    class Broken(MemorySource):
        def interval_agg(self, ref, *args, **kwargs):
            raise SourceError("nope")

    source = Broken()
    source.add("a", "k", [(start, 1.0)])
    with pytest.raises(SourceError):
        LadderEngine(source).sum([("a", "k")], start, start + 3_600_000)


def test_cancel(ten_days):
    source, start, end = ten_days
    engine = LadderEngine(source)
    with pytest.raises(CancelledError):
        engine.sum([("dev-1", "energy")], start, end, cancel=lambda: True)


def test_no_refs(ten_days):
    source, start, end = ten_days
    result = LadderEngine(source).sum([], start, end)
    assert result.rows == []
    assert result.grand_total is None


def test_empty_source():
    start = ms(2026, 1, 1)
    result = LadderEngine(MemorySource()).sum(
        [SeriesRef("missing", "key")], start, start + 3_600_000
    )
    row = result.rows[0]
    assert row.total is None
    assert row.empty_count == row.segments_count == 1
    assert row.segments[0].source == "empty"


def test_one_year_month_folding():
    start, end = ms(2025, 1, 1), ms(2026, 1, 1)
    source = MemorySource()
    points = []
    ts = start
    while ts < end:
        points.append((ts, 1.0))
        ts += 86_400_000
    source.add("dev", "key", points)
    result = LadderEngine(source).sum([("dev", "key")], start, end)
    segments = result.rows[0].segments
    assert len(segments) == 12
    assert [s.level for s in segments] == ["month"] * 12
    assert [s.value for s in segments] == [
        31.0, 28.0, 31.0, 30.0, 31.0, 30.0, 31.0, 31.0, 30.0, 31.0, 30.0, 31.0
    ]
    assert result.grand_total == 365.0


def test_month_expected_and_cnt():
    start, end = ms(2026, 1, 1), ms(2026, 2, 1)
    source = _minute_source(start, end)
    result = LadderEngine(source).sum([("dev", "key")], start, end)
    segment = result.rows[0].segments[0]
    assert segment.level == "month"
    assert segment.expected == 31
    assert segment.cnt == 31
    assert segment.value == 44_640.0


def test_raw_split_keeps_boundary_point():
    """A raw chunk split must not drop a point exactly on the boundary.

    The source contract is [start, end).  Splitting at ``mid`` and ``mid + 1``
    (the old ThingsBoard-inclusive convention) loses the point at ``mid``.
    """
    start = ms(2026, 1, 1)
    count = 10_002  # even, so the split midpoint lands on a point
    end = start + count * 1_000
    source = MemorySource()
    source.add("dev", "key", [(start + i * 1_000, 1.0) for i in range(count)])
    store = MemoryStore()
    engine = LadderEngine(
        source,
        store,
        LadderConfig(max_points=10_000),
        clock=lambda: ms(2030, 1, 1),
    )
    result = engine.materialize([("dev", "key")], start, end)
    assert result["written"] == count
    assert engine.sum_local([("dev", "key")], start, end).grand_total == float(count)
