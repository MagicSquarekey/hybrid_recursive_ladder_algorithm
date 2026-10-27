# Hybrid Recursive Ladder（中文参考）

**语言 / Languages:** [English](SKILL.md) · [简体中文](SKILL.zh-CN.md)

> 这是 `SKILL.md` 的中文参考译本。实际安装 Agent 技能时请使用 `SKILL.md`；
> 本文件用于中文阅读与审阅。

## 功能

把 `[start, end)` 切成**完整日历单位**（月 → 日 → 时 → 分），逐层剥离完整
单位，把残边递归推到下一层更细层级。然后每层用下一层更细聚合只取一次，并本地
折叠。10 个月区间变成约 97 段、约 5–7 次数据源请求，而不是 423,049 个分钟桶。

软件包还提供本地优先读路径：把原始点固化到 PostgreSQL（或内存），已覆盖子区间
读本地，只从数据源取缺失的切片。校验和修复把数据源（权威）与本地副本进行对比。

## 何时使用

当**全部**满足时使用：

* 数据是时间序列，数据源支持区间聚合和原始点读取（ThingsBoard，或自定义
  `TimeSeriesSource`）。
* 你需要对长区间（小时到年）做**求和**。
* 请求数、延迟或离线读取很重要。

**不要**用于：

* 当前版本的平均值或累计量差分规则（平均值需要加权 sum+count；累计量差分需要
  每段首值）。
* 非可加指标或事件流。
* 不支持区间聚合的数据源——先实现两方法协议。

## 安装

```bash
# v0.0.5 GitHub Release wheel
pip install https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm/releases/download/v0.0.5/hybrid_recursive_ladder-0.0.5-py3-none-any.whl

# 可选依赖：克隆后安装
git clone https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm.git
cd hybrid_recursive_ladder_algorithm
pip install -e ".[thingsboard,postgres,api,mcp]"
```

## 快速路径（无需配置）

```bash
hybrid-ladder demo          # 端到端：分解 → 固化 → 混合读 → 校验
hybrid-ladder decompose --start 2026-01-01 --end 2026-10-21T18:49:59
```

## 典型工作流

1. **查看分解**（便宜，不访问数据）：

   ```bash
   hybrid-ladder decompose --start <start> --end <end> --finest minute
   ```

   预期会看到月 + 日 + 时 + 分 + 一个零头。如果段数巨大，说明区间很长，或者
   `finest` 太细。

2. **从数据源求和**：

   ```bash
   export HL_TB_URL=https://tb.example.com
   export HL_TB_TOKEN=...
   hybrid-ladder sum --source thingsboard \
     --series <device_id>:<key> \
     --start <start> --end <end> --json
   ```

3. **启用本地优先读**（可选，但重复查询推荐）：

   ```bash
   export HL_PG_DSN='postgresql://user:pass@127.0.0.1:5432/telemetry'
   hybrid-ladder sum --source thingsboard --series ... --start ... --end ... \
     --mode mixed --materialize
   ```

4. **校验**本地副本，必要时修复：

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
print(result.rows[0].tb_ranges)   # 仍然缺本地的区间
```

关键方法：`decompose`、`sum`、`sum_local`、`sum_mixed`、`materialize`、
`verify`、`repair`。每个长方法都接受 `progress(done, total, message)` 和
`cancel() -> bool`。

## HTTP API / MCP

```bash
hybrid-ladder serve --port 8000     # OpenAPI 在 /docs
hybrid-ladder mcp                   # stdio MCP server
```

HTTP 端点：

* `GET /v1/decompose?start_ts=&end_ts=&finest=`
* `POST /v1/ladder/sum`（异步任务）与 `POST /v1/ladder/sum?sync=true`
* `POST /v1/ladder/verify`、`/repair`、`/materialize`
* `GET /v1/tasks/{id}`、`POST /v1/tasks/{id}/cancel`

成功信封：`{"code":0,"data":...}`；错误：`{"code":1,"detail":...}`。

MCP 工具：`ladder_meta`、`ladder_decompose`、`ladder_sum`、`ladder_verify`。

## 输出语义（重要）

| 字段 | 含义 |
|---|---|
| `value: null` | 该段无采样——显示为 `—`，**不是** `0` |
| `value: 0.0` | 有采样且求和为 0——显示为 `0` |
| `cnt` | 观测到的点数（数据源）或桶数（本地） |
| `expected` | 该段应包含的桶数（仅数据源段） |
| `source` | `local`、`tb`、`mixed`、`empty`、`uncovered` |
| `tb_ranges` | 仍缺本地的合并区间（作为固化输入） |
| `total` | 非空段值之和；空段不计入 |
| `empty_count` | 无数据段的数量 |

`cnt` 相对 `expected` 很低表示数据稀疏。合计对存在的点是正确的；它不是对缺失
数据的估计。

## 不可协商的规则

* `[start, end)`——左闭右开。结束时间正好在边界上时，不产生该边界的段。
* 每一层只输出完整单位；残边向下递归。
* 不足一分钟的余数作为独立零头段，按原始点读取。
* 边界使用配置的 IANA 时区（默认 `Asia/Shanghai`）。

## ThingsBoard 坑（适配器已处理）

* 区间聚合约接受 700 个桶，拒绝 800 个——默认 500。
* 桶时间戳是 `bucket_start + bucket_ms / 2`；适配器会转换回桶起点。
* 没有 `FIRST` 聚合——首值规则需要原始点。
* `COUNT` 会吞同分钟重复点——精确点数用原始点。
* `endTs` 包含端点；适配器把原始点过滤到 `[start, end)`。

## 校验清单

* 各段之和等于数据源在同一区间上的原始点之和。
* `empty_count` 与无采样段一致；零值段不算空段。
* 重复固化幂等（同一时间戳不会重复）。
* 干净固化后 `verify` 报告 0 差异。
* 篡改一个本地点能被发现并修复。
* 覆盖永远不包含正在进行的尾段（默认 5 分钟宽限）。

## 参考

* 算法：`docs/algorithm.zh-CN.md`（英文：`docs/algorithm.md`）
* 架构与适配器协议：`docs/architecture.zh-CN.md`
* API：`docs/api.zh-CN.md`
* 性能：`docs/benchmarks.zh-CN.md`
