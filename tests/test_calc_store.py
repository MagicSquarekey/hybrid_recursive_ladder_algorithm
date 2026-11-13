# -*- coding: utf-8 -*-
"""First/last point reads used by the meter-delta rule (MemoryStore)."""

from __future__ import annotations

from helpers import ms

from hybrid_ladder import MemoryStore, SeriesRef


def _store_with_points():
    store = MemoryStore()
    ref = SeriesRef("dev-1", "energy")
    base = ms(2026, 1, 1)
    store.upsert_points(
        ref,
        [
            (base, 10.0),
            (base + 60_000, 20.0),
            (base + 120_000, 30.0),
            (base + 10 * 60_000, 40.0),
        ],
    )
    return store, ref, base


class TestFirstRanges:
    def test_first_point_of_each_range(self):
        store, ref, base = _store_with_points()
        got = store.first_ranges(
            ref,
            [(base + 60_000, base + 180_000), (base + 5 * 60_000, base + 6 * 60_000)],
        )
        assert got[base + 60_000] == (base + 60_000, 20.0)
        assert got[base + 5 * 60_000] is None

    def test_empty_input(self):
        store, ref, _ = _store_with_points()
        assert store.first_ranges(ref, []) == {}


class TestLastBefore:
    def test_latest_point_inside_the_lookback_window(self):
        store, ref, base = _store_with_points()
        got = store.last_before(ref, [base + 30 * 60_000], 60 * 60_000)
        assert got[base + 30 * 60_000] == (base + 10 * 60_000, 40.0)

    def test_points_outside_the_window_are_ignored(self):
        store, ref, base = _store_with_points()
        got = store.last_before(ref, [base + 30 * 60_000], 5 * 60_000)
        assert got[base + 30 * 60_000] is None

    def test_multiple_targets_and_boundaries(self):
        store, ref, base = _store_with_points()
        targets = [base, base + 61_000, base + 11 * 60_000]
        got = store.last_before(ref, targets, 60_000)
        assert got[base] is None  # nothing strictly before the first point
        assert got[base + 61_000] == (base + 60_000, 20.0)
        assert got[base + 11 * 60_000] == (base + 10 * 60_000, 40.0)

    def test_empty_input(self):
        store, ref, _ = _store_with_points()
        assert store.last_before(ref, [], 60_000) == {}
