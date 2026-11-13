# -*- coding: utf-8 -*-
"""Bucket calculation mixed into :class:`~hybrid_ladder.engine.LadderEngine`.

The ladder answers "sum over a long range"; the calculator answers a related
question the upstream field deployment asked for on 2026-11-13: one value per
minute/hour/day/month bucket, under one of three rules — ``sum``, ``avg`` or
``meter_delta``.  The implementation keeps this library's shape: pure
calendar logic lives in :mod:`hybrid_ladder.calc`, this module only orchestrates
reads through the existing source/store protocols.

Rule semantics (unchanged from the upstream decision):

* ``sum`` — bucket value is the sum of the points in the bucket.
* ``avg`` — bucket value is ``sum / count``; a row total is the unweighted
  mean of the non-empty buckets ("mean of means").
* ``meter_delta`` — bucket value is ``next bucket's first reading minus this
  bucket's first reading``.  The last bucket reads one bucket past ``end``
  (that anchor is never emitted).  A bucket without a reading falls back to
  the last reading before its start, within
  :data:`~hybrid_ladder.models.DELTA_LOOKBACK_MS`.  Missing anchors, repeated
  readings, meter resets and non-numeric values are reported as anomaly codes
  instead of invented numbers.
"""

from __future__ import annotations

import bisect
import math
from collections.abc import Callable, Sequence
from typing import Any

from .calc import build_buckets, delta_chain, fold_row_total
from .core import fold_sum, merge_coverage, next_boundary, split_by_coverage, unit_start
from .errors import CancelledError
from .models import (
    BUCKET_MS,
    DELTA_LOOKBACK_MS,
    DIMENSIONS,
    FETCH_LEVEL,
    RULES,
    BucketValue,
    CalcResult,
    CalcRow,
    SeriesRef,
    coerce_refs,
    source_counts_calc,
)

__all__ = ["CalcMixin"]

ProgressFn = Callable[[int, int, str], None]
CancelFn = Callable[[], bool]


class CalcMixin:
    """``calc`` / ``calc_local`` / ``calc_mixed`` for the ladder engine."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def calc(
        self,
        refs: Sequence[SeriesRef] | SeriesRef,
        start_ms: int,
        end_ms: int,
        *,
        dimension: str = "day",
        rule: str = "sum",
        progress: ProgressFn | None = None,
        cancel: CancelFn | None = None,
    ) -> CalcResult:
        """Bucket ``[start_ms, end_ms)`` and compute one value per bucket.

        Reads from the source only.  See :meth:`calc_mixed` for the local-first
        read path and :meth:`calc_local` for an offline read.
        """
        series = coerce_refs(refs)
        self._check_calc_args(start_ms, end_ms, dimension, rule)

        def one(ref: SeriesRef) -> CalcRow:
            return self._calc_one(ref, start_ms, end_ms, dimension, rule, None, cancel)

        rows, errors = self._run_batch(series, one, progress, cancel, CalcRow)
        return self._calc_result(rule, dimension, rows, errors, "tb")

    def calc_local(
        self,
        refs: Sequence[SeriesRef] | SeriesRef,
        start_ms: int,
        end_ms: int,
        *,
        dimension: str = "day",
        rule: str = "sum",
        progress: ProgressFn | None = None,
        cancel: CancelFn | None = None,
    ) -> CalcResult:
        """Bucket calculation from the local store only (works offline)."""
        store = self._require_store()
        series = coerce_refs(refs)
        self._check_calc_args(start_ms, end_ms, dimension, rule)
        lookback = DELTA_LOOKBACK_MS[dimension]

        def one(ref: SeriesRef) -> CalcRow:
            buckets = build_buckets(start_ms, end_ms, dimension,
                                     timezone=self.config.timezone)
            ranges = [(b.start, b.end) for b in buckets]
            values: list[BucketValue] = []
            if rule in ("sum", "avg"):
                sums = store.sum_ranges(ref, ranges) if ranges else {}
                for bucket in buckets:
                    value, count = sums.get(bucket.start, (None, 0))
                    values.append(self._sum_avg_bucket(
                        rule, bucket, value if (count or value is not None) else None,
                        int(count or 0), None, 0, False))
            else:
                firsts = store.first_ranges(ref, ranges) if ranges else {}
                anchors: list[tuple[int, Any] | None] = []
                missing: list[int] = []
                for bucket in buckets:
                    anchor = firsts.get(bucket.start)
                    if anchor is None:
                        missing.append(bucket.start)
                    anchors.append(anchor)
                fallbacks = store.last_before(ref, missing, lookback) if missing else {}
                chain_firsts = [anchor or fallbacks.get(bucket.start)
                                for anchor, bucket in zip(anchors, buckets, strict=True)]
                ext_end = self._ext_end(buckets, dimension, rule)
                ext_first: tuple[int, Any] | None = None
                if ext_end is not None:
                    ext_first = store.first_ranges(ref, [(end_ms, ext_end)]).get(end_ms)
                    if ext_first is None:
                        ext_first = store.last_before(ref, [end_ms], lookback).get(end_ms)
                cells, chain_total, ok = delta_chain(chain_firsts, ext_first)
                for bucket, cell in zip(buckets, cells, strict=True):
                    values.append(BucketValue(
                        start=bucket.start, end=bucket.end, label=bucket.label,
                        value=cell.value, cnt=None,
                        source="local" if cell.first_ts is not None else "empty",
                        anomaly=cell.anomaly, first_ts=cell.first_ts,
                        next_ts=cell.next_ts,
                    ))
                row = self._calc_row(ref, buckets, values, rule)
                row.ok = ok
                if ok:
                    row.total = round(chain_total, 6)
                return row
            return self._calc_row(ref, buckets, values, rule)

        rows, errors = self._run_batch(series, one, progress, cancel, CalcRow)
        return self._calc_result(rule, dimension, rows, errors, "local")

    def calc_mixed(
        self,
        refs: Sequence[SeriesRef] | SeriesRef,
        start_ms: int,
        end_ms: int,
        *,
        dimension: str = "day",
        rule: str = "sum",
        progress: ProgressFn | None = None,
        cancel: CancelFn | None = None,
    ) -> CalcResult:
        """Bucket calculation, local-first.

        Each bucket is split against the merged coverage ranges: covered
        sub-ranges come from the store, the missing pieces from the source —
        the same read strategy as :meth:`~hybrid_ladder.engine.LadderEngine.sum_mixed`.
        """
        store = self._require_store()
        series = coerce_refs(refs)
        self._check_calc_args(start_ms, end_ms, dimension, rule)

        def one(ref: SeriesRef) -> CalcRow:
            coverage = merge_coverage(store.coverage(ref))
            return self._calc_one(ref, start_ms, end_ms, dimension, rule,
                                  coverage, cancel)

        rows, errors = self._run_batch(series, one, progress, cancel, CalcRow)
        counts = source_counts_calc(rows)
        if counts.get("tb", 0) == 0 and counts.get("uncovered", 0) == 0:
            overall = "local"
        elif counts.get("local", 0) == 0 and counts.get("mixed", 0) == 0:
            overall = "tb"
        else:
            overall = "mixed"
        result = self._calc_result(rule, dimension, rows, errors, overall)
        result.source_counts = counts
        return result

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _check_calc_args(self, start_ms: int, end_ms: int,
                        dimension: str, rule: str) -> None:
        if rule not in RULES:
            raise ValueError(f"rule must be one of {RULES}, got {rule!r}")
        if dimension not in DIMENSIONS:
            raise ValueError(f"dimension must be one of {DIMENSIONS}, got {dimension!r}")
        timezone = self.config.timezone
        if end_ms <= start_ms:
            raise ValueError("end_ms must be greater than start_ms")
        if unit_start(start_ms, dimension, timezone) != start_ms:
            raise ValueError(f"start_ms must be aligned to {dimension} boundaries")
        if unit_start(end_ms, dimension, timezone) != end_ms:
            raise ValueError(f"end_ms must be aligned to {dimension} boundaries")

    def _ext_end(self, buckets: Sequence, dimension: str, rule: str) -> int | None:
        """meter_delta reads one bucket past ``end`` for the last anchor."""
        if rule != "meter_delta" or not buckets:
            return None
        return next_boundary(int(buckets[-1].end), dimension, self.config.timezone)

    def _calc_one(self, ref: SeriesRef, start_ms: int, end_ms: int,
                  dimension: str, rule: str,
                  coverage: Sequence[tuple[int, int]] | None,
                  cancel: CancelFn | None) -> CalcRow:
        buckets = build_buckets(start_ms, end_ms, dimension,
                                timezone=self.config.timezone)
        parts = []
        for bucket in buckets:
            if coverage is None:
                covered, uncovered = [], [(bucket.start, bucket.end)]
            else:
                covered, uncovered = split_by_coverage(bucket.start, bucket.end, coverage)
            parts.append((bucket, covered, uncovered))

        ext_end = self._ext_end(buckets, dimension, rule)
        ext_covered: list[tuple[int, int]] = []
        ext_uncovered: list[tuple[int, int]] = []
        if ext_end is not None:
            if coverage is None:
                ext_uncovered = [(end_ms, ext_end)]
            else:
                ext_covered, ext_uncovered = split_by_coverage(end_ms, ext_end, coverage)

        if rule in ("sum", "avg"):
            values = self._calc_sum_avg(ref, parts, dimension, rule, cancel)
            row = self._calc_row(ref, buckets, values, rule)
        else:
            values, chain_total, ok = self._calc_delta(
                ref, parts, dimension, rule, cancel,
                ext_covered, ext_uncovered, end_ms, ext_end)
            row = self._calc_row(ref, buckets, values, rule)
            row.ok = ok
            row.total = round(chain_total, 6) if ok else None
        uncovered_flat = [r for _, _, uncovered in parts for r in uncovered]
        row.tb_ranges = [(a, b) for a, b in merge_coverage(uncovered_flat) if a < end_ms]
        return row

    def _calc_sum_avg(self, ref, parts, dimension, rule, cancel) -> list[BucketValue]:
        store = self.store
        covered_ranges = [r for _, covered, _ in parts for r in covered]
        local = store.sum_ranges(ref, covered_ranges) if (store and covered_ranges) else {}

        fully_uncovered = [bucket for bucket, covered, uncovered in parts
                           if not covered and uncovered]
        partials = [(bucket, uncovered) for bucket, covered, uncovered in parts
                    if covered and uncovered]

        grouped = self._bucket_source_sums(ref, fully_uncovered, dimension, cancel)

        partial_source: dict[tuple[int, int], tuple[float | None, int]] = {}
        for _, uncovered in partials:
            for a, b in uncovered:
                if (a, b) in partial_source:
                    continue
                if cancel and cancel():
                    raise CancelledError("cancelled")
                partial_source[(a, b)] = self._sum_count_range(ref, a, b)

        values: list[BucketValue] = []
        for bucket, covered, uncovered in parts:
            local_value, local_count, has_local = 0.0, 0, False
            for a, _ in covered:
                value, count = local.get(a, (None, 0))
                if count or value is not None:
                    local_value += float(value or 0.0)
                    local_count += int(count or 0)
                    has_local = True
            source_value, source_count, has_source = 0.0, 0, False
            if not covered:
                value, count = grouped.get(bucket.start, (None, 0))
                if value is not None or count:
                    source_value = float(value or 0.0)
                    source_count = int(count or 0)
                    has_source = True
            else:
                for a, b in uncovered:
                    value, count = partial_source.get((a, b), (None, 0))
                    if value is not None or count:
                        source_value += float(value or 0.0)
                        source_count += int(count or 0)
                        has_source = True
            values.append(self._sum_avg_bucket(
                rule, bucket,
                local_value if has_local else None, local_count,
                source_value if has_source else None, source_count,
                has_source))
        return values

    def _calc_delta(self, ref, parts, dimension, rule, cancel,
                    ext_covered, ext_uncovered, end_ms, ext_end
                    ) -> tuple[list[BucketValue], float, int]:
        store = self.store
        lookback = DELTA_LOOKBACK_MS[dimension]

        covered_ranges = [r for _, covered, _ in parts for r in covered]
        # The extension bucket participates in the chain, so its covered part
        # must go into the same first_ranges call.
        covered_ranges += list(ext_covered)
        local_first = (store.first_ranges(ref, covered_ranges)
                       if (store and covered_ranges) else {})

        uncovered_all = [r for _, _, uncovered in parts for r in uncovered]
        fetch_runs = merge_coverage(list(uncovered_all) + list(ext_uncovered))
        raw: list[tuple[int, Any]] = []
        for a, b in fetch_runs:
            if cancel and cancel():
                raise CancelledError("cancelled")
            raw.extend(self._raw_points(ref, a - lookback, b))
        raw.sort(key=lambda point: point[0])
        raw_ts = [point[0] for point in raw]

        def raw_first(a: int, b: int) -> tuple[int, Any] | None:
            index = bisect.bisect_left(raw_ts, a)
            if index < len(raw_ts) and raw_ts[index] < b:
                return raw[index]
            return None

        def raw_last_before(target: int) -> tuple[int, Any] | None:
            index = bisect.bisect_left(raw_ts, target) - 1
            if index >= 0 and raw_ts[index] >= target - lookback:
                return raw[index]
            return None

        anchors: list[tuple[int, Any] | None] = []
        missing: list[int] = []
        for bucket, covered, uncovered in parts:
            candidates: list[tuple[int, Any]] = []
            for a, _ in covered:
                point = local_first.get(a)
                if point is not None:
                    candidates.append(point)
            for a, b in uncovered:
                point = raw_first(a, b)
                if point is not None:
                    candidates.append(point)
            anchor = min(candidates, key=lambda point: point[0]) if candidates else None
            if anchor is None:
                missing.append(bucket.start)
            anchors.append(anchor)

        ext_anchor: tuple[int, Any] | None = None
        if ext_end is not None:
            ext_candidates: list[tuple[int, Any]] = []
            for a, _ in ext_covered:
                point = local_first.get(a)
                if point is not None:
                    ext_candidates.append(point)
            for a, b in ext_uncovered:
                point = raw_first(a, b)
                if point is not None:
                    ext_candidates.append(point)
            if ext_candidates:
                ext_anchor = min(ext_candidates, key=lambda point: point[0])

        fallback_targets = list(missing)
        if ext_end is not None and ext_anchor is None:
            fallback_targets.append(end_ms)
        local_fallback = (store.last_before(ref, fallback_targets, lookback)
                          if (store and fallback_targets) else {})

        firsts: list[tuple[int, Any] | None] = []
        for index, (bucket, _covered, _uncovered) in enumerate(parts):
            anchor = anchors[index]
            if anchor is None:
                candidates = [point for point in
                              (raw_last_before(bucket.start),
                               local_fallback.get(bucket.start))
                              if point is not None]
                anchor = max(candidates, key=lambda point: point[0]) if candidates else None
            firsts.append(anchor)
        if ext_end is not None and ext_anchor is None:
            candidates = [point for point in
                          (raw_last_before(end_ms), local_fallback.get(end_ms))
                          if point is not None]
            ext_anchor = max(candidates, key=lambda point: point[0]) if candidates else None

        cells, chain_total, ok = delta_chain(firsts, ext_anchor)
        values: list[BucketValue] = []
        for (bucket, covered, uncovered), cell in zip(parts, cells, strict=False):
            if not uncovered:
                source = "local"
            elif not covered:
                source = "tb"
            else:
                source = "mixed"
            values.append(BucketValue(
                start=bucket.start, end=bucket.end, label=bucket.label,
                value=cell.value, cnt=None, source=source,
                anomaly=cell.anomaly, first_ts=cell.first_ts, next_ts=cell.next_ts,
            ))
        return values, chain_total, ok

    def _sum_avg_bucket(self, rule, bucket, local_value, local_count,
                        source_value, source_count, has_source) -> BucketValue:
        has_local = local_value is not None or local_count > 0
        total = (float(local_value or 0.0) if has_local else 0.0) + (
            float(source_value or 0.0) if has_source else 0.0
        )
        count = (int(local_count or 0) if has_local else 0) + (
            int(source_count or 0) if has_source else 0
        )
        has_data = has_local or has_source
        if not has_data:
            value = None
        elif rule == "avg":
            value = round(total / count, 6) if count > 0 else None
        else:
            value = round(total, 6)
        if has_local and has_source:
            source = "mixed"
        elif has_local:
            source = "local"
        elif has_source:
            source = "tb"
        else:
            source = "empty"
        return BucketValue(start=bucket.start, end=bucket.end, label=bucket.label,
                           value=value, cnt=count if has_data else 0, source=source)

    def _bucket_source_sums(self, ref, buckets, dimension, cancel):
        """(sum, count) per bucket via grouped interval aggregation.

        The fetch level follows the ladder's ``FETCH_LEVEL`` table so a month
        folds from days and a day from hours, which keeps DST and calendar
        boundaries correct.  Buckets are packed into requests of at most
        ``config.max_intervals`` fetch buckets.
        """
        out: dict[int, tuple[float | None, int]] = {}
        if not buckets:
            return out
        fetch_bm = BUCKET_MS[FETCH_LEVEL[dimension]]
        chunk: list = []
        fetch_count = 0

        def flush() -> None:
            if not chunk:
                return
            start, end = chunk[0].start, chunk[-1].end
            raw_sum = self.source.interval_agg(ref, start, end, fetch_bm, "SUM")
            raw_count = self.source.interval_agg(ref, start, end, fetch_bm, "COUNT")
            fine_sum = {int(k): v for k, v in raw_sum.items()}
            fine_count = {int(k): v for k, v in raw_count.items()}
            for bucket in chunk:
                out[bucket.start] = (
                    fold_sum(fine_sum, bucket.start, bucket.end),
                    self._fold_count_values(fine_count, bucket.start, bucket.end),
                )
            chunk.clear()

        for bucket in buckets:
            if cancel and cancel():
                raise CancelledError("cancelled")
            estimate = max(1, math.ceil((bucket.end - bucket.start) / fetch_bm))
            if chunk and fetch_count + estimate > self.config.max_intervals:
                flush()
                fetch_count = 0
            chunk.append(bucket)
            fetch_count += estimate
        flush()
        return out

    @staticmethod
    def _fold_count_values(fine: dict[int, Any], start_ms: int, end_ms: int) -> int:
        total = 0
        for bucket_start, value in fine.items():
            if not (start_ms <= bucket_start < end_ms):
                continue
            try:
                total += int(value)
            except (TypeError, ValueError):
                continue
        return total

    def _sum_count_range(self, ref, start_ms: int, end_ms: int) -> tuple[float | None, int]:
        """(sum, count) for an arbitrary sub-range, adaptive bucket size."""
        duration = end_ms - start_ms
        if duration <= 0:
            return None, 0
        step = max(1, self.config.min_bucket_ms)
        bucket = max(step, math.ceil(duration / self.config.max_intervals / step) * step)
        raw_sum = self.source.interval_agg(ref, start_ms, end_ms, bucket, "SUM")
        raw_count = self.source.interval_agg(ref, start_ms, end_ms, bucket, "COUNT")
        values = []
        for value in raw_sum.values():
            if value is None:
                continue
            try:
                values.append(float(value))
            except (TypeError, ValueError):
                continue
        count = 0
        for value in raw_count.values():
            try:
                count += int(value)
            except (TypeError, ValueError):
                continue
        if not values and not count:
            return None, 0
        return (sum(values) if values else 0.0), count

    def _calc_row(self, ref, buckets, values, rule) -> CalcRow:
        row = CalcRow(ref=ref, buckets=values)
        row.total = fold_row_total(rule, [v.value for v in values])
        row.source_counts = source_counts_calc([row])
        return row

    def _calc_result(self, rule, dimension, rows, errors, overall) -> CalcResult:
        totals = [row.total for row in rows if row.total is not None]
        if not totals:
            grand = None
        elif rule == "avg":
            grand = round(sum(totals) / len(totals), 6)
        else:
            grand = round(sum(totals), 6)
        return CalcResult(
            rule=rule,
            dimension=dimension,
            rows=rows,
            grand_total=grand,
            source=overall,
            source_counts=source_counts_calc(rows),
            errors=errors,
        )
