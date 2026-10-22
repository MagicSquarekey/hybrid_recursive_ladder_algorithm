# -*- coding: utf-8 -*-
"""In-process task registry tests."""

from __future__ import annotations

import time

import pytest

from hybrid_ladder import CancelledError
from hybrid_ladder.tasks import TaskRegistry


@pytest.fixture
def registry():
    reg = TaskRegistry(ttl_sec=60, max_tasks=10, workers=2)
    yield reg
    reg.shutdown(wait=False)


def wait_for(registry: TaskRegistry, task_id: str, timeout: float = 3.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        snapshot = registry.snapshot(task_id)
        assert snapshot is not None
        if snapshot["status"] in ("completed", "failed", "cancelled"):
            return snapshot
        time.sleep(0.01)
    raise AssertionError("task did not finish")


def test_lifecycle(registry):
    def runner(progress, cancelled):
        progress(1, 2, "half")
        time.sleep(0.01)
        progress(2, 2, "done")
        return {"ok": True}

    task_id = registry.create("test", 2, runner)
    snapshot = wait_for(registry, task_id)
    assert snapshot["status"] == "completed"
    assert snapshot["result"] == {"ok": True}
    assert snapshot["done"] == 2 and snapshot["total"] == 2
    assert snapshot["message"] == "completed"
    assert snapshot["elapsed"] >= 0


def test_failure_is_reported(registry):
    def runner(progress, cancelled):
        raise ValueError("boom")

    task_id = registry.create("failure", 1, runner)
    snapshot = wait_for(registry, task_id)
    assert snapshot["status"] == "failed"
    assert "boom" in snapshot["error"]


def test_cancel(registry):
    def runner(progress, cancelled):
        for _ in range(200):
            if cancelled():
                raise CancelledError("cancelled")
            time.sleep(0.005)
        return {"never": True}

    task_id = registry.create("cancel", 1, runner)
    assert registry.cancel(task_id) is True
    snapshot = wait_for(registry, task_id)
    assert snapshot["status"] == "cancelled"


def test_cancel_completed_task_returns_false(registry):
    task_id = registry.create("quick", 1, lambda progress, cancelled: 1)
    wait_for(registry, task_id)
    assert registry.cancel(task_id) is False


def test_snapshot_missing(registry):
    assert registry.snapshot("nope") is None


def test_list_and_clear_finished(registry):
    task_id = registry.create("one", 1, lambda progress, cancelled: 1)
    wait_for(registry, task_id)
    listed = registry.list()
    assert any(item["task_id"] == task_id for item in listed)
    assert registry.clear_finished() == 1
    assert registry.snapshot(task_id) is None


def test_ttl_cleanup():
    registry = TaskRegistry(ttl_sec=0.05, max_tasks=10, workers=1)
    try:
        first = registry.create("old", 1, lambda progress, cancelled: 1)
        wait_for(registry, first)
        time.sleep(0.1)
        second = registry.create("new", 1, lambda progress, cancelled: 1)
        wait_for(registry, second)
        assert registry.snapshot(first) is None
        assert registry.snapshot(second) is not None
    finally:
        registry.shutdown(wait=False)


def test_max_tasks_cleanup():
    registry = TaskRegistry(ttl_sec=60, max_tasks=2, workers=2)
    try:
        ids = []
        for index in range(3):
            task_id = registry.create(f"t{index}", 1, lambda progress, cancelled: 1)
            ids.append(task_id)
            wait_for(registry, task_id)
        # Creating a fourth task trims the oldest finished tasks.
        newest = registry.create("t3", 1, lambda progress, cancelled: 1)
        wait_for(registry, newest)
        assert len(registry.list()) <= 2
    finally:
        registry.shutdown(wait=False)
