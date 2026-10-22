# -*- coding: utf-8 -*-
"""Run the HTTP API with an in-memory demo engine.

    pip install "hybrid-recursive-ladder[api]"
    python examples/fastapi_app.py

Then open http://127.0.0.1:8000/docs.
"""

from __future__ import annotations

import uvicorn

from hybrid_ladder.api import create_app
from hybrid_ladder.demo import build_demo_source
from hybrid_ladder.engine import LadderEngine
from hybrid_ladder.stores.memory import MemoryStore

if __name__ == "__main__":
    engine = LadderEngine(build_demo_source(), MemoryStore())
    uvicorn.run(create_app(engine=engine), host="127.0.0.1", port=8000)
