# -*- coding: utf-8 -*-
"""In-memory point store with coverage tracking."""

from __future__ import annotations

import bisect
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from ..models import SeriesRef

__all__ = ["MemoryStore"]


class MemoryStore:
    """A local point store backed by dictionaries."""

    def __init__(self) -> None:
        self._points: dict[tuple[str, str], dict[int, Any]] = {}
        self._coverage: dict[tuple[str, str], list[tuple[int, int, int]]] = {}

    def sum_ranges(
        self,
        ref: SeriesRef,
        ranges: Sequence[tuple[int, int]],
    ) -> Mapping[int, tuple[float | None, int]]:
        points = self._points.get((ref.entity, ref.key), {})
        timestamps = sorted(points)
        out: dict[int, tuple[float | None, int]] = {}
        for start, end in ranges:
            left = bisect.bisect_left(timestamps, start)
            right = bisect.bisect_left(timestamps, end)
            values = []
            for ts in timestamps[left:right]:
                value = points[ts]
                try:
                    values.append(float(value))
                except (TypeError, ValueError):
                    continue
            out[int(start)] = (sum(values) if values else None, len(values))
        return out

    def series(
        self,
        ref: SeriesRef,
        start_ms: int,
        end_ms: int,
        max_points: int = 5_000,
    ) -> list[Mapping[str, Any]]:
        points = self._points.get((ref.entity, ref.key), {})
        timestamps = sorted(points)
        left = bisect.bisect_left(timestamps, start_ms)
        right = bisect.bisect_left(timestamps, end_ms)
        return [{"ts": ts, "value": points[ts]} for ts in timestamps[left:right]]

    def coverage(self, ref: SeriesRef) -> list[tuple[int, int, int]]:
        return list(self._coverage.get((ref.entity, ref.key), []))

    def delete_range(self, ref: SeriesRef, start_ms: int, end_ms: int) -> int:
        points = self._points.get((ref.entity, ref.key), {})
        doomed = [ts for ts in points if start_ms <= ts < end_ms]
        for ts in doomed:
            del points[ts]
        return len(doomed)

    def clear_coverage(self, ref: SeriesRef, start_ms: int, end_ms: int) -> int:
        key = (ref.entity, ref.key)
        rows = self._coverage.get(key, [])
        kept = [row for row in rows if not (row[0] < end_ms and row[1] > start_ms)]
        removed = len(rows) - len(kept)
        self._coverage[key] = kept
        return removed

    def upsert_points(
        self,
        ref: SeriesRef,
        points: Iterable[tuple[int, Any]],
        at_ms: int | None = None,
    ) -> int:
        target = self._points.setdefault((ref.entity, ref.key), {})
        count = 0
        for ts, value in points:
            target[int(ts)] = value
            count += 1
        return count

    def mark_covered(
        self,
        ref: SeriesRef,
        start_ms: int,
        end_ms: int,
        point_cnt: int,
        at_ms: int,
    ) -> None:
        if end_ms <= start_ms:
            return
        self._coverage.setdefault((ref.entity, ref.key), []).append(
            (int(start_ms), int(end_ms), int(at_ms))
        )
