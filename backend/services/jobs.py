from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class JobQueueService:
    def __init__(self, connect: Callable, audit: Callable, log: Callable) -> None:
        self.connect = connect
        self.audit = audit
        self.log = log

    def enqueue(
        self,
        kind: str,
        payload: dict[str, Any],
        *,
        priority: str = "low",
        max_retries: int = 3,
        actor: str = "system",
        event_id: int | None = None,
    ) -> int:
        with self.connect() as db:
            cursor = db.execute(
                """
                INSERT INTO jobs (
                    event_id, kind, priority, status, payload, retry_count, max_retries,
                    retry_at, created_by, created_at, updated_at
                )
                VALUES (?, ?, ?, 'pending', ?, 0, ?, NULL, ?, ?, ?)
                """,
                (event_id, kind, priority, json.dumps(payload, ensure_ascii=True), max_retries, actor, utc_now(), utc_now()),
            )
            job_id = int(cursor.lastrowid)
            self.audit(db, actor, "job.created", "job", job_id, {"kind": kind, "priority": priority, "event_id": event_id})
        return job_id

    def claim_next(self, worker_id: str) -> dict[str, Any] | None:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            lock_clause = " FOR UPDATE SKIP LOCKED" if getattr(db, "engine", "") == "postgres" else ""
            row = db.execute(
                f"""
                SELECT *
                FROM jobs
                WHERE status IN ('pending', 'retrying')
                  AND (retry_at IS NULL OR retry_at <= ?)
                ORDER BY
                    CASE priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
                    id
                LIMIT 1
                {lock_clause}
                """,
                (utc_now(),),
            ).fetchone()
            if not row:
                db.execute("COMMIT")
                return None
            db.execute(
                """
                UPDATE jobs
                SET status = 'processing', worker_id = ?, started_at = ?,
                    updated_at = ?, error = ''
                WHERE id = ?
                """,
                (worker_id, utc_now(), utc_now(), row["id"]),
            )
            db.execute("COMMIT")
            item = dict(row)
            item["payload"] = json.loads(item["payload"] or "{}")
            item["worker_id"] = worker_id
            return item

    def complete(self, job_id: int, result: dict[str, Any]) -> None:
        with self.connect() as db:
            db.execute(
                """
                UPDATE jobs
                SET status = 'completed', result = ?, finished_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (json.dumps(result, ensure_ascii=True), utc_now(), utc_now(), job_id),
            )
            self.audit(db, "worker", "job.completed", "job", job_id, {"result": result})

    def fail(self, job: dict[str, Any], error: str) -> None:
        retry_count = int(job.get("retry_count") or 0) + 1
        max_retries = int(job.get("max_retries") or 0)
        retrying = retry_count <= max_retries
        retry_at = (
            datetime.now(timezone.utc) + timedelta(seconds=min(300, 2 ** retry_count))
        ).isoformat(timespec="seconds") if retrying else None
        with self.connect() as db:
            db.execute(
                """
                UPDATE jobs
                SET status = ?, retry_count = ?, retry_at = ?, error = ?,
                    finished_at = ?, updated_at = ?
                WHERE id = ?
                """,
                ("retrying" if retrying else "failed", retry_count, retry_at, error[:2000], None if retrying else utc_now(), utc_now(), job["id"]),
            )
            self.audit(db, "worker", "job.retry" if retrying else "job.failed", "job", job["id"], {"error": error, "retry_count": retry_count})
        self.log("warning" if retrying else "error", "jobs", f"Job {job['id']} {'reintentando' if retrying else 'fallido'}", error)

    def cancel(self, job_id: int, actor: str) -> bool:
        with self.connect() as db:
            cursor = db.execute(
                "UPDATE jobs SET status = 'cancelled', finished_at = ?, updated_at = ? WHERE id = ? AND status IN ('pending', 'retrying')",
                (utc_now(), utc_now(), job_id),
            )
            if cursor.rowcount:
                self.audit(db, actor, "job.cancelled", "job", job_id, {})
            return bool(cursor.rowcount)


class JobWorker:
    def __init__(self, queue: JobQueueService, handlers: dict[str, Callable[[dict[str, Any]], dict[str, Any]]], worker_id: str = "worker-1") -> None:
        self.queue = queue
        self.handlers = handlers
        self.worker_id = worker_id
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.last_heartbeat = 0.0

    def start(self) -> None:
        if self.thread and self.thread.is_alive():
            return
        self.thread = threading.Thread(target=self.run, name=self.worker_id, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=3)

    def run(self) -> None:
        while not self.stop_event.is_set():
            self.last_heartbeat = time.time()
            job = self.queue.claim_next(self.worker_id)
            if not job:
                self.stop_event.wait(0.2)
                continue
            handler = self.handlers.get(job["kind"])
            if not handler:
                self.queue.fail(job, f"Sin handler para {job['kind']}")
                continue
            started = time.perf_counter()
            try:
                result = handler(job["payload"]) or {}
                result["duration_ms"] = round((time.perf_counter() - started) * 1000, 2)
                self.queue.complete(int(job["id"]), result)
            except Exception as exc:
                self.queue.fail(job, str(exc))
