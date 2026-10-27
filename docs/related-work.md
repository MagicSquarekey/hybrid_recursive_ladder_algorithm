# Related work and positioning

**语言 / Languages:** [English](related-work.md) · [简体中文](related-work.zh-CN.md)

> **Positioning.** The Hybrid Recursive Ladder is a **query-planning method for
> bucket-limited time-series APIs**, not a new general theory of aggregation.
> It is aimed at deployments where you can read an interval-aggregation endpoint
> but cannot write to or reconfigure the source. Its decomposition is a calendar
> mixed-radix instance of canonical interval decomposition; its fold is a
> roll-up; multi-resolution aggregation is the core of RRDtool, Whisper and
> BTrDB. The contribution is the composition: one request plan across calendar
> levels, each level fetched once at the next finer aggregation, local coverage
> filling the gaps, under a hard per-request bucket limit.

This document records the closest systems and historical algorithms we found.
It is meant to be cited from the README and the algorithm spec, and to make the
boundary of the contribution explicit.

## 1. Why the problem is real

Most time-series APIs cap the number of buckets or points per request.
Prometheus rejects a range query that would return more than 11,000 points per
series (`web/api/v1/api.go`); the measured ThingsBoard deployment used for this
project accepts ~700 buckets and rejects 800. A client that issues one query per
statistical bucket therefore pays one round trip per output unit.

The ladder keeps the output granularity (month, day, hour, minute) while making
the number of source requests depend on the range's coarse units, not on the
number of fine buckets.

## 2. Closest systems

| System | Mechanism | Overlap | Difference |
|---|---|---|---|
| [RRDtool](https://github.com/oetiker/rrdtool-1.x) | Round-robin archives (RRAs) at several resolutions; consolidation functions `AVERAGE`, `MIN`, `MAX`, `LAST` compute coarse points from fine PDPs. | Multi-resolution storage; coarse values derived from fine values. | Storage-side; fixed `step`; no calendar hierarchy; no per-request planning. |
| [Whisper](https://github.com/graphite-project/whisper) | Archive tiers with decreasing precision; higher-resolution data degrades into lower-resolution archives. | Same multi-resolution archive idea as RRDtool. | Storage-side; fixed archive definitions; no query decomposition. |
| [BTrDB](https://github.com/BTrDB/btrdb-server) | Time-partitioned, version-annotated copy-on-write tree; each node stores min/max/mean/count for its time slot; slots are power-of-two aligned. | Aligned time partitions, hierarchical summaries, multi-resolution queries. | A database engine that maintains summaries at write time; power-of-two alignment, not calendar units; not a planner for an external API. |
| [TimescaleDB hierarchical continuous aggregates](https://github.com/timescale/docs/blob/latest/use-timescale/continuous-aggregates/hierarchical-continuous-aggregates.md) | Continuous aggregates on top of continuous aggregates; minute-level data summarized into hourly and daily views. | Calendar time buckets; hierarchical roll-up; a query can hit a coarser level. | Precomputed materialized views; schema-bound; no hard per-request bucket cap; not on-demand for arbitrary unplanned ranges. |
| [Apache Druid](https://druid.apache.org/docs/latest/querying/granularities/) | Ingestion-time rollup; `PeriodGranularity` supports ISO8601 periods such as `P1M` and `P2D` with timezone-aware calendar boundaries. | Calendar-aligned buckets; rollup. | One query granularity per request; rollup at ingestion; no multi-level request plan. |
| [`timescaledb-rollups`](https://github.com/lballoriani/timescaledb-rollups) | SQL pipeline with minute → hour → day → week → month continuous aggregates and per-level retention; queries hit the coarsest level that can answer them. | Closest project shape: hierarchical calendar roll-up. | Storage-side pipeline; requires control of the database; no external API, no bucket cap, no coverage-aware gap filling. |
| [`accreta`](https://github.com/StoyanTc/accreta) | `Monoid`/`Aggregator` traits for mergeable state; hierarchical time-series rollups with language bindings. | Mergeable aggregation across levels. | An aggregation library, not a query planner. |
| [`quantum`](https://github.com/marqeta/quantum) | Precomputes aggregates for time windows in Redis; queries return in O(1). | Avoids per-bucket queries. | Precompute + cache; not on-demand; no calendar hierarchy. |
| [`brein-time-utilities`](https://github.com/Breinify/brein-time-utilities), [`ankane/rollup`](https://github.com/ankane/rollup) | `BucketTimeSeries`/`IntervalTree`; Rails rollup tables. | Time buckets and rollups. | Library or storage-side; fixed granularity; no request planning. |

We also checked the ThingsBoard ecosystem. The public projects we found are
export/download tools ([`thingsboard-export`](https://github.com/DPIclimate/thingsboard-export),
[`tb-download`](https://github.com/fargiolas/tb-download)); they paginate or
download, but do not plan a multi-level aggregation.

## 3. Historical algorithms

### 3.1 Canonical interval decomposition

A segment tree (Bentley, 1977) answers a range aggregate by covering `[l, r)`
with O(log n) aligned nodes. Fenwick trees (Fenwick, 1994) and sparse tables use
the same aligned-block idea. The ladder is the calendar mixed-radix analogue.

The difference is the objective. A segment tree merges siblings because the
answer is one aggregate. The ladder must return one value per output unit, so it
cannot merge siblings across levels; it emits every complete unit and uses the
hierarchy to plan fetches. If only a grand total were required, a merged
canonical cover would be possible and would use fewer blocks.

### 3.2 Calendar mixed-radix arithmetic

The recursion is a greedy expansion in a mixed-radix system: months, days,
hours, minutes. The same "peel complete units, push the remainder down" pattern
appears in calendar arithmetic libraries (`dateutil.relativedelta`, Java
`Period`, Rust `jiff` spans) and in temporal-database work on time granularity
(Jensen et al., 1992/1994). The decomposition itself is not novel.

### 3.3 Multi-resolution aggregation

RRDtool (Oetiker, 1999) stores multiple RRAs and consolidates fine PDPs into
coarse CDPs. Whisper uses archive tiers. BTrDB (FAST'16) stores per-node
summaries in a time-partitioned tree. OLAP data cubes (Harinarayan, Rajaraman
and Ullman, 1996) precompute roll-ups along dimension hierarchies. Mallat's
multiresolution analysis (1989) formalizes coarse-from-fine decomposition in
signal processing. The ladder uses the same direction but exact calendar units,
not wavelets or power-of-two scales.

### 3.4 Hierarchical time structures

Hierarchical timing wheels (Varghese and Lauck, 1987/1997) divide timeouts into
levels and cascade from a coarse level to a finer one. Calendar queues (Brown,
1988) use calendar-like buckets for event simulation. Structurally these are
the closest "level + remainder" algorithms, but their purpose is scheduling,
not aggregation.

### 3.5 Query-side single-granularity downsampling

Prometheus `query_range` has a hard 11,000-points-per-series limit and a single
`step`. Grafana computes one interval from `maxDataPoints` and the range.
Druid's period granularity and TimescaleDB's `time_bucket` choose one calendar
granularity per query. The ladder differs by planning multiple granularities in
one query and decoupling output granularity from fetch granularity.

## 4. What is new, and what is not

**Not new:**

* calendar decomposition and mixed-radix expansion;
* canonical aligned interval decomposition;
* roll-up / consolidation;
* multi-resolution storage and querying;
* calendar-aligned buckets;
* local caching and materialized views.

**New as a composition:**

* treating the calendar hierarchy as the query plan, not only as the display
  bucket;
* fetching each level once at the next finer aggregation and folding locally;
* grouping runs by fetch level + contiguity so requests are shared across
  output levels;
* splitting against local coverage and fetching only the uncovered sub-ranges;
* making the request count a function of the coarse units and the source's
  bucket cap, with the bounds in `docs/algorithm.md` §5.3–5.5.

## 5. Defensible novelty statement

> A query-planning method for range aggregation over bucket-limited time-series
> APIs: decompose the range into complete calendar units, fetch each maximal
> contiguous run sharing a fetch level once at the next finer aggregation, and
> fold locally, so the number of source requests is decoupled from the number of
> output units and bounded by the source's per-request bucket limit.

Use this phrasing in a paper or a patent disclosure. Avoid "a new algorithm for
time-series aggregation" or "the first ..."; both are easy to challenge with
RRDtool, BTrDB, TimescaleDB or segment-tree prior art.

## 6. Related-work paragraph (copy-paste)

> Range aggregation over time-series APIs is usually addressed either by
> pre-aggregation or by single-granularity downsampling. Multi-resolution stores
> maintain coarser tiers or per-node summaries and answer a query at a chosen
> resolution (RRDtool; Whisper; BTrDB). OLAP-style systems precompute
> hierarchical roll-ups, including TimescaleDB's hierarchical continuous
> aggregates and Druid's ingestion-time rollup with calendar-aware period
> granularities. Query-side systems instead choose one uniform step under a
> point cap, as in Prometheus's 11,000-point limit and Grafana's `maxDataPoints`
> interval calculation. The Hybrid Recursive Ladder plans a single query across
> multiple calendar levels: it partitions the range into complete calendar
> units, fetches each maximal contiguous run sharing a fetch level once at the
> next finer aggregation, and folds the returned buckets locally. This decouples
> the number of source requests from the number of output units and bounds it by
> the source's per-request bucket limit. Its decomposition is the calendar
> mixed-radix analogue of the canonical interval decomposition used by segment
> trees, with partial edges pushed to finer levels.

## 7. References

1. RRDtool — <https://github.com/oetiker/rrdtool-1.x>; RRA definition in
   `doc/rrdcreate.pod`.
2. Whisper — <https://github.com/graphite-project/whisper>.
3. M. P. Andersen and D. E. Culler, "BTrDB: Optimizing Storage System Design
   for Timeseries Processing," USENIX FAST 2016 —
   <https://www.usenix.org/conference/fast16/technical-sessions/presentation/andersen>.
4. TimescaleDB, "Hierarchical continuous aggregates" —
   <https://github.com/timescale/docs/blob/latest/use-timescale/continuous-aggregates/hierarchical-continuous-aggregates.md>.
5. Apache Druid, "Granularities" —
   <https://druid.apache.org/docs/latest/querying/granularities/>.
6. Prometheus, `query_range` point limit —
   <https://github.com/prometheus/prometheus/blob/main/web/api/v1/api.go#L1102>.
7. Grafana, `calculateInterval` —
   <https://github.com/grafana/grafana/blob/main/packages/grafana-data/src/datetime/rangeutil.ts#L592>.
8. J. L. Bentley, "Solutions to Klee's rectangle problems," 1977 (segment tree);
   overview: <https://en.wikipedia.org/wiki/Segment_tree>.
9. P. M. Fenwick, "A new data structure for cumulative frequency tables,"
   *Software: Practice and Experience*, 1994 —
   <https://doi.org/10.1002/spe.4380240306>.
10. G. Varghese and A. Lauck, "Hashed and hierarchical timing wheels," IEEE/ACM
    Transactions on Networking, 1997 — <https://doi.org/10.1109/90.650142>.
11. R. Brown, "Calendar queues: a fast O(1) priority queue implementation for
    the simulation event set problem," *Communications of the ACM*, 1988 —
    <https://doi.org/10.1145/63039.63045>.
12. V. Harinarayan, A. Rajaraman and J. D. Ullman, "Implementing data cubes
    efficiently," ACM SIGMOD 1996 — <https://doi.org/10.1145/235968.233333>.
13. S. Mallat, "A theory for multiresolution signal decomposition: the wavelet
    representation," *IEEE TPAMI*, 1989 — <https://doi.org/10.1109/34.192463>.
14. C. S. Jensen et al., "A consensus glossary of temporal database concepts,"
    ACM SIGMOD Record, 1994 — <https://doi.org/10.1145/181550.181560>.

## 8. Search scope and limitations

* GitHub was searched at the repository level. Unauthenticated GitHub code
  search was unavailable, so implementations inside larger repositories may be
  missing.
* arXiv, Crossref and the raw documentation of the projects above were
  searched. Wikipedia, general web search and Chinese blog platforms were not
  reachable from the environment used for this review.
* Patent databases (Google Patents, Espacenet, USPTO, CNIPA) and CNKI were not
  searched. Absence of a hit in this document is not proof of novelty.
* The review date is 2026-10-22. Star counts and documentation change; links
  were checked at that date.

For a repeatable search plan aimed at a paper, a patent or a freedom-to-operate
review, see [`prior-art-search.zh-CN.md`](prior-art-search.zh-CN.md).
