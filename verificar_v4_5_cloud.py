from __future__ import annotations

import json
import shutil
import tempfile
import threading
import urllib.error
import urllib.request
from pathlib import Path

import server


def req(base, method, path, payload=None, expect=200, parse_json=True, headers=None, session_cookie=None):
    data = None
    request_headers = headers or {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    if session_cookie:
        request_headers["Cookie"] = session_cookie
    request = urllib.request.Request(base + path, data=data, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            body = response.read()
            status = response.status
            content_type = response.headers.get("Content-Type", "")
            response_headers = response.headers
    except urllib.error.HTTPError as exc:
        body = exc.read()
        status = exc.code
        content_type = exc.headers.get("Content-Type", "")
        response_headers = exc.headers
    if status != expect:
        raise AssertionError(f"{method} {path}: esperado {expect}, recibido {status}: {body!r}")
    if parse_json and "application/json" in content_type:
        return json.loads(body.decode("utf-8")) if body else {}
    return body, response_headers


def assert_true(value, message):
    if not value:
        raise AssertionError(message)


def main() -> None:
    tmp_path = Path(tempfile.mkdtemp(prefix="qr-v4-5-"))
    httpd = None
    old_values = {
        "DB_PATH": server.DB_PATH,
        "BACKUP_DIR": server.BACKUP_DIR,
        "APP_ENV": server.APP_ENV,
        "BASE_URL": server.BASE_URL,
        "HTTPS_REQUIRED": server.HTTPS_REQUIRED,
    }
    try:
        server.DB_PATH = tmp_path / "v4_5.sqlite3"
        server.BACKUP_DIR = tmp_path / "backups"
        server.APP_ENV = "demo"
        server.BASE_URL = "https://bitora-demo.example"
        server.HTTPS_REQUIRED = True
        server.AppHandler.log_message = lambda self, format, *args: None
        server.init_db()
        server.seed_if_empty()
        httpd = server.OperationalHTTPServer(("127.0.0.1", 0), server.AppHandler)
        httpd.require_login = True
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{httpd.server_address[1]}"

        health = req(base, "GET", "/health")
        assert_true(health["status"] == "ok" and health["env"] == "demo", "Health check invalido")

        config = req(base, "GET", "/api/app-config")
        assert_true(config["base_url"] == "https://bitora-demo.example", "BASE_URL no aplicado")
        assert_true(config["demo"] is True, "Modo demo no informado")

        login = req(base, "POST", "/api/auth/login", {"name": "Admin", "pin": "1234"}, parse_json=False)
        cookie = login[1].get("Set-Cookie").split(";", 1)[0]

        event = req(base, "POST", "/api/prepare-event", {"actor": "Admin", "name": "Cloud Demo", "capacity": 100}, session_cookie=cookie)
        event_id = event["event_id"]
        spaces = req(base, "GET", f"/api/spaces?event_id={event_id}", session_cookie=cookie)
        activity = req(
            base,
            "POST",
            "/api/activities",
            {
                "actor": "Admin",
                "event_id": event_id,
                "space_id": spaces[0]["id"],
                "title": "Cloud Test",
                "starts_at": "2027-01-01T10:00",
                "ends_at": "2027-01-01T11:00",
                "capacity": 20,
                "reservation_mode": "optional",
            },
            201,
            session_cookie=cookie,
        )

        registration = req(
            base,
            "POST",
            "/api/register",
            {
                "actor": "public",
                "event_id": event_id,
                "first_name": "Cloud",
                "last_name": "Demo",
                "email": "cloud.demo@example.com",
                "type": "General",
                "source": "landing",
                "device_type": "desktop",
            },
            201,
        )
        assert_true(registration["portal_url"].startswith("https://bitora-demo.example/"), "Portal URL no es absoluta con BASE_URL")

        portal = req(base, "GET", f"/api/portal?token={registration['token']}")
        assert_true(portal["token"] == registration["token"], "Portal participante falla")

        qr = req(base, "GET", f"/api/qr.svg?token={registration['token']}", parse_json=False)
        assert_true(b"<svg" in qr[0], "QR no disponible")

        reservation = req(base, "POST", "/api/portal/reserve", {"token": registration["token"], "activity_id": activity["id"], "confirmed": True, "verification_answer": "7"}, 201)
        assert_true(reservation["reservation"]["ok"], "Reserva cloud falla")

        status = req(base, "GET", f"/api/system-status?event_id={event_id}", session_cookie=cookie)
        assert_true(status["env"] == "demo" and status["base_url"] == "https://bitora-demo.example", "System status cloud incompleto")

        backup = req(base, "GET", f"/api/backup?event_id={event_id}", parse_json=False, session_cookie=cookie)
        assert_true(len(backup[0]) > 0, "Backup cloud falla")

        audit = req(base, "GET", f"/api/audit?event_id={event_id}", session_cookie=cookie)
        actions = {row["action"] for row in audit}
        assert_true("portal.generated" in actions and "backup.created" in actions, "Auditoria cloud incompleta")

        headers_test = req(base, "GET", "/api/app-config", parse_json=False)
        assert_true(headers_test[1].get("X-Content-Type-Options") == "nosniff", "Faltan headers de seguridad")

        print("OK: V4.5 cloud demo")
    finally:
        if httpd:
            httpd.shutdown()
            httpd.server_close()
        for key, value in old_values.items():
            setattr(server, key, value)
        shutil.rmtree(tmp_path, ignore_errors=True)


if __name__ == "__main__":
    main()
