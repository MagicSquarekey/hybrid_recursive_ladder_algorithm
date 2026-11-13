# Hybrid Recursive Ladder — quick reference

**语言 / Languages:** [English](reference.md) · [简体中文](reference.zh-CN.md)

## Segment JSON

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

`level`: `month | day | hour | minute`
`value`: `null` = no samples, `0.0` = samples sum to zero
`source`: `local | tb | mixed | empty | uncovered`

## Query result JSON

```json
{
  "rows": [
    {
      "device_id": "device-1",
      "device_name": "Chiller 1",
      "key": "energy",
      "segments": [],
      "total": 2217024.0,
      "empty_count": 0,
      "segments_count": 69,
      "tb_ranges": [[1792425600000, 1792500000000]]
    }
  ],
  "grand_total": 2217024.0,
  "source": "mixed",
  "source_counts": {"local": 3, "tb": 1, "mixed": 0, "empty": 0, "uncovered": 0},
  "errors": []
}
```

## Source protocol

```python
class TimeSeriesSource(Protocol):
    def interval_agg(ref, start_ms, end_ms, bucket_ms, agg="SUM") -> Mapping[int, Any]: ...
    def raw_series(ref, start_ms, end_ms, limit=10_000) -> list[tuple[int, Any]]: ...
```

* Keys of `interval_agg` are **bucket start** timestamps.
* Ranges are `[start, end)`.
* `raw_series` returns ascending points; if it returns exactly `limit` points,
  the engine assumes truncation and bisects the window.

## Store protocol

```python
class PointStore(Protocol):
    def sum_ranges(ref, ranges) -> Mapping[int, tuple[float | None, int]]: ...
    def series(ref, start_ms, end_ms, max_points=5_000) -> list[Mapping]: ...
    def coverage(ref) -> list[tuple[int, int, int]]: ...
    def delete_range(ref, start_ms, end_ms) -> int: ...
    def clear_coverage(ref, start_ms, end_ms) -> int: ...
    def upsert_points(ref, points, at_ms=None) -> int: ...
    def mark_covered(ref, start_ms, end_ms, point_cnt, at_ms) -> None: ...
```

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `HL_SOURCE` | `memory` | `memory` (demo data) or `thingsboard` |
| `HL_TB_URL` | — | ThingsBoard base URL |
| `HL_TB_TOKEN` | — | JWT token |
| `HL_TB_USERNAME` / `HL_TB_PASSWORD` | — | login credentials (alternative to token) |
| `HL_PG_DSN` | — | PostgreSQL DSN; enables mixed/local modes |
| `HL_NAMESPACE` | `default` | PostgreSQL namespace |
| `HL_TABLE_PREFIX` | `hl_` | PostgreSQL table prefix |
| `HL_FINEST` | `minute` | default finest level |
| `HL_TIMEZONE` | `Asia/Shanghai` | calendar timezone |
| `HL_MAX_INTERVALS` | `500` | buckets per interval request |
| `HL_MAX_POINTS` | `10000` | points per raw request |
| `HL_MATERIALIZE_GRACE_MS` | `300000` | coverage grace period |
| `HL_VERIFY_ON_READ` | `1` | fingerprint covered runs on mixed reads (`0`/`false`/`off` disables) |
| `HL_CONCURRENCY` | `8` | parallel series |
| `HL_CORS_ORIGINS` | — | comma-separated CORS origins |

## Calc output (bucket rules)

`rule`: `sum | avg | meter_delta`; `dimension`: `minute | hour | day | month`
(both edges must align). `meter_delta` reads one bucket past `end` for the
last anchor; meter resets and missing anchors come back as `anomaly` codes
(`no_current_reading`, `no_next_reading`, `same_reading`, `negative_delta`,
`non_numeric`) with `value: null`.

```json
{
  "rule": "meter_delta",
  "dimension": "day",
  "rows": [
    {
      "device_id": "meter-1", "key": "total", "total": 89.2, "ok": 2,
      "buckets": [
        {"label": "2026-11-01", "value": 45.0, "anomaly": null,
         "first_ts": 1793462400000, "next_ts": 1793548800000, "source": "tb"}
      ],
      "tb_ranges": []
    }
  ],
  "grand_total": 89.2,
  "source": "tb"
}
```

## CLI cheat sheet

```bash
hybrid-ladder demo
hybrid-ladder decompose --start 2026-01-01 --end 2026-10-21T18:49:59
hybrid-ladder sum --series device:key --start 2026-01-01 --end 2026-02-01
hybrid-ladder sum --series device:key --start ... --end ... --mode mixed --materialize
hybrid-ladder calc --series device:key --start ... --end ... --rule meter_delta --dimension day
hybrid-ladder verify --series device:key --start ... --end ...
hybrid-ladder repair --series device:key --start ... --end ...
hybrid-ladder materialize --series device:key --start ... --end ...
hybrid-ladder serve --port 8000
hybrid-ladder mcp
hybrid-ladder version
```
