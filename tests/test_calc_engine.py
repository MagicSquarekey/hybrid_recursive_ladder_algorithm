# -*- coding: utf-8 -*-
"""Bucket calculator engine tests: sum / avg / meter_delta, tb / mixed / local."""

from __future__ import annotations

import pytest
from helpers import ms

from hybrid_ladder import (
    ANOMALY_NEGATIVE_DELTA,
    ANOMALY_NO_CURRENT,
    ANOMALY_NO_NEXT,
    ANOMALY_SAME_READING,
    LadderEngine,
    MemorySource,
    MemoryStore,
    SeriesRef,
)

DAY = 86_400_000


def _hourly_source(days: int = 3, value: float = 1.0) -> tuple[MemorySource, int, int]:
    start, end = ms(2026, 11, 1), ms(2026, 11, 1 + days)
    points = [(start + hour * 3_600_000, value) for hour in range(days * 24)]
    source = MemorySource()
    source.add("dev-1", "energy", points)
    return source, start, end


class TestSumAndAvg:
    def test_day_sum_buckets(self):
        source, start, end = _hourly_source(3)
        engine = LadderEngine(source)
        result = engine.calc([("dev-1", "energy")], start, end, dimension="day", rule="sum")
        row = result.rows[0]
        assert [b.label for b in row.buckets] == ["2026-11-01", "2026-11-02", "2026-11-03"]
        assert [b.value for b in row.buckets] == [24.0, 24.0, 24.0]
        assert [b.cnt for b in row.buckets] == [24, 24, 24]
        assert all(b.source == "tb" for b in row.buckets)
        assert row.total == 72.0
        assert result.grand_total == 72.0
        assert result.source_counts == {"tb": 3}

    def test_day_avg_buckets(self):
        source, start, end = _hourly_source(2, value=2.0)
        engine = LadderEngine(source)
        result = engine.calc([("dev-1", "energy")], start, end, dimension="day", rule="avg")
        row = result.rows[0]
        assert [b.value for b in row.buckets] == [2.0, 2.0]
        # Row total is the mean of means, not the weighted average.
        assert row.total == 2.0

    def test_avg_grand_total_is_mean_of_rows(self):
        start, end = ms(2026, 11, 1), ms(2026, 11, 2)
        source = MemorySource()
        source.add("a", "k", [(start, 1.0), (start + 60_000, 3.0)])  # avg 2.0
        source.add("b", "k", [(start, 10.0)])  # avg 10.0
        engine = LadderEngine(source)
        result = engine.calc([("a", "k"), ("b", "k")], start, end,
                             dimension="day", rule="avg")
        assert [r.total for r in result.rows] == [2.0, 10.0]
        assert result.grand_total == 6.0

    def test_month_buckets_fold_from_days(self):
        start, end = ms(2025, 11, 1), ms(2026, 2, 1)
        source = MemorySource()
        points = []
        cursor = start
        while cursor < end:
            points.append((cursor, 1.0))
            cursor += DAY
        source.add("dev-1", "energy", points)
        engine = LadderEngine(source)
        result = engine.calc([("dev-1", "energy")], start, end, dimension="month", rule="sum")
        assert [b.label for b in result.rows[0].buckets] == ["2025-11", "2025-12", "2026-01"]
        assert [b.value for b in result.rows[0].buckets] == [30.0, 31.0, 31.0]
        assert result.rows[0].total == 92.0

    def test_minute_buckets_without_data_are_empty_not_zero(self):
        start, end = ms(2026, 11, 1, 9), ms(2026, 11, 1, 9, 2)
        source = MemorySource()
        source.add("dev-1", "energy", [(start, 5.0)])  # only 09:00 has a point
        engine = LadderEngine(source)
        result = engine.calc([("dev-1", "energy")], start, end, dimension="minute", rule="sum")
        row = result.rows[0]
        assert [b.value for b in row.buckets] == [5.0, None]
        assert [b.source for b in row.buckets] == ["tb", "empty"]
        assert row.total == 5.0

    def test_source_only_sum_matches_ladder_sum(self):
        source, start, end = _hourly_source(3, value=1.5)
        engine = LadderEngine(source)
        calc = engine.calc([("dev-1", "energy")], start, end, dimension="day", rule="sum")
        ladder = engine.sum([("dev-1", "energy")], start, end)
        assert calc.grand_total == ladder.grand_total

    def test_grouped_fetch_keeps_requests_low(self):
        class CountingSource:
            def __init__(self, inner):
                self.inner = inner
                self.interval_calls = 0

            def interval_agg(self, ref, start_ms, end_ms, bucket_ms, agg="SUM"):
                self.interval_calls += 1
                return self.inner.interval_agg(ref, start_ms, end_ms, bucket_ms, agg)

            def raw_series(self, ref, start_ms, end_ms, limit=10_000):
                return self.inner.raw_series(ref, start_ms, end_ms, limit)

        source, start, end = _hourly_source(3)
        counting = CountingSource(source)
        engine = LadderEngine(counting)
        engine.calc([("dev-1", "energy")], start, end, dimension="day", rule="sum")
        # 3 days fold from hours: one chunk, one SUM and one COUNT request.
        assert counting.interval_calls == 2

    def test_bad_args(self):
        source, start, end = _hourly_source(1)
        engine = LadderEngine(source)
        with pytest.raises(ValueError, match="rule must be one of"):
            engine.calc([("dev-1", "energy")], start, end, rule="median")
        with pytest.raises(ValueError, match="dimension must be one of"):
            engine.calc([("dev-1", "energy")], start, end, dimension="week")
        with pytest.raises(ValueError, match="start_ms must be aligned"):
            engine.calc([("dev-1", "energy")], start + 3_600_000, end, dimension="day")
        with pytest.raises(ValueError, match="end_ms must be aligned"):
            engine.calc([("dev-1", "energy")], start, end + 60_000, dimension="day")


class TestMeterDelta:
    def _meter_source(self):
        start = ms(2026, 11, 1)
        source = MemorySource()
        source.add("meter", "total", [
            (start, 100.0),
            (start + DAY, 145.0),
            (start + 2 * DAY, 189.2),
            (start + 3 * DAY, 210.0),
        ])
        return source, start

    def test_delta_reads_one_bucket_past_end(self):
        source, start = self._meter_source()
        engine = LadderEngine(source)
        end = start + 2 * DAY  # 2026-11-01 -> 2026-11-03
        result = engine.calc([("meter", "total")], start, end, dimension="day", rule="meter_delta")
        row = result.rows[0]
        assert [b.value for b in row.buckets] == [45.0, 44.2]
        assert all(b.anomaly is None for b in row.buckets)
        # Telescoping invariant: the sum equals last anchor - first anchor.
        assert row.total == pytest.approx(189.2 - 100.0)
        assert row.ok == 2
        assert result.grand_total == pytest.approx(89.2)

    def test_silent_meter_falls_back_to_previous_reading(self):
        start = ms(2026, 11, 1)
        source = MemorySource()
        # One reading on 11-01, nothing until 11-04; 11-02 and 11-03 fall back.
        source.add("meter", "total", [
            (start, 100.0),
            (start + 3 * DAY, 130.0),
        ])
        engine = LadderEngine(source)
        end = start + 3 * DAY  # buckets 11-01, 11-02, 11-03
        result = engine.calc([("meter", "total")], start, end, dimension="day", rule="meter_delta")
        row = result.rows[0]
        # 11-02 has no reading, so it reuses the 11-01 anchor: same reading.
        assert row.buckets[0].anomaly == ANOMALY_SAME_READING
        assert row.buckets[0].value is None
        # 11-03 has no reading within the 1-day lookback: no anchor at all.
        assert row.buckets[1].anomaly == ANOMALY_NO_NEXT
        # The 11-04 reading anchors the last bucket from outside the range.
        assert row.buckets[2].anomaly == ANOMALY_NO_CURRENT
        assert row.ok == 0
        assert row.total is None

    def test_no_current_reading_when_lookback_is_exceeded(self):
        start = ms(2026, 11, 4)  # readings exist only from 11-05 on
        source = MemorySource()
        source.add("meter", "total", [(start + DAY, 50.0)])
        engine = LadderEngine(source)
        end = start + 2 * DAY
        result = engine.calc([("meter", "total")], start, end, dimension="day", rule="meter_delta")
        row = result.rows[0]
        assert row.buckets[0].anomaly == ANOMALY_NO_CURRENT
        assert row.buckets[0].value is None
        # The 11-05 reading is also the extension fallback, so 11-05 repeats it.
        assert row.buckets[1].anomaly == ANOMALY_SAME_READING
        assert row.ok == 0
        assert row.total is None

    def test_meter_reset_is_reported_not_invented(self):
        start = ms(2026, 11, 1)
        source = MemorySource()
        source.add("meter", "total", [(start, 100.0), (start + DAY, 40.0)])
        engine = LadderEngine(source)
        result = engine.calc([("meter", "total")], start, start + DAY,
                              dimension="day", rule="meter_delta")
        row = result.rows[0]
        assert row.buckets[0].anomaly == ANOMALY_NEGATIVE_DELTA
        assert row.buckets[0].value is None
        assert row.total is None

    def test_delta_matches_local_when_fully_materialized(self):
        source, start = self._meter_source()
        end = start + 2 * DAY
        store = MemoryStore()
        ref = SeriesRef("meter", "total")
        engine = LadderEngine(source, store)
        engine.materialize(ref, start - 4 * DAY, end + DAY)

        source_result = LadderEngine(source).calc(ref, start, end, dimension="day",
                                                  rule="meter_delta")
        local_result = engine.calc_local(ref, start, end, dimension="day",
                                         rule="meter_delta")
        mixed_result = engine.calc_mixed(ref, start, end, dimension="day",
                                          rule="meter_delta")
        for result in (source_result, local_result, mixed_result):
            assert [b.value for b in result.rows[0].buckets] == [45.0, 44.2]
            assert result.rows[0].total == pytest.approx(89.2)
        assert all(b.source == "local" for b in local_result.rows[0].buckets)
        assert all(b.source == "local" for b in mixed_result.rows[0].buckets)


class TestMixedReads:
    def test_partial_coverage_combines_local_and_source(self):
        source, start, end = _hourly_source(3)
        store = MemoryStore()
        engine = LadderEngine(source, store)
        ref = SeriesRef("dev-1", "energy")
        engine.materialize(ref, start, start + 2 * DAY)  # first two days local

        result = engine.calc_mixed(ref, start, end, dimension="day", rule="sum")
        row = result.rows[0]
        assert [b.value for b in row.buckets] == [24.0, 24.0, 24.0]
        assert [b.source for b in row.buckets] == ["local", "local", "tb"]
        assert row.tb_ranges == [(start + 2 * DAY, end)]
        assert result.source == "mixed"
        assert result.source_counts == {"local": 2, "tb": 1}

    def test_partially_covered_bucket_is_split(self):
        source, start, end = _hourly_source(2)
        store = MemoryStore()
        engine = LadderEngine(source, store)
        ref = SeriesRef("dev-1", "energy")
        # Cover only the first 12 hours of day 2.
        engine.materialize(ref, start + DAY, start + DAY + 12 * 3_600_000)

        result = engine.calc_mixed(ref, start, end, dimension="day", rule="sum")
        row = result.rows[0]
        assert [b.value for b in row.buckets] == [24.0, 24.0]
        assert [b.source for b in row.buckets] == ["tb", "mixed"]
        # Day 1 is fully uncovered and only the second half of day 2 is missing.
        assert row.tb_ranges == [
            (start, start + DAY),
            (start + DAY + 12 * 3_600_000, start + 2 * DAY),
        ]

    def test_mixed_equals_pure_source(self):
        source, start, end = _hourly_source(4)
        store = MemoryStore()
        engine = LadderEngine(source, store)
        ref = SeriesRef("dev-1", "energy")
        engine.materialize(ref, start + DAY, start + 3 * DAY)

        mixed = engine.calc_mixed(ref, start, end, dimension="day", rule="sum")
        pure = LadderEngine(source).calc(ref, start, end, dimension="day", rule="sum")
        assert [b.value for b in mixed.rows[0].buckets] == \
            [b.value for b in pure.rows[0].buckets]
        assert mixed.grand_total == pure.grand_total

    def test_local_only_reads_the_store(self):
        source, start, end = _hourly_source(2)
        store = MemoryStore()
        engine = LadderEngine(source, store)
        ref = SeriesRef("dev-1", "energy")
        engine.materialize(ref, start, end)

        result = engine.calc_local(ref, start, end, dimension="day", rule="sum")
        assert [b.value for b in result.rows[0].buckets] == [24.0, 24.0]
        assert result.source == "local"

    def test_source_reads_need_no_store(self):
        source, start, end = _hourly_source(1)
        engine = LadderEngine(source)  # no store at all
        result = engine.calc([("dev-1", "energy")], start, end, dimension="day", rule="avg")
        assert result.rows[0].buckets[0].value == 1.0
