# Hybrid Recursive Ladder — 速查表

**语言 / Languages:** [English](reference.md) · [简体中文](reference.zh-CN.md)

## 段 JSON

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

`level`：`month | day | hour | minute`  
`value`：`null` = 无采样，`0.0` = 有采样但求和为 0  
`source`：`local | tb | mixed | empty | uncovered`

## 查询结果 JSON

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

## 数据源协议

```python
class TimeSeriesSource(Protocol):
    def interval_agg(ref, start_ms, end_ms, bucket_ms, agg="SUM") -> Mapping[int, Any]: ...
    def raw_series(ref, start_ms, end_ms, limit=10_000) -> list[tuple[int, Any]]: ...
```

* `interval_agg` 的键是**桶起点**时间戳。
* 区间是 `[start, end)`。
* `raw_series` 返回升序点；如果正好返回 `limit` 个，引擎会认为被截断并二分
  窗口。

## 存储协议

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

## 环境变量

| 变量 | 默认值 | 用途 |
|---|---|---|
| `HL_SOURCE` | `memory` | `memory`（demo 数据）或 `thingsboard` |
| `HL_TB_URL` | — | ThingsBoard 基础 URL |
| `HL_TB_TOKEN` | — | JWT token |
| `HL_TB_USERNAME` / `HL_TB_PASSWORD` | — | 登录凭据（token 的替代） |
| `HL_PG_DSN` | — | PostgreSQL DSN；启用 mixed/local |
| `HL_NAMESPACE` | `default` | PostgreSQL 命名空间 |
| `HL_TABLE_PREFIX` | `hl_` | PostgreSQL 表名前缀 |
| `HL_FINEST` | `minute` | 默认最细层 |
| `HL_TIMEZONE` | `Asia/Shanghai` | 日历时区 |
| `HL_MAX_INTERVALS` | `500` | 单次区间请求的桶数 |
| `HL_MAX_POINTS` | `10000` | 单次原始点请求的点数 |
| `HL_MATERIALIZE_GRACE_MS` | `300000` | 覆盖宽限期 |
| `HL_CONCURRENCY` | `8` | 并行序列数 |
| `HL_CORS_ORIGINS` | — | 逗号分隔的 CORS 来源 |

## CLI 速查

```bash
hybrid-ladder demo
hybrid-ladder decompose --start 2026-01-01 --end 2026-10-21T18:49:59
hybrid-ladder sum --series device:key --start 2026-01-01 --end 2026-02-01
hybrid-ladder sum --series device:key --start ... --end ... --mode mixed --materialize
hybrid-ladder verify --series device:key --start ... --end ...
hybrid-ladder repair --series device:key --start ... --end ...
hybrid-ladder materialize --series device:key --start ... --end ...
hybrid-ladder serve --port 8000
hybrid-ladder mcp
hybrid-ladder version
```
