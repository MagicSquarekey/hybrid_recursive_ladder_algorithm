# -*- coding: utf-8 -*-
"""Bucket calculator primitives: build_buckets, delta_chain, folding."""

from __future__ import annotations

import itertools

import pytest
from helpers import ms

from hybrid_ladder import (
    ANOMALY_NEGATIVE_DELTA,
    ANOMALY_NO_CURRENT,
    ANOMALY_NO_NEXT,
    ANOMALY_NON_NUMERIC,
    ANOMALY_SAME_READING,
    build_buckets,
    delta_chain,
    fold_avg,
    fold_row_total,
)


class TestBuildBuckets:
    def test_day_buckets_tile_the_range(self):
        start, end = ms(2026, 10, 1), ms(2026, 10, 4)
        buckets = build_buckets(start, end, "day")
        assert [b.label for b in buckets] == ["2026-10-01", "2026-10-02", "2026-10-03"]
        assert buckets[0].start == start
        assert buckets[-1].end == end
        for previous, following in itertools.pairwise(buckets):
            assert previous.end == following.start
        assert sum(b.end - b.start for b in buckets) == end - start

    def test_month_buckets_use_calendar_months(self):
        buckets = build_buckets(ms(2025, 11, 1), ms(2026, 3, 1), "month")
        assert [b.label for b in buckets] == ["2025-11", "2025-12", "2026-01", "2026-02"]
        # February is 28 days, December 31.
        durations = {(b.label, b.end - b.start) for b in buckets}
        assert ("2026-02", 28 * 86_400_000) in durations
        assert ("2025-12", 31 * 86_400_000) in durations

    def test_hour_and_minute_alignments(self):
        buckets = build_buckets(ms(2026, 1, 1, 9), ms(2026, 1, 1, 12), "hour")
        assert len(buckets) == 3
        assert buckets[0].label == "2026-01-01 09:00"
        buckets = build_buckets(ms(2026, 1, 1, 9, 5), ms(2026, 1, 1, 9, 8), "minute")
        assert [b.label for b in buckets] == [
            "2026-01-01 09:05",
            "2026-01-01 09:06",
            "2026-01-01 09:07",
        ]

    def test_unaligned_start_is_rejected(self):
        with pytest.raises(ValueError, match="start_ms must be aligned"):
            build_buckets(ms(2026, 10, 1, 9, 30), ms(2026, 10, 2), "day")

    def test_unaligned_end_is_rejected(self):
        with pytest.raises(ValueError, match="end_ms must be aligned"):
            build_buckets(ms(2026, 10, 1), ms(2026, 10, 2, 12), "day")

    def test_bad_dimension_and_range(self):
        with pytest.raises(ValueError, match="dimension must be one of"):
            build_buckets(0, 60_000, "week")
        with pytest.raises(ValueError, match="end_ms must be greater"):
            build_buckets(60_000, 60_000, "minute")


class TestDeltaChain:
    def test_chain_with_extension_anchor(self):
        cells, total, ok = delta_chain([(0, 100.0), (60_000, 145.0)], (120_000, 189.2))
        assert [c.value for c in cells] == [45.0, 44.2]
        assert all(c.anomaly is None for c in cells)
        assert total == pytest.approx(89.2)
        assert ok == 2
        # The extension anchor is used, never emitted.
        assert [c.next_ts for c in cells] == [60_000, 120_000]

    def test_missing_next_reading(self):
        cells, total, ok = delta_chain([(0, 1.0)], None)
        assert cells[0].anomaly == ANOMALY_NO_NEXT
        assert cells[0].value is None
        assert (total, ok) == (0.0, 0)

    def test_missing_current_reading(self):
        # Meter deltas need an anchor in every bucket: when a middle bucket has
        # no reading, the bucket before it loses its "next" anchor as well.
        cells, _, ok = delta_chain([(0, 1.0), None], (120_000, 3.0))
        assert cells[0].anomaly == ANOMALY_NO_NEXT
        assert cells[1].anomaly == ANOMALY_NO_CURRENT
        assert ok == 0

    def test_same_reading_has_no_new_sample(self):
        point = (60_000, 5.0)
        cells, _, ok = delta_chain([point, point], None)
        assert cells[0].anomaly == ANOMALY_SAME_READING
        assert cells[0].value is None
        assert ok == 0

    def test_meter_reset_is_an_anomaly(self):
        cells, _, ok = delta_chain([(0, 100.0), (60_000, 40.0)], None)
        assert cells[0].anomaly == ANOMALY_NEGATIVE_DELTA
        assert ok == 0

    def test_non_numeric_reading_is_an_anomaly(self):
        cells, _, ok = delta_chain([(0, "NaN-text"), (60_000, 1.0)], None)
        assert cells[0].anomaly == ANOMALY_NON_NUMERIC
        assert ok == 0

    def test_zero_delta_is_a_valid_value(self):
        cells, total, ok = delta_chain([(0, 5.0), (60_000, 5.0)], None)
        assert cells[0].value == 0.0
        assert cells[0].anomaly is None
        assert (total, ok) == (0.0, 1)


class TestFolding:
    def test_fold_avg_weights_by_count(self):
        assert fold_avg([(10.0, 2), (30.0, 6)]) == pytest.approx(5.0)

    def test_fold_avg_empty(self):
        assert fold_avg([]) is None
        assert fold_avg([(None, 0)]) is None

    def test_row_total_sum_adds(self):
        assert fold_row_total("sum", [1.0, None, 2.5]) == 3.5
        assert fold_row_total("meter_delta", [1.0, 0.0]) == 1.0

    def test_row_total_avg_is_mean_of_means(self):
        assert fold_row_total("avg", [2.0, 4.0, None]) == 3.0

    def test_row_total_all_empty(self):
        assert fold_row_total("sum", [None, None]) is None
