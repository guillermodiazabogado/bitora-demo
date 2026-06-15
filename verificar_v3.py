from __future__ import annotations

import json
import shutil
import tempfile
import threading
import urllib.error
import urllib.request
from pathlib import Path

import server


def req(base, method, path, payload=None, expect=200):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            body = response.read()
            status = response.status
            content_type = response.headers.get("Content-Type", "")
    except urllib.error.HTTPError as exc:
        body = exc.read()
        status = exc.code
        content_type = exc.headers.get("Content-Type", "")
    if status != expect:
        raise AssertionError(f"{method} {path}: esperado {expect}, recibido {status}: {body!r}")
    if "application/json" in content_type:
        return json.loads(body.decode("utf-8")) if body else {}
    return body


def main() -> None:
    tmp_path = Path(tempfile.mkdtemp(prefix="qr-v3-"))
    httpd = None
    try:
        server.DB_PATH = tmp_path / "v3.sqlite3"
        server.BACKUP_DIR = tmp_path / "backups"
        server.AppHandler.log_message = lambda self, format, *args: None
        server.init_db()
        server.seed_if_empty()
        httpd = server.OperationalHTTPServer(("127.0.0.1", 0), server.AppHandler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{httpd.server_address[1]}"

        event = req(base, "POST", "/api/prepare-event", {"actor": "Admin", "name": "V3", "capacity": 100})
        event_id = event["event_id"]
        spaces = req(base, "GET", f"/api/spaces?event_id={event_id}")
        activity = req(
            base,
            "POST",
            "/api/activities",
            {
                "actor": "Admin",
                "event_id": event_id,
                "space_id": spaces[0]["id"],
                "title": "Workshop V3",
                "starts_at": "2026-10-01T10:00",
                "ends_at": "2026-10-01T11:00",
                "capacity": 10,
                "reservation_mode": "optional",
            },
            201,
        )
        activity_id = activity["id"]
        registration = req(
            base,
            "POST",
            "/api/register",
            {
                "actor": "public",
                "event_id": event_id,
                "first_name": "Portal",
                "last_name": "Participante",
                "email": "portal@example.test",
                "phone": "5491100000000",
                "type": "General",
                "acepta_email": True,
                "acepta_whatsapp": True,
            },
            201,
        )
        assert registration["portal_url"].startswith("/p.html?token=")
        token = registration["token"]

        page = req(base, "GET", f"/p/{token}")
        assert b"Portal del participante" in page or b"Credencial digital" in page

        portal = req(base, "GET", f"/api/portal?token={token}")
        assert portal["communication_preference"]["acepta_email"] == 1
        assert len(portal["activities"]) == 1
        assert not portal["reservations"]

        reserve = req(base, "POST", "/api/portal/reserve", {"token": token, "activity_id": activity_id, "confirmed": True, "verification_answer": "7"}, 201)
        assert reserve["reservation"]["status"] == "confirmed"
        reservation_id = reserve["portal"]["reservations"][0]["id"]

        cancelled = req(base, "POST", "/api/portal/reservations/status", {"token": token, "id": reservation_id, "status": "cancelled"})
        assert cancelled["portal"]["reservations"][0]["status"] == "cancelled"

        prefs = req(base, "POST", "/api/portal/preferences", {"token": token, "acepta_email": True, "acepta_whatsapp": False, "canal_preferido": "email"})
        assert prefs["portal"]["communication_preference"]["acepta_whatsapp"] == 0

        sent = req(base, "POST", "/api/communications/send", {"actor": "Admin", "event_id": event_id, "channel": "email", "type": "recordatorio", "subject": "Recordatorio", "content": "Mensaje demo"})
        assert sent["sent"] == 1
        comms = req(base, "GET", f"/api/communications?event_id={event_id}")
        assert comms["stats"]["with_consent"] == 1
        assert len(comms["logs"]) >= 1
        print("OK: V3 portal participante y comunicaciones")
    finally:
        if httpd:
            httpd.shutdown()
            httpd.server_close()
        shutil.rmtree(tmp_path, ignore_errors=True)


if __name__ == "__main__":
    main()
