# 混合递归阶梯：公开披露

**语言 / Languages:** [English](defensive-publication.md) · [简体中文](defensive-publication.zh-CN.md)

> 本文是英文原文 [`defensive-publication.md`](defensive-publication.md) 的中文参考译文。
> 英文原文为准；如中英文有歧义，以英文原文为准。

**作者：** MagicSquarekey  
**日期：** 2026-10-22  
**版本：** 0.0.5  
**许可证：** MIT  
**仓库：** <https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm>  
**DOI：** [10.5281/zenodo.23656844](https://doi.org/10.5281/zenodo.23656844)

## 目的

本文公开 Hybrid Recursive Ladder 方法及其形式化性质，作为现有技术（prior
art）。作者不打算为该方申请专利保护。本披露力求可实施（enabling）：同一公开
仓库中附有规范性算法规范、完整开源实现、测试套件和可复现基准。

这是技术披露，不是专利申请。它不授予专利权，也不替代法律意见。其目的是把该
方法放入公共记录，使本文描述的具体组合可以作为现有技术使用。

## 摘要

长区间时序查询常常受请求数限制，而不是受算术限制。许多 API 限制单次请求返回
的桶数或点数。逐桶客户端因此每输出一个单位就要付一次网络往返。Hybrid
Recursive Ladder 是一种查询规划方法：把区间分解为完整日历单位（月、日、时、
分），对共享同一取数层级的最大连续 run 用下一层更细聚合只取一次，再把返回的
桶本地折叠成输出单位。可选的覆盖跟踪会按已固化数据切分区间，只取缺失的子区间。
该方法面向带单请求桶数硬上限的只读区间聚合端点。它是已知技术的组合——日历混
合基数分解、规范区间分解、roll-up 与多分辨率聚合——不是关于时序聚合的新通用
理论。

## 1. 问题

考虑区间 `[s, e)` 和一个单次最多返回 `K` 个桶的区间聚合 API。逐桶客户端大致
每个输出单位发一次请求，另加边界请求。对于两天分钟级区间，就是 2,880 个桶；
在一次实测 ThingsBoard 部署中，1,140 个桶经 VPN 耗时 139 秒。

瓶颈是网络往返次数。预聚合和单一粒度降采样是常见修法，但它们要么需要数据源
的写权限，要么牺牲输出粒度。

## 2. 方法

### 2.1 日历分解

把 `[s, e)` 切分成完整日历单位的段，从月一直到配置的最细层（默认：分）：

1. 每一层只输出完全落在区间内的单位。
2. 把左残边和右残边推到下一层更细层级。
3. 在最细层，把不足一个单位的余数作为独立的“零头”输出。

```
ladder(a, b, level):
    if a >= b: return []
    if level is finest: emit(a, b); return

    if unit_start(a, level) != a:
        nb = next_boundary(a, level)
        if nb >= b: ladder(a, b, next_level); return
        ladder(a, nb, next_level)
        a = nb

    while next_boundary(a, level) <= b:
        nb = next_boundary(a, level)
        emit(a, nb, level)
        a = nb

    if a < b: ladder(a, b, next_level)
```

分解有三个有用性质：

* 段有序、连续、不重叠，且精确铺满区间；
* 比最细层粗的每一段都是完整日历单位；
* 在最细层，最多有两个段是部分的（左残边和零头）。

段数由最粗的完整单位加一个常数界定。对于默认层级，
`N <= N_month + 639`，其中常数是对两个残月、残日和残时的保守上界。递归深度
最多为层级数（默认 4）。

### 2.2 取数计划

输出层级决定输出粒度，不决定取数粒度。对每个输出层级，在一个连续 run 上用
下一层更细聚合取一次，然后本地折叠：

| 输出层 | 取数层 |
|---|---|
| 月 | 日 |
| 日 | 时 |
| 时 | 分 |
| 分 | 分 |
| 不足一分钟的零头 | 原始点 |

取数 run 按**取数层级 + 时间连续性**分组，绝不只按时间连续性。时和分可以共
享一次分钟级取数；月和日不能共享一次取数。只按相邻分组会导致多层级区间被按
最粗层取数，把一整天的值赋给第一个小时，并丢掉其余部分。

对于一个时长为 `T`、取数桶长为 `Δ` 的 run，适配器把 run 切成 `K * Δ` 的窗口，
发出

```
r(run) = ceil(T / (K * Δ))
```

次请求。总聚合请求数是各 run 之和。常见的连续情况下最多有三个聚合 run（日、
时、分），所以和最多三项。由于月输出的日桶数随完整月数增长，而时桶和分桶只
出现在两个残月及其边缘的残日：

```
R_agg = O(N_month / K + 1).
```

请求数随粗粒度单位数除以单请求上限增长，不随分钟桶数增长。零头的原始点取数
取决于数据量，对于 `P` 个点需要 `O(P / max_points)` 次请求。

### 2.3 本地优先覆盖

有本地点存储时，每个输出段按合并后的覆盖区间切成已覆盖和未覆盖子区间：

1. 已覆盖子区间用一条批量本地查询求和。
2. 完整未覆盖的段用分组聚合取数。
3. 部分覆盖的段只取缺失的子区间。
4. 段值 = 本地部分 + 数据源部分。

覆盖只记录到 `now - grace`；正在进行的尾段永远不被视为可信本地数据。重写请求
之前会先使覆盖失效，因此失败的拉取会被重新取数，而不是被信任。

### 2.4 折叠正确性

`fold_sum` 把取数桶归属于包含该桶起点的输出段。如果每个取数桶都完全落在一个
输出段内，或与它不相交，则折叠和等于数据源在该段上的和。固定偏移时区满足这
一点，因为每个日历单位都是固定大小桶的并集。在 DST 时区，日或时的边界可能落
在固定大小桶的内部；在切换点附近应使用更细的取数层或原始点。

## 3. 形式化性质

规范性规范是 [`algorithm.zh-CN.md`](algorithm.zh-CN.md)（英文原文
[`algorithm.md`](algorithm.md)）。它包含：

* **引理 1（双边引理）：** 传给更细层的区间部分最多位于当前层的两个单位内；
  每个完整单位都在自己的层级输出。
* **命题 2（有界细化）：** `N_day <= 62`、`N_hour <= 96`、`N_minute <= 480`、
  `tail <= 1`，因此默认层级下 `N <= N_month + 639`。
* **推论 3：** 总段数为 `N_month + O(1)`。
* **命题 4：** 递归深度最多为层级数。
* **第 5.4 节：** 精确的每 run 请求模型和 `R_agg = O(N_month / K + 1)`。
* **第 5.5 节：** 折叠正确性的对齐条件。

## 4. 现有技术与差异

该方法是已知思想的组合。最接近的系统和算法记录在
[`related-work.zh-CN.md`](related-work.zh-CN.md)（英文原文
[`related-work.md`](related-work.md)）中，并附有参考文献。摘要如下：

| 现有技术 | 重叠 | 差异 |
|---|---|---|
| RRDtool、Whisper | 多分辨率归档；由细值得到粗值 | 存储侧；固定 step；无日历层级；不做请求规划 |
| BTrDB | 对齐时间分区与层级摘要 | 数据库引擎；2 的幂对齐；不是外部 API 规划器 |
| TimescaleDB 层级连续聚合 | 分 → 时 → 日 roll-up | 预计算物化视图；没有单请求桶数硬上限 |
| Apache Druid 周期粒度 | 带时区的日历对齐桶 | 一次查询一个粒度；摄入时 rollup |
| Prometheus / Grafana | 点数上限与单步降采样 | 单一均匀 interval；没有多层级计划 |
| 线段树 | 规范对齐区间分解 | 为单个聚合合并兄弟节点；阶梯需要每个输出单位一个值 |
| 层级时间轮 | 层级 + 余数级联 | 定时器调度，不是聚合 |

本文公开的具体组合是：

1. 把日历层级当作查询计划，而不只是展示桶；
2. 只输出完整日历单位，把残边推到更细层；
3. 对共享同一取数层级的最大 run 用下一层更细聚合取一次，并本地折叠；
4. 按取数层级 + 连续性分组，使请求可以跨输出层共享；
5. 按本地覆盖切分，只取未覆盖子区间；
6. 在单请求桶数硬上限下规划请求数。

## 5. 不主张的内容

本披露不主张：

* 新的时序数据库、存储引擎或压缩格式；
* 新的索引结构；
* 新的日历算术库；
* 第一个多分辨率聚合系统；
* 任何专利权。

它以 MIT 许可证公开一个查询规划组合和开源实现。

## 6. 引用

```bibtex
@software{hybrid_recursive_ladder_2026,
  author  = {MagicSquarekey},
  title   = {Hybrid Recursive Ladder: Query Planning for Bucket-Limited Time-Series APIs},
  year    = {2026},
  version = {0.0.5},
  license = {MIT},
  doi     = {10.5281/zenodo.23656844},
  url     = {https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm}
}
```

归档版本：[10.5281/zenodo.23656844](https://doi.org/10.5281/zenodo.23656844)
（记录：<https://zenodo.org/records/23656844>）。所有版本的 concept DOI 是
[10.5281/zenodo.23556605](https://doi.org/10.5281/zenodo.23556605)。
[`CITATION.cff`](../CITATION.cff) 以 Citation File Format 提供相同元数据；
GitHub 的 “Cite this repository” 按钮读取它。

## 7. 完整性与状态

本文是 `v0.0.5` 发布的一部分。该 tag 上的规范实现是
`src/hybrid_ladder/` 中的 Python 包；规范算法文档是
[`algorithm.zh-CN.md`](algorithm.zh-CN.md)（英文原文
[`algorithm.md`](algorithm.md)）。公开仓库历史和 GitHub Release 提供披露日期。
