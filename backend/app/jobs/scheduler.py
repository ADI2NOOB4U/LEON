"""Persistent, condition-driven scheduler for one-time and recurring jobs."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Protocol

from backend.app.db.database import get_connection, now
from backend.app.notifications.service import notification_service


class ScheduledJobExecutor(Protocol):
    def execute(self, job: dict[str, Any]) -> None:
        """Run a claimed scheduled job."""


class NotificationJobExecutor:
    """Executes the built-in notification job payload."""

    def execute(self, job: dict[str, Any]) -> None:
        payload = job["payload"]
        if payload.get("type") == "news_briefing":
            import asyncio
            from backend.app.news.service import news_service
            asyncio.run(news_service.run(payload.get("schedule", "scheduled"), payload.get("subscription_id")))
            return
        if payload.get("type") != "notification":
            raise ValueError("Unsupported scheduled job type")
        title = payload.get("title")
        body = payload.get("body")
        if not isinstance(title, str) or not isinstance(body, str):
            raise ValueError("Notification jobs require title and body strings")
        notification_service.send(title, body)


def _timestamp(value: datetime | str) -> str:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("run_at must be an ISO-8601 timestamp") from exc
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("run_at must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat()


class SchedulerService:
    """Runs persisted jobs without polling when no job is due."""

    def __init__(
        self,
        executor: ScheduledJobExecutor | None = None,
        retry_delay_seconds: int = 30,
    ) -> None:
        self._executor = executor or NotificationJobExecutor()
        self._retry_delay_seconds = retry_delay_seconds
        self._condition = threading.Condition()
        self._running = False
        self._thread: threading.Thread | None = None

    def schedule_once(
        self, name: str, run_at: datetime | str, payload: dict[str, Any], max_retries: int = 2
    ) -> dict[str, Any]:
        return self._schedule(name, run_at, payload, None, max_retries)

    def schedule_recurring(
        self,
        name: str,
        run_at: datetime | str,
        interval_seconds: int,
        payload: dict[str, Any],
        max_retries: int = 2,
    ) -> dict[str, Any]:
        if isinstance(interval_seconds, bool) or not isinstance(interval_seconds, int) or interval_seconds < 1:
            raise ValueError("interval_seconds must be a positive integer")
        return self._schedule(name, run_at, payload, interval_seconds, max_retries)

    def _schedule(
        self, name: str, run_at: datetime | str, payload: dict[str, Any], interval_seconds: int | None, max_retries: int
    ) -> dict[str, Any]:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("name must be a non-empty string")
        if not isinstance(payload, dict):
            raise ValueError("payload must be an object")
        if isinstance(max_retries, bool) or not isinstance(max_retries, int) or not 0 <= max_retries <= 10:
            raise ValueError("max_retries must be an integer between 0 and 10")
        timestamp = _timestamp(run_at)
        conn = get_connection()
        cursor = conn.execute(
            """INSERT INTO scheduled_jobs
               (name, run_at, interval_seconds, payload, status, retry_count, max_retries, created_at, updated_at)
               VALUES (?, ?, ?, ?, 'pending', 0, ?, ?, ?)""",
            (name.strip(), timestamp, interval_seconds, json.dumps(payload), max_retries, now(), now()),
        )
        job_id = int(cursor.lastrowid)
        conn.commit()
        conn.close()
        with self._condition:
            self._condition.notify_all()
        return self.get_job(job_id)  # type: ignore[return-value]

    def get_job(self, job_id: int) -> dict[str, Any] | None:
        conn = get_connection()
        row = conn.execute("SELECT * FROM scheduled_jobs WHERE id = ?", (job_id,)).fetchone()
        conn.close()
        return self._decode(row) if row else None

    def start(self) -> None:
        with self._condition:
            if self._running:
                return
            self._recover_interrupted_jobs()
            self._running = True
            self._thread = threading.Thread(target=self._run, daemon=True, name="LEON-Scheduler")
            self._thread.start()

    def stop(self) -> None:
        with self._condition:
            self._running = False
            self._condition.notify_all()
            thread = self._thread
        if thread and thread is not threading.current_thread():
            thread.join(timeout=5)

    def _run(self) -> None:
        while True:
            with self._condition:
                if not self._running:
                    return
            job = self._claim_due_job()
            if job:
                self._process(job)
                continue
            with self._condition:
                if not self._running:
                    return
                self._condition.wait(timeout=self._seconds_until_next_job())

    def _claim_due_job(self) -> dict[str, Any] | None:
        conn = get_connection()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT * FROM scheduled_jobs WHERE status = 'pending' AND run_at <= ? ORDER BY run_at, id LIMIT 1",
                (now(),),
            ).fetchone()
            if not row:
                conn.commit()
                return None
            claimed = conn.execute(
                "UPDATE scheduled_jobs SET status = 'running', updated_at = ? WHERE id = ? AND status = 'pending'",
                (now(), row["id"]),
            ).rowcount
            conn.commit()
            return self._decode(row) if claimed else None
        finally:
            conn.close()

    def _process(self, job: dict[str, Any]) -> None:
        try:
            self._executor.execute(job)
        except Exception as exc:
            self._record_failure(job, str(exc))
        else:
            self._record_success(job)

    def _record_success(self, job: dict[str, Any]) -> None:
        status, run_at = "completed", job["run_at"]
        if job["interval_seconds"] is not None:
            next_run = datetime.fromisoformat(job["run_at"]) + timedelta(seconds=job["interval_seconds"])
            while next_run <= datetime.now(timezone.utc):
                next_run += timedelta(seconds=job["interval_seconds"])
            status, run_at = "pending", next_run.isoformat()
        self._update_job(job["id"], status=status, run_at=run_at, last_error=None)

    def _record_failure(self, job: dict[str, Any], error: str) -> None:
        retry_count = job["retry_count"] + 1
        if retry_count <= job["max_retries"]:
            run_at = (datetime.now(timezone.utc) + timedelta(seconds=self._retry_delay_seconds)).isoformat()
            self._update_job(job["id"], status="pending", run_at=run_at, retry_count=retry_count, last_error=error)
        else:
            self._update_job(job["id"], status="failed", retry_count=retry_count, last_error=error)

    def _update_job(self, job_id: int, **fields: Any) -> None:
        fields["updated_at"] = now()
        assignments = ", ".join(f"{name} = ?" for name in fields)
        conn = get_connection()
        conn.execute(f"UPDATE scheduled_jobs SET {assignments} WHERE id = ?", [*fields.values(), job_id])
        conn.commit()
        conn.close()
        with self._condition:
            self._condition.notify_all()

    def _seconds_until_next_job(self) -> float | None:
        conn = get_connection()
        row = conn.execute("SELECT run_at FROM scheduled_jobs WHERE status = 'pending' ORDER BY run_at LIMIT 1").fetchone()
        conn.close()
        if not row:
            return None
        return max(0.01, (datetime.fromisoformat(row["run_at"]) - datetime.now(timezone.utc)).total_seconds())

    def _recover_interrupted_jobs(self) -> None:
        conn = get_connection()
        conn.execute("UPDATE scheduled_jobs SET status = 'pending', updated_at = ? WHERE status = 'running'", (now(),))
        conn.commit()
        conn.close()

    @staticmethod
    def _decode(row: Any) -> dict[str, Any]:
        job = dict(row)
        job["payload"] = json.loads(job["payload"])
        return job


scheduler = SchedulerService()
