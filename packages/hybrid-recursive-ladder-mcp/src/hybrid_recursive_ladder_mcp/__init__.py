# -*- coding: utf-8 -*-
"""Console entry point for the Hybrid Recursive Ladder MCP server.

The server itself lives in :mod:`hybrid_ladder.mcp_server`. This package exists
so that a package manager can resolve a command with the same name as the
package — ``uvx hybrid-recursive-ladder-mcp`` — and install the ``mcp`` extra
the server needs, without callers having to know about extras.
"""

from __future__ import annotations

__all__ = ["main"]


def main() -> None:
    """Start the stdio MCP server."""
    from hybrid_ladder.mcp_server import run

    run()
