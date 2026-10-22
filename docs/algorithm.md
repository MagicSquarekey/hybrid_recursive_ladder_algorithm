# Algorithm specification

> This document is the authoritative specification for the Hybrid Recursive
> Ladder Algorithm. Implementation and tests must follow it; any change in
> semantics must update this file first.

## 1. Definition

Given a range `[start, end)` and a finest level `L ∈ {month, day, hour, minute}`,
the ladder decomposes the range into segments of **complete calendar units**:

1. At each level, emit only units `[u, u+1)` that lie entirely inside the range.
2. A partial left edge and a partial right edge are recursively pushed to the
   next finer level.
3. At the finest level, a remainder shorter than one unit is emitted as its own
   segment (the "tail").

The name is literal: it is a *hybrid* of calendar recursion and a *ladder* that
only steps on complete bricks.

## 2. Boundary rules (non-negotiable)

| Rule | Meaning |
|---|---|
| Left-closed, right-open | The range is `[start, end)`. If `end` is exactly on a boundary, that unit does not exist in the result. |
| Complete units only | A unit is emitted at its level only if it is fully contained in the range. |
| Local calendar | Boundaries use the configured IANA timezone (default `Asia/Shanghai`): month = first day 00:00, day = 00:00, hour = `:00`, minute = `:00`. |
| Unit order | month → day → hour → minute. The finest level is configurable; the default is `minute`. |
| Completeness is relative to the query | Not relative to "now". Historical ranges decompose the same way. |
| Tiling | Segments are ordered, contiguous, non-overlapping, and their union is exactly `[start, end)`. |

## 3. Pseudocode

```
ladder(a, b, level):
    if a >= b: return []

    if level is finest:
        emit(a, b)                       # complete unit or sub-unit tail
        return

    if unit_start(a, level) != a:        # left remainder
        nb = next_boundary(a, level)
        if nb >= b:
            ladder(a, b, next_level)     # whole range is a remainder
            return
        ladder(a, nb, next_level)
        a = nb

    while next_boundary(a, level) <= b:  # complete units
        nb = next_boundary(a, level)
        emit(a, nb, level)
        a = nb

    if a < b:                            # right remainder
        ladder(a, b, next_level)
```

`unit_start` and `next_boundary` are calendar operations in the configured
timezone. `next_boundary` must always advance; the implementation guards
against a non-advancing boundary.

## 4. Worked example

Range `2026-01-01 00:00:00 → 2026-10-21 18:49:59`:

| Level | Segments | Count |
|---|---|---:|
| month | 2026-01 … 2026-09 | 9 |
| day | 2026-10-01 … 2026-10-20 | 20 |
| hour | 2026-10-21 00:00 … 17:00 | 18 |
| minute | 2026-10-21 18:00 … 18:48 | 49 |
| tail | 2026-10-21 18:49:00–18:49:59 | 1 |
| **Total** | | **97** |

A per-minute query would produce 423,049 buckets, a ~4,360× reduction.

Note that 18:00–19:00 is incomplete, so the last complete hour is 17:00. The
18:00 hour is decomposed into complete minutes plus the 59-second tail.

## 5. Fetch strategy

The output level determines the output granularity, not the fetch granularity.
For each output level, fetch the **next finer** aggregation once over the
contiguous run and fold locally:

| Output level | Fetch level | Why |
|---|---|---|
| month | day | Most sources have no natural-month fixed interval; fold days. |
| day | hour | Avoids DST/fixed-bucket day-boundary drift. |
| hour | minute | Folds exact minutes into hours. |
| minute | minute | Direct. |
| sub-minute tail | raw points | An interval bucket cannot represent a partial minute. |

### 5.1 Grouping rule (v0.0.1 fix)

Fetch runs are grouped by **fetch level + time contiguity**, never by time
contiguity alone. Hours and minutes can share one minute-level fetch; months
and days cannot share a fetch. Grouping a multi-level range only by adjacency
(the original implementation) caused the whole range to be fetched at the
coarsest level, assigning a whole day's value to the first hour and losing the
rest.

### 5.2 Request count

For a range with `M` months, `D` days, `H` hours and `N` minutes, the number of
aggregation requests is roughly:

```
ceil(D_total / max_intervals) + ceil(H_total / max_intervals)
+ ceil(N_total / max_intervals) + 1 (tail, if any)
```

`max_intervals` defaults to 500 because ThingsBoard accepts ~700 buckets and
rejects 800 (the documentation's 1000 is not reliable). A 10-month query
typically needs 5–7 requests.

## 6. Correctness

| Rule | Ladder exact? | Notes |
|---|---|---|
| `sum` | ✅ | The sum of all segments equals the sum of the source's points in the range. |
| `max` / `min` | ✅ | Fold extrema. Not implemented in v0.0.1. |
| `last` | ✅ | The last value of the last segment. Not implemented. |
| `avg` | ⚠️ needs weighting | Average of segment averages ≠ average of all points. Needs `sum` + `count`, and `COUNT` may collapse duplicate points. Not implemented. |
| `meter_delta` | ⚠️ different algorithm | Requires the first value of every segment. Most sources (including ThingsBoard) have no `FIRST` aggregation, so raw points or per-segment boundary queries are needed. Not implemented. |

### 6.1 Empty vs zero

`value = null` means the segment has no samples. `value = 0.0` means samples
exist and their sum is zero. They must never be conflated in storage, APIs or
UI.

### 6.2 Time completeness vs data completeness

The ladder guarantees **time completeness**: every segment lies inside the
range. It does not guarantee **data completeness**: the source may have missing
samples. The sum is the sum of the points that exist. `cnt` (observed points or
buckets) and `expected` (buckets the segment should contain) expose sparsity;
they are not used to impute data.

## 7. Coverage and the local-first read path

### 7.1 Coverage

A materialized range is recorded in a coverage table as
`(start_ts, end_ts, covered_at)`. Coverage is only recorded up to
`now - grace` (default 5 minutes); the in-flight tail is never considered
trustworthy local data. A range is recorded even when the source returned zero
points ("we asked, there is nothing"), so the next query does not hit the
source again.

### 7.2 Sub-range split

For every segment:

1. Split it against the merged coverage ranges into covered and uncovered
   sub-ranges.
2. Sum all covered sub-ranges with one batched local query.
3. Fetch fully uncovered segments with grouped aggregation.
4. For partially covered segments, fetch only the missing sub-ranges with an
   adaptive bucket size (`max(min_bucket, ceil(duration / max_intervals / min_bucket) * min_bucket)`).
5. Segment value = local part + source part. Source = `local`, `tb`, `mixed`,
   `empty`, or `uncovered`.

`tb_ranges` in the result is the merged list of uncovered sub-ranges — the
input for materialization.

### 7.3 Rewrite safety

Before rewriting a range, the store clears coverage rows that overlap the
range. If the pull fails halfway, the range is no longer marked as covered, so
a later query re-fetches it instead of trusting incomplete local data.

## 8. Materialization, verification and repair

* **Materialize** pulls raw points in chunks of at most `max_points` (10,000),
  bisecting the window when a page is full. Points are written idempotently;
  the primary key makes a timestamp appear once. The range is marked covered
  after the write.
* **Verify** compares the source (authority) with the local store segment by
  segment using `SUM` and point counts. Only differing segments are drilled
  down to points, reporting `added`, `removed`, `changed` and sample
  timestamps. Drilling is capped by `drill_limit` (default 50).
* **Repair** deletes the local range and re-pulls it from the source in windows
  of at most `max_repair_days` (default 366), then re-marks coverage. Points
  deleted at the source disappear locally.

## 9. Data model

```json
{
  "level": "day",
  "start": 1792339200000,
  "end": 1792425600000,
  "label": "2026-10-19",
  "value": 1245888.0,
  "cnt": 1442,
  "expected": 24,
  "source": "local"
}
```

| Field | Meaning |
|---|---|
| `level` | `month`, `day`, `hour`, `minute` |
| `start`, `end` | Epoch milliseconds, `[start, end)` |
| `label` | `YYYY-MM`, `YYYY-MM-DD`, `YYYY-MM-DD HH:00`, `YYYY-MM-DD HH:MM` |
| `value` | Sum or `null` (no samples) |
| `cnt` | Observed points (raw) or buckets (aggregated) |
| `expected` | Expected buckets for a source segment; `null` for local segments |
| `source` | `local`, `tb`, `mixed`, `empty`, `uncovered` |

A query result contains one row per series with `segments`, `total`,
`empty_count`, `segments_count` and `tb_ranges`, plus a `grand_total`, an
overall `source`, `source_counts` and `errors`.

## 10. Invariants

1. Segments tile the range exactly.
2. No zero-length segments.
3. A unit is emitted at level `L` only if it is fully inside the range.
4. `null` and `0.0` are distinct.
5. Coverage never extends beyond `now - grace`.
6. Materialization is idempotent.
7. The algorithm never writes to the source.

## 11. Known limitations

* Only `sum` is implemented in v0.0.1.
* Data gaps make the total lower than the physical total; `cnt`/`expected`
  expose this but do not fix it.
* ThingsBoard `COUNT` collapses duplicate points within a minute; use raw
  points when exact counts matter.
* In-process background tasks are lost on restart (results are recomputable).
* Fixed-size source buckets mean day/hour folding is designed for fixed-offset
  time zones such as `Asia/Shanghai`; in DST zones, prefer finer fetch levels
  around transitions.
* The stable-key migration (`device_id`) from the original AutoTestHub schema
  is not automatic; see `docs/architecture.md`.

## 12. Version notes

**0.0.1** — initial standalone release. Two correctness fixes relative to the
original AutoTestHub implementation:

1. Fetch runs are grouped by fetch level + contiguity. The original grouped by
   adjacency only, which broke multi-level queries.
2. Raw chunk bisection uses `[a, mid)` and `[mid, b)`. The original used
   `mid + 1`, which dropped a point exactly on the split boundary under an
   exclusive-end contract.
