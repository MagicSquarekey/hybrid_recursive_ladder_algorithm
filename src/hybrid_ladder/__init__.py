# -*- coding: utf-8 -*-
"""Hybrid Recursive Ladder Algorithm.

Aggregate a long time range with a handful of source requests instead of
thousands of per-bucket queries, then serve repeated queries from a local
materialized copy.

Quick start::

    from hybrid_ladder import LadderEngine, MemorySource

    source = MemorySource()
    source.add("device-1", "energy", [(ts, 1.0) for ts in range(0, 86_400_000, 60_000)])
    engine = LadderEngine(source)
    result = engine.sum([("device-1", "energy")], 0, 86_400_000)
    print(result.grand_total)
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _version

from .calc import (
    DeltaCell,
    build_buckets,
    delta_chain,
    fold_avg,
    fold_row_total,
)
from .core import (
    BUCKET_MS,
    LEVELS,
    contiguous_runs,
    decompose,
    fetch_runs,
    fold_count,
    fold_sum,
    label_for,
    merge_coverage,
    next_boundary,
    split_by_coverage,
    unit_start,
)
from .engine import LadderEngine
from .errors import (
    CancelledError,
    ConfigurationError,
    LadderError,
    SourceError,
    StoreError,
)
from .models import (
    ANOMALY_NEGATIVE_DELTA,
    ANOMALY_NO_CURRENT,
    ANOMALY_NO_NEXT,
    ANOMALY_NON_NUMERIC,
    ANOMALY_SAME_READING,
    DELTA_LOOKBACK_MS,
    DIMENSIONS,
    RULES,
    Bucket,
    BucketValue,
    CalcResult,
    CalcRow,
    LadderConfig,
    QueryResult,
    Row,
    Segment,
    SeriesRef,
    coerce_ref,
    coerce_refs,
)
from .protocols import PointStore, TimeSeriesSource
from .sources.memory import MemorySource
from .stores.memory import MemoryStore

__all__ = [
    "ANOMALY_NEGATIVE_DELTA",
    "ANOMALY_NON_NUMERIC",
    "ANOMALY_NO_CURRENT",
    "ANOMALY_NO_NEXT",
    "ANOMALY_SAME_READING",
    "BUCKET_MS",
    "DELTA_LOOKBACK_MS",
    "DIMENSIONS",
    "LEVELS",
    "RULES",
    "Bucket",
    "BucketValue",
    "CalcResult",
    "CalcRow",
    "CancelledError",
    "ConfigurationError",
    "DeltaCell",
    "LadderConfig",
    "LadderEngine",
    "LadderError",
    "MemorySource",
    "MemoryStore",
    "PointStore",
    "QueryResult",
    "Row",
    "Segment",
    "SeriesRef",
    "SourceError",
    "StoreError",
    "TimeSeriesSource",
    "__version__",
    "build_buckets",
    "coerce_ref",
    "coerce_refs",
    "contiguous_runs",
    "decompose",
    "delta_chain",
    "fetch_runs",
    "fold_avg",
    "fold_count",
    "fold_row_total",
    "fold_sum",
    "label_for",
    "merge_coverage",
    "next_boundary",
    "split_by_coverage",
    "unit_start",
]

try:
    __version__ = _version("hybrid-recursive-ladder")
except PackageNotFoundError:  # running from a source tree
    __version__ = "0.0.7"


def __getattr__(name: str):
    # Optional adapters are imported on first use so that the core package can
    # be installed without httpx/psycopg.
    if name == "ThingsBoardSource" or name == "ThingsBoardError":
        from .sources.thingsboard import ThingsBoardError, ThingsBoardSource

        return {"ThingsBoardSource": ThingsBoardSource, "ThingsBoardError": ThingsBoardError}[name]
    if name == "PostgresStore":
        from .stores.postgres import PostgresStore

        return PostgresStore
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
