from __future__ import annotations

import json
import shutil
import tempfile
import threading
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
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
    tmp_path = Path(tempfile.mkdtemp(prefix="qr-v4-2-"))
    httpd = None
    try:
        server.DB_PATH = tmp_path / "v4_2.sqlite3"
        server.BACKUP_DIR = tmp_path / "backups"
        server.AppHandler.log_message = lambda self, format, *args: None
        server.init_db()
        server.seed_if_empty()
        httpd = server.OperationalHTTPServer(("127.0.0.1", 0), server.AppHandler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{httpd.server_address[1]}"

        event = req(
            base,
            "POST",
            "/api/prepare-event",
            {
                "actor": "Admin",
                "name": "V4.2 asistencia",
                "capacity": 100,
                "attendance_mode": "entry_exit",
                "controlar_asistencia": "1",
                "generar_certificados": "1",
                "porcentaje_minimo_asistencia": 80,
            },
        )
        event_id = event["event_id"]
        space_id = req(base, "GET", f"/api/spaces?event_id={event_id}")[0]["id"]
        activity = req(
            base,
            "POST",
            "/api/activities",
            {
                "actor": "Admin",
                "event_id": event_id,
                "space_id": space_id,
                "title": "Workshop asistencia",
                "starts_at": "2026-01-01T10:00",
                "ends_at": "2026-01-01T11:00",
                "capacity": 20,
                "reservation_mode": "free",
                "requiere_asistencia": "1",
                "porcentaje_minimo_asistencia": 80,
                "habilita_certificado": "1",
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
                "first_name": "Asistente",
                "last_name": "Real",
                "email": "asistente.real@example.com",
                "phone": "111",
                "dni": "42",
                "company": "Demo",
                "type": "General",
            },
            201,
        )
        token = registration["token"]

        entry = req(
            base,
            "POST",
            "/api/validate",
            {"operator": "Acceso", "checkpoint": "Sala A", "token": token, "activity_id": activity_id},
        )
        assert_true(entry["result"] == "granted", "No registro ingreso por QR")
        assert_true(entry["attendance"]["status"] == "Presente", "Ingreso en modo ingreso/egreso debe quedar presente")

        with server.connect() as db:
            entry_at = (datetime.now(timezone.utc) - timedelta(minutes=55)).isoformat(timespec="seconds")
            db.execute("UPDATE activity_attendance SET entry_at = ? WHERE activity_id = ?", (entry_at, activity_id))

        exit_result = req(
            base,
            "POST",
            "/api/attendance/exit",
            {"actor": "Acceso", "token": token, "activity_id": activity_id},
        )
        assert_true(exit_result["percentage"] >= 90, "No calculo porcentaje de asistencia")
        assert_true(exit_result["eligibility_status"] == "Elegible", "No determino elegibilidad")

        portal = req(base, "GET", f"/api/portal?token={token}")
        assert_true(portal["attendances"][0]["eligibility_status"] == "Elegible", "Portal no muestra elegibilidad")
        assert_true(portal["attendances"][0]["certificate_generated_at"], "No genero certificado automaticamente")
        pdf = req(base, "GET", f"/api/certificate.pdf?token={token}&activity_id={activity_id}", parse_json=False)
        assert_true(pdf.startswith(b"%PDF"), "Certificado PDF no disponible")

        dashboard = req(base, "GET", f"/api/attendance-dashboard?event_id={event_id}")
        assert_true(dashboard["totals"]["eligible"] == 1, "Dashboard no cuenta elegibles")
        assert_true(dashboard["activities"][0]["present"] == 1, "Dashboard no cuenta presentes")

        csv_body = req(base, "GET", f"/api/attendances.csv?event_id={event_id}", parse_json=False)
        assert_true(b"Workshop asistencia" in csv_body and b"Elegible" in csv_body, "CSV de asistencias incompleto")

        rows = req(base, "GET", f"/api/attendances?event_id={event_id}")
        manual = req(
            base,
            "POST",
            "/api/attendance/manual",
            {"actor": "Admin", "id": rows[0]["id"], "status": "Ausente", "percentage": 0, "reason": "prueba"},
        )
        assert_true(manual["eligibility_status"] == "No elegible", "Correccion manual no recalculo elegibilidad")

        cert_csv = req(base, "GET", f"/api/certificate-eligibility.csv?event_id={event_id}&status=not_eligible", parse_json=False)
        assert_true(b"No elegible" in cert_csv, "CSV de no elegibles incompleto")

        audit = req(base, "GET", f"/api/audit?event_id={event_id}")
        actions = {row["action"] for row in audit}
        assert_true("attendance.entry_registered" in actions, "Falta auditoria de ingreso")
        assert_true("attendance.exit_registered" in actions, "Falta auditoria de egreso")
        assert_true("attendance.manual_corrected" in actions, "Falta auditoria de correccion")

        print("OK: V4.2 asistencia y elegibilidad de certificados")
    finally:
        if httpd:
            httpd.shutdown()
            httpd.server_close()
        shutil.rmtree(tmp_path, ignore_errors=True)


if __name__ == "__main__":
    main()
