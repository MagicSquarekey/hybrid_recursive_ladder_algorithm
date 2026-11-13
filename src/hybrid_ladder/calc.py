# -*- coding: utf-8 -*-
"""Bucket calculator primitives: calendar buckets, rule folding and meter deltas.

The ladder answers "sum over a long range" by decomposing the range into
complete calendar units.  The bucket calculator answers a related question:
"show me one value per minute/hour/day/month, under a rule".  It uses the same
calendar boundaries and the same local-first read path, but the output buckets
are aligned to the requested dimension instead of being peeled as a ladder.

Rules
-----
``sum``
    Bucket value is the sum of the points in the bucket.
``avg``
    Bucket value is ``sum / count`` for the bucket.  A row total is the
    unweighted mean of the non-empty bucket values (the "mean of means"
    convention used by the original application).
``meter_delta``
    Bucket value is ``next bucket's first reading - this bucket's first
    reading``.  The last bucket reads one bucket beyond ``end``.  A bucket
    without a reading falls back to the last reading before its start, within
    :data:`~hybrid_ladder.models.DELTA_LOOKBACK_MS`.  Negative differences
    (meter reset) and missing anchors are reported as anomaly codes instead of
    inventing a value.

All timestamps are epoch milliseconds.  Ranges are left-closed, right-open.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from .core import label_for, next_boundary, unit_start
from .models import (
    ANOMALY_NEGATIVE_DELTA,
    ANOMALY_NO_CURRENT,
    ANOMALY_NO_NEXT,
    ANOMALY_NON_NUMERIC,
    ANOMALY_SAME_READING,
    DIMENSIONS,
    Bucket,
)

__all__ = [
    "DeltaCell",
    "build_buckets",
    "delta_chain",
    "fold_avg",
    "fold_row_total",
]


def build_buckets(
    start_ms: int,
    end_ms: int,
    dimension: str = "day",
    *,
    timezone: str = "Asia/Shanghai",
) -> list[Bucket]:
    """Split an aligned ``[start_ms, end_ms)`` into calendar buckets.

    Both edges must sit exactly on a boundary of ``dimension``; a range that
    is not aligned is rejected instead of silently shifting the buckets.

    :raises ValueError: unknown dimension, empty range or unaligned edge.
    """
    if dimension not in DIMENSIONS:
        raise ValueError(f"dimension must be one of {DIMENSIONS}, got {dimension!r}")
    if end_ms <= start_ms:
        raise ValueError("end_ms must be greater than start_ms")
    if unit_start(start_ms, dimension, timezone) != start_ms:
        raise ValueError(f"start_ms must be aligned to {dimension} boundaries")
    if unit_start(end_ms, dimension, timezone) != end_ms:
        raise ValueError(f"end_ms must be aligned to {dimension} boundaries")

    out: list[Bucket] = []
    cursor = int(start_ms)
    while cursor < end_ms:
        nxt = next_boundary(cursor, dimension, timezone)
        if nxt > end_ms:  # pragma: no cover - defensive; end is aligned
            nxt = int(end_ms)
        if nxt <= cursor:  # pragma: no cover - defensive, would loop forever
            raise RuntimeError(f"next_boundary did not advance at {dimension}: {cursor}")
        out.append(
            Bucket(
                start=cursor,
                end=nxt,
                label=label_for(cursor, dimension, timezone),
                dimension=dimension,
            )
        )
        cursor = nxt
    return out


@dataclass(frozen=True, slots=True)
class DeltaCell:
    """One meter-delta bucket: value plus the two anchors it was built from."""

    value: float | None
    anomaly: str | None
    first_ts: int | None
    next_ts: int | None


def delta_chain(
    firsts: Sequence[tuple[int, Any] | None],
    ext_first: tuple[int, Any] | None,
) -> tuple[list[DeltaCell], float, int]:
    """Build a meter-delta chain from per-bucket first readings.

    ``firsts`` has one entry per bucket (``None`` = no reading and no
    fallback).  ``ext_first`` is the first reading of the bucket after the
    requested range; it is used by the last bucket and is not part of the
    output.  Returns ``(cells, total, ok)`` where ``ok`` is the number of
    valid deltas.
    """
    cells: list[DeltaCell] = []
    total = 0.0
    ok = 0
    last = len(firsts) - 1
    for index, current in enumerate(firsts):
        following = firsts[index + 1] if index < last else ext_first
        first_ts = int(current[0]) if current is not None else None
        next_ts = int(following[0]) if following is not None else None

        if following is None:
            cells.append(DeltaCell(None, ANOMALY_NO_NEXT, first_ts, next_ts))
            continue
        if current is None:
            cells.append(DeltaCell(None, ANOMALY_NO_CURRENT, first_ts, next_ts))
            continue
        try:
            current_value = float(current[1])
            next_value = float(following[1])
        except (TypeError, ValueError):
            cells.append(DeltaCell(None, ANOMALY_NON_NUMERIC, first_ts, next_ts))
            continue
        if current[0] == following[0]:
            cells.append(DeltaCell(None, ANOMALY_SAME_READING, first_ts, next_ts))
            continue
        delta = next_value - current_value
        if delta < 0:
            cells.append(DeltaCell(None, ANOMALY_NEGATIVE_DELTA, first_ts, next_ts))
            continue
        cells.append(DeltaCell(round(delta, 6), None, first_ts, next_ts))
        total += delta
        ok += 1
    return cells, total, ok


def fold_avg(pairs: Sequence[tuple[float | None, int]]) -> float | None:
    """Weighted average from ``(sum, count)`` pairs; ``None`` when empty."""
    total = 0.0
    count = 0
    for value, n in pairs:
        if not n:
            continue
        total += float(value or 0.0)
        count += int(n)
    if count == 0:
        return None
    return round(total / count, 6)


def fold_row_total(rule: str, values: Sequence[float | None]) -> float | None:
    """Fold non-empty bucket values into a row total.

    ``avg`` uses the unweighted mean of non-empty buckets; ``sum`` and
    ``meter_delta`` add them.  Empty buckets are excluded.
    """
    present = [float(v) for v in values if v is not None]
    if not present:
        return None
    if rule == "avg":
        return round(sum(present) / len(present), 6)
    return round(sum(present), 6)
