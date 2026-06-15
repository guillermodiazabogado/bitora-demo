from __future__ import annotations

import json
import shutil
import tempfile
import threading
import urllib.request
import urllib.error
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
    tmp_path = Path(tempfile.mkdtemp(prefix="qr-v2-"))
    httpd = None
    try:
        server.DB_PATH = tmp_path / "v2.sqlite3"
        server.BACKUP_DIR = tmp_path / "backups"
        server.AppHandler.log_message = lambda self, format, *args: None
        server.init_db()
        server.seed_if_empty()
        httpd = server.OperationalHTTPServer(("127.0.0.1", 0), server.AppHandler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{httpd.server_address[1]}"

        event = req(base, "POST", "/api/prepare-event", {"actor": "Admin", "name": "V2", "capacity": 100})
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
                "title": "Actividad V2",
                "starts_at": "2026-10-01T10:00",
                "ends_at": "2026-10-01T11:00",
                "capacity": 2,
                "reservation_mode": "required",
            },
            201,
        )
        activity_id = activity["id"]
        bags = req(base, "GET", f"/api/capacity-bags?event_id={event_id}&activity_id={activity_id}")
        online = next(row for row in bags if row["code"] == "online")
        mostrador = next(row for row in bags if row["code"] == "mostrador")
        assert online["assigned_capacity"] == 2

        req(base, "POST", "/api/capacity-bags", {"actor": "Admin", "id": online["id"], "name": "Online", "assigned_capacity": 1, "priority": 10, "public_visible": True, "public_registration": True, "reception_enabled": True, "status": "active"})
        req(base, "POST", "/api/capacity-bags", {"actor": "Admin", "id": mostrador["id"], "name": "Mostrador", "assigned_capacity": 1, "priority": 20, "public_visible": False, "public_registration": False, "reception_enabled": True, "status": "active"})

        first = req(base, "POST", "/api/register", {"actor": "public", "event_id": event_id, "first_name": "Uno", "last_name": "Publico", "email": "uno@example.test", "type": "General"}, 201)
        first_reserve = req(base, "POST", "/api/portal/reserve", {"token": first["token"], "activity_id": activity_id, "confirmed": True, "verification_answer": "7"}, 201)
        assert first_reserve["reservation"]["status"] == "confirmed"
        second = req(base, "POST", "/api/register", {"actor": "public", "event_id": event_id, "first_name": "Dos", "last_name": "Publico", "email": "dos@example.test", "type": "General"}, 201)
        second_reserve = req(base, "POST", "/api/portal/reserve", {"token": second["token"], "activity_id": activity_id, "confirmed": True, "verification_answer": "7"}, 201)
        assert second_reserve["reservation"]["status"] == "waitlisted"

        public_event = req(base, "GET", f"/api/event?event_id={event_id}")
        public_activity = public_event["activities"][0]
        assert "capacity" not in public_activity
        assert public_activity["public_availability"] == "Completa"

        req(base, "POST", "/api/capacity-bags/move", {"actor": "Admin", "origin_id": mostrador["id"], "target_id": online["id"], "amount": 1, "reason": "liberar publico"})
        after_move = req(base, "GET", f"/api/event?event_id={event_id}")["activities"][0]
        assert after_move["public_remaining"] == 1

        req(base, "POST", "/api/public-display/config", {"actor": "Admin", "event_id": event_id, "mode": "now", "refresh_seconds": 5, "message": "Mensaje V2"})
        req(base, "POST", "/api/public-display/item", {"actor": "Admin", "event_id": event_id, "activity_id": activity_id, "visible": True})
        display = req(base, "GET", f"/api/public-display?event_id={event_id}")
        assert display["config"]["mode"] == "now"
        assert display["activities"][0]["availability"]
        page = req(base, "GET", f"/display.html?event_id={event_id}")
        assert b"displayContent" in page
        print("OK: V2 bolsas y pantalla publica")
    finally:
        if httpd:
            httpd.shutdown()
            httpd.server_close()
        shutil.rmtree(tmp_path, ignore_errors=True)


if __name__ == "__main__":
    main()
