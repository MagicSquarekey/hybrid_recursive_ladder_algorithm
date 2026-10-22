# -*- coding: utf-8 -*-
"""Local-first mixed reads, coverage splitting and materialization."""

from __future__ import annotations

from helpers import build_source, ms

from hybrid_ladder import LadderConfig, LadderEngine, MemorySource, MemoryStore, SeriesRef


def test_uncovered_reads_source(mixed_engine, ten_days):
    _source, start, end = ten_days
    pure = mixed_engine.sum([("dev-1", "energy")], start, end)
    mixed = mixed_engine.sum_mixed([("dev-1", "energy")], start, end)
    assert mixed.grand_total == pure.grand_total
    assert mixed.source == "tb"
    assert mixed.rows[0].tb_ranges == [(start, end)]
    assert mixed.source_counts == {"tb": 10}


def test_full_coverage_reads_local(mixed_engine, ten_days):
    _, start, end = ten_days
    pure = mixed_engine.sum([("dev-1", "energy")], start, end)
    written = mixed_engine.materialize([("dev-1", "energy")], start, end)
    assert written["written"] == 960

    mixed = mixed_engine.sum_mixed([("dev-1", "energy")], start, end)
    assert mixed.grand_total == pure.grand_total
    assert mixed.source == "local"
    assert mixed.rows[0].tb_ranges == []
    assert mixed.source_counts == {"local": 10}


def test_partial_coverage_is_mixed_and_exact(mixed_engine, ten_days):
    _, start, end = ten_days
    pure = mixed_engine.sum([("dev-1", "energy")], start, end)
    half = start + 5 * 86_400_000 + 12 * 3_600_000  # day 5, 12:00
    mixed_engine.materialize([("dev-1", "energy")], start, half)

    mixed = mixed_engine.sum_mixed([("dev-1", "energy")], start, end)
    assert mixed.grand_total == pure.grand_total
    assert mixed.source == "mixed"

    segments = mixed.rows[0].segments
    assert [s.source for s in segments] == [
        "local", "local", "local", "local", "local", "mixed", "tb", "tb", "tb", "tb"
    ]
    assert mixed.rows[0].tb_ranges == [(half, end)]
    assert mixed.source_counts == {"local": 5, "mixed": 1, "tb": 4}


def test_mixed_read_with_data_gap():
    source, start, end = build_source(days=10)
    # Remove one full day (day 3) to exercise empty segments on both sides.
    points = [
        (ts, value)
        for ts, value in source.points("dev-1", "energy")
        if not (start + 3 * 86_400_000 <= ts < start + 4 * 86_400_000)
    ]
    source = MemorySource().add("dev-1", "energy", points)
    store = MemoryStore()
    engine = LadderEngine(source, store, clock=lambda: ms(2030, 1, 1))

    pure = engine.sum([("dev-1", "energy")], start, end)
    engine.materialize([("dev-1", "energy")], start, start + 5 * 86_400_000)
    mixed = engine.sum_mixed([("dev-1", "energy")], start, end)
    assert mixed.grand_total == pure.grand_total
    assert any(s.value is None for s in mixed.rows[0].segments)
    report = engine.verify([("dev-1", "energy")], start, start + 5 * 86_400_000)
    assert report["diff_segments"] == 0


def test_sum_local_offline(mixed_engine, ten_days):
    _, start, end = ten_days
    pure = mixed_engine.sum([("dev-1", "energy")], start, end)
    mixed_engine.materialize([("dev-1", "energy")], start, end)
    local = mixed_engine.sum_local([("dev-1", "energy")], start, end)
    assert local.grand_total == pure.grand_total
    assert local.source == "local"
    assert local.rows[0].tb_ranges == []
    assert all(s.source in ("local", "empty") for s in local.rows[0].segments)


def test_materialize_zero_points_marks_coverage():
    start = ms(2026, 1, 1)
    end = start + 3_600_000
    store = MemoryStore()
    engine = LadderEngine(MemorySource(), store, clock=lambda: ms(2030, 1, 1))
    result = engine.materialize([("missing", "key")], start, end)
    assert result["written"] == 0
    assert store.coverage(SeriesRef("missing", "key")) == [
        (start, end, ms(2030, 1, 1))
    ]

    mixed = engine.sum_mixed([("missing", "key")], start, end)
    assert mixed.source == "local"
    assert mixed.rows[0].tb_ranges == []
    assert mixed.rows[0].segments[0].source == "empty"
    assert mixed.grand_total is None


def test_materialize_respects_grace_period():
    start = ms(2026, 1, 1)
    end = start + 3_600_000
    store = MemoryStore()
    now = end - 60_000  # one minute before the range ends
    engine = LadderEngine(MemorySource(), store, clock=lambda: now)
    engine.materialize([("dev", "key")], start, end)
    coverage = store.coverage(SeriesRef("dev", "key"))
    assert coverage == [(start, now - 5 * 60_000, now)]


def test_materialize_future_range_is_not_covered():
    start = ms(2026, 1, 1)
    end = start + 3_600_000
    store = MemoryStore()
    engine = LadderEngine(MemorySource(), store, clock=lambda: start + 60_000)
    result = engine.materialize([("dev", "key")], start, end)
    assert result["written"] == 0
    assert store.coverage(SeriesRef("dev", "key")) == []


def test_materialize_replaces_coverage_rows():
    source, start, end = build_source()
    store = MemoryStore()
    engine = LadderEngine(source, store, clock=lambda: ms(2030, 1, 1))
    engine.materialize([("dev-1", "energy")], start, end)
    engine.materialize([("dev-1", "energy")], start, end)

    assert len(store.coverage(SeriesRef("dev-1", "energy"))) == 1
    assert engine.sum_local([("dev-1", "energy")], start, end).grand_total == 2400.0


def test_mixed_custom_concurrency():
    source, start, end = build_source()
    source.add("dev-2", "energy", source.points("dev-1", "energy"))
    store = MemoryStore()
    engine = LadderEngine(
        source, store, LadderConfig(concurrency=1), clock=lambda: ms(2030, 1, 1)
    )
    engine.materialize([("dev-1", "energy"), ("dev-2", "energy")], start, end)
    result = engine.sum_mixed(
        [("dev-1", "energy"), ("dev-2", "energy")], start, end
    )
    assert [row.total for row in result.rows] == [2400.0, 2400.0]
    assert result.grand_total == 4800.0
