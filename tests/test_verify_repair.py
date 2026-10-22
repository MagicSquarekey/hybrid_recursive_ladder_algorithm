# -*- coding: utf-8 -*-
"""Verification and repair tests."""

from __future__ import annotations

from helpers import build_source, ms

from hybrid_ladder import (
    ConfigurationError,
    LadderConfig,
    LadderEngine,
    MemorySource,
    MemoryStore,
    SeriesRef,
)


def _setup():
    source, start, end = build_source(days=10)
    store = MemoryStore()
    engine = LadderEngine(source, store, clock=lambda: ms(2030, 1, 1))
    engine.materialize([("dev-1", "energy")], start, end)
    return source, store, engine, start, end


def test_verify_clean():
    _, _, engine, start, end = _setup()
    report = engine.verify([("dev-1", "energy")], start, end)
    assert report["diff_series"] == 0
    assert report["diff_segments"] == 0
    assert report["details"] == []


def test_verify_detects_changed_point():
    source, store, engine, start, end = _setup()
    ref = SeriesRef("dev-1", "energy")
    ts = start + 2 * 86_400_000 + 5 * 3_600_000  # day 2, 05:00
    original = dict(source.points("dev-1", "energy"))[ts]
    store.upsert_points(ref, [(ts, original + 999)])

    report = engine.verify([("dev-1", "energy")], start, end)
    assert report["diff_series"] == 1
    assert report["diff_segments"] == 1
    assert report["drilled"] == 1
    diff = report["details"][0]["diffs"][0]
    assert diff["changed"] == 1
    assert diff["added"] == 0
    assert diff["removed"] == 0
    assert ts in diff["sample_changed"]


def test_verify_detects_added_point():
    _, store, engine, start, end = _setup()
    ref = SeriesRef("dev-1", "energy")
    ts = start + 2 * 86_400_000 + 5 * 3_600_000
    store.delete_range(ref, ts, ts + 1)

    report = engine.verify([("dev-1", "energy")], start, end)
    diff = report["details"][0]["diffs"][0]
    assert diff["added"] == 1
    assert diff["removed"] == 0
    assert diff["changed"] == 0
    assert ts in diff["sample_added"]


def test_verify_detects_removed_point():
    _, store, engine, start, end = _setup()
    ref = SeriesRef("dev-1", "energy")
    ts = start + 2 * 86_400_000 + 5 * 3_600_000 + 1  # not on the 15-minute grid
    store.upsert_points(ref, [(ts, 99.0)])

    report = engine.verify([("dev-1", "energy")], start, end)
    diff = report["details"][0]["diffs"][0]
    assert diff["removed"] == 1
    assert ts in diff["sample_removed"]


def test_verify_ignores_tiny_float_drift():
    source, store, engine, start, end = _setup()
    ref = SeriesRef("dev-1", "energy")
    ts = start + 3_600_000
    original = dict(source.points("dev-1", "energy"))[ts]
    store.upsert_points(ref, [(ts, original + 1e-12)])
    report = engine.verify([("dev-1", "energy")], start, end)
    assert report["diff_segments"] == 0


def test_verify_drill_limit():
    source, store, engine, start, end = _setup()
    ref = SeriesRef("dev-1", "energy")
    points = dict(source.points("dev-1", "energy"))
    for day in (0, 1, 2):
        ts = start + day * 86_400_000 + 3_600_000
        store.upsert_points(ref, [(ts, points[ts] + 1)])
    report = engine.verify([("dev-1", "energy")], start, end, drill_limit=1)
    assert report["diff_segments"] == 3
    assert report["drilled"] == 1
    assert report["drill_skipped"] == 2


def test_repair_restores_tampered_point():
    source, store, engine, start, end = _setup()
    ref = SeriesRef("dev-1", "energy")
    ts = start + 3_600_000
    original = dict(source.points("dev-1", "energy"))[ts]
    store.upsert_points(ref, [(ts, original + 999)])

    result = engine.repair([("dev-1", "energy")], start, end)
    assert result["series"][0]["inserted"] == 960
    assert engine.verify([("dev-1", "energy")], start, end)["diff_segments"] == 0
    assert engine.sum_local([("dev-1", "energy")], start, end).grand_total == 2400.0


def test_repair_removes_points_deleted_at_source():
    """The source is authoritative: repair must drop a point that no longer exists."""
    source, start, end = build_source(days=10)
    store = MemoryStore()
    engine = LadderEngine(source, store, clock=lambda: ms(2030, 1, 1))
    engine.materialize([("dev-1", "energy")], start, end)

    trimmed = [
        (ts, value)
        for ts, value in source.points("dev-1", "energy")
        if ts != start + 3_600_000
    ]
    source2 = MemorySource().add("dev-1", "energy", trimmed)
    engine2 = LadderEngine(source2, store, clock=lambda: ms(2030, 1, 1))
    result = engine2.repair([("dev-1", "energy")], start, end)
    assert result["series"][0]["inserted"] == 959
    assert engine2.verify([("dev-1", "energy")], start, end)["diff_segments"] == 0
    assert engine2.sum_local([("dev-1", "energy")], start, end).grand_total == 2399.0


def test_repair_windows():
    source, start, end = build_source(days=3)
    store = MemoryStore()
    engine = LadderEngine(
        source,
        store,
        LadderConfig(max_repair_days=1),
        clock=lambda: ms(2030, 1, 1),
    )
    result = engine.repair([("dev-1", "energy")], start, end)
    assert result["series"][0]["inserted"] == 288  # 3 days x 96
    assert engine.verify([("dev-1", "energy")], start, end)["diff_segments"] == 0


def test_verify_requires_store():
    import pytest

    source, start, end = build_source()
    engine = LadderEngine(source)
    with pytest.raises(ConfigurationError):
        engine.verify([("dev-1", "energy")], start, end)
