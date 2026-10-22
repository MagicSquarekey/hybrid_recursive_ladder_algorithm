# -*- coding: utf-8 -*-
"""Data models shared by the ladder core, engine, adapters and API."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

LEVELS = ("month", "day", "hour", "minute")
LEVEL_INDEX = {name: i for i, name in enumerate(LEVELS)}

LABEL_FORMATS = {
    "month": "%Y-%m",
    "day": "%Y-%m-%d",
    "hour": "%Y-%m-%d %H:00",
    "minute": "%Y-%m-%d %H:%M",
}

BUCKET_MS = {
    "day": 86_400_000,
    "hour": 3_600_000,
    "minute": 60_000,
}

#: The fetch level used to build each output level.  A month has no fixed
#: interval in most sources, so it is folded from days; day/hour are folded
#: from the next finer level so the result stays correct in DST time zones.
FETCH_LEVEL = {"month": "day", "day": "hour", "hour": "minute", "minute": "minute"}


@dataclass(slots=True)
class Segment:
    """One ladder segment.

    ``value`` semantics are intentionally strict:

    * ``None`` — no samples at all in this segment (render as "—")
    * ``0.0`` — samples exist and their sum is zero (render as "0")

    ``source`` is one of ``local``, ``tb``, ``mixed``, ``empty`` or
    ``uncovered``.
    """

    level: str
    start: int
    end: int
    label: str
    value: float | None = None
    cnt: int | None = None
    expected: int | None = None
    source: str | None = None

    @property
    def duration_ms(self) -> int:
        return self.end - self.start

    @property
    def is_subminute_tail(self) -> bool:
        return self.level == "minute" and self.duration_ms < 60_000

    def as_dict(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "start": self.start,
            "end": self.end,
            "label": self.label,
            "value": self.value,
            "cnt": self.cnt,
            "expected": self.expected,
            "source": self.source,
        }

    to_dict = as_dict

    # Migration convenience: the original AutoTestHub implementation returned
    # plain dicts, so ``seg["level"]`` keeps working.
    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def keys(self):
        return self.as_dict().keys()


@dataclass(frozen=True, slots=True)
class SeriesRef:
    """A stable reference to one time series.

    ``entity`` is the stable identifier in the data source (for ThingsBoard
    this is the device id).  ``name`` is an optional human-readable name used
    by stores that also key on a display name.
    """

    entity: str
    key: str
    name: str | None = None

    @property
    def display_name(self) -> str:
        return self.name or self.entity

    def as_dict(self) -> dict[str, Any]:
        return {"entity": self.entity, "key": self.key, "name": self.name}


RefLike = SeriesRef | Mapping[str, Any] | Sequence[Any]


def coerce_ref(value: RefLike) -> SeriesRef:
    """Accept a SeriesRef, a mapping or a tuple/list."""
    if isinstance(value, SeriesRef):
        return value
    if isinstance(value, Mapping):
        entity = value.get("entity") or value.get("device_id")
        key = value.get("key")
        if not entity or not key:
            raise ValueError("series reference needs 'entity' (or 'device_id') and 'key'")
        name = value.get("name") or value.get("device_name")
        return SeriesRef(entity=str(entity), key=str(key), name=name)
    if isinstance(value, (tuple, list)):
        if len(value) < 2:
            raise ValueError("series reference tuple needs at least (entity, key)")
        name = value[2] if len(value) > 2 else None
        return SeriesRef(entity=str(value[0]), key=str(value[1]), name=name)
    raise TypeError(f"unsupported series reference: {value!r}")


def coerce_refs(values: Sequence[RefLike] | RefLike) -> list[SeriesRef]:
    if isinstance(values, (SeriesRef, Mapping)):
        return [coerce_ref(values)]
    return [coerce_ref(v) for v in values]


@dataclass(slots=True)
class LadderConfig:
    """Tunables.  Defaults mirror the production AutoTestHub deployment."""

    finest: str = "minute"
    timezone: str = "Asia/Shanghai"

    #: Maximum buckets per interval-aggregation request.  ThingsBoard rejects
    #: 800 and accepts 700 (measured), so 500 is the safe default.
    max_intervals: int = 500
    #: Maximum points per raw-series request.
    max_points: int = 10_000
    #: Hard cap for one materialize/repair run, to avoid unbounded memory.
    max_total_points: int = 2_000_000
    #: Coverage is only recorded up to ``now - grace``; the in-flight tail is
    #: never treated as trustworthy local data.
    materialize_grace_ms: int = 5 * 60_000
    #: Repair window per iteration (a single resync window).
    max_repair_days: int = 366
    #: Parallel series per batch.
    concurrency: int = 8
    #: Keep going when one series fails (the row carries an ``error``).
    continue_on_error: bool = False
    #: Optional defensive cap on the number of segments.
    max_segments: int | None = None
    #: Smallest bucket used for arbitrary sub-range sums.
    min_bucket_ms: int = 60_000

    def __post_init__(self) -> None:
        if self.finest not in LEVEL_INDEX:
            raise ValueError(f"finest must be one of {LEVELS}, got {self.finest!r}")
        if self.max_intervals <= 0:
            raise ValueError("max_intervals must be positive")
        if self.max_points <= 0:
            raise ValueError("max_points must be positive")
        if self.concurrency <= 0:
            raise ValueError("concurrency must be positive")
        if self.materialize_grace_ms < 0:
            raise ValueError("materialize_grace_ms must be >= 0")
        if self.max_repair_days <= 0:
            raise ValueError("max_repair_days must be positive")


@dataclass(slots=True)
class Row:
    """Result for one series."""

    ref: SeriesRef
    segments: list[Segment] = field(default_factory=list)
    total: float | None = None
    empty_count: int = 0
    tb_ranges: list[tuple[int, int]] = field(default_factory=list)
    error: str | None = None

    @property
    def segments_count(self) -> int:
        return len(self.segments)

    def as_dict(self) -> dict[str, Any]:
        out = {
            "device_id": self.ref.entity,
            "device_name": self.ref.display_name,
            "key": self.ref.key,
            "segments": [s.as_dict() for s in self.segments],
            "total": self.total,
            "empty_count": self.empty_count,
            "segments_count": self.segments_count,
            "tb_ranges": [[int(a), int(b)] for a, b in self.tb_ranges],
        }
        if self.error is not None:
            out["error"] = self.error
        return out

    to_dict = as_dict


@dataclass(slots=True)
class QueryResult:
    rows: list[Row] = field(default_factory=list)
    grand_total: float | None = None
    source: str = "tb"
    source_counts: dict[str, int] = field(default_factory=dict)
    errors: list[dict[str, Any]] = field(default_factory=list)
    materialized: dict[str, Any] | None = None
    materialize_error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        out = {
            "rows": [r.as_dict() for r in self.rows],
            "grand_total": self.grand_total,
            "source": self.source,
            "source_counts": dict(self.source_counts),
            "errors": list(self.errors),
        }
        if self.materialized is not None:
            out["materialized"] = self.materialized
        if self.materialize_error is not None:
            out["materialize_error"] = self.materialize_error
        return out

    to_dict = as_dict


def summarize_row(ref: SeriesRef, segments: list[Segment],
                  tb_ranges: list[tuple[int, int]] | None = None) -> Row:
    values = [s.value for s in segments if s.value is not None]
    return Row(
        ref=ref,
        segments=segments,
        total=round(sum(values), 6) if values else None,
        empty_count=sum(1 for s in segments if s.value is None),
        tb_ranges=list(tb_ranges or []),
    )


def source_counts(rows: list[Row]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        for seg in row.segments:
            key = seg.source or "unknown"
            counts[key] = counts.get(key, 0) + 1
    return counts
