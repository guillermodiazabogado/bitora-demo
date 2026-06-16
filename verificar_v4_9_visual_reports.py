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
    tmp_path = Path(tempfile.mkdtemp(prefix="qr-v4-9-"))
    httpd = None
    try:
        server.DB_PATH = tmp_path / "v4_9.sqlite3"
        server.BACKUP_DIR = tmp_path / "backups"
        server.AppHandler.log_message = lambda self, format, *args: None
        server.init_db()
        server.seed_if_empty()
        httpd = server.OperationalHTTPServer(("127.0.0.1", 0), server.AppHandler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{httpd.server_address[1]}"

        event = req(base, "POST", "/api/events", {"actor": "Admin", "name": "Sala Control", "status": "published", "capacity": 150}, 201)
        event_id = event["id"]
        space_id = req(base, "GET", f"/api/spaces?event_id={event_id}")[0]["id"]
        activity = req(
            base,
            "POST",
            "/api/activities",
            {
                "actor": "Admin",
                "event_id": event_id,
                "space_id": space_id,
                "title": "Reporte visual",
                "starts_at": "2026-09-03T10:00",
                "ends_at": "2026-09-03T11:00",
                "capacity": 40,
                "reservation_mode": "free",
            },
            201,
        )
        registration = req(
            base,
            "POST",
            "/api/register",
            {
                "actor": "public",
                "event_id": event_id,
                "first_name": "Dato",
                "last_name": "Privado",
                "email": "privado@example.test",
                "phone": "123",
                "dni": "999",
                "type": "General",
                "source": "linkedin",
                "device_type": "desktop",
            },
            201,
        )
        with server.connect() as db:
            acc_id = int(db.execute("SELECT id FROM accreditations WHERE token = ?", (registration["token"],)).fetchone()["id"])
        req(base, "POST", "/api/reservations", {"actor": "Recepcion", "event_id": event_id, "activity_id": activity["id"], "accreditation_id": acc_id}, 201)
        req(base, "POST", "/api/validate", {"token": registration["token"], "operator": "Acceso", "checkpoint": "Puerta"})
        req(base, "POST", "/api/validate", {"token": registration["token"], "operator": "Acceso", "checkpoint": "Puerta"})
        req(base, "POST", "/api/validate", {"token": "EVT-INEXISTENTE", "operator": "Acceso", "checkpoint": "Puerta"}, 404)
        req(base, "POST", "/api/communications/send", {"actor": "Admin", "event_id": event_id, "channel": "email", "content": "Aviso demo"})

        summary = req(base, "GET", f"/api/reports/visual-summary?event_id={event_id}")
        assert_true(summary["event"]["name"] == "Sala Control", "Resumen visual no devuelve evento")
        assert_true(summary["totals"]["registered"] == 1 and summary["totals"]["checked"] == 1, "KPI de acreditacion incorrecto")
        assert_true(summary["by_type"][0]["label"] == "General", "Barras por tipo incompletas")
        assert_true(summary["activity_occupancy"][0]["label"] == "Reporte visual", "Ranking de actividades incompleto")
        assert_true(any(row["value"] >= 1 for row in summary["rejection_reasons"]), "Motivos de rechazo no se calculan")
        assert_true(summary["source_counts"][0]["label"] == "linkedin", "Origen no aparece en resumen visual")
        assert_true(summary["device_counts"][0]["label"] == "desktop", "Dispositivo no aparece en resumen visual")
        assert_true(summary["communication_status_counts"], "Comunicaciones no aparecen en resumen visual")
        assert_true(summary["operator_activity"][0]["label"] == "Acceso", "Operador activo no aparece")

        safe_payload = json.dumps(summary)
        assert_true("privado@example.test" not in safe_payload and "999" not in safe_payload and "123" not in safe_payload, "Resumen visual filtra datos personales")

        dashboard_html = req(base, "GET", "/index.html", parse_json=False)
        assert_true(b"Abrir Sala de Control" in dashboard_html, "Reportes no incluye acceso a Sala de Control")
        assert_true(b"visual-block-picker" in dashboard_html, "No existe configuracion de bloques visuales")

        display_html = req(base, "GET", f"/reports-display?event_id={event_id}&refresh=5&theme=dark&blocks=kpis,status,access", parse_json=False)
        assert_true(b"Sala de Control BITORA" in display_html and b"/api/reports/visual-summary" in display_html, "Ventana independiente no carga resumen visual")
        assert_true(b"privado@example.test" not in display_html and b"999" not in display_html, "Pantalla de control contiene datos sensibles")

        audit = req(base, "GET", f"/api/audit?event_id={event_id}")
        actions = {row["action"] for row in audit}
        assert_true("reports.visual_opened" in actions, "Falta auditoria de apertura de sala de control")

        print("OK: V4.9 reportes visuales y sala de control")
    finally:
        if httpd:
            httpd.shutdown()
            httpd.server_close()
        shutil.rmtree(tmp_path, ignore_errors=True)


if __name__ == "__main__":
    main()
