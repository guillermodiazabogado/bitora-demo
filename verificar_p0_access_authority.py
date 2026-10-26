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
    temp_root = Path(tempfile.mkdtemp(prefix="bitora-p0-access-authority-", dir=workspace_tmp))
    original_db_path = server.DB_PATH
    original_backup_dir = server.BACKUP_DIR
    try:
        server.DB_PATH = temp_root / "authority.sqlite3"
        server.BACKUP_DIR = temp_root / "backups"
        server.init_db()
        server.seed_if_empty()
        with server.connect() as db:
            event = db.execute("SELECT id, organization_id FROM events ORDER BY id LIMIT 1").fetchone()
            event_id = int(event["id"])
            organization_id = server.event_organization_id(db, event_id)
            registration = server.register_accreditation(
                db,
                event_id,
                {"first_name": "Authority", "last_name": "Test", "email": "authority@bitora.test", "type": "General", "actor": "test"},
            )
            assert_true(registration["ok"], registration)
            server.enterprise_core_service().backfill_event(db, organization_id=organization_id, event_id=event_id, actor="test")
            scope = server.access_event_scope(db, registration["token"])
            assert_true(scope is not None, "credential scope missing")

            def validate(direction, key):
                return server.enforced_access_validation(
                    db,
                    token=registration["token"], operator="Admin", checkpoint="Gate A", activity_id=0,
                    direction=direction, correlation_id=key, idempotency_key=key, data={}, event_scope=scope,
                )

            first = validate("ENTRY", "p0-entry")
            assert_true(first["result"] == "granted" and first["authority"] == "v5", first)
            replay = validate("ENTRY", "p0-entry")
            assert_true(replay["idempotent_replay"] and replay["access_event_id"] == first["access_event_id"], replay)
            access_count = db.execute("SELECT access_count FROM accreditations WHERE id = ?", (registration["id"],)).fetchone()["access_count"]
            assert_true(access_count == 1, "idempotent replay mutated legacy count")
            anti = validate("ENTRY", "p0-anti")
            assert_true(anti["result"] == "rejected" and anti["reason_code"] == "ANTI_PASSBACK", anti)
            exit_result = validate("EXIT", "p0-exit")
            assert_true(exit_result["result"] == "granted" and exit_result["current_state"] == "OUTSIDE", exit_result)
            count = db.execute("SELECT COUNT(*) AS c FROM enterprise_access_events").fetchone()["c"]
            assert_true(count == 3, count)
        print("P0 V5 access authority, anti-passback and idempotency: OK")
    finally:
        server.DB_PATH = original_db_path
        server.BACKUP_DIR = original_backup_dir
        shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    main()
