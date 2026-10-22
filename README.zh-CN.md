# 混合递归阶梯算法（Hybrid Recursive Ladder Algorithm）

**用个位数到百级的请求，聚合任意长的时间区间；把「逐桶查询」的几千次往返压成几次。**

**语言 / Languages:** [English](README.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Português](README.pt-BR.md) · [Русский](README.ru.md) · [العربية](README.ar.md) · [हिन्दी](README.hi.md)

[算法规范](docs/algorithm.zh-CN.md) · [API 参考](docs/api.md) · [性能数据](docs/benchmarks.md) · [相关工作](docs/related-work.zh-CN.md) · [公开披露](docs/defensive-publication.md)

[![CI](https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm/actions/workflows/ci.yml/badge.svg)](https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)
[![Version](https://img.shields.io/badge/version-0.0.2-green.svg)](CHANGELOG.md)
[![Website](https://img.shields.io/badge/website-live-5eead4.svg)](https://magicsquarekey.github.io/hybrid_recursive_ladder_algorithm/)

---

## 它解决什么问题

大多数时序数据库按请求数、桶数或往返次数计费。旧的「每个统计桶问一次数据源」实现，把一个两天的分钟级查询变成 2,880 个桶，每桶最多 4 次 HTTP。生产环境实测：**1,140 个桶耗时 139 秒**。

瓶颈不是加法，是网络往返。

## 核心思想

把 `[start, end)` 按 **月 → 日 → 时 → 分** 递归切成「只包含完整单位」的段：先剥离完整月，左右残段交给下一层继续拆，最细层的不足一分钟残段单独成段。取数时每层用「下一层聚合」一次拉取，再本地折叠。

```
2026-01-01 00:00:00 → 2026-10-21 18:49:59

月    2026-01 … 2026-09          9 段
日    10-01 … 10-20             20 段
时    10-21 00:00 … 17:00       18 段
分    10-21 18:00 … 18:48       49 段
零头  10-21 18:49:00–18:49:59    1 段
                                ─────
                                97 段
```

**97 段替代 423,049 个分钟桶**，压缩约 4,360 倍。典型 10 个月查询约 **5–7 次聚合请求**，而不是几千次。

## 相关工作与定位

这是**查询规划方法**，面向「能读区间聚合接口、但不能写源端、也不能改源端存储/降采样策略」的部署；不是新的通用聚合算法。日历分解是「规范区间分解」的混合进制实例；折叠是 roll-up；多分辨率聚合是 RRDtool、Whisper、BTrDB 的核心。这里真正具体的是组合：一次查询跨多个日历经度做请求计划，每层只按「下一级更细」抓一次，本地覆盖补缺口，并且整个计划受源端每请求桶数上限约束。

最接近的系统（BTrDB、RRDtool/Whisper、TimescaleDB 层级连续聚合、Druid 日历经度）、历史算法（线段树、时间轮、日历算术、OLAP roll-up）以及可辩护的新颖性表述，见 [相关工作与定位](docs/related-work.zh-CN.md)。方法同时以[公开披露](docs/defensive-publication.md)的形式发布；[技术文章](docs/articles/why-per-bucket-queries-are-slow.zh-CN.md)完整讲了生产 benchmark 和请求数论证。

## 安装

> v0.0.2 通过 GitHub Release 分发；PyPI 发布已列入计划。

```bash
# v0.0.2 GitHub release wheel
pip install https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm/releases/download/v0.0.2/hybrid_recursive_ladder-0.0.2-py3-none-any.whl

# optional extras: clone and install
git clone https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm.git
cd hybrid_recursive_ladder_algorithm
```

可选依赖：

```bash
pip install -e ".[thingsboard]"   # ThingsBoard 数据源（httpx）
pip install -e ".[postgres]"      # 本地固化（psycopg 3）
pip install -e ".[api]"           # FastAPI HTTP 接口
pip install -e ".[mcp]"           # MCP server
pip install -e ".[all]"           # 全部
```

核心分解**零第三方依赖**（仅 `tzdata`，保证 Windows 上的 IANA 时区可用）。

## 30 秒演示

```bash
hybrid-ladder demo
```

自动生成 15 分钟粒度的合成数据，分解 120 天区间，把前 90 天固化到内存存储，跑一次「本地优先」混合查询，再校验合计一致。不需要数据库、网络或任何配置。

```bash
# 只看分解，不碰数据
hybrid-ladder decompose --start 2026-01-01 --end 2026-10-21T18:49:59
```

## 库用法

```python
from hybrid_ladder import LadderEngine, MemorySource

source = MemorySource()
source.add("device-1", "energy", [(ts, 1.0) for ts in range(0, 86_400_000, 60_000)])

engine = LadderEngine(source)
result = engine.sum([("device-1", "energy")], 0, 86_400_000)

print(result.grand_total)                 # 1440.0
print(result.rows[0].segments[0].label)   # 1970-01-01 00:00
```

### 本地优先 + 固化

```python
from hybrid_ladder import LadderEngine, MemoryStore
from hybrid_ladder.sources.thingsboard import ThingsBoardSource
from hybrid_ladder.stores.postgres import PostgresStore

source = ThingsBoardSource("https://tb.example.com", token="...")
store = PostgresStore("postgresql://user:pass@127.0.0.1:5432/telemetry")
engine = LadderEngine(source, store)

# 1. 拉一次原始点并登记覆盖（幂等）
engine.materialize([("device-id", "energy")], start_ms, end_ms)

# 2. 重复查询读本地，只补未覆盖的子区间
result = engine.sum_mixed([("device-id", "energy")], start_ms, end_ms)
print(result.source, result.source_counts)   # local / mixed / tb
print(result.rows[0].tb_ranges)              # 还缺本地的区间

# 3. 校验；有差异再修复
report = engine.verify([("device-id", "energy")], start_ms, end_ms)
if report["diff_segments"]:
    engine.repair([("device-id", "energy")], start_ms, end_ms)
```

## 五种使用形态

| 形态 | 入口 | 适合 |
|---|---|---|
| **Python 库** | `from hybrid_ladder import ...` | 嵌入服务、数据管道 |
| **CLI** | `hybrid-ladder ...` | 临时排查、脚本、定时任务 |
| **HTTP API** | `hybrid-ladder serve` | 跨语言集成、异步任务 |
| **MCP server** | `hybrid-ladder mcp` | AI Agent / MCP 客户端 |
| **Agent Skill** | [`skills/hybrid-recursive-ladder/SKILL.md`](skills/hybrid-recursive-ladder/SKILL.md) | Claude/ZCode 等技能安装 |

### CLI

```bash
# 用内置 demo 数据求和
hybrid-ladder sum --series demo-chiller-1:energy --start 2026-01-01 --end 2026-02-01

# ThingsBoard + PostgreSQL
export HL_TB_URL=https://tb.example.com
export HL_TB_TOKEN=...
export HL_PG_DSN='postgresql://user:pass@127.0.0.1:5432/telemetry'
hybrid-ladder sum --source thingsboard \
  --series 6f2c...:L_LSJ1_DB_EP \
  --start 2026-01-01 --end 2026-10-21T18:49:59 \
  --mode mixed --materialize

# 校验 / 修复
hybrid-ladder verify --source thingsboard --series ... --start ... --end ...
hybrid-ladder repair --source thingsboard --series ... --start ... --end ...
```

### HTTP API

```bash
hybrid-ladder serve --port 8000
# OpenAPI 文档：http://127.0.0.1:8000/docs
```

```bash
# 分解（同步）
curl "http://127.0.0.1:8000/v1/decompose?start_ts=1767196800000&end_ts=1792512599000"

# 求和（异步任务）
curl -X POST http://127.0.0.1:8000/v1/ladder/sum \
  -H 'content-type: application/json' \
  -d '{"series":[{"entity":"demo-chiller-1","key":"energy"}],
       "start_ts":1767196800000,"end_ts":1777564800000,"mode":"tb"}'

curl http://127.0.0.1:8000/v1/tasks/<task_id>

# 小查询可以直接同步
curl -X POST "http://127.0.0.1:8000/v1/ladder/sum?sync=true" ...
```

成功返回 `{"code":0,"data":...}`，失败返回 `{"code":1,"detail":...}`，与 AutoTestHub 现有契约一致。完整接口见 [`docs/api.md`](docs/api.md)。

### MCP

```bash
pip install -e ".[mcp]"   # from the source checkout
hybrid-ladder mcp
```

工具：`ladder_meta`、`ladder_decompose`、`ladder_sum`、`ladder_verify`。配置与 HTTP API 相同的 `HL_*` 环境变量；不配置时用内置 demo 数据，开箱即用。

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

把 [`skills/hybrid-recursive-ladder/`](skills/hybrid-recursive-ladder/) 复制到 Agent 的技能目录（如 `~/.claude/skills/` 或 `~/.zcode/skills/`）。技能里写清了何时使用、如何调用 CLI/API、如何解释 `null` 与 `0.0`、以及 TB 的坑。

## 规则（不可协商）

1. **左闭右开** `[start, end)`。终点正好是整点时，该整点不属于区间。
2. **只取完整单位**。月/日/时/分只有整体落在区间内才在本层输出。
3. **残段向下拆**。左残段和右残段都交给下一层；不足一分钟的零头单独成段。
4. **本地日历**。按配置的 IANA 时区（默认 `Asia/Shanghai`）对齐。
5. **铺满不变量**。段与段首尾相接、不重不漏，并集恰为 `[start, end)`。

### 值语义

| 值 | 含义 | 展示 |
|---|---|---|
| `null` | 该段没有任何采样 | `—` |
| `0.0` | 有采样，但求和为 0 | `0` |
| 数字 | 采样求和 | 数字 |

每段带 `cnt`（实际点数/桶数）、`expected`（应有桶数，仅数据源段）、`source`（`local` / `tb` / `mixed` / `empty` / `uncovered`）。`cnt` 明显低于 `expected` 表示数据稀疏——合计仍按实际点计算，不会补数。

## 适配器

引擎只依赖两个极小的结构化接口（[`protocols.py`](src/hybrid_ladder/protocols.py)）：

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

内置：

* **`MemorySource` / `MemoryStore`** — 测试、演示、小型嵌入场景。
* **`ThingsBoardSource`** — REST 遥测，封装了 TB 的全部已知怪癖。
* **`PostgresStore`** — 按月分区的 `readings` + `coverage` 表，幂等 upsert，批量区间求和。

InfluxDB / Prometheus / ClickHouse / TimescaleDB 只需实现上述方法即可接入。见 [`docs/architecture.md`](docs/architecture.md)。

## 本地优先读路径

```
对每个段：
    按覆盖区间切成「已覆盖 / 未覆盖」
    已覆盖部分 → 一条批量本地 SQL 求和
    未覆盖部分 → 数据源（整段走分组聚合；部分覆盖只补缺的那一截）
    段值 = 本地部分 + 数据源部分
    来源 = local / tb / mixed / empty / uncovered
```

覆盖只登记到 `now - 5 分钟`，正在发生的尾段永远不算可信本地。未覆盖段查完数据源后**无论有没有数据都登记**（「这段查过了」），避免下次重复请求。重写区间前先清除覆盖：中途失败也不会留下「指向不完整数据」的覆盖记录。

## 校验与修复

* **校验**：先段级比对数据源（权威）与本地，差异段再逐点定位，统计 `added` / `removed` / `changed`，默认最多展开 50 段。
* **修复**：删除本地区间，按 366 天分窗从数据源重拉，重新登记覆盖。数据源删除的点会在本地消失。

## 保证

* `sum` **精确**：所有段之和 = 数据源在区间内所有点之和，无近似、无采样。
* 重复固化**幂等**：主键保证同一时间戳只有一行。
* 空段**不会静默按 0 计入**：`total` 排除空段，`empty_count` 单独报告。
* 算法**只读**数据源，从不写入 ThingsBoard。

## 已知限制

* **v0.0.2 只做 sum**：平均需要 sum+cnt 加权；累计量差分需要每段首值（TB 没有 FIRST 聚合），暂未上阶梯。
* **数据完整 ≠ 加法正确**：数据源缺采样时，合计会偏小；用 `cnt/expected` 识别稀疏。
* **TB 限制**：区间聚合 700 桶可、800 桶拒（默认 500）；原始序列单次 1 万点；`COUNT` 会吞同分钟重复点。
* **后台任务在进程内存**：重启即丢，结果可重算，固化数据不丢。
* **DST 时区**：日历边界支持，但固定桶长意味着日/时折叠更适合固定偏移时区（如 `Asia/Shanghai`）。
* **v0.0.1 修复的两个原实现问题**：多层级取数分组错误；原始点二分丢掉恰好落在中点的点。两者都有回归测试。

## 实测性能

来自生产 AutoTestHub 部署（2026-10，单序列，ThingsBoard over VPN；具体数字随网络与数据密度变化）：

| 场景 | 段数 | 请求数 | 时间 | 结果 |
|---|---:|---:|---:|---|
| 2 天，分钟级 | 69 | ~4 | 0.64 s | 2,217,024.0（与 2,566 个原始点一致） |
| 1 年，日级 | 42 | ~4 | 冷 1.18 s / 热 0.20 s | 36,012,018.25 |
| 10 个月，混合层级 | 97 | ~5–7 | 亚秒级 | 省掉 423,049 个分钟桶 |
| 本地读，42–90 段 | — | 0 | 9–19 ms | 一条 SQL |
| 混合读（3 本地 + 1 数据源） | 4 | 1 | 0.31 s | 与纯数据源一致 |
| 校验/修复（篡改 1 点） | — | — | — | 发现 1 点 → 修复 360 点 → 0 差异 |

见 [`docs/benchmarks.md`](docs/benchmarks.md)。想不连服务器复现段数/请求数：

```bash
python examples/benchmark.py
```

## 项目结构

```
src/hybrid_ladder/
  core.py          纯函数：分解、折叠、覆盖切分
  engine.py        数据源/混合/本地读、固化、校验、修复
  models.py        Segment、SeriesRef、LadderConfig、QueryResult
  protocols.py     TimeSeriesSource / PointStore
  sources/         memory.py, thingsboard.py
  stores/          memory.py, postgres.py
  api.py           FastAPI
  cli.py           hybrid-ladder CLI
  mcp_server.py    MCP 工具
  tasks.py         进程内任务注册表
  demo.py          确定性演示数据
tests/             单测 + API + 适配器测试
docs/              算法、架构、API、性能
skills/            Agent 技能包
examples/          可运行示例
```

## 开发

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

## 路线图

* `avg` 与累计量差分上阶梯（加权 sum + 每段首值）
* InfluxDB / Prometheus / ClickHouse 适配器
* Celery/RQ 任务后端，支持多进程部署
* OpenTelemetry 指标与请求计数
* 打 tag 时自动发布 PyPI

## 引用

如果你使用了本项目，请引用：

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

该方法同时以[公开披露](docs/defensive-publication.md)的形式发布，作为现有技术。GitHub 的 “Cite this repository” 会读取 [`CITATION.cff`](CITATION.cff)。仓库在 Zenodo 归档后会补充 DOI。

## 许可证

[MIT](LICENSE) © 2026 MagicSquarekey
