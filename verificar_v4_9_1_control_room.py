from __future__ import annotations

import json
import shutil
import tempfile
import threading
import urllib.error
import urllib.request
from pathlib import Path

import server


def req(base, method, path, payload=None, expect=200, parse_json=True):
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
    if parse_json and "application/json" in content_type:
        return json.loads(body.decode("utf-8")) if body else {}
    return body


def assert_true(value, message):
    if not value:
        raise AssertionError(message)


def main() -> None:
    tmp_path = Path(tempfile.mkdtemp(prefix="qr-v4-9-control-"))
    httpd = None
    try:
        server.DB_PATH = tmp_path / "v4_9_control.sqlite3"
        server.BACKUP_DIR = tmp_path / "backups"
        server.AppHandler.log_message = lambda self, format, *args: None
        server.init_db()
        server.seed_if_empty()
        httpd = server.OperationalHTTPServer(("127.0.0.1", 0), server.AppHandler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{httpd.server_address[1]}"

        event = req(base, "POST", "/api/events", {"actor": "Admin", "name": "Control Room", "status": "published", "capacity": 300}, 201)
        event_id = event["id"]
        req(base, "POST", "/api/spaces", {"actor": "Admin", "event_id": event_id, "name": "Sala Principal", "capacity": 60})
        req(base, "POST", "/api/spaces", {"actor": "Admin", "event_id": event_id, "name": "Sala B", "capacity": 40})
        spaces = req(base, "GET", f"/api/spaces?event_id={event_id}")
        principal = next(row for row in spaces if row["name"] == "Sala Principal")
        sala_b = next(row for row in spaces if row["name"] == "Sala B")
        activity_a = req(base, "POST", "/api/activities", {"actor": "Admin", "event_id": event_id, "space_id": principal["id"], "title": "Workshop IA", "starts_at": "2026-10-02T10:00", "ends_at": "2026-10-02T11:00", "capacity": 60}, 201)
        activity_b = req(base, "POST", "/api/activities", {"actor": "Admin", "event_id": event_id, "space_id": sala_b["id"], "title": "Sala vacia", "starts_at": "2026-10-02T11:30", "ends_at": "2026-10-02T12:30", "capacity": 40}, 201)
        registration = req(base, "POST", "/api/register", {"actor": "public", "event_id": event_id, "first_name": "Privado", "last_name": "No Mostrar", "email": "sensible@example.test", "phone": "555", "dni": "123456", "type": "General"}, 201)
        with server.connect() as db:
            acc = db.execute("SELECT id FROM accreditations WHERE token = ?", (registration["token"],)).fetchone()
            acc_id = int(acc["id"])
            db.execute(
                """
                INSERT INTO activity_attendance (
                    event_id, activity_id, accreditation_id, entry_at, entry_operator,
                    attended_minutes, attendance_percentage, status, eligibility_status, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, 'Acceso', 60, 100, 'Completa', 'Elegible', ?, ?)
                """,
                (event_id, activity_a["id"], acc_id, server.now_iso(), server.now_iso(), server.now_iso()),
            )
            db.commit()

        summary = req(base, "GET", f"/api/reports/visual-summary?event_id={event_id}&occupancy_low_threshold=30")
        assert_true("occupancy_by_room" in summary and "room_heatmap" in summary and "room_ranking" in summary, "Faltan metricas por sala")
        assert_true("critical_activities" in summary and "operational_alerts" in summary and "event_health" in summary, "Faltan alertas/salud")
        low_alerts = [row for row in summary["operational_alerts"] if row["type"] in {"occupancy_low", "critical_activity"}]
        assert_true(low_alerts, "No genero alerta por ocupacion baja")
        assert_true(summary["room_ranking"][0]["percentage"] >= summary["room_ranking"][-1]["percentage"], "Ranking de salas no ordena por ocupacion")
        payload = json.dumps(summary)
        assert_true("sensible@example.test" not in payload and "123456" not in payload and "555" not in payload, "Sala de control expone datos sensibles")

        dashboard = req(base, "GET", "/index.html", parse_json=False).decode("utf-8")
        assert_true("Alertas operativas" in dashboard and "controlRoomCompact" in dashboard and "controlRoomRotate" in dashboard, "Dashboard no recibio configuracion/alertas")
        display = req(base, "GET", f"/reports-display?event_id={event_id}&compact=1&rotate=15&max_rooms=4&max_alerts=2", parse_json=False).decode("utf-8")
        assert_true("Sala de Control BITORA" in display and "compact-room" in display and "rotate" in display, "Pantalla no soporta compacto/rotacion")
        css = req(base, "GET", "/styles.css", parse_json=False).decode("utf-8")
        assert_true(".control-room-body" in css and "overflow: hidden" in css and "height: 100vh" in css, "CSS no garantiza sala sin scroll")

        print("OK: V4.9.1 sala de control operativa, alertas y sin scroll")
    finally:
        if httpd:
            httpd.shutdown()
            httpd.server_close()
        shutil.rmtree(tmp_path, ignore_errors=True)


if __name__ == "__main__":
    main()
