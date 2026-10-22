# -*- coding: utf-8 -*-
"""Pure decomposition functions — no I/O, no third-party dependencies.

The ladder splits ``[start, end)`` into segments of *complete* calendar units,
from month down to the configured finest level.  Partial units at either edge
are recursively pushed to the next finer level; a sub-minute remainder at the
finest level becomes its own "tail" segment.

Invariants
----------
* Segments are ordered, contiguous and non-overlapping.
* Their union is exactly ``[start, end)`` (left-closed, right-open).
* A unit is emitted at level ``L`` only if it is fully contained in the range.
* ``None`` means "no samples"; ``0.0`` means "samples exist and sum to zero".

Timezone
--------
Boundaries are computed in the configured IANA timezone (default
``Asia/Shanghai``).  Month/day/hour/minute boundaries follow the local wall
clock.  For time zones with DST, day boundaries remain correct because they are
built from calendar fields; fixed-size buckets are only used by data sources,
which is why the engine folds days from hours and hours from minutes.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Any
from zoneinfo import ZoneInfo

from .models import (
    BUCKET_MS,
    FETCH_LEVEL,
    LABEL_FORMATS,
    LEVEL_INDEX,
    LEVELS,
    Segment,
)

__all__ = [
    "BUCKET_MS",
    "LEVELS",
    "contiguous_runs",
    "decompose",
    "fold_count",
    "fold_sum",
    "label_for",
    "merge_coverage",
    "next_boundary",
    "split_by_coverage",
    "unit_start",
]


@lru_cache(maxsize=64)
def _zone(timezone: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone)
    except Exception as exc:
        raise ValueError(f"unknown timezone: {timezone!r}") from exc


def _to_ms(dt: datetime) -> int:
    # round() instead of int(): a datetime built from epoch milliseconds can
    # carry a tiny floating-point error, and truncation would be off by 1 ms.
    return round(dt.timestamp() * 1000)


def _dt(ts_ms: int, timezone: str) -> datetime:
    return datetime.fromtimestamp(ts_ms / 1000, _zone(timezone))


def _check_level(level: str) -> None:
    if level not in LEVEL_INDEX:
        raise ValueError(f"level must be one of {LEVELS}, got {level!r}")


def unit_start(ts_ms: int, level: str, timezone: str = "Asia/Shanghai") -> int:
    """Start of the calendar unit that contains ``ts_ms`` (local time)."""
    _check_level(level)
    dt = _dt(ts_ms, timezone)
    if level == "month":
        dt = datetime(dt.year, dt.month, 1, tzinfo=_zone(timezone))
    elif level == "day":
        dt = datetime(dt.year, dt.month, dt.day, tzinfo=_zone(timezone))
    elif level == "hour":
        dt = dt.replace(minute=0, second=0, microsecond=0)
    else:  # minute
        dt = dt.replace(second=0, microsecond=0)
    return _to_ms(dt)


def next_boundary(ts_ms: int, level: str, timezone: str = "Asia/Shanghai") -> int:
    """The first calendar boundary strictly after ``ts_ms`` at ``level``."""
    _check_level(level)
    dt = _dt(ts_ms, timezone)
    if level == "month":
        year, month = (dt.year + 1, 1) if dt.month == 12 else (dt.year, dt.month + 1)
        nxt = datetime(year, month, 1, tzinfo=_zone(timezone))
    elif level == "day":
        nxt = datetime(dt.year, dt.month, dt.day, tzinfo=_zone(timezone)) + timedelta(days=1)
    elif level == "hour":
        nxt = dt.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    else:  # minute
        nxt = dt.replace(second=0, microsecond=0) + timedelta(minutes=1)
    return _to_ms(nxt)


def label_for(ts_ms: int, level: str, timezone: str = "Asia/Shanghai") -> str:
    """Human-readable label for a segment starting at ``ts_ms``."""
    _check_level(level)
    return _dt(ts_ms, timezone).strftime(LABEL_FORMATS[level])


def decompose(
    start_ms: int,
    end_ms: int,
    finest: str = "minute",
    *,
    timezone: str = "Asia/Shanghai",
    max_segments: int | None = None,
) -> list[Segment]:
    """Split ``[start_ms, end_ms)`` into complete calendar units.

    :param finest: ``month``, ``day``, ``hour`` or ``minute``.
    :param timezone: IANA timezone used for calendar boundaries.
    :param max_segments: optional defensive cap (``None`` means no cap).
    :raises ValueError: invalid range, level, timezone or cap exceeded.
    """
    if finest not in LEVEL_INDEX:
        raise ValueError(f"finest must be one of {LEVELS}, got {finest!r}")
    if end_ms <= start_ms:
        raise ValueError("end_ms must be greater than start_ms")
    if max_segments is not None and max_segments < 1:
        raise ValueError("max_segments must be >= 1 or None")

    _zone(timezone)  # validate early
    finest_idx = LEVEL_INDEX[finest]
    out: list[Segment] = []

    def walk(a: int, b: int, idx: int) -> None:
        if a >= b:
            return
        level = LEVELS[idx]
        is_finest = idx >= finest_idx

        def emit(u: int, v: int) -> None:
            out.append(Segment(level=level, start=u, end=v, label=label_for(u, level, timezone)))
            if max_segments is not None and len(out) > max_segments:
                raise ValueError(f"segment count exceeds max_segments={max_segments}")

        # Left remainder: the start is not aligned to this level.
        if unit_start(a, level, timezone) != a:
            nb = next_boundary(a, level, timezone)
            if nb >= b:
                if is_finest:
                    emit(a, b)
                else:
                    walk(a, b, idx + 1)
                return
            if is_finest:
                emit(a, nb)
            else:
                walk(a, nb, idx + 1)
            a = nb

        # Complete units, peeled one by one.
        while True:
            nb = next_boundary(a, level, timezone)
            if nb > b:
                break
            if nb <= a:  # pragma: no cover - defensive, would loop forever
                raise RuntimeError(f"next_boundary did not advance at {level}: {a}")
            emit(a, nb)
            a = nb

        # Right remainder.
        if a < b:
            if is_finest:
                emit(a, b)
            else:
                walk(a, b, idx + 1)

    walk(start_ms, end_ms, 0)
    return out


def fold_sum(fine: Mapping[int, Any], start_ms: int, end_ms: int) -> float | None:
    """Sum the fine buckets whose **start** falls inside ``[start, end)``.

    Returns ``None`` when the segment contains no buckets at all.  Buckets
    whose value cannot be parsed as a number contribute zero, matching the
    behaviour of the original implementation (a bucket exists => data exists).
    """
    values = [v for bs, v in fine.items() if start_ms <= bs < end_ms]
    if not values:
        return None
    total = 0.0
    for value in values:
        try:
            total += float(value)
        except (TypeError, ValueError):
            continue
    return total


def fold_count(fine: Mapping[int, Any], start_ms: int, end_ms: int) -> int:
    """Number of fine buckets whose start falls inside ``[start, end)``."""
    return sum(1 for bs in fine if start_ms <= bs < end_ms)


def merge_coverage(ranges: Iterable[Sequence[int]]) -> list[tuple[int, int]]:
    """Merge overlapping or touching coverage ranges.

    Accepts ``(start, end)`` or ``(start, end, ...)`` tuples and returns a
    sorted list of disjoint ``(start, end)`` pairs.  Empty/invalid ranges are
    ignored.
    """
    normalized = sorted((int(r[0]), int(r[1])) for r in ranges if len(r) >= 2 and r[1] > r[0])
    out: list[tuple[int, int]] = []
    for start, end in normalized:
        if out and start <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], end))
        else:
            out.append((start, end))
    return out


def split_by_coverage(
    start_ms: int,
    end_ms: int,
    coverage: Sequence[tuple[int, int]],
) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
    """Split ``[start, end)`` into covered and uncovered sub-ranges.

    ``coverage`` must be sorted and merged (use :func:`merge_coverage`).
    """
    covered: list[tuple[int, int]] = []
    uncovered: list[tuple[int, int]] = []
    cur = start_ms
    for cov_start, cov_end in coverage:
        if cov_end <= cur or cov_start >= end_ms:
            continue
        s, e = max(cov_start, cur), min(cov_end, end_ms)
        if s > cur:
            uncovered.append((cur, s))
        if e > s:
            covered.append((s, e))
            cur = e
        if cur >= end_ms:
            break
    if cur < end_ms:
        uncovered.append((cur, end_ms))
    return covered, uncovered


def contiguous_runs(segments: Sequence[Segment], *, same_level: bool = False) -> list[list[Segment]]:
    """Group adjacent segments into runs.

    :param same_level: also require the same output level.  Use ``True`` when
        the result will be fetched with a single aggregation level; use
        ``False`` to merge plain time ranges.
    """
    runs: list[list[Segment]] = []
    for seg in segments:
        if runs:
            last = runs[-1][-1]
            if last.end == seg.start and (not same_level or last.level == seg.level):
                runs[-1].append(seg)
                continue
        runs.append([seg])
    return runs


def fetch_runs(segments: Sequence[Segment]) -> list[tuple[str, list[Segment]]]:
    """Group non-tail segments by the aggregation level needed to fill them.

    Segments at different output levels can share a fetch when they require the
    same fetch level (hours and minutes both use minute buckets), but they are
    never grouped across a time gap.  Sub-minute tails are excluded because
    they are read from the raw series.

    This is the corrected version of the original ``_contiguous_runs`` helper:
    grouping only by adjacency caused a multi-level query to fetch the whole
    range at the coarsest level and produce wrong hour/minute values.
    """
    runs: list[tuple[str, list[Segment]]] = []
    last_end: int | None = None
    for seg in segments:
        if seg.is_subminute_tail:
            continue
        fetch_level = FETCH_LEVEL[seg.level]
        if runs and runs[-1][0] == fetch_level and last_end == seg.start:
            runs[-1][1].append(seg)
        else:
            runs.append((fetch_level, [seg]))
        last_end = seg.end
    return runs
