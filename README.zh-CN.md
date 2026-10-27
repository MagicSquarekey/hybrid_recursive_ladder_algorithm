# 混合递归阶梯算法（Hybrid Recursive Ladder）

**面向「每请求桶数有上限」的时序 API 的查询规划。** 用少量请求聚合长区间，替代逐桶查询。

**语言 / Languages:** [English](README.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Português](README.pt-BR.md) · [Русский](README.ru.md) · [العربية](README.ar.md) · [हिन्दी](README.hi.md)

[算法规范](docs/algorithm.zh-CN.md) · [API 参考](docs/api.zh-CN.md) · [性能数据](docs/benchmarks.zh-CN.md) · [相关工作](docs/related-work.zh-CN.md) · [公开披露](docs/defensive-publication.zh-CN.md) · [文档索引](docs/README.zh-CN.md)

[![CI](https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm/actions/workflows/ci.yml/badge.svg)](https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)
[![Version](https://img.shields.io/badge/version-0.0.6-green.svg)](CHANGELOG.md)
[![Website](https://img.shields.io/badge/website-live-5eead4.svg)](https://magicsquarekey.github.io/hybrid_recursive_ladder_algorithm/)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23656844.svg)](https://doi.org/10.5281/zenodo.23656844)

<p align="center">
  <img src="docs/assets/hero.zh-CN.png" alt="逐桶客户端：1,140 个桶，每桶最多 4 次调用，139 秒。日历阶梯：97 段，约 5–7 次请求，0.64 秒。" width="100%">
</p>

<p align="center"><em>同样的输出粒度。逐桶客户端每个输出行付一次往返；阶梯每层只取一次。</em></p>

## 为什么需要它

大多数时序 API 按请求数、桶数或往返次数计费。旧的「每个统计桶问一次数据源」实现，把一个两天的分钟级查询变成 2,880 个桶，每桶最多 4 次 HTTP。生产环境实测：**1,140 个桶耗时 139 秒**（走 VPN）。

瓶颈不是加法，是网络往返。

三种显而易见的修法，都会牺牲点什么：

| 修法 | 代价 |
|---|---|
| 整段只取一个粗粒度桶 | 每分钟/每天的行没了，而输出粒度正是产品本身 |
| 预聚合（连续聚合、rollup 表） | 需要写源端，或者控制源端数据库 |
| 分页 | 页数没少，边界情况更多 |

阶梯换了一条路：**保留输出粒度，但不再每个输出单位问一次。** 只要数据源能对一段连续区间返回区间聚合，一次请求就能填满很多输出段。

## 怎么工作

1. **分解**：把 `[start, end)` 从月到最细层切成完整日历单位；只输出完整单位，左右残段下沉到下一层。
2. **分组**：只有「取数层级相同且时间连续」的段才合并。小时和分钟可以共用分钟级 run；月和日不能。
3. **取数**：每个最大连续 run 用下一级更细的聚合抓一次：月按日、日按时、时按分、分按分。
4. **折叠**：把返回的桶在本地折成输出段。

<p align="center">
  <img src="docs/assets/decomposition.zh-CN.png" alt="区间先切成 9 个完整月，再把 10 月切成 20 天，把 10 月 21 日切成 18 个小时，把不完整的小时切成 49 分钟和 1 个零头：一共 97 段。" width="100%">
</p>

对 `2026-01-01 00:00:00 → 2026-10-21 18:49:59`，这是 **97 段，而不是 423,049 个分钟桶**。典型 10 个月查询约 **5–7 次聚合请求**。

### 规则

- **左闭右开**：`[start, end)`。
- **只取完整单位**：月/日/时/分只有整体落在区间内，才在该层输出。
- **残段递归**：不完整的边交给下一层；不足一分钟的零头单独成段。
- **本地日历**：边界按配置的 IANA 时区（默认 `Asia/Shanghai`）。
- **铺满**：段有序、首尾相接、不重叠，并集恰为 `[start, end)`。

### 请求数上界

对一个时长为 `T`、取数桶长为 `Δ` 的 run，单请求最多 `K` 个桶：

```
requests(run) = ceil(T / (K * Δ))
```

细粒度工作只发生在两端的残段里。默认层级下 `N <= N_month + 639`，递归深度不超过 4；请求数是 `O(N_month / K + 1)`，随粗粒度单位增长，而不是随分钟桶数增长。形式化命题见 [`docs/algorithm.zh-CN.md`](docs/algorithm.zh-CN.md) §5.3–5.5。

## 快速开始

```bash
pip install https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm/releases/download/v0.0.6/hybrid_recursive_ladder-0.0.6-py3-none-any.whl

hybrid-ladder demo
hybrid-ladder decompose --start 2026-01-01 --end 2026-10-21T18:49:59
```

demo 会构造 15 分钟粒度的合成数据，分解 120 天，固化前 60 天，跑一次本地优先混合查询，并校验合计一致。不需要数据库、网络或配置。

可选 extras：

```bash
pip install -e ".[thingsboard]"   # ThingsBoard 数据源（httpx）
pip install -e ".[postgres]"      # 本地存储（psycopg 3）
pip install -e ".[api]"           # FastAPI HTTP API
pip install -e ".[mcp]"           # MCP server
pip install -e ".[all]"           # 全部
```

核心分解**零第三方依赖**（只有 Windows 上可靠 IANA 时区所需的 `tzdata`）。

## 使用方式

| 形态 | 入口 | 适合 |
|---|---|---|
| **Python 库** | `from hybrid_ladder import ...` | 嵌进服务或数据管道 |
| **CLI** | `hybrid-ladder ...` | 临时检查、脚本、cron |
| **HTTP API** | `hybrid-ladder serve` | 跨语言集成、异步任务 |
| **MCP server** | `hybrid-ladder mcp` | AI agent 和 MCP 客户端 |
| **Agent skill** | [`skills/hybrid-recursive-ladder/`](skills/hybrid-recursive-ladder/) | Claude/ZCode 风格技能安装 |

### Python 库

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

引擎只依赖两个小协议：`TimeSeriesSource`（`interval_agg`、`raw_series`）和 `PointStore`（`sum_ranges`、`series`、`coverage`、`upsert_points` 等）。内置 `MemorySource`/`MemoryStore`、`ThingsBoardSource`、`PostgresStore`；接入其他数据源见 [`docs/architecture.zh-CN.md`](docs/architecture.zh-CN.md)。

### CLI

```bash
# demo 数据
hybrid-ladder sum --series demo-chiller-1:energy --start 2026-01-01 --end 2026-02-01

# ThingsBoard，本地优先
export HL_TB_URL=https://tb.example.com
export HL_TB_TOKEN=...
export HL_PG_DSN='postgresql://user:pass@127.0.0.1:5432/telemetry'
hybrid-ladder sum --source thingsboard --series <device>:<key> \
  --start 2026-01-01 --end 2026-10-21T18:49:59 \
  --mode mixed --materialize

# 校验与修复本地副本
hybrid-ladder verify --source thingsboard --series <device>:<key> --start ... --end ...
hybrid-ladder repair --source thingsboard --series <device>:<key> --start ... --end ...
```

### HTTP API

```bash
hybrid-ladder serve --port 8000
# OpenAPI 文档：http://127.0.0.1:8000/docs
```

```bash
curl "http://127.0.0.1:8000/v1/decompose?start_ts=1767196800000&end_ts=1792512599000"

curl -X POST http://127.0.0.1:8000/v1/ladder/sum \
  -H 'content-type: application/json' \
  -d '{"series":[{"entity":"demo-chiller-1","key":"energy"}],
       "start_ts":1767196800000,"end_ts":1777564800000,"mode":"tb"}'
# → {"code":0,"data":{"task_id":"...","async":true}}

curl http://127.0.0.1:8000/v1/tasks/<task_id>
```

成功返回 `{"code":0,"data":...}`，失败返回 `{"code":1,"detail":...}`。所有端点见 [`docs/api.zh-CN.md`](docs/api.zh-CN.md)。

### MCP server

```bash
pip install -e ".[mcp]"
hybrid-ladder mcp
```

工具：`ladder_meta`、`ladder_decompose`、`ladder_sum`、`ladder_verify`。无配置时直接提供 demo 数据，agent 可以立即试用。客户端配置示例：

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

### Agent skill

把 [`skills/hybrid-recursive-ladder/`](skills/hybrid-recursive-ladder/) 复制到你的 agent skills 目录（例如 `~/.claude/skills/` 或 `~/.zcode/skills/`）。技能会教 agent 什么时候用阶梯、怎么调 CLI/API，以及怎么区分 `null` 与 `0.0`、怎么看 `source`。

## 本地优先模式

有本地点存储时，同一套段会先按已固化的覆盖区间切开：已覆盖部分用一条批量本地查询求和；未覆盖部分走数据源；部分覆盖的段只补缺的那一截。

<p align="center">
  <img src="docs/assets/architecture.zh-CN.png" alt="纯源路径：分解、按取数层级和连续性分组、每个 run 在桶数上限内取一次、本地折叠。本地优先路径：按覆盖切分段、已覆盖部分本地求和、未覆盖部分取源、合并两者。" width="100%">
</p>

```python
from hybrid_ladder import LadderEngine, MemoryStore
from hybrid_ladder.sources.thingsboard import ThingsBoardSource

source = ThingsBoardSource("https://thingsboard.example.com", token="...")
store = MemoryStore()               # 或 PostgresStore("postgresql://...")
engine = LadderEngine(source, store)

# 原始点只拉一次；覆盖会被记录。
engine.materialize([("device-id", "energy")], start_ms, end_ms)

# 重复查询读本地，只补未覆盖子区间。
result = engine.sum_mixed([("device-id", "energy")], start_ms, end_ms)
print(result.source, result.source_counts)   # "local" / "mixed" / "tb"
print(result.rows[0].tb_ranges)              # 本地还缺的区间

# 与源端比对，必要时修复。
report = engine.verify([("device-id", "energy")], start_ms, end_ms)
if report["diff_segments"]:
    engine.repair([("device-id", "energy")], start_ms, end_ms)
```

覆盖只记录到 `now - 5 分钟`；正在发生的尾段永远不算可信。即使源端返回零个点，也会登记「这段查过了」。重写前先失效覆盖，所以拉取失败不会留下指向不完整数据的陈旧覆盖。

**校验**按段比对源端（权威）与本地，只对差异段逐点展开（`added`/`removed`/`changed`）。**修复**按事务窗口删除本地区间并从源端重拉，然后重新登记覆盖。

## 保证与限制

| 值 | 含义 | 展示 |
|---|---|---|
| `null` | 段内没有采样 | `—` |
| `0.0` | 有采样，但求和为 0 | `0` |
| 数字 | 采样之和 | 数字 |

每个段都带 `cnt`（实际点数/桶数）、`expected`（源段应有桶数）和 `source`（`local`、`tb`、`mixed`、`empty`、`uncovered`）。`cnt` 远低于 `expected` 说明数据稀疏；合计仍然算术正确，只是基于更少的点。

**保证**

- `sum` 精确：所有段之和 = 源端在区间内所有点之和，没有近似、没有采样。
- 段精确铺满区间，不产生零长段。
- `null` 与 `0.0` 在所有层都严格区分。
- 固化幂等；重叠的固化不会重复写入同一个时间戳。
- 算法只读数据源，从不写 ThingsBoard。

**限制**

- **v0.0.6 只实现 `sum`。** `avg` 需要 `sum` + `count` 加权；`meter_delta` 需要每段首值（TB 没有 `FIRST`），暂未上阶梯。
- **数据完整 ≠ 算术正确。** 数据缺失会让合计偏小；`cnt`/`expected` 只暴露稀疏，不补数。
- **ThingsBoard 限制**：约 700 个桶可接受，800 会被拒（文档说的 1000 不可信）；适配器默认 500。原始序列每请求上限 10,000 点。`COUNT` 会吞同分钟重复点。
- **进程内任务**重启即丢；结果可重算，固化数据不丢。
- **DST 时区**：日历边界支持，但固定桶长意味着日/时折叠适合固定偏移时区（如 `Asia/Shanghai`）；切换点附近建议用更细的取数层。

历史修复与版本说明见 [`CHANGELOG.md`](CHANGELOG.md)。

## 性能

来自生产 ThingsBoard 部署（数字随网络和数据密度变化）：

| 查询 | 段数 | 源请求 | 时间 | 结果 |
|---|---:|---:|---:|---|
| 2 天，分钟级 | 69 | ~4 | 0.64 s | 2,217,024.0（与 2,566 个原始点一致） |
| 1 年，日级 | 42 | ~4 | 1.18 s 冷 / 0.20 s 热 | 36,012,018.25 |
| 10 个月，混合层级 | 97 | ~5–7 | 亚秒 | 避免 423,049 个分钟桶 |
| 本地读，42–90 段 | — | 0 | 9–19 ms | 一条 SQL |
| 混合读（3 本地 + 1 源段） | 4 | 1 | 0.31 s | 与纯源查询一致 |

方法与注意事项见 [`docs/benchmarks.zh-CN.md`](docs/benchmarks.zh-CN.md)。

## 定位与先例

这是一个**查询规划方法**，面向「能读区间聚合接口、但不能写源端、也不能改源端存储/降采样策略」的部署。它不是新的时序数据库，也不是新的通用聚合理论；它组合了日历混合进制分解、规范区间分解、roll-up 和多分辨率聚合。

最接近的系统是 RRDtool/Whisper（多分辨率归档）、BTrDB（时间分区层级统计）、TimescaleDB 层级连续聚合、Druid 日历经度。Prometheus/Grafana 这类查询侧系统只选一个统一粒度；阶梯在一次查询里规划多个日历层级。

完整对比、历史算法和可辩护的新颖性表述见 [相关工作与定位](docs/related-work.zh-CN.md)。方法同时以[公开披露](docs/defensive-publication.zh-CN.md)的形式发布；[技术文章](docs/articles/why-per-bucket-queries-are-slow.zh-CN.md)完整讲了生产 benchmark 和请求数论证。

## 项目、开发与路线图

<details>
<summary><strong>项目结构</strong></summary>

```
src/hybrid_ladder/
  core.py          纯分解、折叠、覆盖切分
  engine.py        源/混合/本地读、固化、校验、修复
  models.py        Segment, SeriesRef, LadderConfig, QueryResult
  protocols.py     TimeSeriesSource / PointStore
  sources/         memory.py, thingsboard.py
  stores/          memory.py, postgres.py
  api.py           FastAPI 应用
  cli.py           hybrid-ladder CLI
  mcp_server.py    MCP 工具
  tasks.py         进程内任务注册表
  demo.py          确定性 demo 数据
tests/             单元 + API + 适配器测试
docs/              算法、架构、API、性能、先例
skills/            agent skill 包
examples/          可运行示例
```
</details>

```bash
git clone https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm.git
cd hybrid_recursive_ladder_algorithm
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
ruff check .
pytest
```

可选 PostgreSQL 集成测试：

```bash
export HL_TEST_PG_DSN='postgresql://user:pass@127.0.0.1:5432/testdb'
pytest -m integration
```

**路线图：** `avg` 与 `meter_delta`；InfluxDB / Prometheus / ClickHouse 适配器；Celery/RQ 任务后端；OpenTelemetry 指标；PyPI trusted publishing。

## 引用

```bibtex
@software{hybrid_recursive_ladder_2026,
  author  = {MagicSquarekey},
  title   = {Hybrid Recursive Ladder: Query Planning for Bucket-Limited Time-Series APIs},
  year    = {2026},
  version = {0.0.6},
  license = {MIT},
  doi     = {10.5281/zenodo.23656844},
  url     = {https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm}
}
```

版本 DOI：[10.5281/zenodo.23656844](https://doi.org/10.5281/zenodo.23656844)。
所有版本的 concept DOI：[10.5281/zenodo.23556605](https://doi.org/10.5281/zenodo.23556605)。
GitHub 的 “Cite this repository” 会读取 [`CITATION.cff`](CITATION.cff)。

## 许可证

[MIT](LICENSE) © 2026 MagicSquarekey
