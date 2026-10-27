# API 参考

**语言 / Languages:** [English](api.md) · [简体中文](api.zh-CN.md)

本包通过四种接口暴露同一个引擎：Python、CLI、HTTP 和 MCP。

## Python

```python
from hybrid_ladder import LadderEngine, LadderConfig
```

### `LadderEngine(source, store=None, config=None, *, clock=None)`

| 方法 | 用途 |
|---|---|
| `decompose(start_ms, end_ms, finest=None)` | 返回阶梯段 |
| `sum(refs, start_ms, end_ms, *, finest=None, progress=None, cancel=None)` | 只读数据源求和 |
| `sum_local(refs, ...)` | 只读本地存储（离线） |
| `sum_mixed(refs, ...)` | 本地优先的混合读 |
| `materialize(refs, start_ms, end_ms, ...)` | 为整个区间拉取原始点 |
| `materialize_ranges(items, ...)` | 为每个序列的指定区间拉取原始点 |
| `verify(refs, ..., drill_limit=50)` | 数据源与本地对比 |
| `repair(refs, ...)` | 用数据源数据替换本地区间 |

`refs` 接受 `SeriesRef`、`(entity, key)` 元组、`(entity, key, name)` 元组，
或带 `entity`/`device_id`、`key` 以及可选 `name`/`device_name` 的映射。

`progress(done, total, message)` 与 `cancel() -> bool` 都是可选的。当
`cancel()` 返回 true 时，方法抛出 `CancelledError`。

### `LadderConfig`

| 字段 | 默认值 | 含义 |
|---|---|---|
| `finest` | `minute` | 默认最细层 |
| `timezone` | `Asia/Shanghai` | 日历时区 |
| `max_intervals` | `500` | 单次区间聚合的桶数 |
| `max_points` | `10000` | 单次原始点请求的点数 |
| `max_total_points` | `2000000` | 单次操作的硬上限 |
| `materialize_grace_ms` | `300000` | 覆盖宽限期 |
| `max_repair_days` | `366` | 单次修复窗口 |
| `concurrency` | `8` | 并行序列数 |
| `continue_on_error` | `False` | 收集每行错误而不是抛出 |
| `max_segments` | `None` | 可选的防御性段数上限 |
| `min_bucket_ms` | `60000` | 自适应桶长的最小值 |

### 结果

`QueryResult.as_dict()` 与 `Row.as_dict()` 生成 `docs/algorithm.md §9` 中描述的
JSON。`Segment` 同时支持属性访问（`segment.value`）和字典式访问
（`segment["value"]`）。

## CLI

```
hybrid-ladder [--version] <command> ...

commands:
  decompose     show the ladder decomposition of a range
  demo          end-to-end demo with synthetic data
  sum           sum one or more series
  verify        compare the source with the local store
  repair        replace the local range with source data
  materialize   pull raw points into the local store
  serve         run the HTTP API
  mcp           run the MCP server over stdio
  version       print the version
```

`sum`、`verify`、`repair`、`materialize` 的通用选项：

| 选项 | 含义 |
|---|---|
| `--series ENTITY:KEY[:NAME]` | 可重复的序列引用 |
| `--start`, `--end` | ISO-8601 或 epoch 毫秒；结束时间不包含 |
| `--finest` | `month`、`day`、`hour`、`minute` |
| `--timezone` | IANA 时区 |
| `--source` | `memory` 或 `thingsboard` |
| `--tb-url`、`--tb-token`、`--tb-username`、`--tb-password` | ThingsBoard 连接 |
| `--dsn` | PostgreSQL DSN（启用本地存储） |
| `--namespace`、`--table-prefix` | PostgreSQL 命名空间/表名 |
| `--json` | 输出原始 JSON |

`sum` 还接受 `--mode tb|mixed|local` 与 `--materialize`。

示例：

```bash
hybrid-ladder demo
hybrid-ladder decompose --start 2026-01-01 --end 2026-10-21T18:49:59 --json
hybrid-ladder sum --series demo-chiller-1:energy --start 2026-01-01 --end 2026-02-01
hybrid-ladder sum --source thingsboard --series 6f2c...:L_LSJ1_DB_EP \
  --start 2026-01-01 --end 2026-10-21T18:49:59 --mode mixed --materialize
hybrid-ladder verify --source thingsboard --series ... --start ... --end ...
hybrid-ladder repair --source thingsboard --series ... --start ... --end ...
```

## HTTP API

```bash
# 从源码检出安装（见 README 的安装说明）
pip install -e ".[api]"
hybrid-ladder serve --host 127.0.0.1 --port 8000
# OpenAPI: http://127.0.0.1:8000/docs
```

成功响应：`{"code": 0, "data": ...}`。
错误响应：`{"code": 1, "detail": "..."}`，HTTP 状态为 400/404/409/502/503。

### `GET /`

服务元数据；使用 demo 数据时还会返回可直接使用的区间和序列。

### `GET /health`

```json
{"status": "ok", "version": "0.0.6", "source": "ThingsBoardSource", "store": "PostgresStore"}
```

### `GET /v1/meta`

版本、层级、完整配置、数据源/存储类型、demo 信息。

### `GET /v1/demo`

Demo 区间与序列（仅当 `HL_SOURCE=memory`）。

### `GET /v1/decompose`

查询参数：`start_ts`、`end_ts`（epoch 毫秒），可选 `finest`。

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

请求体：

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

* `mode`：`tb`（只用数据源）、`mixed`（本地优先，需要存储）、`local`
  （离线，需要存储）。
* `materialize`：计算完成后，把缺失的原始点补入本地存储。

异步响应（默认）：

```json
{"code": 0, "data": {"task_id": "…", "async": true, "series": 1}}
```

同步：`POST /v1/ladder/sum?sync=true` 直接返回完整结果。对于不能使用查询
参数的客户端，也有 `POST /v1/ladder/sum/sync`。

结果结构：

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

### `POST /v1/ladder/verify`

请求体：`series`、`start_ts`、`end_ts`、`finest`、`drill_limit`。默认异步；
加 `?sync=true` 同步返回。需要本地存储。

结果：

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

请求体：`series`、`start_ts`、`end_ts`。默认异步。删除本地区间并从数据源
重新拉取。结果为每个序列列出 `deleted` 与 `inserted`。

### `POST /v1/ladder/materialize`

请求体：`series`、`start_ts`、`end_ts`。默认异步。结果：

```json
{"written": 11520, "ranges": 1, "series": 1}
```

### 任务

| 方法 | 路径 | 用途 |
|---|---|---|
| `GET` | `/v1/tasks` | 最近任务 |
| `GET` | `/v1/tasks/{task_id}` | 状态、进度、结果 |
| `POST` | `/v1/tasks/{task_id}/cancel` | 请求取消 |

任务快照：

```json
{
  "task_id": "…", "title": "ladder sum", "status": "running",
  "done": 1, "total": 2, "message": "computed 1/2 series",
  "error": null, "cancel": false, "elapsed": 1.234
}
```

`status` 为 `running`、`completed`、`failed` 或 `cancelled`。只有 `completed`
时才会包含结果。

### 环境变量

| 变量 | 默认值 | 用途 |
|---|---|---|
| `HL_SOURCE` | `memory` | `memory` 或 `thingsboard` |
| `HL_TB_URL` | — | ThingsBoard 基础 URL |
| `HL_TB_TOKEN` | — | JWT token |
| `HL_TB_USERNAME` / `HL_TB_PASSWORD` | — | 登录凭据 |
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

## MCP

```bash
# 从源码检出安装
pip install -e ".[mcp]"
hybrid-ladder mcp
```

工具：

| 工具 | 参数 | 结果 |
|---|---|---|
| `ladder_meta` | — | 版本、配置、数据源/存储、demo 区间 |
| `ladder_decompose` | `start`、`end`、`finest`、`timezone` | 段与计数 |
| `ladder_sum` | `series`、`start`、`end`、`finest`、`mode`、`materialize` | 查询结果 |
| `ladder_verify` | `series`、`start`、`end`、`finest`、`drill_limit` | 校验报告 |

时间接受 ISO-8601 或 epoch 毫秒。不传 `series` 时使用 demo 序列。配置使用
相同的 `HL_*` 环境变量。

客户端配置示例：

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

## 错误

| 异常 | HTTP | 含义 |
|---|---|---|
| `ValueError` | 400 | 区间、层级、时区或参数无效 |
| `ConfigurationError` | 400 | 缺少存储、数据源或必需选项 |
| `CancelledError` | 409 | 操作已取消 |
| `SourceError` | 502 | 数据源请求失败 |
| `StoreError` | 503 | 存储请求失败 |
| `LadderError` | 400 | 其他阶梯错误 |
