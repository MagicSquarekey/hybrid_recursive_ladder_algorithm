# 相关工作与定位

**语言 / Languages:** [English](related-work.md) · [简体中文](related-work.zh-CN.md)

> **定位。** Hybrid Recursive Ladder 是一个**面向「每请求桶数有上限」的时序 API 的查询规划方法**，不是一个全新的通用聚合理论。它面向「能读区间聚合接口、但不能写源端、也不能改源端存储/降采样策略」的部署。它的分解是「规范区间分解」在日历混合进制上的实例；它的折叠是 roll-up；多分辨率聚合是 RRDtool、Whisper、BTrDB 的核心。真正属于本项目的，是组合方式：一次查询跨多个日历经度做请求计划，每层只按「下一级更细」抓一次，本地覆盖补缺口，并且整个计划受源端每请求桶数上限约束。

本文记录我们找到的最接近的系统与历史算法，用于 README 和算法规范中的引用，也用于明确贡献边界。

## 一、问题为什么真实存在

大多数时序 API 会限制单次请求的桶数或点数。Prometheus 的 `query_range` 对每条序列最多返回 11,000 个点（`web/api/v1/api.go`）；本项目实测的 ThingsBoard 部署接受约 700 个桶、拒绝 800 个。一个「每个统计桶问一次」的客户端，等于每个输出单位付一次网络往返。

ladder 保留输出粒度（月、日、时、分），但让源端请求数取决于区间的粗粒度单位，而不是细桶的数量。

## 二、最接近的系统

| 系统 | 机制 | 重叠点 | 差异 |
|---|---|---|---|
| [RRDtool](https://github.com/oetiker/rrdtool-1.x) | 多个 RRA 归档，不同分辨率；用 `AVERAGE`、`MIN`、`MAX`、`LAST` 等 consolidation 函数把细粒度 PDP 算成粗粒度 CDP。 | 多分辨率存储；粗值由细值得到。 | 存储侧；固定 `step`；没有日历层级；不做按请求上限的查询规划。 |
| [Whisper](https://github.com/graphite-project/whisper) | 多个 archive tier，精度逐级下降；高精度数据逐步降级到低精度归档。 | 与 RRDtool 相同的多分辨率归档思想。 | 存储侧；固定归档定义；没有查询分解。 |
| [BTrDB](https://github.com/BTrDB/btrdb-server) | 时间分区、带版本、copy-on-write 的树；每个节点存该时间槽的 min/max/mean/count；时间槽按 2 的幂对齐。 | 对齐时间分区、层级统计、多分辨率查询。 | 数据库引擎，统计量在写入时维护；按 2 的幂对齐而不是日历单位；不是外部 API 的查询规划器。 |
| [TimescaleDB 层级连续聚合](https://github.com/timescale/docs/blob/latest/use-timescale/continuous-aggregates/hierarchical-continuous-aggregates.md) | 在 continuous aggregate 之上再建 continuous aggregate；分钟级数据汇总成小时、日级视图。 | 日历时间桶；层级 roll-up；查询可以命中最粗层。 | 预计算物化视图；绑定 schema；没有每请求桶数硬上限；不能对任意未预定义的区间按需计算。 |
| [Apache Druid](https://druid.apache.org/docs/latest/querying/granularities/) | 写入时 rollup；`PeriodGranularity` 支持 `P1M`、`P2D` 等 ISO8601 周期，月份从每月 1 号开始，支持时区。 | 日历经度对齐的桶；rollup。 | 一次查询一个 granularity；rollup 在写入时完成；没有多层级请求计划。 |
| [`timescaledb-rollups`](https://github.com/lballoriani/timescaledb-rollups) | SQL 管道：minute → hour → day → week → month 的连续聚合级联，每层独立保留期；查询命中最粗的可回答层。 | 项目形态最接近：层级日历 roll-up。 | 存储侧管道；要求控制数据库；不面向外部 API，没有桶数上限，也没有按 coverage 补抓。 |
| [`accreta`](https://github.com/StoyanTc/accreta) | `Monoid`/`Aggregator` trait，可合并状态；面向层级 roll-up，带多语言绑定。 | 跨层级可合并聚合。 | 聚合库，不是查询规划器。 |
| [`quantum`](https://github.com/marqeta/quantum) | 预计算多个时间窗口的聚合结果放 Redis，查询 O(1)。 | 避免逐桶查询。 | 预计算 + 缓存；不是按需计算；没有日历层级。 |
| [`brein-time-utilities`](https://github.com/Breinify/brein-time-utilities)、[`ankane/rollup`](https://github.com/ankane/rollup) | `BucketTimeSeries`/`IntervalTree`；Rails rollup 表。 | 时间桶与 rollup。 | 库或存储侧；固定粒度；不做请求规划。 |

我们也查了 ThingsBoard 生态。能找到的公开项目基本是导出/下载工具（[`thingsboard-export`](https://github.com/DPIclimate/thingsboard-export)、[`tb-download`](https://github.com/fargiolas/tb-download)）：它们分页或直接下载，但没有做多层级聚合规划。

## 三、历史算法

### 3.1 规范区间分解

线段树（segment tree，Bentley，1977）用一个 O(log n) 的「对齐节点」集合覆盖查询区间 `[l, r)`。Fenwick 树（1994）和稀疏表（sparse table）用的是同一种「对齐块」思想。ladder 是它在日历混合进制上的版本。

区别在目标。线段树会把相邻兄弟合并成父节点，因为它只要一个聚合结果；ladder 必须为每个输出单位返回一个值，所以不能跨层合并，只能把每个完整单位都发出来，再用层级来规划抓取。如果只想要一个 grand total，理论上可以合并成更少的规范块；现在的设计不这么做，是产品语义决定的。

### 3.2 日历混合进制算术

递归本身就是混合进制下的贪心展开：月、日、时、分。「剥掉完整单位、余数下沉」这个模式在日历算术库里随处可见（`dateutil.relativedelta`、Java `Period`、Rust `jiff` 的 span），在 temporal database 的「时间粒度」研究里也有正式讨论（Jensen 等，1992/1994）。分解本身不新。

### 3.3 多分辨率聚合

RRDtool（Oetiker，1999）存多个 RRA，把细粒度 PDP 合并成粗粒度 CDP；Whisper 用 archive tier；BTrDB（FAST'16）在时间分区树里存每个节点的统计量；OLAP data cube（Harinarayan、Rajaraman、Ullman，1996）沿维度层级预计算 roll-up；Mallat 的多分辨率分析（1989）在信号处理里形式化了「粗层由细层得到」。ladder 的方向相同，但用的是精确的日历单位，不是 wavelet 或 2 的幂尺度。

### 3.4 层级时间结构

层级时间轮（hierarchical timing wheels，Varghese & Lauck，1987/1997）把定时器分到不同层级，到期后从粗层 cascade 到细层；calendar queue（Brown，1988）用类似日历的桶做离散事件模拟。结构上它们和 ladder 的「层级 + 余数下沉」最像，但用途是调度，不是聚合。

### 3.5 查询侧的单粒度降采样

Prometheus 的 `query_range` 有每条序列 11,000 点的硬上限，且只有一个 `step`；Grafana 根据 `maxDataPoints` 和区间算出一个 interval；Druid 的 period granularity 和 TimescaleDB 的 `time_bucket` 也是一次查询一个日历经度。ladder 的区别是在一次查询里规划多个粒度，并把「输出粒度」与「抓取粒度」解耦。

## 四、哪些是新，哪些不是

**不新：**

* 日历分解与混合进制展开；
* 规范对齐区间分解；
* roll-up / consolidation；
* 多分辨率存储与查询；
* 日历对齐的桶；
* 本地缓存与物化视图。

**作为组合是新的：**

* 把日历层级当作查询计划，而不只是显示桶；
* 每层只按「下一级更细」抓一次，再本地折叠；
* 按「取数层级 + 连续性」分组，让不同输出层共享请求；
* 按本地 coverage 切分，只补抓未覆盖的子区间；
* 让请求数成为「粗粒度单位数 + 源端桶数上限」的函数，边界见 `docs/algorithm.md` §5.3–5.5。

## 五、可辩护的新颖性表述

> 一种面向「每请求桶数有上限」的时序 API 的区间聚合查询规划方法：把区间分解为完整的日历单位，对每个「取数层级相同且时间连续」的最大 run，用下一级更细的聚合抓取一次，再在本地折叠；从而使源端请求数与输出单位数解耦，并受源端每请求桶数上限约束。

论文或专利披露里用这个表述。不要写「提出了一种新的时间序列聚合算法」或「首个……」，这两种说法很容易被 RRDtool、BTrDB、TimescaleDB 或线段树的先例挑战。

## 六、可直接引用的 Related work 段落

> Range aggregation over time-series APIs is usually addressed either by pre-aggregation or by single-granularity downsampling. Multi-resolution stores maintain coarser tiers or per-node summaries and answer a query at a chosen resolution (RRDtool; Whisper; BTrDB). OLAP-style systems precompute hierarchical roll-ups, including TimescaleDB's hierarchical continuous aggregates and Druid's ingestion-time rollup with calendar-aware period granularities. Query-side systems instead choose one uniform step under a point cap, as in Prometheus's 11,000-point limit and Grafana's `maxDataPoints` interval calculation. The Hybrid Recursive Ladder plans a single query across multiple calendar levels: it partitions the range into complete calendar units, fetches each maximal contiguous run sharing a fetch level once at the next finer aggregation, and folds the returned buckets locally. This decouples the number of source requests from the number of output units and bounds it by the source's per-request bucket limit. Its decomposition is the calendar mixed-radix analogue of the canonical interval decomposition used by segment trees, with partial edges pushed to finer levels.

## 七、参考文献

1. RRDtool — <https://github.com/oetiker/rrdtool-1.x>；RRA 定义见 `doc/rrdcreate.pod`。
2. Whisper — <https://github.com/graphite-project/whisper>。
3. M. P. Andersen and D. E. Culler, "BTrDB: Optimizing Storage System Design for Timeseries Processing," USENIX FAST 2016 — <https://www.usenix.org/conference/fast16/technical-sessions/presentation/andersen>。
4. TimescaleDB, "Hierarchical continuous aggregates" — <https://github.com/timescale/docs/blob/latest/use-timescale/continuous-aggregates/hierarchical-continuous-aggregates.md>。
5. Apache Druid, "Granularities" — <https://druid.apache.org/docs/latest/querying/granularities/>。
6. Prometheus, `query_range` 点数上限 — <https://github.com/prometheus/prometheus/blob/main/web/api/v1/api.go#L1102>。
7. Grafana, `calculateInterval` — <https://github.com/grafana/grafana/blob/main/packages/grafana-data/src/datetime/rangeutil.ts#L592>。
8. J. L. Bentley, "Solutions to Klee's rectangle problems," 1977（线段树）；概述：<https://en.wikipedia.org/wiki/Segment_tree>。
9. P. M. Fenwick, "A new data structure for cumulative frequency tables," *Software: Practice and Experience*, 1994 — <https://doi.org/10.1002/spe.4380240306>。
10. G. Varghese and A. Lauck, "Hashed and hierarchical timing wheels," IEEE/ACM Transactions on Networking, 1997 — <https://doi.org/10.1109/90.650142>。
11. R. Brown, "Calendar queues: a fast O(1) priority queue implementation for the simulation event set problem," *Communications of the ACM*, 1988 — <https://doi.org/10.1145/63039.63045>。
12. V. Harinarayan, A. Rajaraman and J. D. Ullman, "Implementing data cubes efficiently," ACM SIGMOD 1996 — <https://doi.org/10.1145/235968.233333>。
13. S. Mallat, "A theory for multiresolution signal decomposition: the wavelet representation," *IEEE TPAMI*, 1989 — <https://doi.org/10.1109/34.192463>。
14. C. S. Jensen et al., "A consensus glossary of temporal database concepts," ACM SIGMOD Record, 1994 — <https://doi.org/10.1145/181550.181560>。

## 八、检索范围与局限

* GitHub 只做了仓库级搜索；未认证的 code search 不可用，所以大型仓库内部的实现可能漏掉。
* 检索了 arXiv、Crossref 和上述项目的 raw documentation；当前环境无法访问 Wikipedia、通用搜索引擎和中文博客平台。
* 没有检索专利库（Google Patents、Espacenet、USPTO、CNIPA）和 CNKI。本文没有命中，不等于不存在。
* 检索日期为 2026-10-22。Star 数和文档会变化；链接在该日期核对过。

如果你要写论文、申请专利或做 FTO（自由实施）检索，按 [`prior-art-search.zh-CN.md`](prior-art-search.zh-CN.md) 的可执行流程再做一轮。
