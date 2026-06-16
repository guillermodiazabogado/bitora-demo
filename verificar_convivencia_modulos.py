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
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    request = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            body = response.read()
            status = response.status
            content_type = response.headers.get("Content-Type", "")
    except urllib.error.HTTPError as exc:
        body = exc.read()
        status = exc.code
        content_type = exc.headers.get("Content-Type", "")
    if status != expect:
        raise AssertionError(f"{method} {path}: esperado {expect}, recibido {status}: {body!r}")
    return json.loads(body.decode("utf-8")) if "application/json" in content_type and body else body


def assert_true(value, message):
    if not value:
        raise AssertionError(message)


def create_event(base, name, activities=True, capacity=True, waitlist=False):
    return req(
        base,
        "POST",
        "/api/events",
        {
            "actor": "Admin",
            "name": name,
            "status": "published",
            "capacity": 100,
            "activities_enabled": activities,
            "capacity_control_enabled": capacity,
            "waitlist_enabled": waitlist,
        },
        201,
    )["id"]


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="qr-convivencia-"))
    httpd = None
    try:
        server.DB_PATH = tmp / "convivencia.sqlite3"
        server.BACKUP_DIR = tmp / "backups"
        server.AppHandler.log_message = lambda self, format, *args: None
        server.init_db()
        server.seed_if_empty()
        httpd = server.OperationalHTTPServer(("127.0.0.1", 0), server.AppHandler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{httpd.server_address[1]}"

        scenarios = [
            ("sin actividades", False, True, False),
            ("cupos off", True, False, False),
            ("espera off", True, True, False),
            ("espera on", True, True, True),
        ]
        for name, activities_on, capacity_on, waitlist_on in scenarios:
            event_id = create_event(base, name, activities_on, capacity_on, waitlist_on)
            public_event = req(base, "GET", f"/api/event?event_id={event_id}")
            assert_true(int(public_event["activities_enabled"]) == int(activities_on), f"{name}: flag actividades incorrecto")
            reg = req(base, "POST", "/api/register", {"actor": "public", "event_id": event_id, "first_name": "Modulo", "last_name": name, "email": f"{name.replace(' ', '')}@example.test", "phone": "5492990000000", "type": "General", "acepta_email": True, "acepta_whatsapp": True}, 201)
            portal = req(base, "GET", f"/api/portal?token={reg['token']}")
            if not activities_on:
                assert_true(portal["activities"] == [] and portal["reservations"] == [], f"{name}: portal no oculto actividades")
                continue
            space_id = req(base, "GET", f"/api/spaces?event_id={event_id}")[0]["id"]
            activity_id = req(base, "POST", "/api/activities", {"actor": "Admin", "event_id": event_id, "space_id": space_id, "title": f"Actividad {name}", "starts_at": "2026-12-01T10:00", "ends_at": "2026-12-01T11:00", "capacity": 1}, 201)["id"]
            with server.connect() as db:
                acc_id = db.execute("SELECT id FROM accreditations WHERE token = ?", (reg["token"],)).fetchone()["id"]
            reserve = req(base, "POST", "/api/reservations", {"actor": "Recepcion", "event_id": event_id, "activity_id": activity_id, "accreditation_id": acc_id}, 201)
            assert_true(reserve["status"] == "confirmed", f"{name}: no confirmo primera inscripcion")
            display = req(base, "GET", f"/api/public-display?event_id={event_id}")
            control = req(base, "GET", f"/api/reports/visual-summary?event_id={event_id}")
            comms = req(base, "POST", "/api/communications/send", {"actor": "Admin", "event_id": event_id, "audience": "all", "channel": "email", "subject": "Aviso", "content": "Operativo", "confirm": True})
            display_ok = isinstance(display, dict) and any(key in display for key in ("items", "activities", "agenda", "event"))
            processed = int(comms.get("queued", 0)) + int(comms.get("skipped", 0)) + int(comms.get("sent", 0))
            assert_true(display_ok and "event_health" in control and processed >= 1, f"{name}: modulos no conviven")
        print("OK: convivencia de modulos y flags operativos")
    finally:
        if httpd:
            httpd.shutdown()
            httpd.server_close()
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
