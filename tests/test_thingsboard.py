# -*- coding: utf-8 -*-
"""ThingsBoard adapter tests with a mocked HTTP transport."""

from __future__ import annotations

import httpx
import pytest

from hybrid_ladder.models import SeriesRef
from hybrid_ladder.sources.thingsboard import ThingsBoardError, ThingsBoardSource

REF = SeriesRef("device-1", "energy")


def make_source(handler, **kwargs) -> ThingsBoardSource:
    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport, base_url="http://tb.test")
    return ThingsBoardSource("http://tb.test", token="token", client=client, **kwargs)


def test_interval_agg_normalizes_bucket_starts():
    def handler(request: httpx.Request) -> httpx.Response:
        params = request.url.params
        interval = int(params["interval"])
        start = int(params["startTs"])
        end = int(params["endTs"])
        points = []
        cursor = start
        while cursor < end:
            points.append({"ts": str(cursor + interval // 2), "value": "2"})
            cursor += interval
        return httpx.Response(200, json={"energy": points})

    source = make_source(handler, max_intervals=10)
    result = source.interval_agg(REF, 0, 3 * 60_000, 60_000)
    assert result == {0: "2", 60_000: "2", 120_000: "2"}


def test_interval_agg_chunks_requests():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        params = request.url.params
        interval = int(params["interval"])
        start = int(params["startTs"])
        end = int(params["endTs"])
        calls.append((start, end))
        points = []
        cursor = start
        while cursor < end:
            points.append({"ts": str(cursor + interval // 2), "value": "1"})
            cursor += interval
        return httpx.Response(200, json={"energy": points})

    source = make_source(handler, max_intervals=2)
    result = source.interval_agg(REF, 0, 6 * 60_000, 60_000)
    assert len(calls) == 3
    assert calls == [(0, 120_000), (120_000, 240_000), (240_000, 360_000)]
    assert sorted(result) == [0, 60_000, 120_000, 180_000, 240_000, 300_000]


def test_raw_series_filters_exclusive_end():
    start, end = 0, 60_000

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["endTs"] == str(end - 1)
        return httpx.Response(
            200,
            json={
                "energy": [
                    {"ts": str(start), "value": "1"},
                    {"ts": str(start + 1_000), "value": "2"},
                    {"ts": str(end), "value": "3"},
                ]
            },
        )

    source = make_source(handler)
    points = source.raw_series(REF, start, end)
    assert points == [(0, "1"), (1_000, "2")]


def test_auth_header_is_sent():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("x-authorization")
        return httpx.Response(200, json={"energy": []})

    source = make_source(handler)
    source.raw_series(REF, 0, 1_000)
    assert seen["auth"] == "Bearer token"


def test_login_when_no_token():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.path)
        if request.url.path == "/api/auth/login":
            return httpx.Response(200, json={"token": "fresh"})
        assert request.headers["x-authorization"] == "Bearer fresh"
        return httpx.Response(200, json={"energy": [{"ts": "0", "value": "1"}]})

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport, base_url="http://tb.test")
    source = ThingsBoardSource(
        "http://tb.test", username="user", password="secret", client=client
    )
    points = source.raw_series(REF, 0, 1_000)
    assert points == [(0, "1")]
    assert requests == [
        "/api/auth/login",
        "/api/plugins/telemetry/DEVICE/device-1/values/timeseries",
    ]


def test_retry_after_401():
    requests = []
    telemetry_calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.path)
        if request.url.path == "/api/auth/login":
            return httpx.Response(200, json={"token": f"token-{len(requests)}"})
        telemetry_calls["n"] += 1
        if telemetry_calls["n"] == 1:
            return httpx.Response(401, json={"message": "expired"})
        return httpx.Response(200, json={"energy": [{"ts": "0", "value": "1"}]})

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport, base_url="http://tb.test")
    source = ThingsBoardSource(
        "http://tb.test", username="user", password="secret", client=client
    )
    points = source.raw_series(REF, 0, 1_000)
    assert points == [(0, "1")]
    assert requests.count("/api/auth/login") == 2


def test_http_error_becomes_source_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="kaboom")

    source = make_source(handler)
    with pytest.raises(ThingsBoardError) as exc:
        source.raw_series(REF, 0, 1_000)
    assert "500" in str(exc.value)
    assert "kaboom" in str(exc.value)


def test_requires_credentials():
    with pytest.raises(ValueError):
        ThingsBoardSource("http://tb.test")
    with pytest.raises(ValueError):
        ThingsBoardSource("http://tb.test", username="only-user")
