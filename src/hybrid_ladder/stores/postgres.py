# -*- coding: utf-8 -*-
"""PostgreSQL point store with monthly partitions and coverage tracking.

The schema is deliberately small and independent from the host application:

``{prefix}readings``
    one row per raw point; primary key ``(namespace, entity, key, ts)`` makes
    writes idempotent.  Partitioned by month on ``ts``.

``{prefix}coverage``
    one row per materialized range; used by the local-first read path.

Only ``psycopg`` and ``psycopg_pool`` are needed at runtime (install the
``postgres`` extra).
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from ..errors import StoreError
from ..models import SeriesRef

__all__ = ["PostgresStore"]

_PREFIX_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class PostgresStore:
    """Local point store backed by PostgreSQL 14+."""

    def __init__(
        self,
        dsn: str,
        *,
        namespace: str = "default",
        table_prefix: str = "hl_",
        timezone: str = "Asia/Shanghai",
        min_size: int = 0,
        max_size: int = 8,
        timeout: float = 10.0,
        ensure_schema: bool = True,
    ) -> None:
        if not dsn:
            raise ValueError("dsn is required")
        if not namespace:
            raise ValueError("namespace is required")
        if table_prefix and not _PREFIX_RE.match(table_prefix):
            raise ValueError(
                "table_prefix must match ^[A-Za-z_][A-Za-z0-9_]*$ (or be empty)"
            )
        self.dsn = dsn
        self.namespace = namespace
        self.table_prefix = table_prefix
        self.timezone = timezone
        self._min_size = min_size
        self._max_size = max_size
        self._timeout = timeout
        self._ensure_schema = ensure_schema
        self._pool: Any | None = None
        self._schema_ready = False
        self._zone = ZoneInfo(timezone)

    # ------------------------------------------------------------------
    # Names / schema
    # ------------------------------------------------------------------
    @property
    def readings_table(self) -> str:
        return f"{self.table_prefix}readings"

    @property
    def coverage_table(self) -> str:
        return f"{self.table_prefix}coverage"

    def _pool_or_create(self) -> Any:
        if self._pool is not None:
            return self._pool
        try:
            from psycopg_pool import ConnectionPool
        except ImportError as exc:  # pragma: no cover - dependency error path
            raise ImportError(
                "PostgresStore needs psycopg; install with "
                "'pip install \"hybrid-recursive-ladder[postgres]\"'"
            ) from exc
        self._pool = ConnectionPool(
            self.dsn,
            min_size=self._min_size,
            max_size=self._max_size,
            timeout=self._timeout,
            max_lifetime=1800,
            open=True,
        )
        return self._pool

    def _ensure_ready(self) -> Any:
        pool = self._pool_or_create()
        if self._ensure_schema and not self._schema_ready:
            self.ensure_schema()
            self._schema_ready = True
        return pool

    def ensure_schema(self) -> None:
        """Create tables and indexes if they do not exist (idempotent)."""
        pool = self._pool_or_create()
        readings = self.readings_table
        coverage = self.coverage_table
        sql = f"""
        CREATE TABLE IF NOT EXISTS {readings} (
            namespace    text NOT NULL,
            entity       text NOT NULL,
            name         text,
            key          text NOT NULL,
            ts           bigint NOT NULL,
            value        double precision,
            value_str    text,
            quality      text,
            ingested_at  bigint,
            PRIMARY KEY (namespace, entity, key, ts)
        ) PARTITION BY RANGE (ts);

        CREATE TABLE IF NOT EXISTS {coverage} (
            id          bigserial PRIMARY KEY,
            namespace   text NOT NULL,
            entity      text NOT NULL,
            name        text,
            key         text NOT NULL,
            start_ts    bigint NOT NULL,
            end_ts      bigint NOT NULL,
            point_cnt   bigint,
            covered_at  bigint NOT NULL
        );
        CREATE INDEX IF NOT EXISTS {coverage}_lookup
            ON {coverage} (namespace, entity, key, start_ts);
        """
        with pool.connection() as conn, conn.cursor() as cur:
            cur.execute(sql)
        self._schema_ready = True

    def _month_start_ms(self, ts_ms: int) -> int:
        dt = datetime.fromtimestamp(ts_ms / 1000, self._zone)
        return round(datetime(dt.year, dt.month, 1, tzinfo=self._zone).timestamp() * 1000)

    def _next_month_ms(self, month_start_ms: int) -> int:
        dt = datetime.fromtimestamp(month_start_ms / 1000, self._zone)
        year, month = (dt.year + 1, 1) if dt.month == 12 else (dt.year, dt.month + 1)
        return round(datetime(year, month, 1, tzinfo=self._zone).timestamp() * 1000)

    def ensure_partitions(self, from_ms: int, to_ms: int) -> None:
        """Create monthly partitions covering ``[from_ms, to_ms]``."""
        if to_ms < from_ms:
            from_ms, to_ms = to_ms, from_ms
        pool = self._ensure_ready()
        cursor_ms = self._month_start_ms(from_ms)
        last_ms = self._month_start_ms(to_ms)
        statements = []
        while cursor_ms <= last_ms:
            next_ms = self._next_month_ms(cursor_ms)
            dt = datetime.fromtimestamp(cursor_ms / 1000, self._zone)
            partition = f"{self.readings_table}_y{dt.year}m{dt.month:02d}"
            statements.append(
                f"CREATE TABLE IF NOT EXISTS {partition} "
                f"PARTITION OF {self.readings_table} "
                f"FOR VALUES FROM ({cursor_ms}) TO ({next_ms})"
            )
            cursor_ms = next_ms
        if statements:
            with pool.connection() as conn, conn.cursor() as cur:
                for statement in statements:
                    cur.execute(statement)

    # ------------------------------------------------------------------
    # PointStore: reads
    # ------------------------------------------------------------------
    def sum_ranges(
        self,
        ref: SeriesRef,
        ranges: Sequence[tuple[int, int]],
    ) -> Mapping[int, tuple[float | None, int]]:
        if not ranges:
            return {}
        pool = self._ensure_ready()
        payload = json.dumps(
            [{"i": index, "s": int(start), "e": int(end)} for index, (start, end) in enumerate(ranges)]
        )
        sql = (
            "SELECT b.i, sum(r.value), count(r.value) "
            f"FROM jsonb_to_recordset(%s::jsonb) AS b(i int, s bigint, e bigint) "
            f"LEFT JOIN {self.readings_table} r "
            "ON r.namespace=%s AND r.entity=%s AND r.key=%s "
            "AND r.ts >= b.s AND r.ts < b.e "
            "GROUP BY b.i"
        )
        with pool.connection() as conn, conn.cursor() as cur:
            cur.execute(sql, (payload, self.namespace, ref.entity, ref.key))
            rows = cur.fetchall()
        out: dict[int, tuple[float | None, int]] = {}
        for index, value, count in rows:
            start = int(ranges[int(index)][0])
            out[start] = (float(value) if value is not None else None, int(count or 0))
        return out

    def series(
        self,
        ref: SeriesRef,
        start_ms: int,
        end_ms: int,
        max_points: int = 5_000,
    ) -> list[Mapping[str, Any]]:
        pool = self._ensure_ready()
        page = max(1, int(max_points))
        out: list[Mapping[str, Any]] = []
        last_ts = int(start_ms) - 1
        while True:
            with pool.connection() as conn, conn.cursor() as cur:
                cur.execute(
                    "SELECT ts, value FROM "
                    f"{self.readings_table} "
                    "WHERE namespace=%s AND entity=%s AND key=%s "
                    "AND ts > %s AND ts < %s ORDER BY ts ASC LIMIT %s",
                    (self.namespace, ref.entity, ref.key, last_ts, int(end_ms), page),
                )
                rows = cur.fetchall()
            for ts, value in rows:
                out.append({"ts": int(ts), "value": value})
            if len(rows) < page:
                break
            last_ts = int(rows[-1][0])
        return out

    def coverage(self, ref: SeriesRef) -> list[tuple[int, int, int]]:
        pool = self._ensure_ready()
        with pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT start_ts, end_ts, covered_at FROM "
                f"{self.coverage_table} "
                "WHERE namespace=%s AND entity=%s AND key=%s ORDER BY start_ts",
                (self.namespace, ref.entity, ref.key),
            )
            return [(int(a), int(b), int(c)) for a, b, c in cur.fetchall()]

    # ------------------------------------------------------------------
    # PointStore: writes
    # ------------------------------------------------------------------
    def delete_range(self, ref: SeriesRef, start_ms: int, end_ms: int) -> int:
        if end_ms <= start_ms:
            return 0
        pool = self._ensure_ready()
        with pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                "DELETE FROM "
                f"{self.readings_table} "
                "WHERE namespace=%s AND entity=%s AND key=%s AND ts >= %s AND ts < %s",
                (self.namespace, ref.entity, ref.key, int(start_ms), int(end_ms)),
            )
            return int(cur.rowcount or 0)

    def clear_coverage(self, ref: SeriesRef, start_ms: int, end_ms: int) -> int:
        if end_ms <= start_ms:
            return 0
        pool = self._ensure_ready()
        with pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                "DELETE FROM "
                f"{self.coverage_table} "
                "WHERE namespace=%s AND entity=%s AND key=%s "
                "AND start_ts < %s AND end_ts > %s",
                (self.namespace, ref.entity, ref.key, int(end_ms), int(start_ms)),
            )
            return int(cur.rowcount or 0)

    def upsert_points(
        self,
        ref: SeriesRef,
        points: Iterable[tuple[int, Any]],
        at_ms: int | None = None,
    ) -> int:
        rows = [(int(ts), value) for ts, value in points]
        if not rows:
            return 0
        self.ensure_partitions(min(ts for ts, _ in rows), max(ts for ts, _ in rows))
        pool = self._ensure_ready()
        ingested_at = int(at_ms) if at_ms is not None else None
        records = [
            (
                self.namespace,
                ref.entity,
                ref.name,
                ref.key,
                ts,
                _to_float(value),
                None if value is None else str(value),
                "ok",
                ingested_at,
            )
            for ts, value in rows
        ]
        columns = "namespace, entity, name, key, ts, value, value_str, quality, ingested_at"
        chunk = 2000
        written = 0
        with pool.connection() as conn, conn.cursor() as cur:
            for offset in range(0, len(records), chunk):
                part = records[offset : offset + chunk]
                placeholders = ", ".join("(" + ", ".join(["%s"] * 9) + ")" for _ in part)
                cur.execute(
                    f"INSERT INTO {self.readings_table} ({columns}) VALUES {placeholders} "
                    "ON CONFLICT (namespace, entity, key, ts) DO UPDATE SET "
                    "name=EXCLUDED.name, value=EXCLUDED.value, "
                    "value_str=EXCLUDED.value_str, quality=EXCLUDED.quality, "
                    "ingested_at=EXCLUDED.ingested_at",
                    [value for record in part for value in record],
                )
                written += len(part)
        return written

    def mark_covered(
        self,
        ref: SeriesRef,
        start_ms: int,
        end_ms: int,
        point_cnt: int,
        at_ms: int,
    ) -> None:
        if end_ms <= start_ms:
            return
        pool = self._ensure_ready()
        with pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                f"INSERT INTO {self.coverage_table} "
                "(namespace, entity, name, key, start_ts, end_ts, point_cnt, covered_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    self.namespace,
                    ref.entity,
                    ref.name,
                    ref.key,
                    int(start_ms),
                    int(end_ms),
                    int(point_cnt),
                    int(at_ms),
                ),
            )

    def replace_range(
        self,
        ref: SeriesRef,
        start_ms: int,
        end_ms: int,
        points: Iterable[tuple[int, Any]],
        at_ms: int | None = None,
    ) -> dict[str, int]:
        """Atomically replace a range (delete + insert in one transaction)."""
        rows = list(points)
        self.ensure_partitions(int(start_ms), int(end_ms))
        pool = self._ensure_ready()
        ingested_at = int(at_ms) if at_ms is not None else None
        with pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute(
                "DELETE FROM "
                f"{self.readings_table} "
                "WHERE namespace=%s AND entity=%s AND key=%s AND ts >= %s AND ts < %s",
                (self.namespace, ref.entity, ref.key, int(start_ms), int(end_ms)),
            )
            deleted = int(cur.rowcount or 0)
            inserted = 0
            if rows:
                records = [
                    (
                        self.namespace,
                        ref.entity,
                        ref.name,
                        ref.key,
                        int(ts),
                        _to_float(value),
                        None if value is None else str(value),
                        "ok",
                        ingested_at,
                    )
                    for ts, value in rows
                ]
                columns = (
                    "namespace, entity, name, key, ts, value, value_str, quality, ingested_at"
                )
                chunk = 2000
                for offset in range(0, len(records), chunk):
                    part = records[offset : offset + chunk]
                    placeholders = ", ".join(
                        "(" + ", ".join(["%s"] * 9) + ")" for _ in part
                    )
                    cur.execute(
                        f"INSERT INTO {self.readings_table} ({columns}) "
                        f"VALUES {placeholders} "
                        "ON CONFLICT (namespace, entity, key, ts) DO UPDATE SET "
                        "name=EXCLUDED.name, value=EXCLUDED.value, "
                        "value_str=EXCLUDED.value_str, quality=EXCLUDED.quality, "
                        "ingested_at=EXCLUDED.ingested_at",
                        [value for record in part for value in record],
                    )
                    inserted += len(part)
        return {"deleted": deleted, "inserted": inserted}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def ping(self) -> bool:
        try:
            pool = self._ensure_ready()
            with pool.connection() as conn, conn.cursor() as cur:
                cur.execute("SELECT 1")
            return True
        except Exception as exc:
            raise StoreError(f"PostgreSQL ping failed: {exc}") from exc

    def close(self) -> None:
        if self._pool is not None:
            self._pool.close()
            self._pool = None
            self._schema_ready = False

    def __enter__(self) -> PostgresStore:
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
