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
typically needs 5–7 requests. Section 5.4 gives the exact per-run model,
including the adapter's chunking.

### 5.3 Refinement locality

Write `L_0 = month`, `L_1 = day`, `L_2 = hour`, `L_3 = minute` (coarsest
first), and let `U_i(t)` be the unit of level `L_i` that contains `t`. Let `k`
be the number of levels (4 in the default hierarchy). A unit is **complete** in
`[s, e)` when it is contained in the range.

**Lemma 1 (two-edge lemma).** For every level `L_i` with `i < k - 1`, the parts
of `[s, e)` passed to level `L_{i+1}` lie inside at most two units of level
`L_i`: the unit containing `s` and the unit containing `e - 1`. Every complete
unit at level `L_i` is emitted at `L_i` and is never refined.

*Proof.* At level `L_i` the walk (i) refines the left remainder
`[s, next_boundary(s))` when `s` is not aligned, (ii) emits the maximal run of
complete units, and (iii) refines the right remainder `[a, e)` when `a < e`.
Step (i) is inside `U_i(s)`. Step (iii) is inside `U_i(e - 1)`. Step (ii) emits
complete units and does not recurse. Each refined remainder is shorter than one
unit at its level, i.e. below that level's maximum radix (31 days, 24 hours, 60
minutes). ∎

**Proposition 2 (bounded refinement).** Let `N_j` be the number of segments
emitted at level `L_j`. Then, for every `i`,

```
sum_{j > i} N_j  <=  B_i
```

where `B_i` is the maximum number of segments produced by decomposing at most
two units of level `L_i` down to the finest level. `B_i` depends only on the
calendar hierarchy, not on the length of the range.

For the standard hierarchy and `finest = minute`, a conservative bound is

```
N_day    <= 2 * 31 = 62      # at most two partial months
N_hour   <= 4 * 24 = 96      # two partial days per partial month
N_minute <= 8 * 60 = 480     # two partial hours per partial day
tail     <= 1
```

The factors double because each partial unit can produce at most two partial
units at the next finer level. These bounds are conservative, not tight.
Summing them gives `N <= N_month + 639`, where `N` is the total number of
segments.

**Corollary 3 (segment-count growth).** The total number of segments is
`N_month + O(1)`. It grows with the number of complete months (the coarsest
output level), not with the number of minute buckets. For a range of `Y` years,
`N = O(Y)`; a per-minute query would be `O(Y * 525600)`.

**Proposition 4 (recursion depth).** The recursion depth of `walk` is at most
the number of levels `k` (4 for month through minute). Each recursive call
increments the level index, and the base case is the finest level.

### 5.4 Request-count model

Let `K = max_intervals`, and let a **fetch run** be a maximal contiguous
sequence of segments that share the same fetch level (Section 5.1). For a run of
duration `T` at fetch bucket size `Δ`, the adapter chunks it into windows of
`K * Δ` and issues

```
r(run) = ceil(T / (K * Δ))
```

aggregation requests. The total is therefore

```
R_agg = sum over runs r of ceil(T_r / (K * Δ_r)).
```

This is the exact model implemented by `ThingsBoardSource.interval_agg`: the
engine calls the adapter once per run, and the adapter performs the chunking.
Let `B_F` be the total number of fetch buckets at level `F` over the range; it
is not the number of output segments.

In the common contiguous case there are at most three aggregation runs (day,
hour, minute), so the sum has at most three terms. For the 10-month example with
`K = 500`:

```
months          -> day fetch:    273 buckets -> 1 request
days            -> hour fetch:   480 buckets -> 1 request
hours + minutes -> minute fetch: 1,129 buckets -> 3 requests
R_agg ~= 5
```

By Lemma 1, `B_day = O(N_month)`, while `B_hour` and `B_minute` are bounded by
the two partial months and the partial days at their edges, and are therefore
`O(1)` for a fixed hierarchy. Hence

```
R_agg = O(N_month / K + 1).
```

The request count grows with the number of complete months divided by the cap,
not with the number of minute buckets. The raw-point tail is data-dependent:
each raw request returns at most `max_points` points and a full page is bisected
(Section 8), so `P` points cost `O(P / max_points)` requests, with a hard floor
at `min_bucket_ms`.

### 5.5 Fold correctness (alignment condition)

`fold_sum` attributes a fetch bucket to the output segment that contains the
bucket's **start**. If every fetch bucket is wholly contained in one output
segment or disjoint from it, the folded sum equals the source's sum over the
segment. Fixed-offset time zones satisfy this because every calendar unit is a
union of fixed-size buckets. In DST zones a day or hour boundary can fall inside
a fixed-size bucket; use a finer fetch level or raw points around transitions.
This is a correctness condition, not a claim about arbitrary time zones.

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

## 12. Relationship to known techniques

The decomposition is the calendar mixed-radix instance of the canonical interval
decomposition used by segment trees: a range is covered by aligned units, and
partial edges are pushed to a finer level. It differs in purpose: a segment tree
merges siblings to answer one aggregate, while the ladder must return one value
per output unit, so it emits every complete unit and uses the hierarchy to plan
fetches. The fold is a roll-up/consolidation, the same direction as RRDtool's
RRA consolidation, BTrDB's per-node summaries, and OLAP roll-up. The
contribution here is the composition: one request plan across calendar levels
under a hard per-request bucket limit, with local coverage filling the gaps. It
is intended for sources that expose a read-only interval-aggregation endpoint;
it does not require writing to or reconfiguring the source. See
[`related-work.md`](related-work.md) for the full comparison and citations.

## 13. Version notes

**0.0.4** — documentation release. No algorithm semantics changed. Reworks the READMEs and adds diagrams.

**0.0.3** — archival release. No algorithm semantics changed. Bumps the
version for the Zenodo DOI archive.

**0.0.2** — documentation and public-disclosure release. No algorithm semantics
changed. Adds the prior-art review, the formal refinement/segment-count/
request-count propositions, the public disclosure document, citation metadata
and the technical article.

**0.0.1** — initial standalone release. Two correctness fixes relative to the
original AutoTestHub implementation:

1. Fetch runs are grouped by fetch level + contiguity. The original grouped by
   adjacency only, which broke multi-level queries.
2. Raw chunk bisection uses `[a, mid)` and `[mid, b)`. The original used
   `mid + 1`, which dropped a point exactly on the split boundary under an
   exclusive-end contract.
