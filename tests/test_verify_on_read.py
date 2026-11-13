# -*- coding: utf-8 -*-
"""Query-time verification tests: consistent / mismatch / unverified / heal."""

from __future__ import annotations

import pytest
from helpers import ms

from hybrid_ladder import LadderEngine, MemorySource, MemoryStore, SeriesRef

DAY = 86_400_000


def _hourly_source(days: int = 3, value: float = 1.0):
    start, end = ms(2026, 11, 1), ms(2026, 11, 1 + days)
    points = [(start + hour * 3_600_000, value) for hour in range(days * 24)]
    source = MemorySource()
    source.add("dev-1", "energy", points)
    return source, start, end


class TestSumMixedVerification:
    def test_consistent_run_stays_local(self):
        source, start, end = _hourly_source(3)
        store = MemoryStore()
        engine = LadderEngine(source, store)
        ref = SeriesRef("dev-1", "energy")
        engine.materialize(ref, start, end)

        result = engine.sum_mixed([ref], start, end)
        assert result.verify == {
            "verified": 1,
            "consistent": 1,
            "mismatched": 0,
            "unverified": 0,
            "mismatched_detail": [],
        }
        assert result.source == "local"
        assert result.rows[0].tb_ranges == []

    def test_tampered_run_is_detected_and_bypassed(self):
        source, start, end = _hourly_source(3)
        store = MemoryStore()
        engine = LadderEngine(source, store)
        ref = SeriesRef("dev-1", "energy")
        engine.materialize(ref, start, end)
        # Corrupt one local point; the SUM fingerprint must catch it.
        store.upsert_points(ref, [(start + 60_000, 999.0)])

        result = engine.sum_mixed([ref], start, end)
        assert result.verify["mismatched"] == 1
        detail = result.verify["mismatched_detail"][0]
        assert detail["source"] == 72.0 and detail["local"] == 1071.0
        # The numbers are still correct: the mismatched run was read from the source.
        assert result.grand_total == 72.0
        assert result.rows[0].tb_ranges == [(start, end)]

    def test_mismatch_self_heals_with_materialize(self):
        source, start, end = _hourly_source(3)
        store = MemoryStore()
        engine = LadderEngine(source, store)
        ref = SeriesRef("dev-1", "energy")
        engine.materialize(ref, start, end)
        store.upsert_points(ref, [(start + 60_000, 999.0)])

        first = engine.sum_mixed([ref], start, end)
        assert first.verify["mismatched"] == 1
        # Re-materialize the reported tb_ranges, then verify again.
        engine.materialize_ranges(
            [(row.ref, row.tb_ranges) for row in first.rows if row.tb_ranges]
        )
        second = engine.sum_mixed([ref], start, end)
        assert second.verify["mismatched"] == 0
        assert second.verify["consistent"] == 1
        assert second.source == "local"

    def test_unreachable_source_does_not_block_the_read(self):
        source, start, end = _hourly_source(2)

        class DownSource:
            def __init__(self, inner):
                self.inner = inner

            def interval_agg(self, *a, **k):
                raise RuntimeError("source unreachable")

            def raw_series(self, *a, **k):
                raise RuntimeError("source unreachable")

        store = MemoryStore()
        engine = LadderEngine(source, store)
        ref = SeriesRef("dev-1", "energy")
        engine.materialize(ref, start, end)

        engine_down = LadderEngine(DownSource(source), store)
        result = engine_down.sum_mixed([ref], start, end)
        assert result.verify["unverified"] == 1
        assert result.verify["consistent"] == 0
        # The local copy is used; the query is not blocked.
        assert result.source == "local"
        assert result.grand_total == 48.0

    def test_opt_out_restores_the_old_trusting_behavior(self):
        source, start, end = _hourly_source(3)
        store = MemoryStore()
        engine = LadderEngine(source, store)
        ref = SeriesRef("dev-1", "energy")
        engine.materialize(ref, start, end)
        store.upsert_points(ref, [(start + 60_000, 999.0)])

        result = engine.sum_mixed([ref], start, end, verify_on_read=False)
        assert result.verify is None
        # Stale local data is served silently (the pre-0.0.8 behaviour):
        # the tampered point adds 999 to the local total.
        assert result.grand_total == 1071.0

    def test_config_flag_off_and_per_call_on(self):
        source, start, end = _hourly_source(3)
        store = MemoryStore()
        engine = LadderEngine(source, store)
        engine.config.verify_on_read = False
        ref = SeriesRef("dev-1", "energy")
        engine.materialize(ref, start, end)
        store.upsert_points(ref, [(start + 60_000, 999.0)])

        default_off = engine.sum_mixed([ref], start, end)
        assert default_off.verify is None
        forced_on = engine.sum_mixed([ref], start, end, verify_on_read=True)
        assert forced_on.verify["mismatched"] == 1

    def test_coverage_outside_the_window_is_not_verified(self):
        source, start, end = _hourly_source(4)
        store = MemoryStore()
        engine = LadderEngine(source, store)
        ref = SeriesRef("dev-1", "energy")
        # Materialize all four days, then corrupt a point in day 1 only.
        engine.materialize(ref, start, end)
        store.upsert_points(ref, [(start + 60_000, 999.0)])

        window_start = start + 2 * DAY
        result = engine.sum_mixed([ref], window_start, end)
        # Day 1 is outside the window: no verification, no mismatch reported.
        assert result.verify["verified"] == 1
        assert result.verify["consistent"] == 1
        assert result.verify["mismatched"] == 0


class TestCalcMixedVerification:
    def test_tampered_bucket_is_detected_and_bypassed(self):
        source, start, end = _hourly_source(3)
        store = MemoryStore()
        engine = LadderEngine(source, store)
        ref = SeriesRef("dev-1", "energy")
        engine.materialize(ref, start, end)
        store.upsert_points(ref, [(start + 60_000, 999.0)])

        result = engine.calc_mixed([ref], start, end, dimension="day", rule="sum")
        assert result.verify["mismatched"] == 1
        assert [b.value for b in result.rows[0].buckets] == [24.0, 24.0, 24.0]
        assert result.rows[0].tb_ranges == [(start, end)]
        assert result.grand_total == 72.0

    def test_meter_delta_window_covers_the_extension_bucket(self):
        start = ms(2026, 11, 1)
        source = MemorySource()
        source.add("meter", "total", [
            (start, 100.0), (start + DAY, 145.0),
            (start + 2 * DAY, 189.2), (start + 3 * DAY, 210.0),
        ])
        store = MemoryStore()
        engine = LadderEngine(source, store)
        ref = SeriesRef("meter", "total")
        # Materialize through the extension bucket so everything is covered.
        engine.materialize(ref, start - 4 * DAY, start + 4 * DAY)
        # Corrupt the reading that anchors the last bucket from the extension
        # window [end, end+1d); it lies inside the verification window.
        store.upsert_points(ref, [(start + 2 * DAY, 500.0)])

        end = start + 2 * DAY
        result = engine.calc_mixed([ref], start, end, dimension="day",
                                   rule="meter_delta")
        # The SUM fingerprint caught the tamper; every anchor then came from
        # the source, so the deltas are still correct.
        assert result.verify["mismatched"] >= 1
        assert [b.value for b in result.rows[0].buckets] == [45.0, 44.2]
        assert result.rows[0].total == pytest.approx(89.2)


class TestDeltaCursorEfficiency:
    def test_empty_wide_range_keeps_source_calls_bounded(self):
        class CountingSource:
            def __init__(self):
                self.interval_calls = 0
                self.raw_calls = 0

            def interval_agg(self, ref, start_ms, end_ms, bucket_ms, agg="SUM"):
                self.interval_calls += 1
                return {}

            def raw_series(self, ref, start_ms, end_ms, limit=10_000):
                self.raw_calls += 1
                return []

        start = ms(2026, 11, 1)
        end = start + 2 * DAY
        source = CountingSource()
        engine = LadderEngine(source)
        result = engine.calc([("m", "k")], start, end,
                             dimension="minute", rule="meter_delta")
        # One merged uncovered run (plus its lookback) -> one raw fetch;
        # no per-bucket source traffic for 2,880 empty buckets.
        assert source.raw_calls == 1
        assert source.interval_calls == 0
        assert result.rows[0].ok == 0
        assert result.rows[0].total is None

    def test_cursor_matches_bisect_results_on_sparse_data(self):
        # Sparse meter with lookback fallbacks and repeated readings; the
        # single-cursor rewrite must reproduce the bisect semantics exactly.
        start = ms(2026, 11, 1)
        source = MemorySource()
        source.add("meter", "total", [
            (start, 10.0),
            (start + DAY, 10.0),            # same reading -> anomaly
            (start + 3 * DAY, 30.0),         # silence on day 2/3
            (start + 6 * DAY, 80.0),
        ])
        engine = LadderEngine(source)
        end = start + 7 * DAY
        source_result = engine.calc([("meter", "total")], start, end,
                                    dimension="day", rule="meter_delta")
        store = MemoryStore()
        engine2 = LadderEngine(source, store)
        engine2.materialize([("meter", "total")], start - 8 * DAY, end + DAY)
        mixed_result = engine2.calc_mixed([("meter", "total")], start, end,
                                         dimension="day", rule="meter_delta")
        for source_row, mixed_row in zip(source_result.rows, mixed_result.rows, strict=True):
            assert [(b.value, b.anomaly) for b in source_row.buckets] == \
                [(b.value, b.anomaly) for b in mixed_row.buckets]
