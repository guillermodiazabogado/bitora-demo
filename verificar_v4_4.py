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
    tmp_path = Path(tempfile.mkdtemp(prefix="qr-v4-4-"))
    httpd = None
    try:
        server.DB_PATH = tmp_path / "v4_4.sqlite3"
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
                "name": "V4.4 captacion",
                "capacity": 100,
                "captation_mode": "MIXTO",
                "whatsapp_number": "5492990000000",
            },
        )
        event_id = event["event_id"]

        landing = req(base, "GET", f"/e.html?event_id={event_id}&source=qr_hall&source_detail=hall_a", parse_json=False)
        assert_true(b"captationActions" in landing, "Landing no incluye acciones de captacion")
        public_js = req(base, "GET", "/public.js", parse_json=False)
        assert_true(b"WHATSAPP_PRIMERO" in public_js and b"deviceType" in public_js, "Landing no prepara modos/dispositivo")

        req(base, "POST", "/api/captation/event", {"event_id": event_id, "action": "landing_opened", "source": "qr_hall", "source_detail": "hall_a", "device_type": "mobile", "session_id": "s1"})
        req(base, "POST", "/api/captation/event", {"event_id": event_id, "action": "form_started", "source": "qr_hall", "source_detail": "hall_a", "device_type": "mobile", "session_id": "s1"})
        registration = req(
            base,
            "POST",
            "/api/register",
            {
                "actor": "public",
                "event_id": event_id,
                "first_name": "Origen",
                "last_name": "QR",
                "email": "origen.qr@example.com",
                "phone": "111",
                "dni": "1",
                "company": "Campania",
                "type": "General",
                "source": "qr_hall",
                "source_detail": "hall_a",
                "device_type": "mobile",
                "session_id": "s1",
                "channel": "web",
            },
            201,
        )
        assert_true(registration["token"].startswith("EVT-"), "No creo inscripcion con origen")

        with server.connect() as db:
            acc = db.execute("SELECT * FROM accreditations WHERE token = ?", (registration["token"],)).fetchone()
            person = db.execute("SELECT * FROM people WHERE id = ?", (acc["person_id"],)).fetchone()
            conv = db.execute("SELECT * FROM conversation_sources WHERE accreditation_id = ?", (acc["id"],)).fetchone()
            assert_true(acc["source"] == "qr_hall" and acc["device_type"] == "mobile", "No guardo origen/dispositivo en inscripcion")
            assert_true(person["source"] == "qr_hall" and person["device_type"] == "mobile", "No guardo origen/dispositivo en participante")
            assert_true(conv and conv["source"] == "qr_hall", "No preparo ConversationSource")

        dashboard = req(base, "GET", f"/api/marketing-dashboard?event_id={event_id}")
        source_row = next((row for row in dashboard["by_source"] if row["source"] == "qr_hall"), None)
        assert_true(source_row and source_row["visitors"] == 1 and source_row["registrations"] == 1, "Dashboard por origen incorrecto")
        assert_true(source_row["conversion_rate"] == 100.0, "Conversion incorrecta")
        assert_true(dashboard["by_device"][0]["device_type"] == "mobile", "Dashboard por dispositivo incorrecto")
        assert_true(dashboard["qr_sources"][0]["source_detail"] == "hall_a", "QR de captacion no medido")

        csv_body = req(base, "GET", f"/api/captation.csv?event_id={event_id}", parse_json=False)
        assert_true(b"qr_hall" in csv_body and b"form_completed" in csv_body, "CSV de captacion incompleto")

        audit = req(base, "GET", f"/api/audit?event_id={event_id}")
        actions = {row["action"] for row in audit}
        assert_true("captation.landing_opened" in actions, "Falta auditoria landing")
        assert_true("accreditation.created" in actions, "Falta auditoria de inscripcion")

        web_event = req(base, "POST", "/api/events", {"actor": "Admin", "name": "Web", "captation_mode": "WEB_DIRECTA"}, 201)
        whats_event = req(base, "POST", "/api/events", {"actor": "Admin", "name": "Whats", "captation_mode": "WHATSAPP_PRIMERO"}, 201)
        assert_true(req(base, "GET", f"/api/event?event_id={web_event['id']}")["captation_mode"] == "WEB_DIRECTA", "Modo web no persiste")
        assert_true(req(base, "GET", f"/api/event?event_id={whats_event['id']}")["captation_mode"] == "WHATSAPP_PRIMERO", "Modo WhatsApp no persiste")

        print("OK: V4.4 captacion, conversion y origen")
    finally:
        if httpd:
            httpd.shutdown()
            httpd.server_close()
        shutil.rmtree(tmp_path, ignore_errors=True)


if __name__ == "__main__":
    main()
