# 发布与传播清单

**语言 / Languages:** 简体中文（内部发布清单，暂无英文版）

这份清单记录已完成的公开发布动作，以及需要账号授权的最后几步。

## 已经完成

- 公开仓库 + MIT License + 带日期的 git 历史。
- `docs/defensive-publication.md`：可执行的公开披露文档。
- `CITATION.cff`：GitHub 的 “Cite this repository” 会读取它。
- `.zenodo.json`：Zenodo 归档元数据，启用后自动使用。
- `docs/related-work.md` / `.zh-CN.md`：先例对比与定位。
- `docs/articles/why-per-bucket-queries-are-slow.md` / `.zh-CN.md`：技术文章。
- `docs/index.html`：GitHub Pages 落地页，已启用：<https://magicsquarekey.github.io/hybrid_recursive_ladder_algorithm/>。
- GitHub Release `v0.0.6`、`v0.0.5`、`v0.0.4`：归档 release，触发 Zenodo DOI。

## 1. Zenodo DOI（已完成）

| 版本 | 版本 DOI | 记录 |
|---|---|---|
| v0.0.6 | [10.5281/zenodo.23683292](https://doi.org/10.5281/zenodo.23683292) | <https://zenodo.org/records/23683292> |
| v0.0.5 | [10.5281/zenodo.23656844](https://doi.org/10.5281/zenodo.23656844) | <https://zenodo.org/records/23656844> |
| v0.0.4 | [10.5281/zenodo.23557574](https://doi.org/10.5281/zenodo.23557574) | <https://zenodo.org/records/23557574> |

concept DOI（所有版本）：<https://doi.org/10.5281/zenodo.23556605>

DOI 已填回 `CITATION.cff`、各语言 README、`docs/defensive-publication.md` 和 `docs/index.html`。后续发版时，Zenodo 会在同一个 concept DOI 下生成新版本 DOI。

如果后续版本没有自动归档：

1. 刷新 Zenodo 的 GitHub 页面，确认开关是 ON、状态是 "Repository synced successfully"。
2. 点 **Sync now**。
3. 如果新 release 没有被识别，创建下一个 release；Zenodo 只归档启用之后创建的 release。
4. 也可以手动在 Zenodo 上传 `dist/hybrid_recursive_ladder-<version>.tar.gz` 和 wheel。

DOI 徽章（换成当前版本的版本 DOI）：

```markdown
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23683292.svg)](https://doi.org/10.5281/zenodo.23683292)
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
| 个人博客 / GitHub Pages | 永久链接、SEO | 已启用：<https://magicsquarekey.github.io/hybrid_recursive_ladder_algorithm/> |
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
- Homepage：<https://magicsquarekey.github.io/hybrid_recursive_ladder_algorithm/>。
- Release `v0.0.6`：<https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm/releases/tag/v0.0.6>，文档与站点发布，包含 wheel、sdist 和自动生成的 release notes。
- Release `v0.0.5`：<https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm/releases/tag/v0.0.5>，归档 release，包含 wheel、sdist 和自动生成的 release notes。
- Release `v0.0.4`：<https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm/releases/tag/v0.0.4>，归档 release，包含公开披露说明和 wheel。

## 5. 维护动作

每次发版：

1. 更新 `pyproject.toml` / `__init__.py` / README badge / install URL。
2. 更新 `CHANGELOG.md`。
3. 更新 `CITATION.cff` 的 `version` 和 `date-released`。
4. 如果 DOI 已存在，更新 `CITATION.cff` 的 DOI。
5. 打 tag，推 tag，等 release workflow 完成。
6. 检查 release 资产和 Pages。

## 6. MCP 目录登记

### 已完成

- PyPI 上的 `hybrid-recursive-ladder-mcp`：包名与命令名一致，`uvx hybrid-recursive-ladder-mcp`
  可直接启动 stdio 服务端。这一点必须满足，因为 `uvx` 按包名找同名可执行文件，
  而 `mcp` 在主包里是可选依赖。
- `server.json`：官方 MCP Registry 描述文件，`registryType: pypi`，
  name 为 `io.github.MagicSquarekey/hybrid-recursive-ladder`。
- 该包的 README 含 `<!-- mcp-name: ... -->` 注释。官方 Registry 校验 PyPI 包归属时，
  就是读 PyPI 页面上的这段字符串，所以它必须在**已发布**的 README 里。

### 官方 MCP Registry

```bash
# 1. 安装 mcp-publisher（Windows 用 tar 解包后放进 PATH）
#    https://github.com/modelcontextprotocol/registry/releases

# 2. GitHub 设备码授权
mcp-publisher login github

# 3. 在仓库根目录发布（server.json 所在目录）
mcp-publisher publish

# 4. 验证
curl "https://registry.modelcontextprotocol.io/v0.1/servers?search=hybrid-recursive-ladder"
```

注意：namespace 前缀必须与 GitHub 登录名一致（`io.github.MagicSquarekey/`）。
如果 Registry 报名称不匹配，把 `server.json` 的 `name` 和 README 里的
`mcp-name` 同时改成小写 `io.github.magicsquarekey/...` 再发一版。

### 其他目录

| 目录 | 方式 | 备注 |
|---|---|---|
| Glama <https://glama.ai/mcp/servers> | 自动索引 GitHub + 认领 | 需要 `mcp` topic 和可用的安装方式 |
| mcp.so | 提交表单 | 填仓库地址和安装命令 |
| PulseMCP <https://www.pulsemcp.com/submit> | 提交表单 | 同样吃仓库信息 |
| Smithery | stdio 需要 `.mcpb` 打包 | 成本较高，优先级低于上面几个 |
| awesome-mcp-servers | 提 PR | 按它的表格格式加一行，写清 transport 和安装命令 |

提交文案统一用：一句话说清“把长区间聚合压到几次请求”，
给出 `uvx hybrid-recursive-ladder-mcp`，再给仓库链接。不要写“首个”“唯一”。

## 7. 不要做的事

- 不要在多个社区同一天重复发同一篇内容；会被当成 spam。
- 不要写 “first”“only”“invented” 这类无法穷尽验证的词；用 “we are not aware of” 或直接描述差异。
- 不要把公开披露说成专利；它不是专利，也不授予专利权。
- 不要在没有专业检索的情况下对商业 FTO 下结论。
