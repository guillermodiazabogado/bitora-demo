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
    tmp_path = Path(tempfile.mkdtemp(prefix="qr-v4-8-ics-"))
    httpd = None
    try:
        server.DB_PATH = tmp_path / "v4_8_ics.sqlite3"
        server.BACKUP_DIR = tmp_path / "backups"
        server.AppHandler.log_message = lambda self, format, *args: None
        server.init_db()
        server.seed_if_empty()
        httpd = server.OperationalHTTPServer(("127.0.0.1", 0), server.AppHandler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{httpd.server_address[1]}"

        event = req(base, "POST", "/api/events", {"actor": "Admin", "name": "Calendario ICS", "status": "published"}, 201)
        event_id = event["id"]
        ics = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
SUMMARY:Charla Google Calendar
DESCRIPTION:Importada desde calendario
LOCATION:Sala Calendar
DTSTART:20261001T100000
DTEND:20261001T110000
END:VEVENT
BEGIN:VEVENT
SUMMARY:Charla Outlook
DESCRIPTION:Otra agenda
LOCATION:Sala Calendar
DTSTART:20261001T113000
DTEND:20261001T123000
END:VEVENT
END:VCALENDAR
"""
        preview = req(base, "POST", "/api/agenda/preview", {"actor": "Productor", "event_id": event_id, "ics": ics})
        assert_true(preview["found"] == 2 and preview["valid"] == 2, "Previsualizacion ICS incorrecta")
        imported = req(base, "POST", "/api/agenda/import", {"actor": "Productor", "event_id": event_id, "ics": ics})
        assert_true(imported["created"] == 2 and imported["errors"] == [], "Importacion ICS no creo las actividades")
        public_event = req(base, "GET", f"/api/event?event_id={event_id}")
        titles = {row["title"] for row in public_event["activities"]}
        assert_true("Charla Google Calendar" in titles and "Charla Outlook" in titles, "Actividades ICS no visibles")
        export = req(base, "GET", f"/api/agenda.ics?event_id={event_id}", parse_json=False)
        text = export.decode("utf-8")
        assert_true("BEGIN:VCALENDAR" in text and "Charla Google Calendar" in text and "LOCATION:Sala Calendar" in text, "Exportacion ICS incompleta")
        audit = req(base, "GET", f"/api/audit?event_id={event_id}")
        actions = {row["action"] for row in audit}
        assert_true("agenda.previewed" in actions and "agenda.imported" in actions and "agenda.ics_exported" in actions, "Auditoria ICS incompleta")

        print("OK: V4.8.1 importacion y exportacion de calendario ICS")
    finally:
        if httpd:
            httpd.shutdown()
            httpd.server_close()
        shutil.rmtree(tmp_path, ignore_errors=True)


if __name__ == "__main__":
    main()
