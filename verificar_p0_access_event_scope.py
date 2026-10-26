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
    temp_root = Path(tempfile.mkdtemp(prefix="bitora-p0-access-scope-", dir=workspace_tmp))
    original_db_path = server.DB_PATH
    original_backup_dir = server.BACKUP_DIR
    try:
        server.DB_PATH = temp_root / "access-scope.sqlite3"
        server.BACKUP_DIR = temp_root / "backups"
        server.init_db()
        server.seed_if_empty()

        with server.connect() as db:
            events = db.execute("SELECT id FROM events ORDER BY id LIMIT 2").fetchall()
            if len(events) < 2:
                first = int(events[0]["id"])
                source = db.execute("SELECT * FROM events WHERE id = ?", (first,)).fetchone()
                created = db.execute(
                    "INSERT INTO events (organization_id, name, description, venue, starts_at, ends_at, capacity, created_at) VALUES (?, 'Scope B', '', '', ?, ?, 10, ?)",
                    (source["organization_id"], source["starts_at"], source["ends_at"], server.now_iso()),
                )
                event_b = int(created.lastrowid)
            else:
                event_b = int(events[1]["id"])
            event_a = int(events[0]["id"])

            registration = server.register_accreditation(
                db,
                event_a,
                {
                    "first_name": "Scope",
                    "last_name": "Test",
                    "email": "scope-test@bitora.test",
                    "type": "General",
                    "actor": "test",
                },
            )
            assert_true(registration["ok"], registration)
            token = registration["token"]

            direct = server.access_event_scope(db, token.lower())
            linked = server.access_event_scope(db, f"https://event.test/p.html?token={token.lower()}")
            missing = server.access_event_scope(db, "EVT-NOT-FOUND")
            assert_true(direct and int(direct["event_id"]) == event_a, "token did not resolve its stored event")
            assert_true(linked and int(linked["event_id"]) == event_a, "credential URL did not resolve its stored event")
            assert_true(missing is None, "unknown token unexpectedly resolved")

            user = db.execute("SELECT id, role FROM users WHERE role <> 'Super Admin' ORDER BY id LIMIT 1").fetchone()
            assert_true(user is not None, "seed did not create a scoped non-super-admin user")
            user_id = int(user["id"])
            db.execute("UPDATE user_event_roles SET active = 0 WHERE user_id = ?", (user_id,))
            db.execute(
                "INSERT INTO user_event_roles (user_id, event_id, role, active, created_at) VALUES (?, ?, ?, 1, ?)",
                (user_id, event_b, user["role"], server.now_iso()),
            )
            session = {"id": user_id, "role": user["role"]}
            assert_true(server.session_can_access_event(db, session, event_b), "control assignment was not active")
            assert_true(not server.session_can_access_event(db, session, event_a), "cross-event access was not rejected")

        print("P0 access event scope and cross-event isolation: OK")
    finally:
        server.DB_PATH = original_db_path
        server.BACKUP_DIR = original_backup_dir
        shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    main()
