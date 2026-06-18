from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import server


class FakeResendHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        body = json.dumps({"id": "v5-email-1"}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def req(base, method, path, payload=None, expect=200):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(base + path, data=data, headers={"Content-Type": "application/json"} if data else {}, method=method)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            body = response.read()
            status = response.status
            content_type = response.headers.get("Content-Type", "")
    except urllib.error.HTTPError as exc:  # type: ignore[attr-defined]
        body = exc.read()
        status = exc.code
        content_type = exc.headers.get("Content-Type", "")
    if status != expect:
        raise AssertionError(f"{method} {path}: esperado {expect}, recibido {status}: {body!r}")
    return json.loads(body.decode("utf-8")) if "application/json" in content_type and body else {}


def main() -> None:
    old = {key: os.environ.get(key) for key in ("EMAIL_PROVIDER", "EMAIL_API_KEY", "EMAIL_FROM", "EMAIL_REPLY_TO", "EMAIL_ENABLED", "EMAIL_RESEND_API_URL")}
    tmp = Path(tempfile.mkdtemp(prefix="qr-v5-email-"))
    httpd = None
    provider = ThreadingHTTPServer(("127.0.0.1", 0), FakeResendHandler)
    threading.Thread(target=provider.serve_forever, daemon=True).start()
    try:
        os.environ["EMAIL_PROVIDER"] = "resend"
        os.environ["EMAIL_API_KEY"] = "test-key"
        os.environ["EMAIL_FROM"] = "eventos@example.test"
        os.environ["EMAIL_ENABLED"] = "true"
        os.environ["EMAIL_RESEND_API_URL"] = f"http://127.0.0.1:{provider.server_address[1]}"
        server.DB_PATH = tmp / "email.sqlite3"
        server.BACKUP_DIR = tmp / "backups"
        server.AppHandler.log_message = lambda self, format, *args: None
        server.init_db()
        server.seed_if_empty()
        httpd = server.OperationalHTTPServer(("127.0.0.1", 0), server.AppHandler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        event_id = req(base, "POST", "/api/events", {"actor": "Admin", "name": "Email real", "status": "published"}, 201)["id"]
        req(base, "POST", "/api/register", {"actor": "public", "event_id": event_id, "first_name": "Email", "last_name": "Real", "email": "real@example.test", "phone": "1", "type": "General", "acepta_email": True}, 201)
        sent = req(base, "POST", "/api/communications/email/send", {"actor": "Admin", "event_id": event_id, "audience": "all", "subject": "QR {{nombre}}", "content": "Portal {{portal_participante}}"})
        assert sent["queued"] == 1 and sent["sent"] == 1
        data = req(base, "GET", f"/api/communications?event_id={event_id}")
        assert data["providers"]["email"]["provider"] == "resend" and data["providers"]["email"]["ready"] is True
        assert data["queue"][0]["status"] == "enviado" and data["queue"][0]["provider"] == "resend"
        print("OK: V5 email real preparado por proveedor")
    finally:
        if httpd:
            httpd.shutdown()
            httpd.server_close()
        provider.shutdown()
        provider.server_close()
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
