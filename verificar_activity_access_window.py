from __future__ import annotations

import json
import shutil
import tempfile
import threading
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

import server


CURRENT_TIME = "2026-10-01T14:40:00"


def fake_now() -> str:
    return CURRENT_TIME


def set_time(value: str) -> None:
    global CURRENT_TIME
    CURRENT_TIME = value


def req(base, method, path, payload=None, expect=200):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
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
    if "application/json" in content_type:
        return json.loads(body.decode("utf-8")) if body else {}
    return body


def create_activity(base, event_id, space_id, title, starts_at, access_minutes="", reservation_mode="required"):
    ends_at = (datetime.fromisoformat(starts_at) + timedelta(hours=1)).isoformat(timespec="minutes")
    return req(
        base,
        "POST",
        "/api/activities",
        {
            "actor": "Admin",
            "event_id": event_id,
            "space_id": space_id,
            "title": title,
            "starts_at": starts_at,
            "ends_at": ends_at,
            "capacity": 50,
            "reservation_mode": reservation_mode,
            "access_open_minutes_before": access_minutes,
        },
        201,
    )["id"]


def register(base, event_id, email):
    result = req(
        base,
        "POST",
        "/api/register",
        {
            "actor": "Recepcion",
            "event_id": event_id,
            "first_name": "Test",
            "last_name": email.split("@")[0],
            "email": email,
            "type": "General",
        },
        201,
    )
    with server.connect() as db:
        row = db.execute("SELECT id FROM accreditations WHERE token = ?", (result["token"],)).fetchone()
    result["id"] = int(row["id"])
    return result


def reserve(base, event_id, activity_id, accreditation_id):
    return req(
        base,
        "POST",
        "/api/reservations",
        {
            "actor": "Recepcion",
            "event_id": event_id,
            "activity_id": activity_id,
            "accreditation_id": accreditation_id,
        },
        201,
    )


def validate(base, token, activity_id=None):
    payload = {"token": token, "operator": "Acceso", "checkpoint": "Control QR"}
    if activity_id:
        payload["activity_id"] = activity_id
    return req(base, "POST", "/api/validate", payload)


def main() -> None:
    original_now = server.now_iso
    tmp_path = Path(tempfile.mkdtemp(prefix="qr-access-window-"))
    httpd = None
    try:
        server.now_iso = fake_now
        server.DB_PATH = tmp_path / "access-window.sqlite3"
        server.BACKUP_DIR = tmp_path / "backups"
        server.AppHandler.log_message = lambda self, format, *args: None
        server.init_db()
        httpd = server.OperationalHTTPServer(("127.0.0.1", 0), server.AppHandler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{httpd.server_address[1]}"

        event = req(
            base,
            "POST",
            "/api/events",
            {
                "actor": "Admin",
                "name": "Ventana QR",
                "status": "published",
                "capacity": 100,
                "activity_access_open_minutes_before": 10,
            },
            201,
        )
        event_id = event["id"]
        space_id = req(base, "GET", f"/api/spaces?event_id={event_id}")[0]["id"]
        activity_a = create_activity(base, event_id, space_id, "Charla A", "2026-10-01T15:00")
        person_a = register(base, event_id, "ventana-a@example.test")
        reserve(base, event_id, activity_a, person_a["id"])

        early = validate(base, person_a["token"], activity_a)
        assert early["result"] == "rejected"
        assert "Acceso aun no habilitado" in early["reason"]
        with server.connect() as db:
            acc = db.execute("SELECT access_count FROM accreditations WHERE id = ?", (person_a["id"],)).fetchone()
            attendance_count = db.execute("SELECT COUNT(*) AS c FROM activity_attendance WHERE activity_id = ?", (activity_a,)).fetchone()["c"]
            granted_count = db.execute("SELECT COUNT(*) AS c FROM access_logs WHERE activity_id = ? AND result = 'granted'", (activity_a,)).fetchone()["c"]
            early_count = db.execute("SELECT COUNT(*) AS c FROM access_logs WHERE activity_id = ? AND reason LIKE 'Acceso aun no habilitado%'", (activity_a,)).fetchone()["c"]
        assert int(acc["access_count"]) == 0
        assert int(attendance_count) == 0
        assert int(granted_count) == 0
        assert int(early_count) == 1

        set_time("2026-10-01T14:50:00")
        granted = validate(base, person_a["token"], activity_a)
        assert granted["result"] == "granted"
        duplicate = validate(base, person_a["token"], activity_a)
        assert duplicate["result"] == "rejected"
        assert "Ya ingreso a esta actividad" in duplicate["reason"]

        set_time("2026-10-01T16:20:00")
        activity_b = create_activity(base, event_id, space_id, "Charla B", "2026-10-01T16:30")
        reserve(base, event_id, activity_b, person_a["id"])
        second_activity = validate(base, person_a["token"], activity_b)
        assert second_activity["result"] == "granted"

        person_b = register(base, event_id, "general-before@example.test")
        general = validate(base, person_b["token"])
        assert general["result"] == "granted"
        set_time("2026-10-01T17:35:00")
        activity_c = create_activity(base, event_id, space_id, "Charla C", "2026-10-01T17:45")
        reserve(base, event_id, activity_c, person_b["id"])
        after_general = validate(base, person_b["token"], activity_c)
        assert after_general["result"] == "granted"

        activity_override = create_activity(base, event_id, space_id, "Override 5", "2026-10-01T19:00", access_minutes=5)
        person_c = register(base, event_id, "override@example.test")
        reserve(base, event_id, activity_override, person_c["id"])
        set_time("2026-10-01T18:52:00")
        override_early = validate(base, person_c["token"], activity_override)
        assert override_early["result"] == "rejected"
        set_time("2026-10-01T18:55:00")
        override_granted = validate(base, person_c["token"], activity_override)
        assert override_granted["result"] == "granted"

        set_time("2026-10-01T20:20:00")
        activity_concurrent = create_activity(base, event_id, space_id, "Simultanea", "2026-10-01T20:30")
        person_d = register(base, event_id, "simultanea@example.test")
        reserve(base, event_id, activity_concurrent, person_d["id"])
        results: list[dict] = []

        def scan_once() -> None:
            results.append(validate(base, person_d["token"], activity_concurrent))

        t1 = threading.Thread(target=scan_once)
        t2 = threading.Thread(target=scan_once)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        assert sorted(row["result"] for row in results) == ["granted", "rejected"]
        assert sum(1 for row in results if "Ya ingreso" in row["reason"]) == 1
        with server.connect() as db:
            concurrent_granted = db.execute(
                "SELECT COUNT(*) AS c FROM access_logs WHERE activity_id = ? AND result = 'granted'",
                (activity_concurrent,),
            ).fetchone()["c"]
        assert int(concurrent_granted) == 1

        print("OK: ventana de habilitacion QR por actividad")
    finally:
        if httpd:
            httpd.shutdown()
        server.now_iso = original_now
        shutil.rmtree(tmp_path, ignore_errors=True)


if __name__ == "__main__":
    main()
