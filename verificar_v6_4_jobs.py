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

        communication_attempts = {"email": 0, "whatsapp": 0}

        def retrying_email(_payload):
            communication_attempts["email"] += 1
            if communication_attempts["email"] == 1:
                return {"ok": False, "status": "pendiente", "error": "fallo transitorio"}
            return {"ok": True, "status": "enviado"}

        def terminal_whatsapp(_payload):
            communication_attempts["whatsapp"] += 1
            return {"ok": False, "status": "error", "error": "fallo definitivo"}

        worker = JobWorker(
            queue,
            {
                "test.ok": ok_handler,
                "test.fail": lambda payload: (_ for _ in ()).throw(RuntimeError("fallo controlado")),
                "email.send": retrying_email,
                "whatsapp.send": terminal_whatsapp,
            },
            "test-worker",
        )
        worker.start()
        job_id = queue.enqueue("test.ok", {"value": "email"}, priority="high", max_retries=1, actor="Admin")
        failed_id = queue.enqueue("test.fail", {}, priority="low", max_retries=0, actor="Admin")
        email_id = queue.enqueue("email.send", {}, priority="high", max_retries=1, actor="Admin")
        whatsapp_id = queue.enqueue("whatsapp.send", {}, priority="high", max_retries=3, actor="Admin")
        cancel_id = queue.enqueue("test.ok", {"value": "cancelled"}, actor="Admin")
        assert queue.cancel(cancel_id, "Admin")
        deadline = time.time() + 5
        while time.time() < deadline:
            with server.connect() as db:
                rows = {row["id"]: row["status"] for row in db.execute("SELECT id, status FROM jobs").fetchall()}
            if (
                rows.get(job_id) == "completed"
                and rows.get(failed_id) == "failed"
                and rows.get(email_id) == "completed"
                and rows.get(whatsapp_id) == "failed"
            ):
                break
            time.sleep(0.1)
        assert rows[job_id] == "completed" and rows[failed_id] == "failed" and rows[cancel_id] == "cancelled"
        assert processed == ["email"]
        assert communication_attempts == {"email": 2, "whatsapp": 1}
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
