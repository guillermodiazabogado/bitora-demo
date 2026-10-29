import os
import tempfile

import server


def main() -> None:
    fd, path = tempfile.mkstemp(prefix="bitora-access-registration-", suffix=".db")
    os.close(fd)
    previous = server.DB_PATH
    try:
        server.DB_PATH = path
        server.init_db()
        server.seed_if_empty()
        with server.connect() as db:
            event_id = int(db.execute("SELECT id FROM events ORDER BY id LIMIT 1").fetchone()["id"])
            activation = server.set_access_state_enforcement(db, event_id, enabled=True, actor="regression")
            assert activation["ok"] and activation["ready"], activation
            registration = server.register_accreditation(
                db,
                event_id,
                {
                    "first_name": "Nueva",
                    "last_name": "Credencial",
                    "email": "new-after-enforcement@bitora.test",
                    "type": "General",
                    "actor": "regression",
                },
            )
            assert registration["ok"] and not registration["existing"], registration
            projected = db.execute(
                "SELECT id, status FROM enterprise_credentials WHERE event_id = ? AND accreditation_id = ?",
                (event_id, registration["id"]),
            ).fetchone()
            assert projected and projected["status"] == "ACTIVE", projected
            readiness = server.access_state_enforcement_readiness(db, event_id)
            assert readiness["ready"], readiness
            scope = server.access_event_scope(db, registration["token"])
            first = server.enforced_access_validation(
                db,
                token=registration["token"], operator="Regression", checkpoint="Gate", activity_id=0,
                direction="ENTRY", correlation_id="post-enforcement-entry-1",
                idempotency_key="post-enforcement-entry-1", data={}, event_scope=scope,
            )
            assert first["result"] == "granted" and first["reason_code"] == "VALID", first
            second = server.enforced_access_validation(
                db,
                token=registration["token"], operator="Regression", checkpoint="Gate", activity_id=0,
                direction="ENTRY", correlation_id="post-enforcement-entry-2",
                idempotency_key="post-enforcement-entry-2", data={}, event_scope=scope,
            )
            assert second["result"] == "rejected" and second["reason_code"] == "ANTI_PASSBACK", second
        print("PASS: registrations created after enforcement receive an enterprise credential")
    finally:
        server.DB_PATH = previous
        try:
            os.remove(path)
        except OSError:
            pass


if __name__ == "__main__":
    main()
