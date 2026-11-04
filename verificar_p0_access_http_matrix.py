from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import threading
import urllib.error
import urllib.request

import server
from verificar_v5_1_access_state_engine_shadow import create_event


def post(base: str, payload: dict, expected: int = 200) -> dict:
    request = urllib.request.Request(
        base + "/api/validate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            status = response.status
            body = response.read()
    except urllib.error.HTTPError as exc:
        status = exc.code
        body = exc.read()
    assert status == expected, (status, body)
    return json.loads(body.decode("utf-8"))


def register(db, event_id: int, name: str) -> dict:
    result = server.register_accreditation(
        db,
        event_id,
        {
            "first_name": name,
            "last_name": "HTTP",
            "email": f"{name.lower()}-http@bitora.test",
            "type": "General",
            "actor": "test",
        },
    )
    assert result["ok"], result
    return result


def request_payload(token: str, key: str) -> dict:
    return {
        "token": token,
        "operator": "Admin",
        "checkpoint": "HTTP Matrix",
        "direction": "ENTRY",
        "correlation_id": key,
        "idempotency_key": key,
    }


def main() -> int:
    workspace_tmp = Path(__file__).resolve().parent / "tmp"
    workspace_tmp.mkdir(parents=True, exist_ok=True)
    temp_root = Path(tempfile.mkdtemp(prefix="bitora-p0-access-http-", dir=workspace_tmp))
    original_db_path = server.DB_PATH
    original_backup_dir = server.BACKUP_DIR
    httpd = None
    try:
        server.DB_PATH = temp_root / "access-http.sqlite3"
        server.BACKUP_DIR = temp_root / "backups"
        server.init_db()
        server.seed_if_empty()
        with server.connect() as db:
            event_id, _activity, _future = create_event(db, "Access HTTP Matrix")
            valid = register(db, event_id, "Valid")
            inactive = register(db, event_id, "Inactive")
            revoked = register(db, event_id, "Revoked")
            enabled = server.set_access_state_enforcement(db, event_id, enabled=True, actor="Admin")
            assert enabled["ok"] and enabled["ready"], enabled
            db.execute(
                "UPDATE enterprise_credentials SET status = 'INACTIVE' WHERE accreditation_id = ?",
                (inactive["id"],),
            )
            revoked_credential = db.execute(
                "SELECT id FROM enterprise_credentials WHERE accreditation_id = ?",
                (revoked["id"],),
            ).fetchone()
            server.access_state_engine_service().revoke_credential(
                db,
                organization_id=server.event_organization_id(db, event_id),
                event_id=event_id,
                credential_id=int(revoked_credential["id"]),
                actor="test",
            )

        server.AppHandler.log_message = lambda self, format, *args: None
        httpd = server.OperationalHTTPServer(("127.0.0.1", 0), server.AppHandler)
        httpd.require_login = False
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{httpd.server_address[1]}"

        granted = post(base, request_payload(valid["token"], "http-valid"))
        assert granted["result"] == "granted" and granted["reason_code"] == "VALID", granted
        replay = post(base, request_payload(valid["token"], "http-valid"))
        assert replay["idempotent_replay"] is True
        unknown = post(base, request_payload("EVT-NOT-FOUND", "http-unknown"), expected=404)
        assert unknown["result"] == "rejected", unknown
        inactive_result = post(base, request_payload(inactive["token"], "http-inactive"))
        assert inactive_result["result"] == "rejected" and inactive_result["reason_code"] == "INACTIVE_CREDENTIAL"
        revoked_result = post(base, request_payload(revoked["token"], "http-revoked"))
        assert revoked_result["result"] == "rejected" and revoked_result["reason_code"] == "REVOKED"

        with server.connect() as db:
            valid_events = db.execute(
                "SELECT COUNT(*) AS c FROM enterprise_access_events WHERE idempotency_key = 'http-valid'"
            ).fetchone()["c"]
            assert valid_events == 1, valid_events
            assert db.execute("SELECT COUNT(*) AS c FROM audit_logs WHERE action = 'access.validated'").fetchone()["c"] >= 3
        print("P0 access HTTP valid/replay/unknown/inactive/revoked matrix: OK")
        return 0
    finally:
        if httpd:
            httpd.shutdown()
            httpd.server_close()
        server.DB_PATH = original_db_path
        server.BACKUP_DIR = original_backup_dir
        shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
