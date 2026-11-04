from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
import shutil
import tempfile
import threading
import uuid

import server


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def create_event(db) -> tuple[int, int]:
    suffix = uuid.uuid4().hex[:8]
    now = datetime.now()
    event = db.execute(
        """
        INSERT INTO events (
            organization_id, name, description, venue, starts_at, ends_at,
            capacity, created_at
        ) VALUES (1, ?, '', 'Race lab', ?, ?, 1000, ?)
        """,
        (
            f"P2 access race {suffix}",
            (now - timedelta(hours=1)).date().isoformat(),
            (now + timedelta(hours=1)).date().isoformat(),
            server.now_iso(),
        ),
    )
    event_id = int(event.lastrowid)
    db.execute(
        "INSERT INTO accreditation_types (event_id, name, capacity, access_enabled, created_at) VALUES (?, 'General', 0, 1, ?)",
        (event_id, server.now_iso()),
    )
    space = db.execute(
        "INSERT INTO spaces (event_id, name, capacity, transition_minutes, status, created_at) VALUES (?, 'Activity room', 1000, 0, 'active', ?)",
        (event_id, server.now_iso()),
    )
    activity = db.execute(
        """
        INSERT INTO activities (
            event_id, space_id, title, starts_at, ends_at, capacity,
            reservation_mode, status, created_at
        ) VALUES (?, ?, 'Concurrent activity', ?, ?, 1000, 'open', 'published', ?)
        """,
        (
            event_id,
            int(space.lastrowid),
            (now - timedelta(minutes=30)).isoformat(timespec="seconds"),
            (now + timedelta(minutes=30)).isoformat(timespec="seconds"),
            server.now_iso(),
        ),
    )
    return event_id, int(activity.lastrowid)


def register(db, event_id: int, label: str) -> dict:
    result = server.register_accreditation(
        db,
        event_id,
        {
            "first_name": label,
            "last_name": "Race",
            "email": f"{label.lower()}-{uuid.uuid4().hex[:8]}@bitora.test",
            "type": "General",
            "actor": "p2-race-test",
        },
    )
    assert_true(result.get("ok"), result)
    return result


def run_validation(
    token: str,
    key: str,
    *,
    barrier: threading.Barrier | None = None,
    activity_id: int = 0,
) -> dict:
    if barrier:
        barrier.wait(timeout=10)
    with server.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        try:
            scope = server.access_event_scope(db, token)
            assert_true(scope, "credential scope missing")
            result = server.enforced_access_validation(
                db,
                token=token,
                operator="P2 race",
                checkpoint="Concurrent gate",
                activity_id=activity_id,
                direction="ENTRY",
                correlation_id=f"race-{key}",
                idempotency_key=key,
                data={},
                event_scope=scope,
            )
            db.execute("COMMIT")
            return result
        except Exception:
            db.execute("ROLLBACK")
            raise


def concurrent_pair(fn_a, fn_b) -> list[dict]:
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(fn_a), pool.submit(fn_b)]
        return [future.result(timeout=30) for future in futures]


def main() -> None:
    temp_root: Path | None = None
    original_db_path = server.DB_PATH
    original_backup_dir = server.BACKUP_DIR
    if server.DB_CONFIG.engine == "sqlite":
        workspace_tmp = Path(__file__).resolve().parent / "tmp"
        workspace_tmp.mkdir(exist_ok=True)
        temp_root = Path(tempfile.mkdtemp(prefix="bitora-p2-races-", dir=workspace_tmp))
        server.DB_PATH = temp_root / "races.sqlite3"
        server.BACKUP_DIR = temp_root / "backups"

    try:
        server.init_db()
        server.seed_if_empty()
        with server.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            event_id, activity_id = create_event(db)
            idem = register(db, event_id, "Idempotent")
            entity_a = register(db, event_id, "EntityA")
            entity_b = register(db, event_id, "EntityB")
            revoked = register(db, event_id, "Revoked")
            activity = register(db, event_id, "Activity")
            db.execute(
                "UPDATE accreditations SET checked_in_at = ? WHERE id = ?",
                (server.now_iso(), activity["id"]),
            )
            enabled = server.set_access_state_enforcement(db, event_id, enabled=True, actor="p2-race-test")
            assert_true(enabled.get("ok") and enabled.get("ready"), enabled)

            credentials = {
                int(row["accreditation_id"]): dict(row)
                for row in db.execute(
                    "SELECT * FROM enterprise_credentials WHERE event_id = ?",
                    (event_id,),
                ).fetchall()
            }
            first_entity_id = int(credentials[int(entity_a["id"])]["entity_id"])
            second_credential_id = int(credentials[int(entity_b["id"])]["id"])
            # The schema permits several credentials for one enterprise entity.
            # Exercise that supported cardinality instead of assuming one token.
            db.execute(
                "UPDATE enterprise_credentials SET entity_id = ? WHERE id = ?",
                (first_entity_id, second_credential_id),
            )
            db.execute("COMMIT")

        with server.connect() as db:
            entity_a_scope = server.access_event_scope(db, entity_a["token"])
            entity_b_scope = server.access_event_scope(db, entity_b["token"])
            assert_true(entity_a_scope and entity_b_scope, "enterprise access scope missing")
            assert_true(int(entity_a_scope["entity_id"]) == first_entity_id, entity_a_scope)
            assert_true(int(entity_b_scope["entity_id"]) == first_entity_id, entity_b_scope)

        failures: list[dict] = []
        passed: list[str] = []
        idem_key = f"same-key-{uuid.uuid4().hex}"
        try:
            barrier = threading.Barrier(2)
            idem_results = concurrent_pair(
                lambda: run_validation(idem["token"], idem_key, barrier=barrier),
                lambda: run_validation(idem["token"], idem_key, barrier=barrier),
            )
            assert_true(all(item["result"] == "granted" for item in idem_results), idem_results)
            assert_true(len({int(item["access_event_id"]) for item in idem_results}) == 1, idem_results)
            assert_true(sum(bool(item.get("idempotent_replay")) for item in idem_results) == 1, idem_results)
            passed.append("same_credential_same_idempotency_key")
        except Exception as exc:
            failures.append({"case": "same_credential_same_idempotency_key", "error": f"{type(exc).__name__}: {exc}"})

        try:
            barrier = threading.Barrier(2)
            entity_results = concurrent_pair(
                lambda: run_validation(entity_a["token"], f"entity-a-{uuid.uuid4().hex}", barrier=barrier),
                lambda: run_validation(entity_b["token"], f"entity-b-{uuid.uuid4().hex}", barrier=barrier),
            )
            assert_true(sum(item["result"] == "granted" for item in entity_results) == 1, entity_results)
            assert_true(sum(item.get("reason_code") == "ANTI_PASSBACK" for item in entity_results) == 1, entity_results)
            passed.append("two_credentials_same_entity")
        except Exception as exc:
            failures.append({"case": "two_credentials_same_entity", "error": f"{type(exc).__name__}: {exc}"})

        revoked_credential_id = 0
        with server.connect() as db:
            revoked_credential_id = int(
                db.execute(
                    "SELECT id FROM enterprise_credentials WHERE event_id = ? AND accreditation_id = ?",
                    (event_id, revoked["id"]),
                ).fetchone()["id"]
            )
        barrier = threading.Barrier(2)

        def revoke_concurrently() -> dict:
            barrier.wait(timeout=10)
            with server.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                try:
                    result = server.access_state_engine_service().revoke_credential(
                        db,
                        organization_id=1,
                        event_id=event_id,
                        credential_id=revoked_credential_id,
                        actor="p2-race-test",
                        reason="concurrent revocation",
                    )
                    db.execute("COMMIT")
                    return result
                except Exception:
                    db.execute("ROLLBACK")
                    raise

        try:
            concurrent_result = concurrent_pair(
                lambda: run_validation(revoked["token"], f"revocation-race-{uuid.uuid4().hex}", barrier=barrier),
                revoke_concurrently,
            )[0]
            assert_true(concurrent_result.get("result") in {"granted", "rejected"}, concurrent_result)
            post_revocation = run_validation(revoked["token"], f"revocation-post-{uuid.uuid4().hex}")
            assert_true(post_revocation.get("reason_code") == "REVOKED", post_revocation)
            passed.append("concurrent_revocation")
        except Exception as exc:
            failures.append({"case": "concurrent_revocation", "error": f"{type(exc).__name__}: {exc}"})

        try:
            barrier = threading.Barrier(2)
            activity_results = concurrent_pair(
                lambda: run_validation(activity["token"], f"activity-a-{uuid.uuid4().hex}", barrier=barrier, activity_id=activity_id),
                lambda: run_validation(activity["token"], f"activity-b-{uuid.uuid4().hex}", barrier=barrier, activity_id=activity_id),
            )
            assert_true(sum(item["result"] == "granted" for item in activity_results) == 1, activity_results)
            assert_true(sum(item.get("reason_code") == "ANTI_PASSBACK" for item in activity_results) == 1, activity_results)
            passed.append("activity_id")
        except Exception as exc:
            failures.append({"case": "activity_id", "error": f"{type(exc).__name__}: {exc}"})

        with server.connect() as db:
            idem_events = int(db.execute(
                "SELECT COUNT(*) AS c FROM enterprise_access_events WHERE organization_id = 1 AND idempotency_key = ?",
                (idem_key,),
            ).fetchone()["c"])
            entity_allows = int(db.execute(
                "SELECT COUNT(*) AS c FROM enterprise_access_events WHERE event_id = ? AND entity_id = ? AND decision = 'ALLOW'",
                (event_id, first_entity_id),
            ).fetchone()["c"])
            revocations = int(db.execute(
                "SELECT COUNT(*) AS c FROM enterprise_credential_revocations WHERE credential_id = ? AND status = 'ACTIVE'",
                (revoked_credential_id,),
            ).fetchone()["c"])
            activity_grants = int(db.execute(
                "SELECT COUNT(*) AS c FROM access_logs WHERE event_id = ? AND activity_id = ? AND accreditation_id = ? AND result = 'granted'",
                (event_id, activity_id, activity["id"]),
            ).fetchone()["c"])
            activity_metadata = [
                str(row["metadata_json"])
                for row in db.execute(
                    "SELECT metadata_json FROM enterprise_access_events WHERE event_id = ? AND accreditation_id = ?",
                    (event_id, activity["id"]),
                ).fetchall()
            ]
        persisted_checks = (
            (idem_events == 1, "same_credential_same_idempotency_key", {"idempotency_events": idem_events}),
            (entity_allows == 1, "two_credentials_same_entity", {"entity_allows": entity_allows}),
            (revocations == 1, "concurrent_revocation", {"active_revocations": revocations}),
            (activity_grants == 1, "activity_id", {"activity_grants": activity_grants}),
            (
                len(activity_metadata) == 2 and all(f'"activity_id": {activity_id}' in value for value in activity_metadata),
                "activity_id",
                {"activity_metadata": activity_metadata},
            ),
        )
        for condition, case, details in persisted_checks:
            if not condition:
                failures.append({"case": case, "error": f"persistence check failed: {details}"})

        print({"passed": passed, "failures": failures})
        assert_true(not failures, {"passed": passed, "failures": failures})
    finally:
        server.DB_PATH = original_db_path
        server.BACKUP_DIR = original_backup_dir
        if temp_root is not None:
            shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    main()
