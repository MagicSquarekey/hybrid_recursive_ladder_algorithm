# 贡献指南

**语言 / Languages:** [English](CONTRIBUTING.md) · [简体中文](CONTRIBUTING.zh-CN.md)

感谢你考虑贡献。这个项目更看重正确性和清晰度，而不是功能数量：算法的保证就是
产品本身。

## 开发环境

```bash
git clone https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm.git
cd hybrid_recursive_ladder_algorithm
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
ruff check .
pytest
```

可选的 PostgreSQL 集成测试：

```bash
export HL_TEST_PG_DSN='postgresql://user:pass@127.0.0.1:5432/testdb'
pytest -m integration
```

集成测试使用唯一的 `namespace` 和 `hl_test_` 表前缀；每个测试后会清理自己的行。

## 开 PR 前要跑什么

```bash
ruff check .
pytest
python examples/benchmark.py       # 段数/请求数应保持稳定
python tools/check_docs_i18n.py    # 每份文档/示意图都要有中文版
```

如果改动了算法语义，请在同一个 PR 中更新 `docs/algorithm.md`、
`docs/algorithm.zh-CN.md` 和相关测试。

## 提交信息

推荐使用 Conventional Commits：

```
feat(engine): add max/min folding
fix(core): keep boundary point on raw bisection
docs(api): document sync endpoints
test(mixed): cover grace-period clamping
```

保持每次提交聚焦。Bug 修复应包含一个在修复前会失败的回归测试。

## 新增数据源适配器

1. 实现 `hybrid_ladder.protocols.TimeSeriesSource` 的 `interval_agg` 和
   `raw_series`。
2. `interval_agg` 返回 `{bucket_start_ms: value}`；如果你的数据源使用半桶时间
   戳，归一化它。
3. `raw_series` 强制 `[start, end)` 和升序；最多返回 `limit` 个点。
4. 不要把凭据写进日志或错误信息。
5. 用 `httpx.MockTransport`（HTTP 数据源）或确定性 fixture 加测试。覆盖：桶
   归一化、分块、认证、错误翻译和排除端点。

## 新增存储适配器

1. 实现 `hybrid_ladder.protocols.PointStore` 的七个方法。
2. 空区间返回 `(None, 0)`，零值区间返回 `(0.0, n)`。这个区分是核心保证。
3. 让 `upsert_points` 在 `(entity, key, ts)` 上幂等。
4. `clear_coverage` 必须在重写前删除重叠的覆盖行。
5. `series` 可以在内部翻页；`max_points` 是页大小，不是上限。
6. 加一个由环境变量控制的选择性集成测试。

## 代码风格

* Python 3.10+，公开函数加类型标注。
* 行宽 100，使用配置好的 `ruff` 规则。
* 核心（`core.py`）必须保持无 I/O、无第三方依赖。
* 优先使用明确的命名而不是缩写；注释应解释约束，而不是复述代码。

## 文档

* 英文是主要 README；行为变化时同步更新 `README.zh-CN.md`。
* **每一份说明文档都必须有中文版**：英文文件 `foo.md` 配套 `foo.zh-CN.md`；
  中文文件也要在顶部放语言切换链接。
* **每一张示意图都必须有中文版**：`docs/assets/<name>.svg` 配套
  `<name>.zh-CN.svg` 和 `<name>.zh-CN.png`。README 图由
  `python tools/localize_assets.py` 从英文 SVG 生成；改完 SVG 或翻译后重跑，
  `--check` 会报告还没有翻译的字符串。
* API 变化需要同时更新 `docs/api.md`、`docs/api.zh-CN.md` 和
  `CHANGELOG.md`。
* 基准数据必须附方法和注意事项；不要把单机数字说成保证。
* 提交前运行 `python tools/check_docs_i18n.py`（CI 也会跑）。

## 发布流程

1. 更新 `CHANGELOG.md`、`CHANGELOG.zh-CN.md` 和 `pyproject.toml` 中的版本。
2. 运行 `ruff check .`、`pytest`、`python examples/benchmark.py` 和
   `python tools/check_docs_i18n.py`。
3. 提交、打 tag（`vX.Y.Z`）、推 tag。`release.yml` 工作流会构建分发包并创建
   GitHub Release。
4. 如果启用了 PyPI 发布，使用 `pypi` 环境和 trusted publishing。

## 报告问题

请包含：

* 区间和 `finest` 层级；
* 数据源类型和适配器版本；
* 预期与实际合计/段数；
* 是否涉及本地存储（`source` / `source_counts`）；
* 尽可能提供最小复现。

永远不要在 issue 中包含凭据或生产数据。
