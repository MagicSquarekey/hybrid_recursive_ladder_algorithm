<!-- mcp-name: io.github.MagicSquarekey/hybrid-recursive-ladder -->

# Hybrid Recursive Ladder MCP

**语言 / Languages:** [English](https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm/blob/main/packages/hybrid-recursive-ladder-mcp/README.md) · [简体中文](https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm/blob/main/packages/hybrid-recursive-ladder-mcp/README.zh-CN.md)

**Aggregate long time-series ranges with a handful of source requests instead of one per bucket.**

An MCP server (stdio) for the [Hybrid Recursive Ladder](https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm) query planner. It splits a time range into complete calendar units — month, day, hour, minute — and reads each level once, so a ten-month range costs about five to seven source requests instead of 423,049 per-minute buckets.

Works with no configuration: the server exposes deterministic demo data, so every tool answers immediately. Point it at ThingsBoard or PostgreSQL when you have real data.

## Install

```bash
uvx hybrid-recursive-ladder-mcp
```

or, with pip:

```bash
pip install hybrid-recursive-ladder-mcp
hybrid-recursive-ladder-mcp
```

## Client configuration

```json
{
  "mcpServers": {
    "hybrid-recursive-ladder": {
      "command": "uvx",
      "args": ["hybrid-recursive-ladder-mcp"]
    }
  }
}
```

## Tools

| Tool | Reads | What it does |
|---|---|---|
| `ladder_meta` | local | Version, ladder levels, active source and store, demo range. |
| `ladder_decompose` | local | Split `[start, end)` into ordered, contiguous ladder segments. No I/O. |
| `ladder_sum` | source | Sum a range, optionally materializing raw points into the local store first. |
| `ladder_verify` | source | Compare the local copy against the source and report or repair drift. |

All four are annotated: `ladder_meta` and `ladder_decompose` are local and side-effect free, `ladder_sum` can write through `materialize=True`, and `ladder_verify` reaches the source.

## Configuration

Set these as environment variables in the client config. All are optional.

| Variable | Meaning |
|---|---|
| `HL_SOURCE` | `demo` (default), `thingsboard`, or `postgres`. |
| `HL_TB_URL`, `HL_TB_USERNAME`, `HL_TB_PASSWORD` | ThingsBoard endpoint and credentials. |
| `HL_TB_TOKEN` | ThingsBoard access token, instead of username/password. |
| `HL_PG_DSN` | PostgreSQL DSN for the local store. |
| `HL_TIMEZONE` | IANA zone used for calendar boundaries (default `Asia/Shanghai`). |
| `HL_FINEST` | Finest ladder level: `minute`, `hour`, `day`, or `month`. |

## When not to use it

The tool computes **sums** only in this version. It does not do averages (needs weighted sum plus count), meter deltas, or non-additive metrics, and it needs a source that supports interval aggregation.

## Links

- Repository and full docs: <https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm>
- Algorithm specification: <https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm/blob/main/docs/algorithm.md>
- Benchmarks: <https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm/blob/main/docs/benchmarks.md>
- Project site: <https://magicsquarekey.github.io/hybrid_recursive_ladder_algorithm/>
- License: MIT
