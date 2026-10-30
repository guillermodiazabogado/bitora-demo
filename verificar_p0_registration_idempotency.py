from __future__ import annotations

import json
import hashlib
import http.client
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import shutil
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

import server


def post_json(
    base: str,
    path: str,
    payload: dict,
    *,
    idempotency_key: str | None = None,
    expected: set[int] | None = None,
) -> tuple[int, dict, object]:
    headers = {"Content-Type": "application/json"}
    if idempotency_key is not None:
        headers["Idempotency-Key"] = idempotency_key
    request = urllib.request.Request(
        base + path,
        json.dumps(payload).encode("utf-8"),
        headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            status, body, response_headers = response.status, response.read(), response.headers
    except urllib.error.HTTPError as exc:
        status, body, response_headers = exc.code, exc.read(), exc.headers
    if expected is not None and status not in expected:
        raise AssertionError((path, expected, status, body.decode("utf-8", errors="replace")))
    return status, json.loads(body.decode("utf-8")), response_headers


def registration_payload(event_id: int, email: str, *, first_name: str = "Idempotent") -> dict:
    return {
        "event_id": event_id,
        "first_name": first_name,
        "last_name": "Registration",
        "email": email,
        "phone": "+5491100000000",
        "type": "General",
        "actor": "public",
        "source": "landing",
        "device_type": "desktop",
    }


def discard_http_response(base: str, path: str, payload: dict, idempotency_key: str) -> None:
    """Send a complete request and close the client socket before reading its response."""
    target = urllib.parse.urlparse(base)
    connection = http.client.HTTPConnection(target.hostname, target.port, timeout=10)
    connection.request(
        "POST",
        path,
        body=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Idempotency-Key": idempotency_key},
    )
    connection.close()


def wait_for_completed_operation(event_id: int, key: str, timeout: float = 10.0) -> None:
    key_hash = hashlib.sha256(key.encode("utf-8")).hexdigest()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with server.connect() as db:
            row = db.execute(
                "SELECT status FROM registration_idempotency WHERE event_id = ? AND key_hash = ?",
                (event_id, key_hash),
            ).fetchone()
        if row and row["status"] == "COMPLETED":
            return
        time.sleep(0.05)
    raise AssertionError("registration operation did not reach COMPLETED after discarded response")


def main() -> None:
    workspace_tmp = Path(__file__).resolve().parent / "tmp"
    workspace_tmp.mkdir(exist_ok=True)
    temp_root = Path(tempfile.mkdtemp(prefix="bitora-registration-idempotency-", dir=workspace_tmp))
    original_db_path = server.DB_PATH
    original_backup_dir = server.BACKUP_DIR
    original_log_message = server.AppHandler.log_message
    httpd = None
    try:
        server.DB_PATH = temp_root / "registration-idempotency.sqlite3"
        server.BACKUP_DIR = temp_root / "backups"
        server.init_db()
        server.seed_if_empty()
        with server.connect() as db:
            event_id = int(db.execute("SELECT id FROM events ORDER BY id LIMIT 1").fetchone()["id"])
            activation = server.set_access_state_enforcement(db, event_id, enabled=True, actor="regression")
            assert activation["ok"] and activation["ready"], activation
            second_event_id = server.insert_event_from_config(
                db,
                {
                    "name": "Registration idempotency isolation",
                    "starts_at": "2026-07-02T09:00",
                    "ends_at": "2026-07-02T18:00",
                    "capacity": 3000,
                },
                "Admin",
                status="published",
            )
            server.ensure_default_types(db, second_event_id)

        server.AppHandler.log_message = lambda self, format, *args: None
        httpd = server.OperationalHTTPServer(("127.0.0.1", 0), server.AppHandler)
        httpd.require_login = False
        server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        server_thread.start()
        base = f"http://127.0.0.1:{httpd.server_address[1]}"

        payload = registration_payload(event_id, "idem-first@bitora.test")
        key = "registration-idempotency-first-0001"
        first_status, first, _ = post_json(base, "/api/register", payload, idempotency_key=key, expected={201})
        replay_status, replay, _ = post_json(base, "/api/register", payload, idempotency_key=key, expected={200})
        assert first_status == 201 and replay_status == 200
        assert replay.get("idempotent_replay") is True, replay
        assert replay.get("token") == first.get("token"), (first, replay)

        lost_payload = registration_payload(event_id, "idem-lost-response@bitora.test")
        lost_key = "registration-idempotency-lost-response-0001"
        discard_http_response(base, "/api/register", lost_payload, lost_key)
        wait_for_completed_operation(event_id, lost_key)
        recovered_status, recovered, _ = post_json(
            base,
            "/api/register",
            lost_payload,
            idempotency_key=lost_key,
            expected={200},
        )
        assert recovered_status == 200 and recovered.get("idempotent_replay") is True, recovered

        conflicting = dict(payload, first_name="Different")
        conflict_status, conflict, _ = post_json(
            base,
            "/api/register",
            conflicting,
            idempotency_key=key,
            expected={409},
        )
        assert conflict_status == 409
        assert conflict.get("code") == "REGISTRATION_IDEMPOTENCY_CONFLICT", conflict

        invalid_status, invalid, _ = post_json(
            base,
            "/api/register",
            registration_payload(event_id, "idem-invalid@bitora.test"),
            idempotency_key="short",
            expected={400},
        )
        assert invalid_status == 400, invalid

        legacy_status, legacy, _ = post_json(
            base,
            "/api/register",
            registration_payload(event_id, "idem-legacy@bitora.test"),
            expected={201},
        )
        assert legacy_status == 201 and legacy.get("token"), legacy

        isolation_key = "registration-idempotency-isolation-0001"
        event_one_status, event_one, _ = post_json(
            base,
            "/api/register",
            registration_payload(event_id, "idem-event-one@bitora.test"),
            idempotency_key=isolation_key,
            expected={201},
        )
        event_two_status, event_two, _ = post_json(
            base,
            "/api/register",
            registration_payload(second_event_id, "idem-event-two@bitora.test"),
            idempotency_key=isolation_key,
            expected={201},
        )
        assert event_one_status == event_two_status == 201
        assert event_one["token"] != event_two["token"]

        concurrent_payload = registration_payload(event_id, "idem-concurrent@bitora.test")
        concurrent_key = "registration-idempotency-concurrent-0001"
        barrier = threading.Barrier(3)

        def concurrent_request() -> tuple[int, dict, object]:
            barrier.wait(timeout=10)
            return post_json(
                base,
                "/api/register",
                concurrent_payload,
                idempotency_key=concurrent_key,
                expected={200, 201},
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(concurrent_request) for _ in range(2)]
            barrier.wait(timeout=10)
            concurrent_results = [future.result(timeout=30) for future in futures]
        assert sorted(status for status, _, _ in concurrent_results) == [200, 201], concurrent_results
        concurrent_tokens = {body.get("token") for _, body, _ in concurrent_results}
        assert len(concurrent_tokens) == 1 and None not in concurrent_tokens, concurrent_results
        replay_bodies = [body for status, body, _ in concurrent_results if status == 200]
        assert len(replay_bodies) == 1 and replay_bodies[0].get("idempotent_replay") is True, concurrent_results

        with server.connect() as db:
            accreditation = db.execute(
                """
                SELECT a.id
                FROM accreditations a
                JOIN people p ON p.id = a.person_id
                WHERE a.event_id = ? AND lower(p.email) = lower(?)
                """,
                (event_id, concurrent_payload["email"]),
            ).fetchall()
            assert len(accreditation) == 1, accreditation
            credential_count = int(
                db.execute(
                    "SELECT COUNT(*) AS c FROM enterprise_credentials WHERE event_id = ? AND accreditation_id = ?",
                    (event_id, accreditation[0]["id"]),
                ).fetchone()["c"]
            )
            assert credential_count == 1, credential_count
            idempotency_count = int(
                db.execute(
                    "SELECT COUNT(*) AS c FROM registration_idempotency WHERE event_id = ? AND key_hash = ?",
                    (event_id, hashlib.sha256(concurrent_key.encode("utf-8")).hexdigest()),
                ).fetchone()["c"]
            )
            assert idempotency_count == 1, idempotency_count

            lost_rows = db.execute(
                """
                SELECT a.id
                FROM accreditations a
                JOIN people p ON p.id = a.person_id
                WHERE a.event_id = ? AND lower(p.email) = lower(?)
                """,
                (event_id, lost_payload["email"]),
            ).fetchall()
            assert len(lost_rows) == 1, lost_rows
            lost_credentials = int(
                db.execute(
                    "SELECT COUNT(*) AS c FROM enterprise_credentials WHERE event_id = ? AND accreditation_id = ?",
                    (event_id, lost_rows[0]["id"]),
                ).fetchone()["c"]
            )
            assert lost_credentials == 1, lost_credentials

        print("P0 registration idempotency, lost response recovery, conflict, compatibility, event isolation and concurrency: OK")
    finally:
        if httpd:
            httpd.shutdown()
            httpd.server_close()
        server.AppHandler.log_message = original_log_message
        server.DB_PATH = original_db_path
        server.BACKUP_DIR = original_backup_dir
        shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    main()
