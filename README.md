# Hybrid Recursive Ladder Algorithm

**Aggregate long time-series ranges with a handful of source requests instead of thousands of per-bucket queries.**

**Languages:** [English](README.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Português](README.pt-BR.md) · [Русский](README.ru.md) · [العربية](README.ar.md) · [हिन्दी](README.hi.md)

[Algorithm spec](docs/algorithm.md) · [API reference](docs/api.md) · [Benchmarks](docs/benchmarks.md) · [Related work](docs/related-work.md) · [Public disclosure](docs/defensive-publication.md)

[![CI](https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm/actions/workflows/ci.yml/badge.svg)](https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)
[![Version](https://img.shields.io/badge/version-0.0.2-green.svg)](CHANGELOG.md)
[![Website](https://img.shields.io/badge/website-live-5eead4.svg)](https://magicsquarekey.github.io/hybrid_recursive_ladder_algorithm/)

---

## The problem

Most time-series APIs charge you per request, per bucket, or per round trip. A
naive "one query per statistical bucket" implementation turns a two-day
minute-level query into 2,880 buckets, each needing up to four HTTP calls. In a
production ThingsBoard deployment this took **139 seconds** for 1,140 buckets.

The bottleneck is not arithmetic — it is the number of network round trips.

## The idea

Split `[start, end)` into **complete calendar units**, from month down to minute.
Peel complete months first; push the partial left/right edges to the next finer
level; repeat. Then fetch each level once using the *next finer* aggregation and
fold locally.

```
2026-01-01 00:00:00 → 2026-10-21 18:49:59

month   Jan … Sep                 9 segments
day     Oct 1 … Oct 20           20 segments
hour    Oct 21 00:00 … 17:00     18 segments
minute  Oct 21 18:00 … 18:48     49 segments
tail    Oct 21 18:49:00–18:49:59  1 segment
                                  ───────────
                                  97 segments
```

That is **97 segments instead of 423,049 minute buckets** — a ~4,360× reduction
in the number of things you ask the source about. A typical 10-month query needs
roughly **5–7 aggregation requests**, not thousands.

The name is literal: a *hybrid* of calendar recursion and a *ladder* that only
steps on complete bricks.

## Prior art and positioning

This is a **query-planning method** for deployments where you can read an
interval-aggregation endpoint but cannot write to or reconfigure the source. It
is not a new general-purpose aggregation algorithm. Calendar decomposition is a
mixed-radix instance of canonical interval decomposition; folding is a roll-up;
multi-resolution aggregation is the core of RRDtool, Whisper and BTrDB. What is
specific here is the combination: one request plan across calendar levels, each
level fetched once at the next finer aggregation, local coverage filling the
gaps, under a hard per-request bucket limit.

See [Related work and positioning](docs/related-work.md) for the closest systems
(BTrDB, RRDtool/Whisper, TimescaleDB hierarchical continuous aggregates, Druid
period granularity), the historical algorithms (segment trees, timing wheels,
calendar arithmetic, OLAP roll-up), and the defensible novelty statement. The
method is also published as a [public disclosure](docs/defensive-publication.md);
a [technical article](docs/articles/why-per-bucket-queries-are-slow.md) walks
through the production benchmark and the request-count argument.

## Install

> v0.0.2 is distributed through the GitHub release. PyPI publication is planned.

```bash
# v0.0.2 GitHub release wheel
pip install https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm/releases/download/v0.0.2/hybrid_recursive_ladder-0.0.2-py3-none-any.whl

# optional extras: clone and install
git clone https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm.git
cd hybrid_recursive_ladder_algorithm
```

Optional extras:

```bash
pip install -e ".[thingsboard]"   # ThingsBoard source (httpx)
pip install -e ".[postgres]"      # local store (psycopg 3)
pip install -e ".[api]"           # FastAPI HTTP API
pip install -e ".[mcp]"           # MCP server
pip install -e ".[all]"           # everything
```

The core decomposition has **zero third-party dependencies** (only `tzdata` for
reliable IANA time zones on Windows).

## 30-second demo

```bash
hybrid-ladder demo
```

This builds synthetic 15-minute data, decomposes a 120-day range, materializes
the first 60 days into an in-memory store, runs a local-first mixed query, and
verifies that the totals match. No database, no network, no configuration.

```text
decomposition: 6 segments (month=3, day=1, hour=1, minute=1)
source-only sum: grand_total=40,319.400 ...
mixed sum:       grand_total=40,319.400 ...
totals match: YES
verify: diff_series=0 diff_segments=0
```

Inspect a decomposition without any data:

```bash
hybrid-ladder decompose --start 2026-01-01 --end 2026-10-21T18:49:59
```

## Library

```python
from hybrid_ladder import LadderEngine, MemorySource

source = MemorySource()
source.add("device-1", "energy", [(ts, 1.0) for ts in range(0, 86_400_000, 60_000)])

engine = LadderEngine(source)
result = engine.sum([("device-1", "energy")], 0, 86_400_000)

print(result.grand_total)                 # 1440.0
print(result.rows[0].segments[0].label)   # 1970-01-01 00:00
print(result.rows[0].empty_count)         # 0
```

### With a local store (local-first reads)

```python
from hybrid_ladder import LadderEngine, MemoryStore
from hybrid_ladder.sources.thingsboard import ThingsBoardSource

source = ThingsBoardSource(
    "https://thingsboard.example.com",
    token="...",                    # or username=/password=
)
store = MemoryStore()               # or PostgresStore("postgresql://...")

engine = LadderEngine(source, store)

# 1. Pull raw points once (idempotent; coverage is recorded)
engine.materialize([("device-id", "energy")], start_ms, end_ms)

# 2. Repeated queries read local data and only fetch uncovered sub-ranges
result = engine.sum_mixed([("device-id", "energy")], start_ms, end_ms)
print(result.source, result.source_counts)   # "local" / "mixed" / "tb"
print(result.rows[0].tb_ranges)              # ranges still missing locally

# 3. Compare the source with the local copy, then repair if needed
report = engine.verify([("device-id", "energy")], start_ms, end_ms)
if report["diff_segments"]:
    engine.repair([("device-id", "energy")], start_ms, end_ms)
```

## Four ways to use it

| Form | Entry point | Best for |
|---|---|---|
| **Python library** | `from hybrid_ladder import ...` | embedding in a service or data pipeline |
| **CLI** | `hybrid-ladder ...` | ad-hoc inspection, scripts, cron |
| **HTTP API** | `hybrid-ladder serve` | language-agnostic integration, async tasks |
| **MCP server** | `hybrid-ladder mcp` | AI agents and MCP-compatible clients |
| **Agent skill** | [`skills/hybrid-recursive-ladder/SKILL.md`](skills/hybrid-recursive-ladder/SKILL.md) | Claude/ZCode-style skill installation |

### CLI

```bash
# Sum a series from the built-in demo data
hybrid-ladder sum --series demo-chiller-1:energy --start 2026-01-01 --end 2026-02-01

# ThingsBoard
export HL_TB_URL=https://tb.example.com
export HL_TB_TOKEN=...
export HL_PG_DSN='postgresql://user:pass@127.0.0.1:5432/telemetry'
hybrid-ladder sum --source thingsboard \
  --series 6f2c...:L_LSJ1_DB_EP \
  --start 2026-01-01 --end 2026-10-21T18:49:59 \
  --mode mixed --materialize

# Verify and repair the local copy
hybrid-ladder verify --source thingsboard --series ... --start ... --end ...
hybrid-ladder repair --source thingsboard --series ... --start ... --end ...
```

### HTTP API

```bash
hybrid-ladder serve --port 8000
# OpenAPI docs: http://127.0.0.1:8000/docs
```

```bash
# Decompose only (synchronous)
curl "http://127.0.0.1:8000/v1/decompose?start_ts=1767196800000&end_ts=1792512599000"

# Sum (asynchronous task)
curl -X POST http://127.0.0.1:8000/v1/ladder/sum \
  -H 'content-type: application/json' \
  -d '{"series":[{"entity":"demo-chiller-1","key":"energy"}],
       "start_ts":1767196800000,"end_ts":1777564800000,"mode":"tb"}'
# → {"code":0,"data":{"task_id":"...","async":true}}

curl http://127.0.0.1:8000/v1/tasks/<task_id>

# Synchronous variant for small queries
curl -X POST "http://127.0.0.1:8000/v1/ladder/sum?sync=true" ...
```

The API uses `{"code":0,"data":...}` on success and `{"code":1,"detail":...}`
on error, matching the original AutoTestHub contract. See
[`docs/api.md`](docs/api.md) for every endpoint.

### MCP server

```bash
pip install -e ".[mcp]"   # from the source checkout
hybrid-ladder mcp
```

Tools: `ladder_meta`, `ladder_decompose`, `ladder_sum`, `ladder_verify`.
Configuration uses the same `HL_*` environment variables as the HTTP API. With
no configuration it serves demo data, so an agent can try it immediately.

Example MCP client configuration:

```json
{
  "mcpServers": {
    "hybrid-ladder": {
      "command": "hybrid-ladder",
      "args": ["mcp"],
      "env": {
        "HL_SOURCE": "thingsboard",
        "HL_TB_URL": "https://tb.example.com",
        "HL_TB_TOKEN": "...",
        "HL_PG_DSN": "postgresql://..."
      }
    }
  }
}
```

### Skill

Copy [`skills/hybrid-recursive-ladder/`](skills/hybrid-recursive-ladder/) into
your agent's skills directory (for example `~/.claude/skills/` or
`~/.zcode/skills/`); see [`skills/README.md`](skills/README.md) for snippets.
The skill teaches the agent when to reach for the ladder,
how to call the CLI/API, and how to interpret `null` vs `0.0` and `source`.

## Rules (non-negotiable)

1. **Left-closed, right-open** — `[start, end)`. If `end` is exactly on an hour
   boundary, that hour does not exist in the result.
2. **Complete units only** — a month/day/hour/minute is emitted at its level
   only when it lies entirely inside the range.
3. **Recursive edges** — a partial left or right edge is pushed to the next
   finer level. A sub-minute remainder becomes its own tail segment.
4. **Local calendar** — boundaries use the configured IANA timezone (default
   `Asia/Shanghai`). Month = first day 00:00, day = 00:00, hour = :00,
   minute = :00.
5. **Tiling invariant** — segments are ordered, contiguous, non-overlapping,
   and their union is exactly `[start, end)`.

### Value semantics

| Value | Meaning | Render as |
|---|---|---|
| `null` | no samples in the segment | `—` |
| `0.0` | samples exist and sum to zero | `0` |
| number | sum of the samples | the number |

Every segment carries `cnt` (observed points/buckets), `expected` (buckets the
segment should contain, for source segments) and `source` (`local`, `tb`,
`mixed`, `empty`, `uncovered`). A low `cnt` relative to `expected` means the
data is sparse — the sum is still arithmetically correct, just based on fewer
points.

## Adapters

The engine depends on two tiny structural interfaces
([`protocols.py`](src/hybrid_ladder/protocols.py)):

```python
class TimeSeriesSource(Protocol):
    def interval_agg(ref, start_ms, end_ms, bucket_ms, agg="SUM") -> Mapping[int, Any]: ...
    def raw_series(ref, start_ms, end_ms, limit=10_000) -> list[tuple[int, Any]]: ...

class PointStore(Protocol):
    def sum_ranges(ref, ranges) -> Mapping[int, tuple[float | None, int]]: ...
    def series(ref, start_ms, end_ms, max_points=5_000) -> list[Mapping]: ...
    def coverage(ref) -> list[tuple[int, int, int]]: ...
    def delete_range(ref, start_ms, end_ms) -> int: ...
    def clear_coverage(ref, start_ms, end_ms) -> int: ...
    def upsert_points(ref, points, at_ms=None) -> int: ...
    def mark_covered(ref, start_ms, end_ms, point_cnt, at_ms) -> None: ...
```

Built-in adapters:

* **`MemorySource` / `MemoryStore`** — tests, demos, small embedded workloads.
* **`ThingsBoardSource`** — REST telemetry, with all TB quirks handled.
* **`PostgresStore`** — monthly-partitioned `readings` + `coverage` tables,
  idempotent upserts, batched range sums.

Anything else (InfluxDB, Prometheus, ClickHouse, TimescaleDB) only needs those
methods. See [`docs/architecture.md`](docs/architecture.md).

## How local-first reads work

```text
for each segment:
    split [segment] by materialized coverage
    covered part      → one batched local SQL sum
    uncovered part    → source (grouped aggregation for whole segments,
                        adaptive-bucket sum for partial segments)
    segment value     = local part + source part
    segment source    = local | tb | mixed | empty
```

Coverage is only recorded up to `now - 5 minutes`; the in-flight tail is never
treated as trustworthy local data. A range is marked covered even when the
source returned zero points ("we asked, there is nothing"), so the next query
does not hit the source again. Before rewriting a range, its coverage is
cleared first — a failed materialize can never leave stale coverage pointing at
incomplete data.

## Verification and repair

* **Verify** compares the source (authority) with the local store segment by
  segment. Only differing segments are drilled down to individual points, with
  `added` / `removed` / `changed` counts (capped by `drill_limit`).
* **Repair** deletes the local range and re-pulls it from the source in
  transaction-sized windows (366 days by default), then re-marks coverage.

## Guarantees

* `sum` is **exact** — the sum of all segments equals the sum of the source's
  points in the range. No approximation, no sampling.
* Overlapping materialize runs are **idempotent** — the store primary key makes
  a timestamp appear once.
* Empty segments are **not silently counted as zero** — `total` excludes them
  and `empty_count` reports them.
* The algorithm only reads from the source. It never writes to ThingsBoard.

## Known limitations

* **Sum only in v0.0.2.** Average needs `sum` + `count` weighting; meter-delta
  needs the first value of every segment (ThingsBoard has no `FIRST`
  aggregation), so those rules are not on the ladder yet.
* **Data completeness ≠ arithmetic correctness.** If the source has missing
  samples, the total is the sum of the points that exist and will be lower than
  the "true" physical total. Use `cnt`/`expected` to detect sparse data.
* **ThingsBoard limits:** interval aggregation accepts ~700 buckets and rejects
  800 (the docs' 1000 is wrong); the adapter defaults to 500. Raw series are
  capped at 10,000 points per request. `COUNT` collapses duplicate points in the
  same minute; use raw points for an exact count.
* **In-process tasks** are lost on restart. Results can always be recomputed;
  materialized data is not lost.
* **DST time zones** are supported for calendar boundaries, but fixed-size
  source buckets mean day/hour folds are designed for fixed-offset zones such as
  `Asia/Shanghai`. Use `hour` or `minute` fetching in DST zones if you need
  second-level certainty around transitions.
* **The v0.0.1 fix:** the original implementation grouped contiguous segments
  without checking their level, which could fetch a multi-level range at the
  coarsest level and mis-assign hour/minute values. This package groups by
  *fetch level + contiguity* and includes a regression test
  (`tests/test_engine.py::test_multilevel_query_is_exact`).

## Measured performance

From a production ThingsBoard deployment (numbers vary by network and data
density):

| Query | Segments | Source requests | Time | Result |
|---|---:|---:|---:|---|
| 2 days, minute level | 69 | ~4 | 0.64 s | 2,217,024.0 (matches 2,566 raw points) |
| 1 year, day level | 42 | ~4 | 1.18 s cold / 0.20 s warm | 36,012,018.25 |
| 10 months, mixed levels | 97 | ~5–7 | sub-second | 423,049 minute buckets avoided |
| Local read, 42–90 segments | — | 0 | 9–19 ms | one SQL statement |
| Mixed read (3 local + 1 source) | 4 | 1 | 0.31 s | equals source-only |

See [`docs/benchmarks.md`](docs/benchmarks.md) for methodology and caveats.

## Project layout

```
src/hybrid_ladder/
  core.py          pure decomposition, folding, coverage splitting
  engine.py        source/mixed/local reads, materialize, verify, repair
  models.py        Segment, SeriesRef, LadderConfig, QueryResult
  protocols.py     TimeSeriesSource / PointStore
  sources/         memory.py, thingsboard.py
  stores/          memory.py, postgres.py
  api.py           FastAPI app
  cli.py           hybrid-ladder CLI
  mcp_server.py    MCP tools
  tasks.py         in-process task registry
  demo.py          deterministic demo data
tests/             unit + API + adapter tests
docs/              algorithm, architecture, API, benchmarks
skills/            agent skill package
examples/          runnable examples
```

## Development

```bash
git clone https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm.git
cd hybrid_recursive_ladder_algorithm
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
ruff check .
pytest
```

Optional PostgreSQL integration test:

```bash
export HL_TEST_PG_DSN='postgresql://user:pass@127.0.0.1:5432/testdb'
pytest -m integration
```

## Roadmap

* `avg` and `meter_delta` rules on the ladder (weighted sum + per-segment first
  value)
* InfluxDB / Prometheus / ClickHouse source adapters
* Celery/RQ task backend for multi-process deployments
* OpenTelemetry metrics and structured request accounting
* PyPI trusted publishing on tag

## Citation

If you use this project, cite the software:

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

The method is also published as a [public disclosure](docs/defensive-publication.md)
and as prior art. [`CITATION.cff`](CITATION.cff) provides the same metadata for
GitHub's "Cite this repository" button. A DOI will be added when the repository
is archived on Zenodo.

## License

[MIT](LICENSE) © 2026 MagicSquarekey
