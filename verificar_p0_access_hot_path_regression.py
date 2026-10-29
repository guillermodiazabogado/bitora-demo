import os
import tempfile

import server


def main() -> None:
    fd, path = tempfile.mkstemp(prefix="bitora-access-hot-path-", suffix=".db")
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
                    "first_name": "Hot",
                    "last_name": "Path",
                    "email": "access-hot-path@bitora.test",
                    "type": "General",
                    "actor": "regression",
                },
            )
            scope = server.access_event_scope(db, registration["token"])
            first = server.enforced_access_validation(
                db,
                token=registration["token"], operator="Admin", checkpoint="Gate", activity_id=0,
                direction="ENTRY", correlation_id="hot-path-1", idempotency_key="hot-path-1",
                data={}, event_scope=scope,
            )
            replay = server.enforced_access_validation(
                db,
                token=registration["token"], operator="Admin", checkpoint="Gate", activity_id=0,
                direction="ENTRY", correlation_id="hot-path-replay", idempotency_key="hot-path-1",
                data={}, event_scope=scope,
            )
            duplicate = server.enforced_access_validation(
                db,
                token=registration["token"], operator="Admin", checkpoint="Gate", activity_id=0,
                direction="ENTRY", correlation_id="hot-path-2", idempotency_key="hot-path-2",
                data={}, event_scope=scope,
            )
            assert first["result"] == "granted" and first["reason_code"] == "VALID", first
            assert replay["idempotent_replay"] is True and replay["access_event_id"] == first["access_event_id"], replay
            assert duplicate["result"] == "rejected" and duplicate["reason_code"] == "ANTI_PASSBACK", duplicate
            rows = db.execute(
                "SELECT idempotency_key, COUNT(*) AS c FROM enterprise_access_events GROUP BY idempotency_key ORDER BY idempotency_key"
            ).fetchall()
            assert [(row["idempotency_key"], row["c"]) for row in rows] == [("hot-path-1", 1), ("hot-path-2", 1)], rows
        print("PASS: optimized access path preserves idempotency and anti-passback")
    finally:
        server.DB_PATH = previous
        try:
            os.remove(path)
        except OSError:
            pass


if __name__ == "__main__":
    main()
