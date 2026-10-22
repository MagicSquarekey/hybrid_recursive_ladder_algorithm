# -*- coding: utf-8 -*-
"""ThingsBoard telemetry adapter (read-only).

ThingsBoard quirks handled here (all measured against a live deployment):

* Interval aggregation accepts ~700 buckets per request and rejects 800; the
  default ``max_intervals`` is 500.
* Bucket timestamps are returned at ``bucket_start + bucket_ms / 2``; the
  adapter converts them back to bucket starts so the engine can fold them.
* ``endTs`` is inclusive; raw series are filtered to ``[start, end)``.
* There is no ``FIRST`` aggregation, so "first point of a segment" rules need
  raw series (not used by the sum path).
* ``COUNT`` collapses duplicate points within the same minute; use raw series
  when an exact point count is required.
"""

from __future__ import annotations

import threading
from collections.abc import Mapping
from typing import Any

from ..errors import SourceError
from ..models import SeriesRef

__all__ = ["ThingsBoardError", "ThingsBoardSource"]


class ThingsBoardError(SourceError):
    """ThingsBoard request failed."""


class ThingsBoardSource:
    """Read-only ThingsBoard REST client implementing ``TimeSeriesSource``."""

    def __init__(
        self,
        base_url: str,
        *,
        token: str | None = None,
        username: str | None = None,
        password: str | None = None,
        timeout: float = 30.0,
        max_intervals: int = 500,
        max_points: int = 10_000,
        verify: bool = True,
        client: Any | None = None,
    ) -> None:
        if not base_url:
            raise ValueError("base_url is required")
        if not token and not (username and password):
            raise ValueError("provide token=... or username=.../password=...")
        if max_intervals <= 0:
            raise ValueError("max_intervals must be positive")
        self.base_url = base_url.rstrip("/")
        self.max_intervals = int(max_intervals)
        self.max_points = int(max_points)
        self._token = token
        self._username = username
        self._password = password
        self._lock = threading.Lock()

        if client is not None:
            self._client = client
            self._owns_client = False
        else:
            try:
                import httpx
            except ImportError as exc:  # pragma: no cover - dependency error path
                raise ImportError(
                    "ThingsBoardSource needs httpx; install with "
                    "'pip install -e \".[thingsboard]\" (source checkout)'"
                ) from exc
            self._client = httpx.Client(
                timeout=timeout, verify=verify, follow_redirects=True
            )
            self._owns_client = True

    # ------------------------------------------------------------------
    # HTTP plumbing
    # ------------------------------------------------------------------
    def _login(self) -> None:
        if self._token:
            return
        if not (self._username and self._password):
            raise ThingsBoardError("no token and no username/password configured")
        response = self._client.post(
            f"{self.base_url}/api/auth/login",
            json={"username": self._username, "password": self._password},
        )
        if response.status_code >= 400:
            raise ThingsBoardError(
                f"ThingsBoard login failed ({response.status_code}): "
                f"{_snippet(response)}"
            )
        payload = response.json()
        token = payload.get("token")
        if not token:
            raise ThingsBoardError("ThingsBoard login response has no token")
        self._token = token

    def _headers(self) -> dict[str, str]:
        return {"X-Authorization": f"Bearer {self._token}"}

    def _get(self, path: str, params: Mapping[str, Any]) -> Any:
        with self._lock:
            self._login()
            token = self._token
        response = self._client.get(
            f"{self.base_url}{path}", params=dict(params), headers={"X-Authorization": f"Bearer {token}"}
        )
        if response.status_code == 401 and self._username and self._password:
            # Token expired: log in again once and retry.
            with self._lock:
                self._token = None
                self._login()
                token = self._token
            response = self._client.get(
                f"{self.base_url}{path}",
                params=dict(params),
                headers={"X-Authorization": f"Bearer {token}"},
            )
        if response.status_code >= 400:
            raise ThingsBoardError(
                f"ThingsBoard GET {path} failed ({response.status_code}): {_snippet(response)}"
            )
        try:
            return response.json()
        except ValueError as exc:
            raise ThingsBoardError(f"ThingsBoard returned non-JSON for {path}") from exc

    def _telemetry(self, ref: SeriesRef, params: Mapping[str, Any]) -> Mapping[str, Any]:
        path = f"/api/plugins/telemetry/DEVICE/{ref.entity}/values/timeseries"
        payload = self._get(path, {"keys": ref.key, **params})
        return payload if isinstance(payload, Mapping) else {}

    # ------------------------------------------------------------------
    # TimeSeriesSource
    # ------------------------------------------------------------------
    def interval_agg(
        self,
        ref: SeriesRef,
        start_ms: int,
        end_ms: int,
        bucket_ms: int,
        agg: str = "SUM",
    ) -> Mapping[int, Any]:
        if bucket_ms <= 0:
            raise ValueError("bucket_ms must be positive")
        if end_ms <= start_ms:
            return {}
        out: dict[int, Any] = {}
        span = self.max_intervals * bucket_ms
        cursor = int(start_ms)
        while cursor < end_ms:
            chunk_end = min(cursor + span, int(end_ms))
            data = self._telemetry(
                ref,
                {
                    "startTs": cursor,
                    "endTs": chunk_end,
                    "interval": bucket_ms,
                    "intervalType": "MILLISECONDS",
                    "agg": agg,
                    "limit": self.max_intervals,
                },
            )
            for point in data.get(ref.key) or []:
                try:
                    ts = int(float(point.get("ts") or 0))
                except (TypeError, ValueError):
                    continue
                # TB returns bucket_start + half a bucket.
                index = round((ts - cursor - bucket_ms / 2.0) / bucket_ms)
                bucket_start = cursor + index * bucket_ms
                if start_ms <= bucket_start < end_ms:
                    out[bucket_start] = point.get("value")
            cursor = chunk_end
        return out

    def raw_series(
        self,
        ref: SeriesRef,
        start_ms: int,
        end_ms: int,
        limit: int = 10_000,
    ) -> list[tuple[int, Any]]:
        if end_ms <= start_ms:
            return []
        data = self._telemetry(
            ref,
            {
                "startTs": int(start_ms),
                "endTs": int(end_ms) - 1,  # TB is inclusive; keep [start, end)
                "orderBy": "ASC",
                "limit": int(limit),
            },
        )
        points: list[tuple[int, Any]] = []
        for point in data.get(ref.key) or []:
            try:
                ts = int(float(point.get("ts") or 0))
            except (TypeError, ValueError):
                continue
            if start_ms <= ts < end_ms:
                points.append((ts, point.get("value")))
        points.sort(key=lambda item: item[0])
        return points[:limit]

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> ThingsBoardSource:
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()


def _snippet(response: Any, limit: int = 200) -> str:
    try:
        text = response.text
    except Exception:
        return "<no body>"
    text = " ".join(text.split())
    return text[:limit]
