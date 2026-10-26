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


def request(base, path, payload, *, bearer="", expected=200):
    headers = {"Content-Type": "application/json"}
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    req = urllib.request.Request(
        base + path,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            status = response.status
            body = response.read()
    except urllib.error.HTTPError as exc:
        status = exc.code
        body = exc.read()
    if status != expected:
        raise AssertionError(f"{path}: expected {expected}, got {status}: {body!r}")
    return json.loads(body.decode("utf-8"))


def main() -> None:
    workspace_tmp = Path(__file__).resolve().parent / "tmp"
    workspace_tmp.mkdir(parents=True, exist_ok=True)
    temp_root = Path(tempfile.mkdtemp(prefix="bitora-p0-device-http-", dir=workspace_tmp))
    original_db_path = server.DB_PATH
    original_backup_dir = server.BACKUP_DIR
    httpd = None
    try:
        server.DB_PATH = temp_root / "device-http.sqlite3"
        server.BACKUP_DIR = temp_root / "backups"
        server.init_db()
        server.seed_if_empty()
        with server.connect() as db:
            event_id, _activity, _future = create_event(db, "Device HTTP")
            other_event_id, _activity_b, _future_b = create_event(db, "Device HTTP Other")
            server.edge_admin_action(db, event_id, "profiles", {}, actor="Admin")
            edge = server.edge_admin_action(db, event_id, "provision", {"name": "HTTP Edge"}, actor="Admin")
            pairing = server.edge_admin_action(
                db,
                event_id,
                "pairing-code",
                {"edge_id": edge["edge"]["id"], "profile_key": "ACCESS_FAST", "device_type": "HANDHELD"},
                actor="Admin",
            )

        server.AppHandler.log_message = lambda self, format, *args: None
        httpd = server.OperationalHTTPServer(("127.0.0.1", 0), server.AppHandler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{httpd.server_address[1]}"

        paired = request(
            base,
            f"/api/events/{event_id}/devices/pair",
            {"pairing_code": pairing["pairing_code"], "display_name": "HTTP Device"},
            expected=201,
        )
        if "credential_hash" in paired["device"] or not paired["secret"].startswith("dev_"):
            raise AssertionError(paired)
        device_id = int(paired["device"]["id"])
        request(base, f"/api/events/{event_id}/devices/{device_id}/heartbeat", {}, expected=401)
        request(
            base,
            f"/api/events/{event_id}/devices/{device_id}/heartbeat",
            {"queue_depth": 0, "sync_status": "ONLINE"},
            bearer=paired["secret"],
        )
        request(
            base,
            f"/api/events/{other_event_id}/devices/{device_id}/heartbeat",
            {"queue_depth": 0, "sync_status": "ONLINE"},
            bearer=paired["secret"],
            expected=401,
        )
        request(
            base,
            f"/api/events/{event_id}/devices/{device_id}/sync",
            {"operations": []},
            bearer=paired["secret"],
        )
        request(
            base,
            f"/api/events/{event_id}/devices/pair",
            {"pairing_code": pairing["pairing_code"], "display_name": "Replay"},
            expected=400,
        )
        for _ in range(4):
            request(base, f"/api/events/{event_id}/devices/pair", {"pairing_code": "000000", "display_name": "Probe"}, expected=400)
        request(base, f"/api/events/{event_id}/devices/pair", {"pairing_code": "000000", "display_name": "Probe"}, expected=429)
        print("P0 Device HTTP pairing, Bearer auth, replay, isolation and rate limiting: OK")
    finally:
        if httpd:
            httpd.shutdown()
            httpd.server_close()
        server.DB_PATH = original_db_path
        server.BACKUP_DIR = original_backup_dir
        shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    main()
