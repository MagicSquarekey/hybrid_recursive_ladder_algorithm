# -*- coding: utf-8 -*-
"""In-memory source — useful for tests, demos and small embedded workloads."""

from __future__ import annotations

import bisect
from collections.abc import Iterable, Mapping
from typing import Any

from ..models import SeriesRef

__all__ = ["MemorySource"]


class MemorySource:
    """A deterministic time-series source backed by Python lists."""

    def __init__(self) -> None:
        self._points: dict[tuple[str, str], list[tuple[int, Any]]] = {}

    def add(
        self,
        entity: str,
        key: str,
        points: Iterable[tuple[int, Any]],
    ) -> MemorySource:
        """Add points (any order); timestamps are de-duplicated, last wins."""
        merged = dict(self._points.get((entity, key), []))
        for ts, value in points:
            merged[int(ts)] = value
        self._points[(entity, key)] = sorted(merged.items())
        return self

    def extend(self, entity: str, key: str, points: Iterable[tuple[int, Any]]) -> MemorySource:
        return self.add(entity, key, points)

    def points(self, entity: str, key: str) -> list[tuple[int, Any]]:
        return list(self._points.get((entity, key), []))

    def interval_agg(
        self,
        ref: SeriesRef,
        start_ms: int,
        end_ms: int,
        bucket_ms: int,
        agg: str = "SUM",
    ) -> Mapping[int, Any]:
        if bucket_ms <= 0:
            raise ValueError("bucket_ms must be positive")
        if agg not in ("SUM", "COUNT", "MIN", "MAX", "AVG"):
            raise ValueError(f"unsupported aggregation: {agg}")
        buckets: dict[int, list[float]] = {}
        for ts, value in self._points.get((ref.entity, ref.key), []):
            if not (start_ms <= ts < end_ms):
                continue
            bucket_start = start_ms + ((ts - start_ms) // bucket_ms) * bucket_ms
            try:
                number = float(value)
            except (TypeError, ValueError):
                continue
            buckets.setdefault(bucket_start, []).append(number)
        out: dict[int, Any] = {}
        for bucket_start, values in buckets.items():
            if agg == "SUM":
                out[bucket_start] = sum(values)
            elif agg == "COUNT":
                out[bucket_start] = len(values)
            elif agg == "MIN":
                out[bucket_start] = min(values)
            elif agg == "MAX":
                out[bucket_start] = max(values)
            else:
                out[bucket_start] = sum(values) / len(values)
        return out

    def raw_series(
        self,
        ref: SeriesRef,
        start_ms: int,
        end_ms: int,
        limit: int = 10_000,
    ) -> list[tuple[int, Any]]:
        points = self._points.get((ref.entity, ref.key), [])
        timestamps = [ts for ts, _ in points]
        left = bisect.bisect_left(timestamps, start_ms)
        right = bisect.bisect_left(timestamps, end_ms)
        return points[left:right][:limit]
