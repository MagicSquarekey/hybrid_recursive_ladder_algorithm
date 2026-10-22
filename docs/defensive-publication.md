# Hybrid Recursive Ladder: public disclosure

**Author:** MagicSquarekey  
**Date:** 2026-10-22  
**Version:** 0.0.2  
**License:** MIT  
**Repository:** <https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm>

## Purpose

This document publishes the Hybrid Recursive Ladder method and its formal
properties as prior art. The author does not intend to seek patent protection
for the method. The disclosure is intended to be enabling: it is accompanied by
a normative algorithm specification, a complete open-source implementation, a
test suite and a reproducible benchmark in the same public repository.

This is a technical disclosure, not a patent application. It does not grant
patent rights and does not replace legal advice. Its purpose is to place the
method in the public record so that the specific combination described here is
available as prior art.

## Abstract

Long-range time-series queries are often limited by the number of requests, not
by arithmetic. Many APIs cap the number of buckets or points returned per
request. A client that queries one statistical bucket at a time therefore pays
one network round trip per output unit. The Hybrid Recursive Ladder is a
query-planning method that decomposes a range into complete calendar units
(month, day, hour, minute), fetches each maximal contiguous run of units sharing
a fetch level once at the next finer aggregation, and folds the returned buckets
into the output units locally. Optional coverage tracking splits the range
against already materialized data and fetches only the missing sub-ranges. The
method is intended for read-only interval-aggregation endpoints with a hard
per-request bucket limit. It is a composition of known techniques—calendar
mixed-radix decomposition, canonical interval decomposition, roll-up and
multi-resolution aggregation—not a new general theory of time-series
aggregation.

## 1. Problem

Consider a range `[s, e)` and an API that returns interval aggregates with at
most `K` buckets per request. A per-bucket client issues roughly one request per
output unit, plus boundary requests. For a two-day minute-level range, that is
2,880 buckets; in a measured ThingsBoard deployment, 1,140 buckets took 139
seconds over a VPN.

The bottleneck is the number of network round trips. Pre-aggregation and
single-granularity downsampling are common fixes, but they either require write
access to the source or sacrifice the output granularity.

## 2. Method

### 2.1 Calendar decomposition

Split `[s, e)` into segments of complete calendar units, from month down to the
configured finest level (default: minute):

1. At each level, emit only units fully contained in the range.
2. Push the partial left edge and the partial right edge to the next finer
   level.
3. At the finest level, emit a sub-unit remainder as its own "tail".

```
ladder(a, b, level):
    if a >= b: return []
    if level is finest: emit(a, b); return

    if unit_start(a, level) != a:
        nb = next_boundary(a, level)
        if nb >= b: ladder(a, b, next_level); return
        ladder(a, nb, next_level)
        a = nb

    while next_boundary(a, level) <= b:
        nb = next_boundary(a, level)
        emit(a, nb, level)
        a = nb

    if a < b: ladder(a, b, next_level)
```

The decomposition has three useful properties:

* segments are ordered, contiguous, non-overlapping and tile the range exactly;
* every segment at a level coarser than the finest is a complete calendar unit;
* at the finest level, at most two segments are partial (the left edge and the
  tail).

The number of segments is bounded by the coarsest complete units plus a
constant. For the default hierarchy, `N <= N_month + 639`, where the constant is
a conservative bound on the two partial months, the partial days and the partial
hours. Recursion depth is at most the number of levels (4 by default).

### 2.2 Fetch plan

The output level determines the output granularity, not the fetch granularity.
For each output level, fetch the next finer aggregation once over a contiguous
run and fold locally:

| Output level | Fetch level |
|---|---|
| month | day |
| day | hour |
| hour | minute |
| minute | minute |
| sub-minute tail | raw points |

Fetch runs are grouped by **fetch level + time contiguity**, never by time
contiguity alone. Hours and minutes can share one minute-level fetch; months and
days cannot share a fetch. Grouping only by adjacency caused a multi-level range
to be fetched at the coarsest level, assigning a whole day's value to the first
hour and losing the rest.

For a run of duration `T` at fetch bucket size `Δ`, the adapter chunks the run
into windows of `K * Δ` and issues

```
r(run) = ceil(T / (K * Δ))
```

requests. The total aggregation request count is the sum over runs. In the
common contiguous case there are at most three aggregation runs (day, hour,
minute), so the sum has at most three terms. Since the number of day buckets for
month output grows with the number of complete months, while the hour and minute
buckets are confined to the two partial months and the partial days at their
edges:

```
R_agg = O(N_month / K + 1).
```

The request count grows with the coarse units divided by the cap, not with the
number of minute buckets. Raw-point fetches for the sub-minute tail are
data-dependent and cost `O(P / max_points)` requests for `P` points.

### 2.3 Local-first coverage

When a local point store is available, each output segment is split against the
merged coverage ranges into covered and uncovered sub-ranges:

1. Sum covered sub-ranges with one batched local query.
2. Fetch fully uncovered segments with grouped aggregation.
3. For partially covered segments, fetch only the missing sub-ranges.
4. Segment value = local part + source part.

Coverage is recorded only up to `now - grace`; the in-flight tail is never
treated as trustworthy local data. Coverage is invalidated before a rewriting
request, so a failed pull is re-fetched rather than trusted.

### 2.4 Fold correctness

`fold_sum` attributes a fetch bucket to the output segment containing the
bucket's start. If every fetch bucket is wholly contained in one output segment
or disjoint from it, the folded sum equals the source's sum over the segment.
Fixed-offset time zones satisfy this because every calendar unit is a union of
fixed-size buckets. In DST zones a day or hour boundary can fall inside a
fixed-size bucket; use a finer fetch level or raw points around transitions.

## 3. Formal properties

The normative specification is [`algorithm.md`](algorithm.md). It contains:

* **Lemma 1 (two-edge lemma):** the parts of a range passed to a finer level lie
  inside at most two units of the current level; every complete unit is emitted
  at its own level.
* **Proposition 2 (bounded refinement):** `N_day <= 62`, `N_hour <= 96`,
  `N_minute <= 480`, `tail <= 1`, hence `N <= N_month + 639` for the default
  hierarchy.
* **Corollary 3:** total segments are `N_month + O(1)`.
* **Proposition 4:** recursion depth is at most the number of levels.
* **Section 5.4:** the exact per-run request model and
  `R_agg = O(N_month / K + 1)`.
* **Section 5.5:** the fold-correctness alignment condition.

## 4. Prior art and differences

The method is a composition of known ideas. The closest systems and algorithms
are documented in [`related-work.md`](related-work.md), with references. In
summary:

| Prior art | Overlap | Difference |
|---|---|---|
| RRDtool, Whisper | Multi-resolution archives; coarse values from fine values | Storage-side; fixed step; no calendar hierarchy; no request planning |
| BTrDB | Aligned time partitions and hierarchical summaries | Database engine; power-of-two alignment; not an external API planner |
| TimescaleDB hierarchical continuous aggregates | Minute → hour → day roll-up | Precomputed materialized views; no hard per-request bucket cap |
| Apache Druid period granularity | Calendar-aligned buckets with time zones | One granularity per query; ingestion-time rollup |
| Prometheus / Grafana | Point caps and single-step downsampling | One uniform interval; no multi-level plan |
| Segment tree | Canonical aligned interval decomposition | Merges siblings for one aggregate; the ladder needs one value per output unit |
| Hierarchical timing wheels | Level + remainder cascade | Timer scheduling, not aggregation |

The specific combination published here is:

1. treating the calendar hierarchy as the query plan, not only as the display
   bucket;
2. emitting only complete calendar units and pushing partial edges to finer
   levels;
3. fetching each maximal run sharing a fetch level once at the next finer
   aggregation and folding locally;
4. grouping runs by fetch level + contiguity so requests are shared across
   output levels;
5. splitting against local coverage and fetching only uncovered sub-ranges;
6. planning the request count under a hard per-request bucket limit.

## 5. What is not claimed

This disclosure does not claim:

* a new time-series database, storage engine or compression format;
* a new index structure;
* a new calendar-arithmetic library;
* the first multi-resolution aggregation system;
* any patent rights.

It publishes a query-planning composition and an open-source implementation
under the MIT License.

## 6. Citation

```bibtex
@software{hybrid_recursive_ladder_2026,
  author  = {MagicSquarekey},
  title   = {Hybrid Recursive Ladder: Query Planning for Bucket-Limited Time-Series APIs},
  year    = {2026},
  version = {0.0.2},
  license = {MIT},
  url     = {https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm}
}
```

A DOI will be added when the repository is archived on Zenodo. The
[`CITATION.cff`](../CITATION.cff) file provides the same metadata in Citation
File Format; GitHub's "Cite this repository" button reads it.

## 7. Integrity and status

This document is part of the `v0.0.2` release. The normative implementation at
that tag is the Python package in `src/hybrid_ladder/`; the normative algorithm
specification is [`algorithm.md`](algorithm.md), with a Chinese mirror at
[`algorithm.zh-CN.md`](algorithm.zh-CN.md). The public repository history and
the GitHub release provide the disclosure date.
