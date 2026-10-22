# -*- coding: utf-8 -*-
"""The ladder engine: source reads, local-first mixed reads, materialize, verify, repair."""

from __future__ import annotations

import math
import time
from collections.abc import Callable, Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from .core import (
    BUCKET_MS,
    decompose,
    fetch_runs,
    fold_count,
    fold_sum,
    merge_coverage,
    split_by_coverage,
)
from .errors import CancelledError, ConfigurationError, SourceError
from .models import (
    LadderConfig,
    QueryResult,
    Row,
    SeriesRef,
    coerce_refs,
    source_counts,
    summarize_row,
)
from .protocols import PointStore, TimeSeriesSource

__all__ = ["LadderEngine"]

ProgressFn = Callable[[int, int, str], None]
CancelFn = Callable[[], bool]

_TOLERANCE = 1e-9


def _grand_total(rows: Sequence[Row]) -> float | None:
    values = [r.total for r in rows if r.total is not None]
    return round(sum(values), 6) if values else None


class LadderEngine:
    """Coordinate a :class:`TimeSeriesSource` and an optional :class:`PointStore`.

    The engine is thread-safe as long as the adapters are.  Batch methods run
    up to ``config.concurrency`` series in parallel.
    """

    def __init__(
        self,
        source: TimeSeriesSource,
        store: PointStore | None = None,
        config: LadderConfig | None = None,
        *,
        clock: Callable[[], int] | None = None,
    ) -> None:
        self.source = source
        self.store = store
        self.config = config or LadderConfig()
        self._clock = clock or (lambda: int(time.time() * 1000))

    # ------------------------------------------------------------------
    # Decomposition
    # ------------------------------------------------------------------
    def decompose(self, start_ms: int, end_ms: int, finest: str | None = None) -> list:
        return decompose(
            start_ms,
            end_ms,
            finest or self.config.finest,
            timezone=self.config.timezone,
            max_segments=self.config.max_segments,
        )

    # ------------------------------------------------------------------
    # Source-only reads
    # ------------------------------------------------------------------
    def sum(
        self,
        refs: Sequence[SeriesRef] | SeriesRef,
        start_ms: int,
        end_ms: int,
        *,
        finest: str | None = None,
        progress: ProgressFn | None = None,
        cancel: CancelFn | None = None,
    ) -> QueryResult:
        """Sum every series using the source only (no local store)."""
        series = coerce_refs(refs)
        finest = finest or self.config.finest
        self.decompose(start_ms, end_ms, finest)  # validate once up front

        def one(ref: SeriesRef) -> Row:
            return self._sum_one_source(ref, start_ms, end_ms, finest, cancel)

        rows, errors = self._run_batch(series, one, progress, cancel)
        return QueryResult(
            rows=rows,
            grand_total=_grand_total(rows),
            source="tb",
            source_counts=source_counts(rows),
            errors=errors,
        )

    def _sum_one_source(
        self,
        ref: SeriesRef,
        start_ms: int,
        end_ms: int,
        finest: str,
        cancel: CancelFn | None = None,
    ) -> Row:
        segments = self.decompose(start_ms, end_ms, finest)
        self._fill_from_source(ref, segments, cancel)
        return summarize_row(ref, segments)

    def _fill_from_source(
        self,
        ref: SeriesRef,
        segments: Sequence,
        cancel: CancelFn | None = None,
    ) -> None:
        """Fill segment values from the source, in place.

        Segments are grouped by *fetch level* and contiguity.  Hours and
        minutes can share one minute-level fetch; months use day buckets and
        days use hour buckets so that DST and non-midnight-aligned ranges stay
        correct.
        """
        for fetch_level, run in fetch_runs(segments):
            if cancel and cancel():
                raise CancelledError("cancelled")
            start, end = run[0].start, run[-1].end
            raw = self.source.interval_agg(ref, start, end, BUCKET_MS[fetch_level], "SUM")
            fine = {int(k): v for k, v in raw.items()}
            for seg in run:
                seg.value = fold_sum(fine, seg.start, seg.end)
                seg.cnt = fold_count(fine, seg.start, seg.end)
                seg.expected = max(1, seg.duration_ms // BUCKET_MS[fetch_level])
                seg.source = "tb" if seg.value is not None else "empty"

        # Sub-minute remainders are read as raw points: an interval bucket is
        # always a full minute and cannot represent them.
        for seg in segments:
            if not seg.is_subminute_tail:
                continue
            if cancel and cancel():
                raise CancelledError("cancelled")
            points = self._raw_points(ref, seg.start, seg.end)
            if not points:
                seg.value, seg.cnt, seg.expected, seg.source = None, 0, None, "empty"
                continue
            total = 0.0
            for _, value in points:
                try:
                    total += float(value)
                except (TypeError, ValueError):
                    continue
            seg.value, seg.cnt, seg.expected, seg.source = total, len(points), None, "tb"

    # ------------------------------------------------------------------
    # Local reads
    # ------------------------------------------------------------------
    def sum_local(
        self,
        refs: Sequence[SeriesRef] | SeriesRef,
        start_ms: int,
        end_ms: int,
        *,
        finest: str | None = None,
        progress: ProgressFn | None = None,
        cancel: CancelFn | None = None,
    ) -> QueryResult:
        """Sum every series from the local store only (works offline)."""
        store = self._require_store()
        series = coerce_refs(refs)
        finest = finest or self.config.finest
        self.decompose(start_ms, end_ms, finest)

        def one(ref: SeriesRef) -> Row:
            segments = self.decompose(start_ms, end_ms, finest)
            ranges = [(s.start, s.end) for s in segments]
            got = store.sum_ranges(ref, ranges)
            for seg in segments:
                value, cnt = got.get(seg.start, (None, 0))
                seg.value = float(value) if value is not None else None
                seg.cnt = int(cnt or 0)
                seg.expected = None
                seg.source = "local" if seg.cnt else "empty"
            return summarize_row(ref, segments)

        rows, errors = self._run_batch(series, one, progress, cancel)
        return QueryResult(
            rows=rows,
            grand_total=_grand_total(rows),
            source="local",
            source_counts=source_counts(rows),
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Local-first mixed reads
    # ------------------------------------------------------------------
    def sum_mixed(
        self,
        refs: Sequence[SeriesRef] | SeriesRef,
        start_ms: int,
        end_ms: int,
        *,
        finest: str | None = None,
        progress: ProgressFn | None = None,
        cancel: CancelFn | None = None,
    ) -> QueryResult:
        """Read covered sub-ranges locally and fetch only the missing pieces.

        Each segment is split against the merged coverage ranges.  Fully
        covered segments use one batched SQL sum; fully uncovered segments are
        fetched with grouped aggregation; partially covered segments combine a
        local sum with a source sum for the missing tail only.
        """
        store = self._require_store()
        series = coerce_refs(refs)
        finest = finest or self.config.finest
        self.decompose(start_ms, end_ms, finest)

        def one(ref: SeriesRef) -> Row:
            segments = self.decompose(start_ms, end_ms, finest)
            coverage = merge_coverage(store.coverage(ref))
            parts = []
            for seg in segments:
                covered, uncovered = split_by_coverage(seg.start, seg.end, coverage)
                parts.append((seg, covered, uncovered))

            fully_uncovered = [seg for seg, covered, _ in parts if not covered]
            partials = [(seg, covered, uncovered) for seg, covered, uncovered in parts
                        if covered and uncovered]
            fully_covered = [(seg, covered) for seg, covered, uncovered in parts
                             if covered and not uncovered]

            covered_ranges = [r for _, covered in fully_covered for r in covered]
            covered_ranges += [r for _, covered, _ in partials for r in covered]
            local = store.sum_ranges(ref, covered_ranges) if covered_ranges else {}

            if fully_uncovered:
                self._fill_from_source(ref, fully_uncovered, cancel)

            partial_source: dict[tuple[int, int], tuple[float | None, int]] = {}
            for _, _, uncovered_ranges in partials:
                for a, b in uncovered_ranges:
                    if (a, b) in partial_source:
                        continue
                    if cancel and cancel():
                        raise CancelledError("cancelled")
                    partial_source[(a, b)] = self._sum_range(ref, a, b)

            for seg, covered in fully_covered:
                local_value, local_cnt, has_local = 0.0, 0, False
                for a, _ in covered:
                    value, cnt = local.get(a, (None, 0))
                    if cnt:
                        local_value += float(value or 0.0)
                        local_cnt += int(cnt)
                        has_local = True
                seg.value = round(local_value, 6) if has_local else None
                seg.cnt = local_cnt
                seg.expected = None
                seg.source = "local" if has_local else "empty"

            for seg, covered, uncovered_ranges in partials:
                local_value, local_cnt, has_local = 0.0, 0, False
                for a, _ in covered:
                    value, cnt = local.get(a, (None, 0))
                    if cnt:
                        local_value += float(value or 0.0)
                        local_cnt += int(cnt)
                        has_local = True

                source_value, source_cnt, has_source = 0.0, 0, False
                for a, b in uncovered_ranges:
                    value, cnt = partial_source.get((a, b), (None, 0))
                    if value is not None:
                        source_value += float(value)
                        source_cnt += int(cnt)
                        has_source = True

                if not has_local and not has_source:
                    seg.value, seg.cnt, seg.source = None, 0, "empty"
                else:
                    seg.value = round(local_value + source_value, 6)
                    seg.cnt = local_cnt + source_cnt
                    if has_local and has_source:
                        seg.source = "mixed"
                    elif has_local:
                        seg.source = "local"
                    else:
                        seg.source = "tb"
                seg.expected = None

            tb_ranges = merge_coverage([r for _, _, uncovered in parts for r in uncovered])
            return summarize_row(ref, segments, tb_ranges)

        rows, errors = self._run_batch(series, one, progress, cancel)
        counts = source_counts(rows)
        if counts.get("tb", 0) == 0 and counts.get("uncovered", 0) == 0:
            overall = "local"
        elif counts.get("local", 0) == 0 and counts.get("mixed", 0) == 0:
            overall = "tb"
        else:
            overall = "mixed"
        return QueryResult(
            rows=rows,
            grand_total=_grand_total(rows),
            source=overall,
            source_counts=counts,
            errors=errors,
        )

    def _sum_range(self, ref: SeriesRef, start_ms: int, end_ms: int) -> tuple[float | None, int]:
        """Sum an arbitrary sub-range with an adaptive bucket size."""
        duration = end_ms - start_ms
        if duration <= 0:
            return None, 0
        step = max(1, self.config.min_bucket_ms)
        bucket = max(step, math.ceil(duration / self.config.max_intervals / step) * step)
        raw = self.source.interval_agg(ref, start_ms, end_ms, bucket, "SUM")
        values = []
        for value in raw.values():
            if value is None:
                continue
            try:
                values.append(float(value))
            except (TypeError, ValueError):
                continue
        if not values:
            return None, 0
        return sum(values), len(values)

    # ------------------------------------------------------------------
    # Materialize (source -> store)
    # ------------------------------------------------------------------
    def materialize(
        self,
        refs: Sequence[SeriesRef] | SeriesRef,
        start_ms: int,
        end_ms: int,
        *,
        progress: ProgressFn | None = None,
        cancel: CancelFn | None = None,
    ) -> dict[str, Any]:
        """Pull raw points for the whole range and mark it as covered."""
        series = coerce_refs(refs)
        return self.materialize_ranges(
            [(ref, [(start_ms, end_ms)]) for ref in series],
            progress=progress,
            cancel=cancel,
        )

    def materialize_ranges(
        self,
        items: Iterable[tuple[SeriesRef, Sequence[tuple[int, int]]]],
        *,
        progress: ProgressFn | None = None,
        cancel: CancelFn | None = None,
    ) -> dict[str, Any]:
        """Pull raw points for explicit per-series ranges and mark coverage.

        ``items`` is ``[(SeriesRef, [(start, end), ...]), ...]``.  Ranges are
        clamped to ``now - materialize_grace_ms``; the in-flight tail is never
        marked as trustworthy.
        """
        store = self._require_store()
        items = [(ref, list(ranges)) for ref, ranges in items]
        total = sum(len(ranges) for _, ranges in items)
        now = self._clock()
        claim_limit = now - self.config.materialize_grace_ms
        written = 0
        done = 0

        for ref, ranges in items:
            for a, b in ranges:
                if cancel and cancel():
                    raise CancelledError("cancelled")
                claim_end = min(int(b), claim_limit)
                written_here = 0
                if claim_end > a:
                    # Invalidate coverage first: if the pull fails halfway the
                    # range must not stay marked as trustworthy.
                    store.clear_coverage(ref, a, claim_end)
                    store.delete_range(ref, a, claim_end)
                    for chunk in self._iter_raw_chunks(ref, a, claim_end, cancel):
                        written_here += store.upsert_points(ref, chunk, at_ms=now)
                # Mark even a zero-point range: "we asked the source, there is
                # nothing here" is a valid fact and prevents repeated fetches.
                store.mark_covered(ref, a, claim_end, written_here, now)
                written += written_here
                done += 1
                if progress:
                    progress(done, total, f"materialized {done}/{total} ranges ({written} points)")

        return {"written": written, "ranges": total, "series": len(items)}

    # ------------------------------------------------------------------
    # Verification and repair
    # ------------------------------------------------------------------
    def verify(
        self,
        refs: Sequence[SeriesRef] | SeriesRef,
        start_ms: int,
        end_ms: int,
        *,
        finest: str | None = None,
        drill_limit: int = 50,
        progress: ProgressFn | None = None,
        cancel: CancelFn | None = None,
    ) -> dict[str, Any]:
        """Compare the source (authority) with the local store, segment by segment.

        Only differing segments are drilled down to individual points, capped by
        ``drill_limit`` across the whole report.
        """
        store = self._require_store()
        series = coerce_refs(refs)
        finest = finest or self.config.finest
        segments = self.decompose(start_ms, end_ms, finest)
        ranges = [(s.start, s.end) for s in segments]

        report: dict[str, Any] = {
            "series": len(series),
            "segments": len(segments),
            "diff_series": 0,
            "diff_segments": 0,
            "details": [],
            "drilled": 0,
            "drill_skipped": 0,
        }

        for index, ref in enumerate(series, start=1):
            if cancel and cancel():
                raise CancelledError("cancelled")
            tb_row = self._sum_one_source(ref, start_ms, end_ms, finest, cancel)
            local = store.sum_ranges(ref, ranges)
            diffs = []
            for seg in tb_row.segments:
                tb_value = seg.value
                local_value, local_cnt = local.get(seg.start, (None, 0))
                local_value = float(local_value) if local_value is not None else None
                same = (tb_value is None and local_value is None) or (
                    tb_value is not None
                    and local_value is not None
                    and abs(tb_value - local_value) <= _TOLERANCE * max(1.0, abs(tb_value))
                )
                if not same:
                    diffs.append(
                        {
                            "level": seg.level,
                            "label": seg.label,
                            "start": seg.start,
                            "end": seg.end,
                            "tb": tb_value,
                            "local": local_value,
                            "local_cnt": int(local_cnt or 0),
                        }
                    )

            if diffs:
                report["diff_series"] += 1
                report["diff_segments"] += len(diffs)
                for diff in diffs:
                    if report["drilled"] >= drill_limit:
                        report["drill_skipped"] += 1
                        continue
                    if cancel and cancel():
                        raise CancelledError("cancelled")
                    tb_points = dict(self._raw_points(ref, diff["start"], diff["end"]))
                    local_rows = store.series(ref, diff["start"], diff["end"])
                    local_points = {int(row["ts"]): row["value"] for row in local_rows}
                    added = [ts for ts in tb_points if ts not in local_points]
                    removed = [ts for ts in local_points if ts not in tb_points]
                    changed = [
                        ts
                        for ts in tb_points
                        if ts in local_points
                        and tb_points[ts] is not None
                        and local_points[ts] is not None
                        and abs(float(tb_points[ts]) - float(local_points[ts])) > _TOLERANCE
                    ]
                    diff.update(
                        {
                            "tb_points": len(tb_points),
                            "local_points": len(local_points),
                            "added": len(added),
                            "removed": len(removed),
                            "changed": len(changed),
                            "sample_added": added[:5],
                            "sample_removed": removed[:5],
                            "sample_changed": changed[:5],
                        }
                    )
                    report["drilled"] += 1
                report["details"].append(
                    {"device_name": ref.display_name, "key": ref.key, "diffs": diffs}
                )

            if progress:
                progress(index, len(series), f"verified {index}/{len(series)} series")

        return report

    def repair(
        self,
        refs: Sequence[SeriesRef] | SeriesRef,
        start_ms: int,
        end_ms: int,
        *,
        progress: ProgressFn | None = None,
        cancel: CancelFn | None = None,
    ) -> dict[str, Any]:
        """Replace the local range with the source's current data (authority wins)."""
        store = self._require_store()
        series = coerce_refs(refs)
        now = self._clock()
        claim_end = min(int(end_ms), now - self.config.materialize_grace_ms)
        window_ms = self.config.max_repair_days * 86_400_000
        results = []

        for index, ref in enumerate(series, start=1):
            if cancel and cancel():
                raise CancelledError("cancelled")
            deleted = inserted = 0
            cursor = int(start_ms)
            while cursor < claim_end:
                if cancel and cancel():
                    raise CancelledError("cancelled")
                window_end = min(cursor + window_ms, claim_end)
                store.clear_coverage(ref, cursor, window_end)
                deleted += store.delete_range(ref, cursor, window_end)
                for chunk in self._iter_raw_chunks(ref, cursor, window_end, cancel):
                    inserted += store.upsert_points(ref, chunk, at_ms=now)
                cursor = window_end
            if claim_end > start_ms:
                store.mark_covered(ref, start_ms, claim_end, inserted, now)
            results.append(
                {
                    "device_id": ref.entity,
                    "device_name": ref.display_name,
                    "key": ref.key,
                    "deleted": deleted,
                    "inserted": inserted,
                }
            )
            if progress:
                progress(index, len(series), f"repaired {index}/{len(series)} series")

        return {"series": results, "range": [int(start_ms), claim_end]}

    # ------------------------------------------------------------------
    # Raw point streaming
    # ------------------------------------------------------------------
    def _raw_points(
        self,
        ref: SeriesRef,
        start_ms: int,
        end_ms: int,
        state: dict[str, int] | None = None,
    ) -> list[tuple[int, Any]]:
        """All raw points in ``[start, end)``; bisects when a page is full."""
        if state is None:
            state = {"n": 0}
        if start_ms >= end_ms:
            return []
        points = self.source.raw_series(ref, start_ms, end_ms, self.config.max_points)
        if len(points) < self.config.max_points:
            state["n"] += len(points)
            if state["n"] > self.config.max_total_points:
                raise SourceError(
                    f"more than {self.config.max_total_points} points in one request; "
                    "narrow the time range"
                )
            return list(points)
        if end_ms - start_ms <= self.config.min_bucket_ms:
            raise SourceError(
                f"more than {self.config.max_points} points in a single minute; "
                "narrow the time range"
            )
        mid = (start_ms + end_ms) // 2
        # The source contract is [start, end), so both halves must use ``mid``
        # as the boundary.  ``mid + 1`` (the original TB-inclusive convention)
        # would drop a point that lands exactly on ``mid``.
        return self._raw_points(ref, start_ms, mid, state) + self._raw_points(
            ref, mid, end_ms, state
        )

    def _iter_raw_chunks(
        self,
        ref: SeriesRef,
        start_ms: int,
        end_ms: int,
        cancel: CancelFn | None = None,
    ):
        """Yield raw-point chunks, each at most ``max_points`` long."""
        state = {"n": 0}

        def rec(a: int, b: int):
            if cancel and cancel():
                raise CancelledError("cancelled")
            if a >= b:
                return
            points = self.source.raw_series(ref, a, b, self.config.max_points)
            if len(points) < self.config.max_points:
                state["n"] += len(points)
                if state["n"] > self.config.max_total_points:
                    raise SourceError(
                        f"more than {self.config.max_total_points} points in one request; "
                        "narrow the time range"
                    )
                if points:
                    yield list(points)
                return
            if b - a <= self.config.min_bucket_ms:
                raise SourceError(
                    f"more than {self.config.max_points} points in a single minute; "
                    "narrow the time range"
                )
            mid = (a + b) // 2
            # Both halves are [start, end): never skip the boundary point.
            yield from rec(a, mid)
            yield from rec(mid, b)

        yield from rec(int(start_ms), int(end_ms))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _run_batch(
        self,
        refs: Sequence[SeriesRef],
        fn: Callable[[SeriesRef], Row],
        progress: ProgressFn | None,
        cancel: CancelFn | None,
    ) -> tuple[list[Row], list[dict[str, Any]]]:
        total = len(refs)
        if total == 0:
            return [], []

        rows: list[Row | None] = [None] * total
        errors: list[dict[str, Any]] = []
        done = 0
        workers = min(self.config.concurrency, total)

        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="hybrid-ladder") as pool:
            futures = {pool.submit(fn, ref): index for index, ref in enumerate(refs)}
            for future in as_completed(futures):
                if cancel and cancel():
                    for pending in futures:
                        pending.cancel()
                    raise CancelledError("cancelled")
                index = futures[future]
                try:
                    rows[index] = future.result()
                except CancelledError:
                    raise
                except Exception as exc:
                    if not self.config.continue_on_error:
                        raise
                    message = f"{type(exc).__name__}: {exc}"
                    rows[index] = Row(ref=refs[index], error=message)
                    errors.append(
                        {
                            "device_id": refs[index].entity,
                            "key": refs[index].key,
                            "error": message,
                        }
                    )
                done += 1
                if progress:
                    progress(done, total, f"computed {done}/{total} series")

        return [row for row in rows if row is not None], errors

    def _require_store(self) -> PointStore:
        if self.store is None:
            raise ConfigurationError(
                "this operation needs a PointStore; pass store=... to LadderEngine"
            )
        return self.store
