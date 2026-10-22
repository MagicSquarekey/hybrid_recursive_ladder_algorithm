# -*- coding: utf-8 -*-
"""HTTP API tests (FastAPI TestClient)."""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient
from helpers import ms

from hybrid_ladder import LadderEngine, MemoryStore
from hybrid_ladder.api import create_app
from hybrid_ladder.demo import DEMO_SERIES, build_demo_source, demo_range
from hybrid_ladder.tasks import TaskRegistry


@pytest.fixture
def app_client():
    store = MemoryStore()
    engine = LadderEngine(build_demo_source(), store, clock=lambda: ms(2030, 1, 1))
    registry = TaskRegistry(ttl_sec=60, max_tasks=20, workers=2)
    app = create_app(engine=engine, registry=registry)
    with TestClient(app) as client:
        yield client, engine, registry
    registry.shutdown(wait=False)


@pytest.fixture
def no_store_client():
    engine = LadderEngine(build_demo_source())
    registry = TaskRegistry(ttl_sec=60, max_tasks=20, workers=2)
    app = create_app(engine=engine, registry=registry)
    with TestClient(app) as client:
        yield client
    registry.shutdown(wait=False)


def _demo_request(**overrides):
    start, end = demo_range()
    payload = {
        "series": [{"entity": DEMO_SERIES[0].entity, "key": DEMO_SERIES[0].key}],
        "start_ts": start,
        "end_ts": end,
        "finest": "minute",
        "mode": "tb",
    }
    payload.update(overrides)
    return payload


def test_health_and_meta(app_client):
    client, _engine, _ = app_client
    health = client.get("/health").json()
    assert health["status"] == "ok"
    assert health["source"] == "MemorySource"
    assert health["store"] == "MemoryStore"

    meta = client.get("/v1/meta").json()
    assert meta["levels"] == ["month", "day", "hour", "minute"]
    assert meta["config"]["finest"] == "minute"
    assert meta["demo"]["series"][0]["entity"] == DEMO_SERIES[0].entity


def test_root_and_demo(app_client):
    client, _, _ = app_client
    root = client.get("/").json()
    assert root["name"] == "hybrid-recursive-ladder"
    assert root["demo"]["start_ts"] == demo_range()[0]
    demo = client.get("/v1/demo").json()
    assert len(demo["series"]) == 2


def test_decompose_endpoint(app_client):
    client, _, _ = app_client
    response = client.get(
        "/v1/decompose",
        params={"start_ts": ms(2026, 1, 1), "end_ts": ms(2026, 10, 21, 18, 49, 59)},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 97
    assert body["by_level"] == {"month": 9, "day": 20, "hour": 18, "minute": 50}


def test_decompose_bad_range_uses_error_envelope(app_client):
    client, _, _ = app_client
    response = client.get("/v1/decompose", params={"start_ts": 1000, "end_ts": 1000})
    assert response.status_code == 400
    assert response.json()["code"] == 1


def test_sum_sync(app_client):
    client, engine, _ = app_client
    start, end = demo_range()
    expected = engine.sum([DEMO_SERIES[0]], start, end).grand_total
    response = client.post("/v1/ladder/sum?sync=true", json=_demo_request())
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    assert body["data"]["grand_total"] == expected
    assert body["data"]["rows"][0]["segments_count"] == 4


def test_sum_async_task(app_client):
    client, engine, _ = app_client
    start, end = demo_range()
    expected = engine.sum([DEMO_SERIES[0]], start, end).grand_total
    response = client.post("/v1/ladder/sum", json=_demo_request())
    assert response.status_code == 200
    task_id = response.json()["data"]["task_id"]

    deadline = time.time() + 5
    snapshot = None
    while time.time() < deadline:
        snapshot = client.get(f"/v1/tasks/{task_id}").json()["data"]
        if snapshot["status"] in ("completed", "failed", "cancelled"):
            break
        time.sleep(0.02)
    assert snapshot["status"] == "completed"
    assert snapshot["result"]["grand_total"] == expected


def test_materialize_then_mixed_and_verify(app_client):
    client, _, _ = app_client
    start, end = demo_range()
    materialized = client.post(
        "/v1/ladder/materialize?sync=true",
        json={
            "series": [{"entity": DEMO_SERIES[0].entity, "key": DEMO_SERIES[0].key}],
            "start_ts": start,
            "end_ts": end,
        },
    )
    assert materialized.status_code == 200
    assert materialized.json()["data"]["written"] == 11_520

    mixed = client.post(
        "/v1/ladder/sum?sync=true", json=_demo_request(mode="mixed")
    ).json()["data"]
    assert mixed["source"] == "local"
    assert mixed["rows"][0]["tb_ranges"] == []

    verify = client.post(
        "/v1/ladder/verify?sync=true", json=_demo_request()
    ).json()["data"]
    assert verify["diff_segments"] == 0

    repair = client.post(
        "/v1/ladder/repair?sync=true", json=_demo_request()
    ).json()["data"]
    assert repair["series"][0]["inserted"] == 11_520


def test_mixed_without_store_returns_400(no_store_client):
    response = no_store_client.post(
        "/v1/ladder/sum?sync=true", json=_demo_request(mode="mixed")
    )
    assert response.status_code == 400
    assert response.json()["code"] == 1


def test_sum_validation_errors(app_client):
    client, _, _ = app_client
    assert client.post(
        "/v1/ladder/sum?sync=true", json=_demo_request(series=[])
    ).status_code == 400
    assert client.post(
        "/v1/ladder/sum?sync=true", json=_demo_request(mode="nope")
    ).status_code == 400
    bad_range = _demo_request()
    bad_range["end_ts"] = bad_range["start_ts"]
    assert client.post("/v1/ladder/sum?sync=true", json=bad_range).status_code == 400


def test_task_404_and_cancel(app_client):
    client, _, _ = app_client
    response = client.get("/v1/tasks/missing")
    assert response.status_code == 404
    assert response.json()["code"] == 1

    task_id = client.post("/v1/ladder/sum", json=_demo_request()).json()["data"]["task_id"]
    deadline = time.time() + 5
    while time.time() < deadline:
        snapshot = client.get(f"/v1/tasks/{task_id}").json()["data"]
        if snapshot["status"] != "running":
            break
        time.sleep(0.02)
    cancelled = client.post(f"/v1/tasks/{task_id}/cancel").json()["data"]
    assert cancelled["cancelled"] is False


def test_list_tasks(app_client):
    client, _, _ = app_client
    client.post("/v1/ladder/sum", json=_demo_request())
    response = client.get("/v1/tasks")
    assert response.status_code == 200
    assert len(response.json()["tasks"]) >= 1
