# -*- coding: utf-8 -*-
"""A tiny in-process task registry for long-running ladder operations.

Queries can take seconds to minutes when a range is large or a source is slow.
The registry runs them on a small thread pool, exposes progress, and supports
cancellation.  Results live in memory and expire after ``ttl_sec``; a process
restart loses them, but every result can be recomputed.
"""

from __future__ import annotations

import threading
import time
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from .errors import CancelledError

__all__ = ["TaskRegistry", "default_registry"]

ProgressFn = Callable[[int | None, int | None, str | None], None]
CancelFn = Callable[[], bool]
Runner = Callable[[ProgressFn, CancelFn], Any]


class TaskRegistry:
    """Thread-pool backed task registry."""

    def __init__(self, *, ttl_sec: int = 3600, max_tasks: int = 100, workers: int = 4) -> None:
        if ttl_sec <= 0:
            raise ValueError("ttl_sec must be positive")
        if max_tasks <= 0:
            raise ValueError("max_tasks must be positive")
        if workers <= 0:
            raise ValueError("workers must be positive")
        self.ttl_sec = ttl_sec
        self.max_tasks = max_tasks
        self._lock = threading.Lock()
        self._tasks: dict[str, dict[str, Any]] = {}
        self._pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="hybrid-task")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def create(self, title: str, total: int, runner: Runner) -> str:
        """Create and start a task; returns its id."""
        task_id = uuid.uuid4().hex
        with self._lock:
            self._tasks[task_id] = {
                "task_id": task_id,
                "title": title,
                "status": "running",
                "done": 0,
                "total": max(1, int(total or 1)),
                "message": "starting…",
                "result": None,
                "error": None,
                "cancel": False,
                "started_at": time.time(),
                "finished_at": None,
            }
            # Clean up after inserting the new task, otherwise the registry can
            # grow one task past ``max_tasks`` before the next create().
            self._cleanup_locked()
        self._pool.submit(self._run, task_id, runner)
        return task_id

    def snapshot(self, task_id: str, with_result: bool = True) -> dict[str, Any] | None:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return None
            out = {key: value for key, value in task.items() if key != "result"}
            out["elapsed"] = round(
                (task.get("finished_at") or time.time()) - task["started_at"], 3
            )
            if with_result and task["status"] == "completed":
                out["result"] = task["result"]
            return out

    def cancel(self, task_id: str) -> bool:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None or task["status"] != "running":
                return False
            task["cancel"] = True
            task["message"] = "cancelling…"
            return True

    def list(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            tasks = sorted(
                self._tasks.values(), key=lambda t: t["started_at"], reverse=True
            )[:limit]
            return [
                {
                    "task_id": t["task_id"],
                    "title": t["title"],
                    "status": t["status"],
                    "done": t["done"],
                    "total": t["total"],
                    "message": t["message"],
                }
                for t in tasks
            ]

    def clear_finished(self) -> int:
        with self._lock:
            finished = [tid for tid, t in self._tasks.items() if t.get("finished_at")]
            for tid in finished:
                self._tasks.pop(tid, None)
            return len(finished)

    def shutdown(self, wait: bool = False) -> None:
        self._pool.shutdown(wait=wait, cancel_futures=True)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _cleanup_locked(self) -> None:
        now = time.time()
        expired = [
            tid
            for tid, task in self._tasks.items()
            if task.get("finished_at") and now - task["finished_at"] > self.ttl_sec
        ]
        for tid in expired:
            self._tasks.pop(tid, None)
        if len(self._tasks) > self.max_tasks:
            finished = sorted(
                (t for t in self._tasks.values() if t.get("finished_at")),
                key=lambda t: t["finished_at"],
            )
            for task in finished[: len(self._tasks) - self.max_tasks]:
                self._tasks.pop(task["task_id"], None)

    def _run(self, task_id: str, runner: Runner) -> None:
        with self._lock:
            if task_id not in self._tasks:
                return

        def progress(done: int | None = None, total: int | None = None,
                     message: str | None = None) -> None:
            with self._lock:
                task = self._tasks.get(task_id)
                if task is None:
                    return
                if done is not None:
                    task["done"] = int(done)
                if total is not None:
                    task["total"] = max(1, int(total))
                if message:
                    task["message"] = str(message)[:200]

        def cancelled() -> bool:
            with self._lock:
                task = self._tasks.get(task_id)
                return bool(task and task["cancel"])

        try:
            result = runner(progress, cancelled)
            with self._lock:
                task = self._tasks.get(task_id)
                if task is None:
                    return
                if task["cancel"]:
                    task["status"] = "cancelled"
                    task["message"] = "cancelled"
                else:
                    task["status"] = "completed"
                    task["result"] = result
                    task["done"] = task["total"]
                    task["message"] = "completed"
                task["finished_at"] = time.time()
        except BaseException as exc:
            with self._lock:
                task = self._tasks.get(task_id)
                if task is None:
                    return
                if task["cancel"] or isinstance(exc, CancelledError):
                    task["status"] = "cancelled"
                    task["message"] = "cancelled"
                else:
                    task["status"] = "failed"
                    task["error"] = str(exc)[:500]
                    task["message"] = "failed: " + str(exc)[:160]
                task["finished_at"] = time.time()


_default_registry: TaskRegistry | None = None
_default_lock = threading.Lock()


def default_registry() -> TaskRegistry:
    """Return the process-wide registry used by the HTTP app."""
    global _default_registry
    if _default_registry is None:
        with _default_lock:
            if _default_registry is None:
                _default_registry = TaskRegistry()
    return _default_registry
