# Agent skills

## `hybrid-recursive-ladder`

The skill teaches an agent:

* when the ladder is the right tool (long-range sums; not averages or
  meter-delta in v0.0.1),
* how to call the CLI, HTTP API or MCP tools,
* how to interpret `null` vs `0.0`, `source`, `cnt`/`expected` and `tb_ranges`,
* the ThingsBoard pitfalls that the adapter already handles,
* the verification checklist before trusting a local copy.

### Install the skill

Claude Code:

```bash
mkdir -p ~/.claude/skills
cp -r skills/hybrid-recursive-ladder ~/.claude/skills/
```

ZCode:

```bash
mkdir -p ~/.zcode/skills
cp -r skills/hybrid-recursive-ladder ~/.zcode/skills/
```

Other clients: copy the `hybrid-recursive-ladder/` directory into the client's
skills directory.

### Install the package

The skill's commands need the package. v0.0.1 is distributed through the GitHub
release (PyPI publication is planned):

```bash
pip install https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm/releases/download/v0.0.1/hybrid_recursive_ladder-0.0.1-py3-none-any.whl
```

With optional integrations, install from a source checkout:

```bash
git clone https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm.git
cd hybrid_recursive_ladder_algorithm
pip install -e ".[thingsboard,postgres,api,mcp]"
```

### Try it

```bash
hybrid-ladder demo
hybrid-ladder decompose --start 2026-01-01 --end 2026-10-21T18:49:59
```

* [`SKILL.md`](hybrid-recursive-ladder/SKILL.md) — when and how to use it.
* [`reference.md`](hybrid-recursive-ladder/reference.md) — JSON, HTTP and CLI
  cheat sheet.
