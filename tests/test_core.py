# -*- coding: utf-8 -*-
"""Pure decomposition, folding and coverage-splitting tests."""

from __future__ import annotations

import itertools

import pytest
from helpers import ms

from hybrid_ladder import (
    contiguous_runs,
    decompose,
    fetch_runs,
    fold_count,
    fold_sum,
    label_for,
    merge_coverage,
    next_boundary,
    split_by_coverage,
    unit_start,
)
from hybrid_ladder.models import Segment


def test_example_97_segments():
    """The documented example: 2026-01-01 00:00:00 → 2026-10-21 18:49:59."""
    segments = decompose(ms(2026, 1, 1), ms(2026, 10, 21, 18, 49, 59))
    by_level: dict[str, int] = {}
    for segment in segments:
        by_level[segment.level] = by_level.get(segment.level, 0) + 1
    assert by_level == {"month": 9, "day": 20, "hour": 18, "minute": 50}
    assert len(segments) == 97

    assert segments[0].label == "2026-01"
    assert segments[9].label == "2026-10-01"
    assert segments[29].label == "2026-10-21 00:00"
    # 18:00-19:00 is incomplete, so the last complete hour is 17:00.
    assert segments[29 + 17].label == "2026-10-21 17:00"
    # The final segment is the 18:49 tail (59 seconds).
    assert segments[-1].label == "2026-10-21 18:49"
    assert segments[-1].end - segments[-1].start == 59_000


def test_segments_tile_range_exactly():
    start, end = ms(2026, 3, 15, 13, 27, 41), ms(2026, 11, 3, 7, 5, 9)
    segments = decompose(start, end)
    assert segments[0].start == start
    assert segments[-1].end == end
    for previous, following in itertools.pairwise(segments):
        assert previous.end == following.start
    assert sum(s.end - s.start for s in segments) == end - start


def test_unaligned_start_goes_to_finer_level():
    segments = decompose(ms(2026, 1, 15, 13, 27), ms(2026, 3, 10))
    # The first segment is the sub-hour remainder, not a half month.
    assert segments[0].level == "minute"
    assert segments[0].label == "2026-01-15 13:27"
    # January is not emitted as a complete month.
    assert not any(s.level == "month" and s.start < ms(2026, 2, 1) for s in segments)
    # February is complete.
    assert any(s.label == "2026-02" and s.level == "month" for s in segments)
    # March 1-9 are complete days; the end (Mar 10 00:00) is exclusive.
    assert segments[-1].level == "day" and segments[-1].label == "2026-03-09"


def test_end_on_boundary_has_no_empty_tail():
    segments = decompose(ms(2026, 10, 21), ms(2026, 10, 21, 20, 0, 0))
    assert all(s.level == "hour" for s in segments)
    assert len(segments) == 20  # 0-19, no 20:00 segment
    assert segments[-1].label == "2026-10-21 19:00"

    day = decompose(ms(2026, 10, 21), ms(2026, 10, 22))
    assert [s.label for s in day] == ["2026-10-21"]


def test_finest_level_respected():
    segments = decompose(ms(2026, 10, 21), ms(2026, 10, 21, 5, 30), finest="hour")
    assert all(s.level == "hour" for s in segments)
    assert len(segments) == 6  # 0-4 complete + 5:00-5:30 tail
    assert segments[-1].end - segments[-1].start == 30 * 60_000


def test_finest_month_emits_partial_months():
    segments = decompose(ms(2026, 1, 15), ms(2026, 3, 10), finest="month")
    assert [s.level for s in segments] == ["month", "month", "month"]
    assert segments[0].start == ms(2026, 1, 15)
    assert segments[0].end == ms(2026, 2, 1)
    assert segments[1].label == "2026-02"
    assert segments[-1].end == ms(2026, 3, 10)


def test_max_segments_guard():
    with pytest.raises(ValueError):
        decompose(ms(2026, 1, 1), ms(2026, 10, 21), max_segments=10)
    with pytest.raises(ValueError):
        decompose(ms(2026, 1, 1), ms(2026, 10, 21), max_segments=0)


@pytest.mark.parametrize(
    "start,end,finest",
    [
        (100, 100, "minute"),
        (200, 100, "minute"),
        (0, 1000, "week"),
    ],
)
def test_invalid_inputs(start, end, finest):
    with pytest.raises(ValueError):
        decompose(start, end, finest)


def test_invalid_timezone():
    with pytest.raises(ValueError):
        decompose(0, 1000, timezone="Mars/Olympus")


def test_boundaries_and_labels():
    ts = ms(2026, 1, 15, 13, 27, 41)
    assert unit_start(ts, "month") == ms(2026, 1, 1)
    assert unit_start(ts, "day") == ms(2026, 1, 15)
    assert unit_start(ts, "hour") == ms(2026, 1, 15, 13)
    assert unit_start(ts, "minute") == ms(2026, 1, 15, 13, 27)
    assert next_boundary(ts, "month") == ms(2026, 2, 1)
    assert next_boundary(ts, "day") == ms(2026, 1, 16)
    assert next_boundary(ts, "hour") == ms(2026, 1, 15, 14)
    assert next_boundary(ts, "minute") == ms(2026, 1, 15, 13, 28)
    assert label_for(ts, "month") == "2026-01"
    assert label_for(ts, "day") == "2026-01-15"
    assert label_for(ts, "hour") == "2026-01-15 13:00"
    assert label_for(ts, "minute") == "2026-01-15 13:27"


def test_december_rollover():
    assert next_boundary(ms(2026, 12, 31), "month") == ms(2027, 1, 1)
    assert next_boundary(ms(2026, 12, 31, 23, 59), "day") == ms(2027, 1, 1)


def test_fold_sum_empty_vs_zero():
    fine = {1_000: "0", 2_000: "0"}
    assert fold_sum(fine, 0, 3_000) == 0.0
    assert fold_sum(fine, 5_000, 6_000) is None
    assert fold_count(fine, 0, 3_000) == 2
    # Invalid values still count as buckets but add zero.
    assert fold_sum({1_000: "bad"}, 0, 3_000) == 0.0


def test_merge_coverage():
    assert merge_coverage([(0, 10), (5, 15), (20, 25), (25, 30)]) == [
        (0, 15),
        (20, 30),
    ]
    assert merge_coverage([(10, 20), (0, 5), (5, 10)]) == [(0, 20)]
    assert merge_coverage([(5, 5), (10, 9)]) == []
    assert merge_coverage([]) == []


def test_split_by_coverage():
    covered, uncovered = split_by_coverage(0, 100, [(20, 40), (60, 80)])
    assert covered == [(20, 40), (60, 80)]
    assert uncovered == [(0, 20), (40, 60), (80, 100)]

    covered, uncovered = split_by_coverage(0, 100, [(0, 100)])
    assert covered == [(0, 100)] and uncovered == []

    covered, uncovered = split_by_coverage(0, 100, [])
    assert covered == [] and uncovered == [(0, 100)]

    covered, uncovered = split_by_coverage(0, 100, [(-50, 10), (90, 150)])
    assert covered == [(0, 10), (90, 100)]
    assert uncovered == [(10, 90)]


def test_contiguous_runs_same_level():
    segments = [
        Segment("hour", 0, 100, "a"),
        Segment("minute", 100, 200, "b"),
        Segment("minute", 200, 300, "c"),
        Segment("hour", 300, 400, "d"),
    ]
    assert len(contiguous_runs(segments)) == 1
    assert [len(run) for run in contiguous_runs(segments, same_level=True)] == [1, 2, 1]


def test_fetch_runs_group_by_fetch_level():
    """Regression for the original grouping bug.

    The whole 97-segment range is time-contiguous, but it must not be fetched
    with one level.  Months need day buckets, days need hour buckets, and
    hours/minutes share minute buckets.
    """
    segments = decompose(ms(2026, 1, 1), ms(2026, 10, 21, 18, 49, 59))
    runs = fetch_runs(segments)
    assert [level for level, _ in runs] == ["day", "hour", "minute"]
    assert len(runs[0][1]) == 9
    assert len(runs[1][1]) == 20
    assert len(runs[2][1]) == 18 + 49  # hours + complete minutes; tail excluded
    for level, run in runs:
        assert {segment.level for segment in run} <= (
            {"month"} if level == "day" else {"day"} if level == "hour" else {"hour", "minute"}
        )


def test_fetch_runs_excludes_subminute_tail():
    segments = decompose(ms(2026, 10, 21, 18, 49), ms(2026, 10, 21, 18, 49, 59))
    assert len(segments) == 1 and segments[0].is_subminute_tail
    assert fetch_runs(segments) == []
