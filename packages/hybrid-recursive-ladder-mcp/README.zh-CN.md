<!-- mcp-name: io.github.MagicSquarekey/hybrid-recursive-ladder -->

# Hybrid Recursive Ladder MCP

**语言 / Languages:** [English](https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm/blob/main/packages/hybrid-recursive-ladder-mcp/README.md) · [简体中文](https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm/blob/main/packages/hybrid-recursive-ladder-mcp/README.zh-CN.md)

**用少量请求聚合长时间序列区间，替代逐桶查询。**

这是 [Hybrid Recursive Ladder](https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm) 查询规划器的 MCP 服务端（stdio）。它把时间区间拆成完整的日历单元——月、日、时、分——每一层只读一次，因此 10 个月的区间只需 5–7 次源请求，而不是 423,049 个逐分钟桶。

零配置可用：未配置时服务端暴露确定性的演示数据，四个工具都能立刻响应。有真实数据时再指向 ThingsBoard 或 PostgreSQL。

## 安装

```bash
uvx hybrid-recursive-ladder-mcp
```

或者用 pip：

```bash
pip install hybrid-recursive-ladder-mcp
hybrid-recursive-ladder-mcp
```

## 客户端配置

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

## 工具

| 工具 | 读取 | 作用 |
|---|---|---|
| `ladder_meta` | 本地 | 版本、阶梯层级、当前源与存储、演示区间。 |
| `ladder_decompose` | 本地 | 把 `[start, end)` 拆成有序、连续、无重叠的阶梯段，不做任何 I/O。 |
| `ladder_sum` | 源 | 对区间求和；可选先把原始点固化到本地存储。 |
| `ladder_verify` | 源 | 比对本地副本与源，报告或修复差异。 |

四个工具都带注解：`ladder_meta` 和 `ladder_decompose` 只读且无副作用；`ladder_sum` 在 `materialize=True` 时写本地存储；`ladder_verify` 会访问源端。

## 配置项

以下都是可选环境变量，写在客户端配置里。

| 变量 | 含义 |
|---|---|
| `HL_SOURCE` | `demo`（默认）、`thingsboard` 或 `postgres`。 |
| `HL_TB_URL`、`HL_TB_USERNAME`、`HL_TB_PASSWORD` | ThingsBoard 地址与凭据。 |
| `HL_TB_TOKEN` | ThingsBoard 访问令牌，替代用户名/密码。 |
| `HL_PG_DSN` | 本地存储的 PostgreSQL 连接串。 |
| `HL_TIMEZONE` | 日历边界使用的 IANA 时区，默认 `Asia/Shanghai`。 |
| `HL_FINEST` | 最细阶梯层级：`minute`、`hour`、`day` 或 `month`。 |

## 不适用的场景

当前版本只计算**求和**，不做平均值（需要加权求和与计数）、电表差值（需要每段首值）或非可加指标；源端也必须支持区间聚合。

## 链接

- 仓库与完整文档：<https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm>
- 算法说明：<https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm/blob/main/docs/algorithm.zh-CN.md>
- 基准数据：<https://github.com/MagicSquarekey/hybrid_recursive_ladder_algorithm/blob/main/docs/benchmarks.zh-CN.md>
- 项目站点：<https://magicsquarekey.github.io/hybrid_recursive_ladder_algorithm/>
- 许可证：MIT
