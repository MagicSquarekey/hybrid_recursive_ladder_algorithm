# 发布与传播清单

这份清单记录 v0.0.2 已经完成的公开发布动作，以及需要账号授权的最后几步。

## 已经完成

- 公开仓库 + MIT License + 带日期的 git 历史。
- `docs/defensive-publication.md`：可执行的公开披露文档。
- `CITATION.cff`：GitHub 的 “Cite this repository” 会读取它。
- `.zenodo.json`：Zenodo 归档元数据，启用后自动使用。
- `docs/related-work.md` / `.zh-CN.md`：先例对比与定位。
- `docs/articles/why-per-bucket-queries-are-slow.md` / `.zh-CN.md`：技术文章。
- `site/index.html`：GitHub Pages 落地页。
- GitHub Release `v0.0.2`：公开时间戳 + wheel 构建。

## 1. Zenodo DOI（需要你登录一次）

Zenodo 不能由仓库里的代码自动创建，需要账户授权。步骤：

1. 用 GitHub 登录 <https://zenodo.org>。
2. 打开 **Settings → GitHub**，找到 `MagicSquarekey/hybrid_recursive_ladder_algorithm`，把开关打开。
3. 回到 GitHub，创建一个新的 release（例如 `v0.0.3`；已经存在的 `v0.0.2` 不会被自动补归档）。
4. Zenodo 会自动读取 `.zenodo.json`，生成 DOI。
5. 把 DOI 填回：
   - `CITATION.cff` 的 `identifiers`（或 `doi` 字段）；
   - `README.md` / `README.zh-CN.md` 的 Citation 部分；
   - `docs/defensive-publication.md` 的 Citation 部分；
   - `site/index.html` 的 Cite 部分；
   - GitHub 仓库的 **About → DOI** 徽章（可选）。

DOI 徽章示例：

```markdown
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.XXXXXXX.svg)](https://doi.org/10.5281/zenodo.XXXXXXX)
```

## 2. PyPI（可选，需要账号）

当前仓库没有 PyPI 凭据。两种做法：

**手动上传：**

```bash
python -m build
python -m twine upload dist/*
```

需要 `~/.pypirc` 或 `TWINE_USERNAME` / `TWINE_PASSWORD`。

**Trusted Publishing（推荐，不需要存 token）：**

1. 在 PyPI 创建项目 `hybrid-recursive-ladder`。
2. 在 PyPI 的 Publishing 设置里添加 GitHub trusted publisher：
   - owner: `MagicSquarekey`
   - repo: `hybrid_recursive_ladder_algorithm`
   - workflow: `release.yml`
   - environment: `pypi`（如果 workflow 里用了 environment）
3. 在 `.github/workflows/release.yml` 里加一个 `pypi` job，使用 `pypa/gh-action-pypi-publish@release/v1` 和 `id-token: write` 权限。

在完成之前，GitHub Release 的 wheel 已经可以直接 `pip install <url>`。

## 3. 技术文章分发

文章已经写好：

- 英文：`docs/articles/why-per-bucket-queries-are-slow.md`
- 中文：`docs/articles/why-per-bucket-queries-are-slow.zh-CN.md`

建议渠道（选 2–3 个，不要一次全发）：

| 渠道 | 适合 | 注意 |
|---|---|---|
| 个人博客 / GitHub Pages | 永久链接、SEO | 已在 `site/` 准备落地页 |
| dev.to | 英文开发者 | 加 `#timeseries #performance #database` 标签 |
| Medium | 英文/综合 | 可以同步，但注意 canonical URL 指回博客 |
| 知乎 | 中文技术读者 | 标题偏“为什么逐桶查询慢”，不要硬广 |
| 掘金 | 中文开发者 | 适合带 benchmark 和代码 |
| V2EX | 中文技术社区 | 用“分享创造”节点，附 demo |
| Hacker News | 英文 | `Show HN: ...`，不要在多个时间重复发 |
| Reddit r/programming / r/dataengineering | 英文 | 先读版规，避免纯推广 |

标题备选：

- “1,140 buckets, 139 seconds: why per-bucket time-series queries fail”
- “How to aggregate a year of time-series data in a handful of requests”
- “1,140 个桶，139 秒：逐桶时序查询为什么慢”
- “把一年的时序聚合压到几次请求：日历阶梯查询规划”

文章开头要直接给结果（139 秒 → 0.64 秒），不要先讲目录结构；结尾给 GitHub 链接和 demo 命令。

## 4. GitHub 仓库资料（已通过 API 更新）

- Description：以 “Query planning for bucket-limited time-series APIs” 开头。
- Topics：`time-series`, `aggregation`, `query-planning`, `downsampling`, `multi-resolution`, `thingsboard`, `observability`, `python`, `mcp`, `iot` 等。
- Homepage：GitHub Pages 地址。
- Release `v0.0.2`：包含公开披露说明和 wheel。

## 5. 维护动作

每次发版：

1. 更新 `pyproject.toml` / `__init__.py` / README badge / install URL。
2. 更新 `CHANGELOG.md`。
3. 更新 `CITATION.cff` 的 `version` 和 `date-released`。
4. 如果 DOI 已存在，更新 `CITATION.cff` 的 DOI。
5. 打 tag，推 tag，等 release workflow 完成。
6. 检查 release 资产和 Pages。

## 6. 不要做的事

- 不要在多个社区同一天重复发同一篇内容；会被当成 spam。
- 不要写 “first”“only”“invented” 这类无法穷尽验证的词；用 “we are not aware of” 或直接描述差异。
- 不要把公开披露说成专利；它不是专利，也不授予专利权。
- 不要在没有专业检索的情况下对商业 FTO 下结论。
