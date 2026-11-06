from __future__ import annotations

import shutil
import tempfile
import time
from pathlib import Path

import server
from backend.services.jobs import JobWorker


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="bitora-v64-jobs-"))
    old_db, old_backup = server.DB_PATH, server.BACKUP_DIR
    worker = None
    try:
        server.DB_PATH = tmp / "jobs.sqlite3"
        server.BACKUP_DIR = tmp / "backups"
        server.init_db()
        server.seed_if_empty()
        queue = server.job_queue_service()
        processed: list[str] = []

        def ok_handler(payload):
            processed.append(payload["value"])
            return {"ok": True}

        worker = JobWorker(queue, {"test.ok": ok_handler, "test.fail": lambda payload: (_ for _ in ()).throw(RuntimeError("fallo controlado"))}, "test-worker")
        worker.start()
        job_id = queue.enqueue("test.ok", {"value": "email"}, priority="high", max_retries=1, actor="Admin")
        failed_id = queue.enqueue("test.fail", {}, priority="low", max_retries=0, actor="Admin")
        cancel_id = queue.enqueue("test.ok", {"value": "cancelled"}, actor="Admin")
        assert queue.cancel(cancel_id, "Admin")
        deadline = time.time() + 5
        while time.time() < deadline:
            with server.connect() as db:
                rows = {row["id"]: row["status"] for row in db.execute("SELECT id, status FROM jobs").fetchall()}
            if rows.get(job_id) == "completed" and rows.get(failed_id) == "failed":
                break
            time.sleep(0.1)
        assert rows[job_id] == "completed" and rows[failed_id] == "failed" and rows[cancel_id] == "cancelled"
        assert processed == ["email"]
        with server.connect() as db:
            recovered = queue.enqueue("test.ok", {"value": "recovered"}, actor="Admin")
        worker.stop()
        worker = JobWorker(queue, {"test.ok": ok_handler}, "recovery-worker")
        worker.start()
        deadline = time.time() + 5
        while time.time() < deadline:
            with server.connect() as db:
                status = db.execute("SELECT status FROM jobs WHERE id = ?", (recovered,)).fetchone()["status"]
            if status == "completed":
                break
            time.sleep(0.1)
        assert status == "completed"
        print("OK: V6.4 cola persistente, worker, fallo, cancelacion y recuperacion")
    finally:
        if worker:
            worker.stop()
        server.DB_PATH, server.BACKUP_DIR = old_db, old_backup
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
