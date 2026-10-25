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
        event = req(base, "POST", "/api/events", {
            "actor": "Admin",
            "name": "V5 Comunicaciones",
            "status": "published",
            "registration_confirmation_subject": "Tu acceso a {{evento}}",
            "registration_confirmation_message": "Hola {{nombre}}. Descarga o imprime tu QR desde {{portal_participante}}. Referencia: https://example.test/info",
        }, 201)
        event_id = event["id"]
        req(base, "POST", "/api/events/update", {
            "actor": "Admin",
            "event_id": event_id,
            "name": "V5 Comunicaciones",
            "registration_confirmation_subject": "Tu acceso a {{evento}}",
            "registration_confirmation_message": "Hola {{nombre}}. Descarga o imprime tu QR desde {{portal_participante}}. Referencia: https://example.test/info",
        })
        configured_event = next(row for row in req(base, "GET", "/api/events") if int(row["id"]) == event_id)
        assert_true(configured_event["registration_confirmation_subject"] == "Tu acceso a {{evento}}", "No se guardo el asunto configurable")
        assert_true("https://example.test/info" in configured_event["registration_confirmation_message"], "No se guardo el mensaje configurable")
        ok = req(base, "POST", "/api/register", {"actor": "public", "event_id": event_id, "first_name": "Con", "last_name": "Consentimiento", "email": "ok@example.test", "phone": "54911111111", "type": "General", "acepta_email": True, "acepta_whatsapp": True}, 201)
        req(base, "POST", "/api/register", {"actor": "public", "event_id": event_id, "first_name": "Sin", "last_name": "Consentimiento", "email": "no@example.test", "phone": "54922222222", "type": "General"}, 201)
        assert_true(ok["communications"]["email"]["status"] == "sent", "La confirmacion automatica por email no fue enviada")
        assert_true(ok["communications"]["whatsapp"]["status"] == "sent", "La confirmacion automatica por WhatsApp no fue enviada")
        with server.connect() as db:
            automatic = db.execute(
                "SELECT channel, subject, content FROM communication_queue WHERE event_id = ? AND accreditation_id = ? ORDER BY channel",
                (event_id, db.execute("SELECT id FROM accreditations WHERE token = ?", (ok["token"],)).fetchone()["id"]),
            ).fetchall()
        assert_true(len(automatic) == 2, "La inscripcion debe generar exactamente email y WhatsApp")
        assert_true(all(row["subject"] == "Tu acceso a V5 Comunicaciones" for row in automatic), "El asunto parametrizado no se renderizo")
        assert_true(all("https://example.test/info" in row["content"] and "Hola Con" in row["content"] for row in automatic), "El mensaje parametrizado no llego a ambos canales")
        result = req(base, "POST", "/api/communications/send", {"actor": "Admin", "event_id": event_id, "audience": "all", "channel": "both", "template_code": "registration_confirmation", "subject": "Hola {{nombre}}", "content": "Portal {{portal_participante}}", "confirm": True})
        assert_true(result["queued"] == 2 and result["sent"] == 2 and result["skipped"] == 2, "Cola/exclusiones por consentimiento incorrectas")
        dashboard = req(base, "GET", f"/api/communications?event_id={event_id}")
        assert_true(dashboard["mode"] == "demo", "Debe iniciar en modo demo")
        assert_true(dashboard["queue_metrics"]["emails_sent"] == 2 and dashboard["queue_metrics"]["whatsapp_sent"] == 2, "Metricas de cola incorrectas")
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
