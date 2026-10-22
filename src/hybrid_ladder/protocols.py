# -*- coding: utf-8 -*-
"""Structural interfaces for data sources and point stores.

Both interfaces are small on purpose: the ladder engine only needs two read
operations from a source and six operations from a store.  Adapters for
ThingsBoard and PostgreSQL ship with the package, but any object that
implements these methods works.

Conventions
-----------
* All timestamps are integer milliseconds since the Unix epoch.
* All ranges are **left-closed, right-open**: ``[start, end)``.
* ``interval_agg`` returns a mapping ``{bucket_start_ms: value}``.  Empty
  buckets are omitted.  ``value`` may be ``None`` for a bucket that exists but
  has no numeric value.
* ``raw_series`` returns ``[(ts, value), ...]`` in ascending order, capped at
  ``limit`` points.  If exactly ``limit`` points are returned the engine
  assumes the result may be truncated and bisects the window.
* A store returns ``(None, 0)`` for a range with no points, and
  ``(0.0, n)`` for a range whose points sum to zero.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any, Protocol, runtime_checkable

from .models import SeriesRef

__all__ = ["PointStore", "TimeSeriesSource"]


@runtime_checkable
class TimeSeriesSource(Protocol):
    """Read-only access to a time-series database."""

    def interval_agg(
        self,
        ref: SeriesRef,
        start_ms: int,
        end_ms: int,
        bucket_ms: int,
        agg: str = "SUM",
    ) -> Mapping[int, Any]:
        """Aggregate ``[start_ms, end_ms)`` into fixed buckets."""
        ...

    def raw_series(
        self,
        ref: SeriesRef,
        start_ms: int,
        end_ms: int,
        limit: int = 10_000,
    ) -> list[tuple[int, Any]]:
        """Return raw points in ``[start_ms, end_ms)``, ascending."""
        ...


@runtime_checkable
class PointStore(Protocol):
    """Local point store with coverage tracking."""

    def sum_ranges(
        self,
        ref: SeriesRef,
        ranges: Sequence[tuple[int, int]],
    ) -> Mapping[int, tuple[float | None, int]]:
        """Sum each range in one call; keys are the range start timestamps."""
        ...

    def series(
        self,
        ref: SeriesRef,
        start_ms: int,
        end_ms: int,
        max_points: int = 5_000,
    ) -> list[Mapping[str, Any]]:
        """Return stored points in ``[start_ms, end_ms)``, ascending."""
        ...

    def coverage(self, ref: SeriesRef) -> list[tuple[int, int, int]]:
        """Return ``(start_ms, end_ms, covered_at_ms)`` rows."""
        ...

    def delete_range(self, ref: SeriesRef, start_ms: int, end_ms: int) -> int:
        """Delete points in ``[start_ms, end_ms)``; return the row count."""
        ...

    def clear_coverage(self, ref: SeriesRef, start_ms: int, end_ms: int) -> int:
        """Drop coverage rows that overlap ``[start_ms, end_ms)``.

        Called before rewriting a range so a failed materialize can never leave
        stale coverage pointing at incomplete local data.
        """
        ...

    def upsert_points(
        self,
        ref: SeriesRef,
        points: Iterable[tuple[int, Any]],
        at_ms: int | None = None,
    ) -> int:
        """Idempotently write points; return the number of points written."""
        ...

    def mark_covered(
        self,
        ref: SeriesRef,
        start_ms: int,
        end_ms: int,
        point_cnt: int,
        at_ms: int,
    ) -> None:
        """Record that ``[start_ms, end_ms)`` was fully pulled from the source."""
        ...
