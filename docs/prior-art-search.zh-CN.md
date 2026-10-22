# 现有技术检索实操方案（论文 / 专利 / FTO）

> 这不是法律意见。涉及专利申请或自由实施（FTO）时，本文只帮你把材料准备好，最终判断请交给专利代理师或律师。

如果你从没做过现有技术检索，按下面的顺序做即可。核心原则只有一句：**不要搜项目名，搜机制。**

## 0. 先确定你要的是哪一种

三种检索的目标不同，不要混在一起：

| 目标 | 要回答的问题 | 建议投入 | 产出 |
|---|---|---|---|
| 论文相关工作 | 我的贡献和谁最接近？差异是否站得住？ | 2–4 天；先自己查，再请图书馆员补漏 | Related work 一节 + 差异段 |
| 专利可行性 | 这个方案有没有可能被授予专利？ | 先自己做 1 周预检，再请专业检索 | 特征对比表 + 初步新颖性判断 |
| FTO（自由实施） | 我实施这个方案会不会侵犯别人的专利权？ | 必须请专业检索 + 律师意见 | FTO 报告 |

如果你只是想把 README 写得更可信、或准备投论文，做到第 6 节就够了。如果你准备申请专利，至少做到第 7 节，然后找专业的人。

## 1. 一张「特征表」是全部检索的核心

先把你的方案拆成可检索的机制，而不是一个名字。下面这张表可以直接用：

| # | 特征 | 你项目里的具体做法 | 建议检索词 |
|---|---|---|---|
| F1 | 日历层级分解 | 月 → 日 → 时 → 分，按完整单位切 | calendar hierarchy, time granularity, multi-level time buckets |
| F2 | 只输出完整单位，余数下沉 | 左右残段递归到下一层，最细层留 tail | aligned interval decomposition, canonical interval, remainder recursion |
| F3 | 每层按「下一级更细」抓取 | 月按日抓、日按时抓、时按分抓 | hierarchical aggregation, roll-up, consolidation, multi-resolution |
| F4 | 按取数层级 + 连续性分组 | 同 fetch level 且相邻的段共用一个请求 | query planning, request batching, aggregation pushdown |
| F5 | 本地覆盖补抓 | 按 coverage 切成已覆盖/未覆盖，只补缺口 | materialized view, coverage, gap filling, cache |
| F6 | 每请求桶数上限 | `max_intervals=500`，按 `K*Δ` 分窗 | bucket limit, max data points, interval limit, point cap |
| F7 | 输出粒度与抓取粒度解耦 | 输出是月/日/时/分，抓取可以更细 | output granularity vs fetch granularity, decoupled resolution |

同时写一张「**非特征**」表，明确你不主张什么：

* 不是新的时序数据库；
* 不是新的压缩算法；
* 不是新的索引结构；
* 不是新的日历算术库；
* 不是第一个多分辨率聚合系统。

这张表在跟代理师/律师沟通时非常有用：它能防止对方把检索范围做得过宽，也能防止你把别人的先例误当成自己的创新。

## 2. 关键词矩阵与检索式

### 2.1 关键词矩阵

| 概念 | 英文 | 中文 | 同义词/近义词 |
|---|---|---|---|
| 时序 | time series, telemetry, metrics | 时间序列、遥测、指标 | time-stamped data, sensor data |
| 聚合 | aggregation, rollup, consolidation | 聚合、汇总、上卷 | summarize, downsample, reduce |
| 层级 | hierarchy, multi-level, multi-resolution | 层级、多级、多分辨率 | tiered, cascaded, pyramid |
| 日历 | calendar, time granularity | 日历、时间粒度 | month/day/hour/minute, period granularity |
| 区间 | interval, range, window | 区间、范围、窗口 | bucket, window, span |
| 查询规划 | query planning, query decomposition | 查询规划、查询分解 | query splitting, pushdown, request planning |
| 上限 | limit, cap, budget | 上限、配额、预算 | max points, max buckets, max intervals |
| 本地/缓存 | local, cache, materialized view | 本地、缓存、物化视图 | coverage, precomputed, prefetch |

### 2.2 可以直接粘贴的检索式

```
("time series" OR telemetry OR metrics)
AND (aggregat* OR rollup OR downsample)
AND (hierarch* OR "multi-level" OR "multi-resolution" OR "calendar")
AND (bucket OR interval OR granularity OR resolution)
```

```
("time series" OR telemetry)
AND ("query planning" OR "query decomposition" OR "query splitting" OR "aggregation pushdown")
AND (aggregat* OR rollup)
AND (limit OR cap OR budget OR "max points")
```

```
("aligned interval" OR "canonical interval" OR "dyadic decomposition")
AND ("range query" OR aggregation OR rollup)
```

```
("hierarchical continuous aggregate" OR "continuous aggregate" OR "materialized view")
AND ("time series" OR telemetry)
AND (rollup OR downsample)
```

```
("calendar" OR "time granularity")
AND ("time series" OR telemetry)
AND (aggregat* OR bucket)
AND (hierarch* OR "multi-level")
```

```
("multi-resolution" OR "multi-resolution storage")
AND ("time series database" OR TSDB)
AND (query OR aggregation)
```

```
("bucket limit" OR "max data points" OR "point cap")
AND ("time series" OR metrics)
AND (query OR aggregation)
```

```
("segment tree" OR "Fenwick" OR "sparse table")
AND ("range query" OR "canonical decomposition")
```

中文检索式（CNKI/万方/百度学术）：

```
（时间序列 OR 遥测 OR 时序数据）
AND（聚合 OR 汇总 OR 降采样）
AND（多级 OR 分层 OR 多分辨率 OR 日历）
AND（桶 OR 区间 OR 粒度）
```

```
（时序数据库 OR 时间序列数据库）
AND（查询优化 OR 查询规划 OR 聚合下推）
AND（层级 OR 多粒度）
```

## 3. 数据库清单

### 3.1 论文

免费优先：

* **Google Scholar**：覆盖面最广，适合第一轮和「被引」追踪。
* **Semantic Scholar**：免费 API，适合批量导出和引用链。
* **arXiv**：预印本，计算机系统/数据库方向更新快。
* **Crossref**：DOI 元数据，适合确认正式出版信息。
* **DBLP**：计算机会议/期刊目录，适合查会议论文。
* **USENIX**：FAST、ATC、OSDI 等系统会议论文全文免费。
* **ACM Digital Library / IEEE Xplore**：摘要免费，全文可能需要机构权限。

### 3.2 专利

* **Google Patents**：最易用，支持全文搜索和 CPC 浏览。
* **Espacenet**（EPO）：分类检索和专利族信息强。
* **USPTO Patent Public Search**：美国专利全文。
* **CNIPA**（国家知识产权局）：中国专利。
* **Lens.org**：免费学术 + 专利联合检索，引用链和专利族视图好用。

### 3.3 代码与产品文档

* **GitHub**：仓库搜索；登录后可用 code search。重点搜 `next_boundary`、`time_bucket`、`hierarchical rollup`、`max_intervals`、`fetch level`。
* **Sourcegraph**：跨仓库代码搜索。
* **grep.app**：轻量代码搜索（如可访问）。
* **产品文档**：RRDtool、Graphite/Whisper、TimescaleDB、Apache Druid、Prometheus、Grafana、InfluxDB、ThingsBoard。

### 3.4 中文资料

* **CNKI**、**万方**、**百度学术**：中文论文和学位论文。
* **CSDN/知乎/博客园**：只能作为线索，不能作为法律意义上的现有技术证据；一定要回到原始论文/专利/产品文档确认日期。

## 4. 四天执行计划

### Day 1：把问题变成检索式

* 写第 1 节的特征表和非特征表。
* 从第 2 节挑 8–10 条检索式。
* 每个库只看前 2 页，记录 20–30 个候选。
* 读标题 + 摘要，留下 8–10 个「可能相关」。

### Day 2：找最近的 5 个，做引用链

* 从 8–10 个里选出 5 个最接近的。
* 对每个做：
  * ** backward citation**：看它的参考文献，找更早的祖先；
  * **forward citation**：看谁引用了它，找后续改进。
* 同时开始专利检索：先用关键词，再用 CPC。

### Day 3：精读 + 填矩阵

* 对 5 个最近的做全文精读（至少读摘要、方法、系统设计、评估）。
* 填 `docs/prior-art-matrix.csv`：重叠特征、缺失特征、相关性、结论。
* 对专利，读**独立权利要求**，不要只读摘要。

### Day 4：写差异段 + 决定是否请专业检索

* 写一段 150–250 词的「差异陈述」：最接近的系统做了什么、你做了什么、为什么不是同一个东西。
* 判断是否继续：如果最近 5 个里有 3 个以上覆盖了你的核心组合，说明新颖性弱，应该调整定位或放弃专利。
* 如果准备申请专利或做 FTO，带着材料找专业检索。

**停止条件（saturation）**：连续 2–3 条新检索式不再出现新概念、新系统、新专利族，就可以停。不要用「搜到第 1 页没有」作为停止条件。

## 5. 引用链是最快的路径

不要从零开始扫几千条结果。做法：

1. 用关键词找到 3 篇「明显相关」的论文/专利。
2. 打开它们的参考文献（backward）和被引列表（forward）。
3. 从被引列表里再挑 2 篇，重复一轮。
4. 通常两轮就能覆盖一个领域的「最近一圈」。

工具：

* Google Scholar：「Cited by」。
* Semantic Scholar：论文页的 References / Citations。
* Lens.org：专利的 Citations / Cited by / Family。
* Connected Papers：可视化引用网络（适合找综述和祖先）。

## 6. 记录模板

用 [`prior-art-matrix.csv`](prior-art-matrix.csv)，列的含义：

| 列 | 填什么 |
|---|---|
| `id` | 自定义编号，如 P01 |
| `type` | paper / patent / system / doc / code |
| `title` | 标题 |
| `authors_assignee` | 作者或专利权人 |
| `year` | 发表年或优先权年 |
| `venue_or_jurisdiction` | 会议/期刊，或 US/CN/EP |
| `link` | URL |
| `identifier` | DOI / 专利号 |
| `features_overlap` | 覆盖了特征表里的哪些项（F1–F7） |
| `features_missing` | 缺哪些 |
| `relevance` | A（非常接近）/ B（相关）/ C（背景） |
| `decision` | cite / distinguish / ignore |
| `notes` | 一句话说明为什么 |

矩阵填完后，你就能一眼看出：谁覆盖了 F1+F3，谁只覆盖了 F3，谁覆盖了 F1–F6 但没有 F7。**新颖性通常藏在「组合」和「约束」里，不在单个特征里。**

## 7. 专利检索的具体做法

### 7.1 先找分类号，不要凭记忆猜

1. 在 Google Patents 搜到一个最接近的专利。
2. 打开它的 CPC 分类（Classification）。
3. 点进分类，浏览同一分类下的其他专利。
4. 记录 2–3 个反复出现的 CPC 号，再用「CPC + 关键词」组合检索。

可能相关的分类方向（只作为起点，需用上面的方法确认）：

* `G06F16/*`：信息检索、数据库结构与查询；
* `G06F11/34`：监控/日志；
* `H04L43/00`：网络监控；
* `G06Q50/06`：能源/公用事业；
* `G01D4/00`：计量。

### 7.2 读专利的正确顺序

1. **优先权日（priority date）**：判断现有技术的时间基准，不是公开日。
2. **独立权利要求（independent claim）**：保护范围由它决定。
3. **从属权利要求**：看具体限定。
4. **说明书**：看实施例和替代方案。
5. **法律状态**：有效、过期、放弃、审查中。
6. **专利族**：同一发明可能在美国、中国、欧洲各有成员；用 Lens/Espacenet 查 family。

### 7.3 专利检索的常见误区

* 只搜标题，不搜权利要求和说明书。
* 只看美国专利，漏掉中国/欧洲同族。
* 把公开日当优先权日。
* 看到「没有完全一样的」就认为可以申请；专利看的是权利要求范围，不是标题。
* 忽略失效专利：过期的专利不能阻止你实施，但仍可能影响新颖性判断（取决于日期和法域）。

## 8. 什么时候找专业的人

| 场景 | 建议 |
|---|---|
| 投论文 | 自己做 2–4 天 + 图书馆员/导师补漏即可 |
| 申请专利 | 先自己做预检，再请专利代理师做正式检索和权利要求起草 |
| FTO | 必须请专业检索机构 + 律师；不要用 DIY 结果做商业决策 |
| 融资/尽调 | 让律师看专利组合和 FTO，不要只给一张矩阵 |

给专业人士的材料包：

* 1–2 页技术披露：问题、现有系统、你的方法、关键步骤、与现有系统的差异。
* 第 1 节的特征表（F1–F7）。
* 最接近的 5 篇论文/专利，附链接和一句话差异。
* 目标法域（中国/美国/欧洲）、时间节点、预算。
* 你**不**主张什么（非特征表）。

费用和周期因范围而异，通常从几百到几千美元/人民币不等，1–3 周；FTO 会更贵。先用 DIY 预检把范围缩小，可以显著降低费用。

## 9. 论文 vs 专利的写法差异

**论文 Related work：**

* 按主题分组，不要按时间流水账。
* 每组用 1–2 句说「他们做了什么」，再用 1 句说「和本文的差异」。
* 差异要具体到机制，不要写「我们的方法更好」。
* 不要写「first」「only」「novel」除非你做过穷尽检索；用「we are not aware of」更安全。

**专利说明书：**

* 背景技术：描述现有系统及其不足，不要贬低具体公司。
* 发明内容：用步骤描述方法，突出「如何做」，不是「效果更好」。
* 具体实施方式：给出至少一个完整实施例（对应你的 `decompose` + `fetch_runs` + `fold`）。
* 权利要求：独立权利要求覆盖核心步骤；从属权利要求覆盖日历层级、时区、coverage、桶数上限等具体限定。
* 不要把「性能提升 100 倍」写进独立权利要求；性能是效果，不是保护范围。

## 10. 常见坑

1. **只搜项目名**：`hybrid recursive ladder` 很可能只有你自己；要搜机制。
2. **只搜英文**：漏掉中国专利和中文论文。
3. **只搜 Google**：漏掉 IEEE/ACM/DBLP/专利库。
4. **只看第一页**：相关结果可能在第 3–5 页。
5. **把博客当证据**：博客没有同行评审和明确日期，只能当线索。
6. **忽略日期**：现有技术看公开日/优先权日，不看下载日期。
7. **把 AI 摘要当证据**：AI 可以帮你扩展关键词，但结论必须回到原文。
8. **没有记录**：检索完不填矩阵，一周后全部忘记。
9. **把「没找到」当成「不存在」**：不同数据库覆盖不同，没找到只是「在本库本检索式下没找到」。

## 11. 最小可执行清单

- [ ] 写一页特征表（F1–F7）和非特征表。
- [ ] 选 8 条检索式，在 Google Scholar / arXiv / Crossref 各跑一遍。
- [ ] 每个库看前 2 页，记录 20 个候选。
- [ ] 选出 5 个最接近的，做一轮 backward + forward 引用链。
- [ ] 在 Google Patents 用 2 条检索式 + 1 个 CPC 分类各跑一遍。
- [ ] 填 [`prior-art-matrix.csv`](prior-art-matrix.csv)。
- [ ] 写 150–250 词的差异陈述。
- [ ] 判断：继续 DIY、找图书馆员，还是找专利代理师。

做到这里，你已经比大多数「搜一下没搜到就说自己首创」的人严谨得多了。
