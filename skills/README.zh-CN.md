# Agent 技能

**语言 / Languages:** [English](README.md) · [简体中文](README.zh-CN.md)

## `hybrid-recursive-ladder`

这个技能教 Agent：

* 什么时候阶梯是合适的工具（长区间求和；当前版本不支持平均值或累计量差分）；
* 如何调用 CLI、HTTP API 或 MCP 工具；
* 如何解释 `null` 与 `0.0`、`source`、`cnt`/`expected` 和 `tb_ranges`；
* 适配器已经处理了哪些 ThingsBoard 坑；
* 信任本地副本之前的校验清单。

### 安装技能

Claude Code：

```bash
mkdir -p ~/.claude/skills
cp -r skills/hybrid-recursive-ladder ~/.claude/skills/
```

ZCode：

```bash
mkdir -p ~/.zcode/skills
cp -r skills/hybrid-recursive-ladder ~/.zcode/skills/
```

其他客户端：把 `hybrid-recursive-ladder/` 目录复制到客户端的技能目录。

### 安装软件包

技能中的命令需要软件包。v0.0.5 通过 GitHub Release 分发（PyPI 发布在计划中）：

```bash
pip install https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm/releases/download/v0.0.5/hybrid_recursive_ladder-0.0.5-py3-none-any.whl
```

需要可选集成时，从源码检出安装：

```bash
git clone https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm.git
cd hybrid_recursive_ladder_algorithm
pip install -e ".[thingsboard,postgres,api,mcp]"
```

### 试一试

```bash
hybrid-ladder demo
hybrid-ladder decompose --start 2026-01-01 --end 2026-10-21T18:49:59
```

* [`SKILL.md`](hybrid-recursive-ladder/SKILL.md) — 何时使用、如何使用（英文）。
* [`SKILL.zh-CN.md`](hybrid-recursive-ladder/SKILL.zh-CN.md) — 中文参考译本。
* [`reference.md`](hybrid-recursive-ladder/reference.md) — JSON、HTTP 和 CLI
  速查表（英文）。
* [`reference.zh-CN.md`](hybrid-recursive-ladder/reference.zh-CN.md) — 中文速查表。
