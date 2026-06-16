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


def assert_true(value, message):
    if not value:
        raise AssertionError(message)


def setup_app():
    tmp_path = Path(tempfile.mkdtemp(prefix="qr-v5-comms-"))
    server.DB_PATH = tmp_path / "v5.sqlite3"
    server.BACKUP_DIR = tmp_path / "backups"
    server.AppHandler.log_message = lambda self, format, *args: None
    server.init_db()
    server.seed_if_empty()
    httpd = server.OperationalHTTPServer(("127.0.0.1", 0), server.AppHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return tmp_path, httpd, f"http://127.0.0.1:{httpd.server_address[1]}"


def main() -> None:
    tmp_path, httpd, base = setup_app()
    try:
        event = req(base, "POST", "/api/events", {"actor": "Admin", "name": "V5 Comunicaciones", "status": "published"}, 201)
        event_id = event["id"]
        ok = req(base, "POST", "/api/register", {"actor": "public", "event_id": event_id, "first_name": "Con", "last_name": "Consentimiento", "email": "ok@example.test", "phone": "54911111111", "type": "General", "acepta_email": True, "acepta_whatsapp": True}, 201)
        req(base, "POST", "/api/register", {"actor": "public", "event_id": event_id, "first_name": "Sin", "last_name": "Consentimiento", "email": "no@example.test", "phone": "54922222222", "type": "General"}, 201)
        result = req(base, "POST", "/api/communications/send", {"actor": "Admin", "event_id": event_id, "audience": "all", "channel": "both", "template_code": "registration_confirmation", "subject": "Hola {{nombre}}", "content": "Portal {{portal_participante}}", "confirm": True})
        assert_true(result["queued"] == 2 and result["sent"] == 2 and result["skipped"] == 2, "Cola/exclusiones por consentimiento incorrectas")
        dashboard = req(base, "GET", f"/api/communications?event_id={event_id}")
        assert_true(dashboard["mode"] == "demo", "Debe iniciar en modo demo")
        assert_true(dashboard["queue_metrics"]["emails_sent"] == 1 and dashboard["queue_metrics"]["whatsapp_sent"] == 1, "Metricas de cola incorrectas")
        assert_true(any("{{nombre}}" in row["contenido"] for row in dashboard["templates"]), "Plantillas no incluyen variables")
        history = req(base, "GET", f"/api/communications/history?event_id={event_id}")
        assert_true(len(history) >= 2, "Historial por persona incompleto")
        audit = req(base, "GET", f"/api/audit?event_id={event_id}")
        assert_true(any(row["action"] == "communications.queued" for row in audit), "Falta auditoria de comunicaciones")
        assert_true(ok["token"].startswith("EVT-"), "Inscripcion base invalida")
        print("OK: V5 centro de comunicaciones, audiencias, cola, historial y auditoria")
    finally:
        httpd.shutdown()
        httpd.server_close()
        shutil.rmtree(tmp_path, ignore_errors=True)


if __name__ == "__main__":
    main()
