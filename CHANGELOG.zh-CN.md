# 变更日志

**语言 / Languages:** [English](CHANGELOG.md) · [简体中文](CHANGELOG.zh-CN.md)

本文件记录项目的所有重要变更。格式遵循
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/)，项目从 0.0.1 起使用
[语义化版本](https://semver.org/spec/v2.0.0.html)。

## [0.0.5] — 2026-10-26

### 新增

* 四个 MCP 工具都加了工具注解：人类可读的 `title`，以及
  `readOnlyHint`、`destructiveHint`、`idempotentHint`、`openWorldHint`。
  客户端现在可以判断：`ladder_meta` 和 `ladder_decompose` 是本地、无副作用
  的；`ladder_sum` 在 `materialize=True` 时可能写本地存储；`ladder_verify`
  会访问数据源。
* 每种语言的 README 配图。每个翻译版 README 都有
  `docs/assets/hero.<lang>.png`，`decomposition`/`architecture` 也提供了中文
  版。`tools/localize_assets.py` 从英文 SVG 重新生成这些图。

### 修复

* `tests/test_mcp.py` 现在接受当前 MCP SDK 版本中 `call_tool` 返回的
  `(content, structured)`；此前的断言在 `mcp` 1.27 及更高版本上失败。

## [0.0.4] — 2026-10-22

文档发布。没有代码或算法变更。重写 README 并增加示意图。

### 新增

* Zenodo 归档与 DOI：[10.5281/zenodo.23557574](https://doi.org/10.5281/zenodo.23557574)。

### 变更

* 把 `README.md` 与 `README.zh-CN.md` 重写为单一叙事，并加入前后对比、日历
  分解和本地优先读路径的示意图。
* 给其他语言 README 加入 hero 图和 DOI/网站徽章。
* 包版本升到 `0.0.4`。

## [0.0.3] — 2026-10-22

归档发布。没有代码或算法变更。此发布触发 Zenodo 的 GitHub 集成，使公开披露
获得 DOI。

### 新增

* Zenodo 归档与 DOI：[10.5281/zenodo.23556606](https://doi.org/10.5281/zenodo.23556606)。

### 变更

* 包版本升到 `0.0.3`，并更新引用、安装和站点元数据。

## [0.0.2] — 2026-10-22

文档与公开披露发布。算法语义未变。

### 新增

* `docs/defensive-publication.md`：方法及其形式化性质的公开披露，作为现有技术。
* `CITATION.cff` 与 `.zenodo.json`：引用与归档元数据。
* `docs/articles/why-per-bucket-queries-are-slow.md` 及其中文版：带生产基准和
  现有技术定位的技术文章。
* `docs/index.html`：GitHub Pages 静态落地页。
* `docs/publishing.md`：发布、Zenodo、PyPI 与传播清单。
* `docs/related-work.md` 与 `docs/related-work.zh-CN.md`：现有技术对比、历史
  算法和可辩护的新颖性陈述。
* `docs/prior-art-search.zh-CN.md` 与 `docs/prior-art-matrix.csv`：可重复的
  现有技术/专利检索计划和记录模板。
* 算法规范中的形式化细化局部性、段数和请求数命题。

### 变更

* 把项目重新定位为面向桶数受限时序 API 的查询规划方法（README、算法规范、
  包描述）。
* 包版本升到 `0.0.2`，用于公开披露发布。

## [0.0.1] — 2026-10-22

首个独立开源版本，从 AutoTestHub 抽离。

### 新增

* 纯分解核心（`month → day → hour → minute`），可配置最细层、IANA 时区支持和
  严格的铺满不变量。
* `LadderEngine`：纯源、纯本地和本地优先混合读。
* 本地固化，带覆盖跟踪、5 分钟宽限期和重写安全的覆盖失效。
* 段级校验与点级展开（`added`、`removed`、`changed`），以及从权威数据源修复。
* `TimeSeriesSource` 与 `PointStore` 协议；ThingsBoard、PostgreSQL 和内存适配器。
* PostgreSQL 表结构：月分区、幂等 upsert、批量区间求和和覆盖表
  （`hl_readings`、`hl_coverage`）。
* ThingsBoard 适配器：500 桶上限、半桶时间戳、包含端点的 `endTs`、token 刷新
  和错误翻译。
* `hybrid-ladder` CLI：`decompose`、`demo`、`sum`、`verify`、`repair`、
  `materialize`、`serve`、`mcp`、`version`。
* FastAPI 应用：异步任务、进度、取消、同步变体和 `{"code":0,"data":...}` 信封。
* MCP server：`ladder_meta`、`ladder_decompose`、`ladder_sum`、`ladder_verify`
  （支持 MCP 1.x 与 2.x）。
* `skills/hybrid-recursive-ladder/` 下的 Agent 技能包。
* 确定性演示数据和端到端 `hybrid-ladder demo`。
* 90+ 个测试，覆盖分解、折叠、混合读、固化、校验、修复、任务、API、CLI、
  MCP、ThingsBoard 和 PostgreSQL。

### 修复（相对原 AutoTestHub 实现）

* **多层级取数分组。** 取数 run 按取数层级 + 连续性分组，而不是只按相邻分组。
  原实现把整个多层级区间按最粗层取数，把一整天的值赋给第一个小时，并丢掉其余
  小时/分钟。回归测试：`tests/test_engine.py::test_multilevel_query_is_exact`。
* **原始点分块边界。** 在左闭右开契约下，二分改为 `[a, mid)` 与 `[mid, b)`。
  原实现用 `mid + 1`，会丢掉正好落在分块边界上的点。回归测试：
  `tests/test_engine.py::test_raw_split_keeps_boundary_point`。

### 变更

* PostgreSQL 表使用命名空间（`namespace`、`entity`、`name`），并支持可配置的
  `table_prefix`，替代 AutoTestHub 的 `connection_id/device_id/device`。
* `TaskRegistry` 可复用（多实例、TTL、最大任务数），不再是模块级单例。
* MCP 工具层与 HTTP 层共享一个 `runtime.engine_from_env()`。

### 已知限制

* 只实现 `sum` 规则。`avg` 和 `meter_delta` 需要额外的聚合语义。
* 进程内任务结果在重启后丢失（数据不丢）。
* 原 AutoTestHub 的 `device_id` 迁移不是自动的。
