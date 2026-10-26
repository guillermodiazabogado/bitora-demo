from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import shutil
import tempfile

import server


def main() -> None:
    workspace_tmp = Path(__file__).resolve().parent / "tmp"
    workspace_tmp.mkdir(exist_ok=True)
    temp_root = Path(tempfile.mkdtemp(prefix="bitora-p1-concurrency-", dir=workspace_tmp))
    original_db_path = server.DB_PATH
    original_backup_dir = server.BACKUP_DIR
    try:
        server.DB_PATH = temp_root / "concurrency.sqlite3"
        server.BACKUP_DIR = temp_root / "backups"
        server.init_db()
        server.seed_if_empty()
        with server.connect() as db:
            event_id = int(db.execute("SELECT id FROM events ORDER BY id LIMIT 1").fetchone()["id"])
            registration = server.register_accreditation(
                db,
                event_id,
                {"first_name": "Concurrent", "last_name": "Access", "email": "concurrent@bitora.test", "type": "General", "actor": "test"},
            )
            if not registration["ok"]:
                raise AssertionError(registration)
            activated = server.set_access_state_enforcement(db, event_id, enabled=True, actor="test")
            if not activated["ok"]:
                raise AssertionError(activated)
            token = registration["token"]

        def attempt(index: int) -> dict:
            with server.DB_LOCK, server.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                scope = server.access_event_scope(db, token)
                result = server.enforced_access_validation(
                    db,
                    token=token,
                    operator="Concurrent",
                    checkpoint="Gate",
                    activity_id=0,
                    direction="ENTRY",
                    correlation_id=f"concurrent-{index}",
                    idempotency_key=f"concurrent-{index}",
                    data={},
                    event_scope=scope,
                )
                db.execute("COMMIT")
                return result

        with ThreadPoolExecutor(max_workers=30) as pool:
            results = list(pool.map(attempt, range(30)))
        granted = [item for item in results if item["result"] == "granted"]
        denied = [item for item in results if item["reason_code"] == "ANTI_PASSBACK"]
        if len(granted) != 1 or len(denied) != 29:
            raise AssertionError({"granted": len(granted), "anti_passback": len(denied), "results": results})
        with server.connect() as db:
            snapshot = db.execute(
                "SELECT current_state FROM enterprise_access_state_snapshots WHERE event_id = ?",
                (event_id,),
            ).fetchone()
            allowed_events = int(db.execute(
                "SELECT COUNT(*) AS c FROM enterprise_access_events WHERE event_id = ? AND decision = 'ALLOW'",
                (event_id,),
            ).fetchone()["c"])
        if not snapshot or snapshot["current_state"] != "INSIDE" or allowed_events != 1:
            raise AssertionError((snapshot, allowed_events))
        print("P1 direct concurrency: 30 ENTRY, 1 ALLOW, 29 ANTI_PASSBACK: OK")
    finally:
        server.DB_PATH = original_db_path
        server.BACKUP_DIR = original_backup_dir
        shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    main()
