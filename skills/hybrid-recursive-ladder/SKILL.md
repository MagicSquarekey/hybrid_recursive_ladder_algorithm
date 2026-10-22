---
name: hybrid-recursive-ladder
description: Use when a task needs to aggregate long time-series ranges with few source requests — decompose a range into month/day/hour/minute ladder segments, sum from ThingsBoard or PostgreSQL, reduce thousands of per-bucket queries to a handful of requests, do local-first mixed reads, materialize raw points, or verify/repair a local telemetry copy. Triggers include 混合递归阶梯, 阶梯算法, long-range sum, 长区间求和, 请求数压缩, 本地固化, 校验/修复.
---

# Hybrid Recursive Ladder

## What it does

Splits `[start, end)` into **complete calendar units** (month → day → hour →
minute), peels complete units at each level, and recursively pushes partial
edges to the next finer level. It then fetches each level once using the next
finer aggregation and folds locally. A 10-month range becomes ~97 segments and
~5–7 source requests instead of 423,049 per-minute buckets.

The package also provides a local-first read path: materialize raw points into
PostgreSQL (or memory), read covered sub-ranges locally, and only fetch the
missing slices from the source. Verification and repair compare the source
(authority) with the local copy.

## When to use it

Use it when **all** of these are true:

* The data is a time series with a source that supports interval aggregation
  and raw point reads (ThingsBoard, or a custom `TimeSeriesSource`).
* You need a **sum** over a long range (hours to years).
* Request count, latency, or offline reads matter.

Do **not** use it for:

* Average or meter-delta rules in v0.0.1 (average needs weighted sum+count;
  meter-delta needs the first value of every segment).
* Non-additive metrics or event streams.
* Sources without interval aggregation — implement the two-method protocol
  first.

## Install

```bash
# v0.0.1 GitHub release wheel
pip install https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm/releases/download/v0.0.1/hybrid_recursive_ladder-0.0.1-py3-none-any.whl

# optional extras: clone and install
git clone https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm.git
cd hybrid_recursive_ladder_algorithm
pip install -e ".[thingsboard,postgres,api,mcp]"
```

## Fast path (no configuration)

```bash
hybrid-ladder demo          # end-to-end: decompose → materialize → mixed read → verify
hybrid-ladder decompose --start 2026-01-01 --end 2026-10-21T18:49:59
```

## Typical task workflow

1. **Inspect the decomposition** (cheap, no data access):

   ```bash
   hybrid-ladder decompose --start <start> --end <end> --finest minute
   ```

   Expect months + days + hours + minutes + one tail. If the count is huge,
   the range is long or `finest` is too fine.

2. **Sum from the source**:

   ```bash
   export HL_TB_URL=https://tb.example.com
   export HL_TB_TOKEN=...
   hybrid-ladder sum --source thingsboard \
     --series <device_id>:<key> \
     --start <start> --end <end> --json
   ```

3. **Enable local-first reads** (optional but recommended for repeated queries):

   ```bash
   export HL_PG_DSN='postgresql://user:pass@127.0.0.1:5432/telemetry'
   hybrid-ladder sum --source thingsboard --series ... --start ... --end ... \
     --mode mixed --materialize
   ```

4. **Verify** the local copy, then repair if needed:

   ```bash
   hybrid-ladder verify --source thingsboard --series ... --start ... --end ...
   hybrid-ladder repair --source thingsboard --series ... --start ... --end ...
   ```

## Python API

```python
from hybrid_ladder import LadderEngine
from hybrid_ladder.sources.thingsboard import ThingsBoardSource
from hybrid_ladder.stores.postgres import PostgresStore

source = ThingsBoardSource("https://tb.example.com", token="...")
store = PostgresStore("postgresql://user:pass@127.0.0.1:5432/telemetry")
engine = LadderEngine(source, store)

result = engine.sum_mixed([("<device_id>", "<key>")], start_ms, end_ms)
print(result.grand_total)
print(result.source, result.source_counts)
print(result.rows[0].tb_ranges)   # ranges still missing locally
```

Key methods: `decompose`, `sum`, `sum_local`, `sum_mixed`, `materialize`,
`verify`, `repair`. Every long method accepts `progress(done, total, message)`
and `cancel() -> bool`.

## HTTP API / MCP

```bash
hybrid-ladder serve --port 8000     # OpenAPI at /docs
hybrid-ladder mcp                   # stdio MCP server
```

HTTP endpoints:

* `GET /v1/decompose?start_ts=&end_ts=&finest=`
* `POST /v1/ladder/sum` (async task) and `POST /v1/ladder/sum?sync=true`
* `POST /v1/ladder/verify`, `/repair`, `/materialize`
* `GET /v1/tasks/{id}`, `POST /v1/tasks/{id}/cancel`

Success envelope: `{"code":0,"data":...}`; errors: `{"code":1,"detail":...}`.

MCP tools: `ladder_meta`, `ladder_decompose`, `ladder_sum`, `ladder_verify`.

## Output semantics (important)

| Field | Meaning |
|---|---|
| `value: null` | no samples in the segment — render as `—`, **not** `0` |
| `value: 0.0` | samples exist and sum to zero — render as `0` |
| `cnt` | observed points (source) or buckets (local) |
| `expected` | buckets the segment should contain (source segments only) |
| `source` | `local`, `tb`, `mixed`, `empty`, `uncovered` |
| `tb_ranges` | merged ranges still missing locally (feed to materialize) |
| `total` | sum of non-empty segment values; empty segments are excluded |
| `empty_count` | number of segments with no data |

A low `cnt` relative to `expected` means sparse data. The sum is still correct
for the points that exist; it is not an estimate of missing data.

## Non-negotiable rules

* `[start, end)` — left-closed, right-open. An end on an exact boundary does
  not create a segment for that boundary.
* Only complete units are emitted at a level; partial edges recurse downward.
* A sub-minute remainder is its own tail segment, read from raw points.
* Boundaries use the configured IANA timezone (default `Asia/Shanghai`).

## ThingsBoard pitfalls (already handled by the adapter)

* Interval aggregation accepts ~700 buckets, rejects 800 — the default is 500.
* Bucket timestamps are `bucket_start + bucket_ms / 2`; the adapter converts
  them back to bucket starts.
* No `FIRST` aggregation — first-value rules require raw points.
* `COUNT` collapses duplicate points within a minute — use raw points for an
  exact count.
* `endTs` is inclusive; the adapter filters raw points to `[start, end)`.

## Verification checklist

* `sum` of segments equals the source's raw-point sum for the same range.
* `empty_count` matches segments with no samples; zero-valued segments are not
  counted as empty.
* Repeated materialize is idempotent (same timestamps do not duplicate).
* `verify` reports 0 differences after a clean materialize.
* Tampering with one local point is detected and can be repaired.
* Coverage never includes the in-flight tail (5-minute grace by default).

## Reference

* Algorithm: `docs/algorithm.md`
* Architecture and adapter protocol: `docs/architecture.md`
* API: `docs/api.md`
* Benchmarks: `docs/benchmarks.md`
