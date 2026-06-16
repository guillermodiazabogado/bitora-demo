from __future__ import annotations

import json
import os
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
    old = {key: os.environ.get(key) for key in ("WHATSAPP_PROVIDER", "WHATSAPP_API_KEY", "WHATSAPP_PHONE_ID", "WHATSAPP_BUSINESS_ID")}
    tmp = Path(tempfile.mkdtemp(prefix="qr-v5-wa-"))
    httpd = None
    try:
        os.environ["WHATSAPP_PROVIDER"] = "business_platform"
        os.environ["WHATSAPP_API_KEY"] = "test-key"
        os.environ["WHATSAPP_PHONE_ID"] = "phone-id"
        server.DB_PATH = tmp / "wa.sqlite3"
        server.BACKUP_DIR = tmp / "backups"
        server.AppHandler.log_message = lambda self, format, *args: None
        server.init_db()
        server.seed_if_empty()
        httpd = server.OperationalHTTPServer(("127.0.0.1", 0), server.AppHandler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        event_id = req(base, "POST", "/api/events", {"actor": "Admin", "name": "WhatsApp real", "status": "published"}, 201)["id"]
        req(base, "POST", "/api/register", {"actor": "public", "event_id": event_id, "first_name": "Whats", "last_name": "App", "email": "wa@example.test", "phone": "5492991234567", "type": "General", "acepta_whatsapp": True}, 201)
        sent = req(base, "POST", "/api/communications/whatsapp/send", {"actor": "Admin", "event_id": event_id, "audience": "all", "subject": "QR", "content": "Portal {{portal_participante}}"})
        assert sent["queued"] == 1 and sent["sent"] == 1
        data = req(base, "GET", f"/api/communications?event_id={event_id}")
        assert data["providers"]["whatsapp"]["ready"] is True
        queue_id = data["queue"][0]["id"]
        webhook = req(base, "POST", "/api/communications/whatsapp/webhook", {"event_id": event_id, "queue_id": queue_id, "status": "leido"})
        assert webhook["status"] == "leido"
        data2 = req(base, "GET", f"/api/communications?event_id={event_id}")
        assert data2["queue"][0]["status"] == "leido"
        print("OK: V5 WhatsApp real y webhook preparados")
    finally:
        if httpd:
            httpd.shutdown()
            httpd.server_close()
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
