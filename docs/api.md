# API reference

**语言 / Languages:** [English](api.md) · [简体中文](api.zh-CN.md)

The package exposes the same engine through four interfaces: Python, CLI, HTTP
and MCP.

## Python

```python
from hybrid_ladder import LadderEngine, LadderConfig
```

### `LadderEngine(source, store=None, config=None, *, clock=None)`

| Method | Purpose |
|---|---|
| `decompose(start_ms, end_ms, finest=None)` | Ladder segments |
| `sum(refs, start_ms, end_ms, *, finest=None, progress=None, cancel=None)` | Source-only sum |
| `sum_local(refs, ...)` | Local store only (offline) |
| `sum_mixed(refs, ...)` | Local-first mixed read |
| `materialize(refs, start_ms, end_ms, ...)` | Pull raw points for whole ranges |
| `materialize_ranges(items, ...)` | Pull explicit per-series ranges |
| `verify(refs, ..., drill_limit=50)` | Source vs local comparison |
| `repair(refs, ...)` | Replace local range with source data |

`refs` accepts `SeriesRef`, `(entity, key)` tuples, `(entity, key, name)`
tuples, or mappings with `entity`/`device_id`, `key`, and optional
`name`/`device_name`.

`progress(done, total, message)` and `cancel() -> bool` are optional. Methods
raise `CancelledError` when `cancel()` returns true.

### `LadderConfig`

| Field | Default | Meaning |
|---|---|---|
| `finest` | `minute` | Default finest level |
| `timezone` | `Asia/Shanghai` | Calendar timezone |
| `max_intervals` | `500` | Buckets per interval request |
| `max_points` | `10000` | Points per raw request |
| `max_total_points` | `2000000` | Hard cap per operation |
| `materialize_grace_ms` | `300000` | Coverage grace period |
| `max_repair_days` | `366` | Repair window |
| `concurrency` | `8` | Parallel series |
| `continue_on_error` | `False` | Collect per-row errors instead of raising |
| `max_segments` | `None` | Optional defensive cap |
| `min_bucket_ms` | `60000` | Smallest adaptive bucket |

### `calc` / `calc_local` / `calc_mixed`

```python
result = engine.calc(refs, start_ms, end_ms, dimension="day", rule="sum")
result = engine.calc_mixed(refs, start_ms, end_ms, dimension="day",
                           rule="meter_delta")
```

`rule` is `sum`, `avg` or `meter_delta`; `dimension` is `minute`, `hour`,
`day` or `month` and both edges must align to it. The result is a
`CalcResult` with `rule`, `dimension`, `rows` (`CalcRow`: `buckets`,
`total`, `ok`, `tb_ranges`, `source_counts`) and `grand_total`. Rule
semantics and anomaly codes are specified in `docs/algorithm.md §7`.

### Results

`QueryResult.as_dict()` and `Row.as_dict()` produce the JSON documented in
`docs/algorithm.md §10`. `Segment` supports both attribute access
(`segment.value`) and dict-style access (`segment["value"]`).

## CLI

```
hybrid-ladder [--version] <command> ...

commands:
  decompose     show the ladder decomposition of a range
  demo          end-to-end demo with synthetic data
  sum           sum one or more series
  calc          bucket a range and apply sum / avg / meter_delta
  verify        compare the source with the local store
  repair        replace the local range with source data
  materialize   pull raw points into the local store
  serve         run the HTTP API
  mcp           run the MCP server over stdio
  version       print the version
```

Common options for `sum`, `calc`, `verify`, `repair`, `materialize`:

| Option | Meaning |
|---|---|
| `--series ENTITY:KEY[:NAME]` | Repeatable series reference |
| `--start`, `--end` | ISO-8601 or epoch milliseconds; end is exclusive |
| `--finest` | `month`, `day`, `hour`, `minute` |
| `--timezone` | IANA timezone |
| `--source` | `memory` or `thingsboard` |
| `--tb-url`, `--tb-token`, `--tb-username`, `--tb-password` | ThingsBoard connection |
| `--dsn` | PostgreSQL DSN (enables local store) |
| `--namespace`, `--table-prefix` | PostgreSQL namespace/tables |
| `--json` | Print raw JSON |

`sum` also accepts `--mode tb|mixed|local` and `--materialize`.

`calc` accepts the same mode/materialize options plus:

| Option | Meaning |
|---|---|
| `--dimension minute|hour|day|month` | Bucket size; both edges of the range must align to it (default `day`) |
| `--rule sum|avg|meter_delta` | Per-bucket aggregation rule (default `sum`) |

Examples:

```bash
hybrid-ladder calc --start 2026-01-01 --end 2026-02-01 --rule sum
hybrid-ladder calc --start 2026-01-01 --end 2026-02-01 --rule avg --dimension hour
hybrid-ladder calc --start 2026-01-01 --end 2026-02-01 --rule meter_delta --dimension day
hybrid-ladder calc --source thingsboard --series 6f2c...:L_LSJ1_DB_EP \
  --start 2026-01-01 --end 2026-02-01 --rule meter_delta --mode mixed --materialize
```


Examples:

```bash
hybrid-ladder demo
hybrid-ladder decompose --start 2026-01-01 --end 2026-10-21T18:49:59 --json
hybrid-ladder sum --series demo-chiller-1:energy --start 2026-01-01 --end 2026-02-01
hybrid-ladder sum --source thingsboard --series 6f2c...:L_LSJ1_DB_EP \
  --start 2026-01-01 --end 2026-10-21T18:49:59 --mode mixed --materialize
hybrid-ladder calc --series demo-chiller-1:energy --start 2026-01-01 \
  --end 2026-02-01 --rule meter_delta
hybrid-ladder verify --source thingsboard --series ... --start ... --end ...
hybrid-ladder repair --source thingsboard --series ... --start ... --end ...
```

## HTTP API

```bash
# from a source checkout (see README Install)
pip install -e ".[api]"
hybrid-ladder serve --host 127.0.0.1 --port 8000
# OpenAPI: http://127.0.0.1:8000/docs
```

Success envelope: `{"code": 0, "data": ...}`.
Error envelope: `{"code": 1, "detail": "..."}` with HTTP 400/404/409/502/503.

### `GET /`

Service metadata and, with demo data, a ready-to-use range and series.

### `GET /health`

```json
{"status": "ok", "version": "0.0.7", "source": "ThingsBoardSource", "store": "PostgresStore"}
```

### `GET /v1/meta`

Version, levels, full config, source/store type, demo info.

### `GET /v1/demo`

Demo range and series (only with `HL_SOURCE=memory`).

### `GET /v1/decompose`

Query: `start_ts`, `end_ts` (epoch ms), optional `finest`.

```json
{
  "count": 97,
  "by_level": {"month": 9, "day": 20, "hour": 18, "minute": 50},
  "segments": [{"level": "month", "start": 1767196800000, "end": 1769875200000,
                "label": "2026-01", "value": null, "cnt": null,
                "expected": null, "source": null}]
}
```

### `POST /v1/ladder/sum`

Body:

```json
{
  "series": [{"entity": "device-id", "key": "energy", "name": "Chiller 1"}],
  "start_ts": 1767196800000,
  "end_ts": 1792512599000,
  "finest": "minute",
  "mode": "tb",
  "materialize": false
}
```

* `mode`: `tb` (source only), `mixed` (local first, needs a store), `local`
  (offline, needs a store).
* `materialize`: after computing, pull missing raw points into the store.

Async response (default):

```json
{"code": 0, "data": {"task_id": "…", "async": true, "series": 1}}
```

Synchronous: `POST /v1/ladder/sum?sync=true` returns the full result. There is
also `POST /v1/ladder/sum/sync` for clients that cannot use query parameters.

Result shape:

```json
{
  "code": 0,
  "data": {
    "rows": [{
      "device_id": "device-id", "device_name": "Chiller 1", "key": "energy",
      "segments": [], "total": 2217024.0, "empty_count": 0,
      "segments_count": 69, "tb_ranges": [[1792425600000, 1792500000000]]
    }],
    "grand_total": 2217024.0,
    "source": "mixed",
    "source_counts": {"local": 3, "tb": 1, "mixed": 0, "empty": 0, "uncovered": 0},
    "errors": []
  }
}
```

### `POST /v1/ladder/calc`

Bucket a range and compute one value per bucket under a rule. Body:

```json
{
  "series": [{"entity": "demo-chiller-1", "key": "energy"}],
  "start_ts": 1767196800000,
  "end_ts": 1798732800000,
  "dimension": "day",
  "rule": "meter_delta",
  "mode": "tb",
  "materialize": false
}
```

* `dimension` — `minute`, `hour`, `day` or `month`; both edges must align to it.
* `rule` — `sum`, `avg` or `meter_delta` (semantics in `docs/algorithm.md §7`).
* `mode` — `tb` (source only), `mixed` (local first, needs a store) or
  `local` (offline, needs a store).
* `materialize` — after a `mixed` calculation, pull the uncovered
  `tb_ranges` into the store.

The response rows carry `buckets` (`label`, `value`, `cnt`, `source`,
`anomaly`, `first_ts`, `next_ts`), a per-row `total`, `ok` (valid delta count)
and `tb_ranges`. Async form: `POST /v1/ladder/calc` returns a `task_id`
immediately; `POST /v1/ladder/calc/sync` runs inline.

```json
{
  "code": 0,
  "data": {
    "rule": "meter_delta",
    "dimension": "day",
    "rows": [
      {
        "device_id": "demo-chiller-1",
        "key": "energy",
        "total": 96.0,
        "ok": 2,
        "buckets": [
          {"label": "2026-01-01", "value": 48.0, "anomaly": null,
           "first_ts": 1767196800000, "next_ts": 1767283200000, "source": "tb"}
        ],
        "tb_ranges": [[1767196800000, 1767283200000]]
      }
    ],
    "grand_total": 96.0,
    "source": "tb"
  }
}
```

Anomaly codes on `meter_delta` buckets: `no_current_reading`,
`no_next_reading`, `same_reading`, `negative_delta` (meter reset) and
`non_numeric`. Anomalous buckets carry `value: null` — they never invent
a number.

### `POST /v1/ladder/verify`

Body: `series`, `start_ts`, `end_ts`, `finest`, `drill_limit`. Async by
default, `?sync=true` for a synchronous response. Requires a store.

Result:

```json
{
  "series": 1, "segments": 10, "diff_series": 1, "diff_segments": 1,
  "drilled": 1, "drill_skipped": 0,
  "details": [{
    "device_name": "Chiller 1", "key": "energy",
    "diffs": [{
      "level": "day", "label": "2026-01-03", "start": 0, "end": 0,
      "tb": 240.0, "local": 1239.0, "local_cnt": 96,
      "tb_points": 96, "local_points": 96,
      "added": 0, "removed": 0, "changed": 1,
      "sample_added": [], "sample_removed": [], "sample_changed": [1767…]
    }]
  }]
}
```

### `POST /v1/ladder/repair`

Body: `series`, `start_ts`, `end_ts`. Async by default. Deletes and re-pulls
the range from the source. Result lists `deleted` and `inserted` per series.

### `POST /v1/ladder/materialize`

Body: `series`, `start_ts`, `end_ts`. Async by default. Result:

```json
{"written": 11520, "ranges": 1, "series": 1}
```

### Tasks

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/v1/tasks` | Recent tasks |
| `GET` | `/v1/tasks/{task_id}` | Status, progress, result |
| `POST` | `/v1/tasks/{task_id}/cancel` | Request cancellation |

Task snapshot:

```json
{
  "task_id": "…", "title": "ladder sum", "status": "running",
  "done": 1, "total": 2, "message": "computed 1/2 series",
  "error": null, "cancel": false, "elapsed": 1.234
}
```

`status` is `running`, `completed`, `failed` or `cancelled`. The result is
included only when `completed`.

### Environment

| Variable | Default | Purpose |
|---|---|---|
| `HL_SOURCE` | `memory` | `memory` or `thingsboard` |
| `HL_TB_URL` | — | ThingsBoard base URL |
| `HL_TB_TOKEN` | — | JWT token |
| `HL_TB_USERNAME` / `HL_TB_PASSWORD` | — | login credentials |
| `HL_PG_DSN` | — | PostgreSQL DSN; enables mixed/local |
| `HL_NAMESPACE` | `default` | PostgreSQL namespace |
| `HL_TABLE_PREFIX` | `hl_` | PostgreSQL table prefix |
| `HL_FINEST` | `minute` | default finest level |
| `HL_TIMEZONE` | `Asia/Shanghai` | calendar timezone |
| `HL_MAX_INTERVALS` | `500` | buckets per interval request |
| `HL_MAX_POINTS` | `10000` | points per raw request |
| `HL_MATERIALIZE_GRACE_MS` | `300000` | coverage grace |
| `HL_CONCURRENCY` | `8` | parallel series |
| `HL_CORS_ORIGINS` | — | comma-separated CORS origins |

## MCP

```bash
# from a source checkout
pip install -e ".[mcp]"
hybrid-ladder mcp
```

Tools:

| Tool | Arguments | Result |
|---|---|---|
| `ladder_meta` | — | version, config, source/store, demo range |
| `ladder_decompose` | `start`, `end`, `finest`, `timezone` | segments + counts |
| `ladder_sum` | `series`, `start`, `end`, `finest`, `mode`, `materialize` | query result |
* `ladder_calc` — bucket a range and apply `sum` / `avg` / `meter_delta` (`dimension`, `rule`, `mode`, `materialize`).
| `ladder_verify` | `series`, `start`, `end`, `finest`, `drill_limit` | verify report |

Times accept ISO-8601 or epoch milliseconds. With no `series`, the demo series
are used. Configuration uses the same `HL_*` variables.

Example client configuration:

```json
{
  "mcpServers": {
    "hybrid-ladder": {
      "command": "hybrid-ladder",
      "args": ["mcp"],
      "env": {"HL_SOURCE": "thingsboard", "HL_TB_URL": "https://tb.example.com",
              "HL_TB_TOKEN": "...", "HL_PG_DSN": "postgresql://..."}
    }
  }
}
```

## Errors

| Exception | HTTP | Meaning |
|---|---|---|
| `ValueError` | 400 | Invalid range, level, timezone or argument |
| `ConfigurationError` | 400 | Missing store, source or required option |
| `CancelledError` | 409 | Operation cancelled |
| `SourceError` | 502 | Source request failed |
| `StoreError` | 503 | Store request failed |
| `LadderError` | 400 | Other ladder error |
