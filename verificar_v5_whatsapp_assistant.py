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
    request = urllib.request.Request(base + path, data=data, headers={"Content-Type": "application/json"} if data else {}, method=method)
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
    return json.loads(body.decode("utf-8")) if "application/json" in content_type and body else {}


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="qr-v5-assistant-"))
    httpd = None
    try:
        server.DB_PATH = tmp / "assistant.sqlite3"
        server.BACKUP_DIR = tmp / "backups"
        server.AppHandler.log_message = lambda self, format, *args: None
        server.init_db()
        server.seed_if_empty()
        httpd = server.OperationalHTTPServer(("127.0.0.1", 0), server.AppHandler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        event_id = req(base, "POST", "/api/events", {"actor": "Admin", "name": "Asistente", "status": "published"}, 201)["id"]
        space_id = req(base, "GET", f"/api/spaces?event_id={event_id}")[0]["id"]
        activity_id = req(base, "POST", "/api/activities", {"actor": "Admin", "event_id": event_id, "space_id": space_id, "title": "Agenda IA", "starts_at": "2026-10-10T10:00", "ends_at": "2026-10-10T11:00", "capacity": 20}, 201)["id"]
        reg = req(base, "POST", "/api/register", {"actor": "public", "event_id": event_id, "first_name": "Asis", "last_name": "Tente", "email": "asis@example.test", "phone": "5492997777777", "type": "General", "acepta_whatsapp": True}, 201)
        with server.connect() as db:
            acc_id = db.execute("SELECT id FROM accreditations WHERE token = ?", (reg["token"],)).fetchone()["id"]
        req(base, "POST", "/api/reservations", {"actor": "Recepcion", "event_id": event_id, "activity_id": activity_id, "accreditation_id": acc_id}, 201)
        qr = req(base, "POST", "/api/communications/assistant/message", {"event_id": event_id, "phone": "5492997777777", "message": "QR"})
        assert qr["intent"] == "qr" and "/p.html?token=" in qr["reply"]
        agenda = req(base, "POST", "/api/communications/assistant/message", {"event_id": event_id, "phone": "5492997777777", "message": "Agenda"})
        assert "Agenda IA" in agenda["reply"]
        handoff = req(base, "POST", "/api/communications/assistant/message", {"event_id": event_id, "phone": "5492997777777", "message": "Operador"})
        assert handoff["intent"] == "handoff"
        history = req(base, "GET", f"/api/communications/assistant/history?event_id={event_id}")
        assert len(history) >= 3
        dashboard = req(base, "GET", f"/api/communications?event_id={event_id}")
        assert dashboard["assistant_metrics"]["received"] >= 3 and dashboard["assistant_metrics"]["handoffs"] >= 1
        payload = json.dumps(history)
        assert "asis@example.test" not in payload
        print("OK: V5 WhatsApp inteligente, menu, QR, agenda y derivacion")
    finally:
        if httpd:
            httpd.shutdown()
            httpd.server_close()
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
