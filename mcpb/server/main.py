# -*- coding: utf-8 -*-
"""Entry point referenced by the MCPB manifest.

The bundle does not vendor the package: ``mcp_config`` runs the published PyPI
distribution through ``uvx``, so the versions stay in step with
``hybrid-recursive-ladder``. This file exists so the manifest has a real
``entry_point`` and so the server can also be started from an environment where
the package is already installed.
"""

from hybrid_ladder.mcp_server import run

if __name__ == "__main__":
    run()
