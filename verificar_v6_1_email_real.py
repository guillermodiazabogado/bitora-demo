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
    sent: list[dict] = []
    fail_next = False

    def log_message(self, format, *args):
        return

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        if self.path != "/emails":
            self.send_error(404)
            return
        if self.__class__.fail_next:
            self.__class__.fail_next = False
            body = json.dumps({"message": "fallo simulado"}).encode()
            self.send_response(503)
        else:
            self.__class__.sent.append(payload)
            body = json.dumps({"id": f"email-{len(self.__class__.sent)}"}).encode()
            self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        body = json.dumps({"id": self.path.rsplit("/", 1)[-1], "status": "delivered"}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def req(base, method, path, payload=None, expect=200):
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        base + path,
        data=body,
        headers={"Content-Type": "application/json"} if body else {},
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            raw = response.read()
            status = response.status
            content_type = response.headers.get("Content-Type", "")
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        status = exc.code
        content_type = exc.headers.get("Content-Type", "")
    if status != expect:
        raise AssertionError(f"{method} {path}: esperado {expect}, recibido {status}: {raw!r}")
    return json.loads(raw.decode("utf-8")) if raw and "application/json" in content_type else {}


def main() -> None:
    env_keys = (
        "EMAIL_PROVIDER",
        "EMAIL_API_KEY",
        "EMAIL_FROM",
        "EMAIL_REPLY_TO",
        "EMAIL_ENABLED",
        "EMAIL_MAX_RETRIES",
        "EMAIL_RESEND_API_URL",
        "EMAIL_WEBHOOK_SECRET",
    )
    old_env = {key: os.environ.get(key) for key in env_keys}
    tmp = Path(tempfile.mkdtemp(prefix="bitora-v61-"))
    provider_server = ThreadingHTTPServer(("127.0.0.1", 0), FakeResendHandler)
    threading.Thread(target=provider_server.serve_forever, daemon=True).start()
    app_server = None
    try:
        os.environ.update({
            "EMAIL_PROVIDER": "resend",
            "EMAIL_API_KEY": "test-key",
            "EMAIL_FROM": "BITORA <eventos@example.test>",
            "EMAIL_REPLY_TO": "soporte@example.test",
            "EMAIL_ENABLED": "true",
            "EMAIL_MAX_RETRIES": "1",
            "EMAIL_RESEND_API_URL": f"http://127.0.0.1:{provider_server.server_address[1]}",
        })
        os.environ.pop("EMAIL_WEBHOOK_SECRET", None)
        server.DB_PATH = tmp / "email.sqlite3"
        server.BACKUP_DIR = tmp / "backups"
        server.AppHandler.log_message = lambda self, format, *args: None
        server.init_db()
        server.seed_if_empty()
        app_server = server.OperationalHTTPServer(("127.0.0.1", 0), server.AppHandler)
        threading.Thread(target=app_server.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{app_server.server_address[1]}"

        event_id = req(base, "POST", "/api/events", {
            "actor": "Admin",
            "name": "V6.1 Email",
            "starts_at": "2026-08-01T09:00",
            "status": "published",
        }, 201)["id"]
        consented = req(base, "POST", "/api/register", {
            "actor": "public",
            "event_id": event_id,
            "first_name": "Ana",
            "last_name": "Prueba",
            "email": "ana@example.test",
            "phone": "1",
            "company": "BITORA",
            "type": "General",
            "acepta_email": True,
        }, 201)
        req(base, "POST", "/api/register", {
            "actor": "public",
            "event_id": event_id,
            "first_name": "Sin",
            "last_name": "Consentimiento",
            "email": "no@example.test",
            "phone": "2",
            "type": "General",
        }, 201)

        sent = req(base, "POST", "/api/communications/email/send", {
            "actor": "Admin",
            "event_id": event_id,
            "audience": "all",
            "template_code": "registration_confirmation",
            "subject": "Hola {{nombre}}",
            "content": "Evento {{evento}} - Portal {{portal_participante}}",
            "confirm": True,
        })
        assert sent["queued"] == 1 and sent["sent"] == 1 and sent["skipped"] == 1
        payload = FakeResendHandler.sent[-1]
        assert payload["to"] == ["ana@example.test"]
        assert payload["subject"] == "Hola Ana"
        assert "V6.1 Email" in payload["html"] and consented["token"] in payload["html"]
        assert payload["reply_to"] == "soporte@example.test"

        webhook = req(base, "POST", "/api/communications/email/webhook", {
            "type": "email.delivered",
            "data": {"email_id": "email-1"},
        })
        assert webhook["status"] == "entregado"
        dashboard = req(base, "GET", f"/api/communications?event_id={event_id}")
        assert dashboard["providers"]["email"]["ready"] is True
        assert dashboard["queue_metrics"]["emails_delivered"] == 1
        assert dashboard["queue_metrics"]["emails_bounced"] == 0
        assert any(row["estado"] == "omitido" for row in dashboard["logs"])
        assert any(row["estado"] == "entregado" for row in dashboard["logs"])

        test_send = req(base, "POST", "/api/communications/email/test", {
            "actor": "Admin",
            "event_id": event_id,
            "email": "admin@example.test",
        })
        assert test_send["ok"] and test_send["sent"] == 1

        FakeResendHandler.fail_next = True
        failed = req(base, "POST", "/api/communications/send", {
            "actor": "Admin",
            "event_id": event_id,
            "audience": "all",
            "channel": "email",
            "subject": "Fallo controlado",
            "content": "Prueba",
            "confirm": True,
        })
        assert failed["errors"] == 1
        dashboard = req(base, "GET", f"/api/communications?event_id={event_id}")
        assert dashboard["queue_metrics"]["emails_failed"] == 1
        audit_rows = req(base, "GET", f"/api/audit?event_id={event_id}")
        actions = {row["action"] for row in audit_rows}
        assert "communications.email_sent" in actions
        assert "communications.email_status" in actions
        assert "communications.email_retry" in actions
        print("OK: V6.1 Resend, plantillas, webhook, historial, consentimiento, reintentos y errores")
    finally:
        if app_server:
            app_server.shutdown()
            app_server.server_close()
        provider_server.shutdown()
        provider_server.server_close()
        for key, value in old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
