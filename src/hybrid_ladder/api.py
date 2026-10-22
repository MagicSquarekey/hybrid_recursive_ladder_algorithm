# -*- coding: utf-8 -*-
"""Optional FastAPI application.

Run with::

    pip install "hybrid-recursive-ladder[api]"
    hybrid-ladder serve --port 8000

Or embed::

    from hybrid_ladder.api import create_app
    app = create_app(engine=my_engine)
"""

from __future__ import annotations

import os
from dataclasses import asdict
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from . import __version__
from .demo import demo_info
from .engine import LadderEngine
from .errors import (
    CancelledError,
    ConfigurationError,
    LadderError,
    SourceError,
    StoreError,
)
from .models import LEVELS, LadderConfig, SeriesRef
from .runtime import engine_from_env
from .sources.memory import MemorySource
from .tasks import TaskRegistry, default_registry

__all__ = ["create_app", "engine_from_env"]


# ----------------------------------------------------------------------
# Request models
# ----------------------------------------------------------------------
class SeriesIn(BaseModel):
    entity: str | None = None
    device_id: str | None = None
    key: str
    name: str | None = None
    device_name: str | None = None

    def to_ref(self) -> SeriesRef:
        entity = self.entity or self.device_id
        if not entity:
            raise ValueError("series needs 'entity' (or 'device_id')")
        return SeriesRef(entity=str(entity), key=str(self.key),
                         name=self.name or self.device_name)


class SumRequest(BaseModel):
    series: list[SeriesIn] = Field(default_factory=list)
    start_ts: int
    end_ts: int
    finest: str = "minute"
    mode: str = "tb"  # tb | mixed | local
    materialize: bool = False


class VerifyRequest(BaseModel):
    series: list[SeriesIn] = Field(default_factory=list)
    start_ts: int
    end_ts: int
    finest: str = "minute"
    drill_limit: int = 50


class RepairRequest(BaseModel):
    series: list[SeriesIn] = Field(default_factory=list)
    start_ts: int
    end_ts: int


class MaterializeRequest(BaseModel):
    series: list[SeriesIn] = Field(default_factory=list)
    start_ts: int
    end_ts: int


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _refs(series: list[SeriesIn]) -> list[SeriesRef]:
    if not series:
        raise HTTPException(status_code=400, detail="at least one series is required")
    return [item.to_ref() for item in series]


def _check_range(start_ts: int, end_ts: int, finest: str | None = None) -> None:
    if end_ts <= start_ts:
        raise HTTPException(status_code=400, detail="end_ts must be greater than start_ts")
    if finest is not None and finest not in LEVELS:
        raise HTTPException(status_code=400, detail=f"finest must be one of {LEVELS}")


def _require_store(engine: LadderEngine) -> None:
    if engine.store is None:
        raise HTTPException(
            status_code=400,
            detail="this mode needs a local store; set HL_PG_DSN or pass store=...",
        )


def _envelope(data: Any) -> dict[str, Any]:
    return {"code": 0, "data": data}


# ----------------------------------------------------------------------
# Application factory
# ----------------------------------------------------------------------
def create_app(
    engine: LadderEngine | None = None,
    *,
    source: Any | None = None,
    store: Any | None = None,
    config: LadderConfig | None = None,
    registry: TaskRegistry | None = None,
) -> FastAPI:
    """Create the FastAPI app.  All arguments are optional."""
    if engine is None:
        if source is None:
            engine = engine_from_env()
        else:
            engine = LadderEngine(source, store, config or LadderConfig())
    registry = registry or default_registry()

    app = FastAPI(
        title="Hybrid Recursive Ladder API",
        version=__version__,
        description=(
            "Decompose a time range into month/day/hour/minute segments and aggregate "
            "it with a handful of source requests.  Local-first reads, materialization, "
            "verification and repair are included."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.state.engine = engine
    app.state.registry = registry

    origins = os.getenv("HL_CORS_ORIGINS", "").strip()
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[item.strip() for item in origins.split(",") if item.strip()],
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # --------------------------------------------------------------
    # Exception mapping
    # --------------------------------------------------------------
    @app.exception_handler(HTTPException)
    async def _http_error(_: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": 1, "detail": exc.detail},
        )

    @app.exception_handler(ValueError)
    async def _value_error(_: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"code": 1, "detail": str(exc)})

    @app.exception_handler(ConfigurationError)
    async def _config_error(_: Request, exc: ConfigurationError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"code": 1, "detail": str(exc)})

    @app.exception_handler(SourceError)
    async def _source_error(_: Request, exc: SourceError) -> JSONResponse:
        return JSONResponse(status_code=502, content={"code": 1, "detail": str(exc)})

    @app.exception_handler(StoreError)
    async def _store_error(_: Request, exc: StoreError) -> JSONResponse:
        return JSONResponse(status_code=503, content={"code": 1, "detail": str(exc)})

    @app.exception_handler(CancelledError)
    async def _cancelled(_: Request, exc: CancelledError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"code": 1, "detail": str(exc)})

    @app.exception_handler(LadderError)
    async def _ladder_error(_: Request, exc: LadderError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"code": 1, "detail": str(exc)})

    # --------------------------------------------------------------
    # Meta
    # --------------------------------------------------------------
    @app.get("/")
    def root() -> dict[str, Any]:
        return {
            "name": "hybrid-recursive-ladder",
            "version": __version__,
            "docs": "/docs",
            "openapi": "/openapi.json",
            "demo": demo_info() if isinstance(engine.source, MemorySource) else None,
        }

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "version": __version__,
            "source": type(engine.source).__name__,
            "store": type(engine.store).__name__ if engine.store is not None else None,
        }

    @app.get("/v1/meta")
    def meta() -> dict[str, Any]:
        return {
            "version": __version__,
            "levels": list(LEVELS),
            "config": asdict(engine.config),
            "source": type(engine.source).__name__,
            "store": type(engine.store).__name__ if engine.store is not None else None,
            "demo": demo_info() if isinstance(engine.source, MemorySource) else None,
        }

    @app.get("/v1/demo")
    def demo() -> dict[str, Any]:
        if not isinstance(engine.source, MemorySource):
            raise HTTPException(status_code=404, detail="demo data is only available with HL_SOURCE=memory")
        return demo_info()

    # --------------------------------------------------------------
    # Decomposition
    # --------------------------------------------------------------
    @app.get("/v1/decompose")
    def decompose_range(
        start_ts: int = Query(..., description="inclusive start, epoch milliseconds"),
        end_ts: int = Query(..., description="exclusive end, epoch milliseconds"),
        finest: str | None = Query(None),
    ) -> dict[str, Any]:
        _check_range(start_ts, end_ts, finest)
        segments = engine.decompose(start_ts, end_ts, finest)
        by_level: dict[str, int] = {}
        for segment in segments:
            by_level[segment.level] = by_level.get(segment.level, 0) + 1
        return {
            "segments": [segment.as_dict() for segment in segments],
            "count": len(segments),
            "by_level": by_level,
        }

    # --------------------------------------------------------------
    # Sum
    # --------------------------------------------------------------
    def sum_runner(request: SumRequest):
        refs = _refs(request.series)
        _check_range(request.start_ts, request.end_ts, request.finest)
        mode = request.mode.lower()
        if mode not in ("tb", "mixed", "local"):
            raise HTTPException(status_code=400, detail="mode must be tb, mixed or local")
        if mode in ("mixed", "local"):
            _require_store(engine)

        def runner(progress, cancelled):
            if mode == "tb":
                result = engine.sum(
                    refs, request.start_ts, request.end_ts,
                    finest=request.finest, progress=progress, cancel=cancelled,
                )
            elif mode == "local":
                result = engine.sum_local(
                    refs, request.start_ts, request.end_ts,
                    finest=request.finest, progress=progress, cancel=cancelled,
                )
            else:
                result = engine.sum_mixed(
                    refs, request.start_ts, request.end_ts,
                    finest=request.finest, progress=progress, cancel=cancelled,
                )

            if request.materialize and engine.store is not None:
                if mode == "tb":
                    items = [(ref, [(request.start_ts, request.end_ts)]) for ref in refs]
                else:
                    items = [(row.ref, row.tb_ranges) for row in result.rows if row.tb_ranges]
                if items:
                    progress(len(refs), len(refs), "total ready; materializing raw points…")
                    try:
                        result.materialized = engine.materialize_ranges(
                            items, progress=progress, cancel=cancelled
                        )
                    except Exception as exc:
                        result.materialize_error = str(exc)[:300]
            return result.as_dict()

        return runner

    @app.post("/v1/ladder/sum")
    def ladder_sum(request: SumRequest, sync: bool = Query(False)) -> dict[str, Any]:
        runner = sum_runner(request)
        if sync:
            return _envelope(runner(lambda *_: None, lambda: False))
        task_id = registry.create("ladder sum", len(request.series), runner)
        return _envelope({"task_id": task_id, "async": True, "series": len(request.series)})

    @app.post("/v1/ladder/sum/sync")
    def ladder_sum_sync(request: SumRequest) -> dict[str, Any]:
        return _envelope(sum_runner(request)(lambda *_: None, lambda: False))

    # --------------------------------------------------------------
    # Verify / repair / materialize
    # --------------------------------------------------------------
    @app.post("/v1/ladder/verify")
    def ladder_verify(request: VerifyRequest, sync: bool = Query(False)) -> dict[str, Any]:
        refs = _refs(request.series)
        _check_range(request.start_ts, request.end_ts, request.finest)
        _require_store(engine)

        def runner(progress, cancelled):
            return engine.verify(
                refs, request.start_ts, request.end_ts,
                finest=request.finest, drill_limit=request.drill_limit,
                progress=progress, cancel=cancelled,
            )

        if sync:
            return _envelope(runner(lambda *_: None, lambda: False))
        return _envelope({"task_id": registry.create("ladder verify", len(refs), runner),
                          "async": True})

    @app.post("/v1/ladder/repair")
    def ladder_repair(request: RepairRequest, sync: bool = Query(False)) -> dict[str, Any]:
        refs = _refs(request.series)
        _check_range(request.start_ts, request.end_ts)
        _require_store(engine)

        def runner(progress, cancelled):
            return engine.repair(
                refs, request.start_ts, request.end_ts,
                progress=progress, cancel=cancelled,
            )

        if sync:
            return _envelope(runner(lambda *_: None, lambda: False))
        return _envelope({"task_id": registry.create("ladder repair", len(refs), runner),
                          "async": True})

    @app.post("/v1/ladder/materialize")
    def ladder_materialize(
        request: MaterializeRequest, sync: bool = Query(False)
    ) -> dict[str, Any]:
        refs = _refs(request.series)
        _check_range(request.start_ts, request.end_ts)
        _require_store(engine)

        def runner(progress, cancelled):
            return engine.materialize(
                refs, request.start_ts, request.end_ts,
                progress=progress, cancel=cancelled,
            )

        if sync:
            return _envelope(runner(lambda *_: None, lambda: False))
        return _envelope({"task_id": registry.create("ladder materialize", len(refs), runner),
                          "async": True})

    # --------------------------------------------------------------
    # Tasks
    # --------------------------------------------------------------
    @app.get("/v1/tasks")
    def list_tasks() -> dict[str, Any]:
        return {"tasks": registry.list()}

    @app.get("/v1/tasks/{task_id}")
    def task_status(task_id: str) -> dict[str, Any]:
        snapshot = registry.snapshot(task_id)
        if snapshot is None:
            raise HTTPException(status_code=404, detail=f"task not found or expired: {task_id}")
        return _envelope(snapshot)

    @app.post("/v1/tasks/{task_id}/cancel")
    def task_cancel(task_id: str) -> dict[str, Any]:
        return _envelope({"cancelled": registry.cancel(task_id)})

    return app


def app_factory() -> FastAPI:
    """Uvicorn factory entry point: ``uvicorn hybrid_ladder.api:app_factory --factory``."""
    return create_app()
