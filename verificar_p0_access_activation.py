from __future__ import annotations

from pathlib import Path
import shutil
import tempfile

import server


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main() -> None:
    workspace_tmp = Path(__file__).resolve().parent / "tmp"
    workspace_tmp.mkdir(parents=True, exist_ok=True)
    temp_root = Path(tempfile.mkdtemp(prefix="bitora-p0-access-activation-", dir=workspace_tmp))
    original_db_path = server.DB_PATH
    original_backup_dir = server.BACKUP_DIR
    try:
        server.DB_PATH = temp_root / "activation.sqlite3"
        server.BACKUP_DIR = temp_root / "backups"
        server.init_db()
        server.seed_if_empty()
        with server.connect() as db:
            event_id = int(db.execute("SELECT id FROM events ORDER BY id LIMIT 1").fetchone()["id"])
            first = server.register_accreditation(db, event_id, {"first_name": "Legacy", "last_name": "Inside", "email": "legacy-inside@bitora.test", "type": "General", "actor": "test"})
            second = server.register_accreditation(db, event_id, {"first_name": "Fresh", "last_name": "Outside", "email": "fresh-outside@bitora.test", "type": "General", "actor": "test"})
            assert_true(first["ok"] and second["ok"], (first, second))
            legacy = server.access_validation_service().validate(db, first["token"], "Admin", "Legacy Gate")
            assert_true(legacy["result"] == "granted", legacy)

            before = server.access_state_enforcement_readiness(db, event_id)
            assert_true(not before["ready"] and before["unmapped_active_credentials"] >= 2, before)
            activated = server.set_access_state_enforcement(db, event_id, enabled=True, actor="Admin")
            assert_true(activated["ok"] and activated["ready"] and activated["enabled"], activated)
            assert_true(activated["state_snapshots"] >= 1, activated)

            scope = server.access_event_scope(db, second["token"])
            result = server.enforced_access_validation(
                db,
                token=second["token"], operator="Admin", checkpoint="Gate", activity_id=0,
                direction="ENTRY", correlation_id="activation-entry", idempotency_key="activation-entry", data={}, event_scope=scope,
            )
            assert_true(result["result"] == "granted" and result["authority"] == "v5", result)

            deactivated = server.set_access_state_enforcement(db, event_id, enabled=False, actor="Admin")
            assert_true(deactivated["ok"] and not deactivated["enabled"], deactivated)
        print("P0 access enforcement readiness, activation and rollback-safe disable: OK")
    finally:
        server.DB_PATH = original_db_path
        server.BACKUP_DIR = original_backup_dir
        shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    main()
