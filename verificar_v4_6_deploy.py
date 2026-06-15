from __future__ import annotations

import json
import shutil
import tempfile
import threading
import urllib.error
import urllib.request
from pathlib import Path

import server


ROOT = Path(__file__).resolve().parent


def req(base, method, path, payload=None, expect=200, parse_json=True, headers=None, session_cookie=None):
    data = None
    request_headers = headers.copy() if headers else {}
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


def assert_file_contains(path: str, terms: list[str]) -> None:
    full_path = ROOT / path
    assert_true(full_path.exists(), f"Falta archivo requerido: {path}")
    content = full_path.read_text(encoding="utf-8")
    for term in terms:
        assert_true(term in content, f"{path} no contiene {term}")


def main() -> None:
    assert_file_contains("requirements.txt", ["Pillow"])
    assert_file_contains("Procfile", ["python backend/app.py"])
    assert_file_contains("render.yaml", ["healthCheckPath: /health", "APP_ENV", "QR_DB_ENGINE"])
    assert_file_contains(".env.example", ["APP_ENV", "BASE_URL", "PORT", "QR_SQLITE_PATH", "QR_POSTGRES_DSN", "HTTPS_REQUIRED"])
    assert_file_contains(".gitignore", [".env", "*.sqlite3", "backups/", "*.log"])
    assert_file_contains("README_DEPLOY.md", ["Render", "Railway", "/health", "BASE_URL"])
    assert_file_contains("DEPLOYMENT_READINESS_REPORT.md", ["SQLite", "Health check", "Riesgos"])

    tmp_path = Path(tempfile.mkdtemp(prefix="qr-v4-6-"))
    httpd = None
    old_values = {
        "DB_PATH": server.DB_PATH,
        "BACKUP_DIR": server.BACKUP_DIR,
        "APP_ENV": server.APP_ENV,
        "BASE_URL": server.BASE_URL,
        "HTTPS_REQUIRED": server.HTTPS_REQUIRED,
    }
    try:
        server.DB_PATH = tmp_path / "v4_6.sqlite3"
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
        assert_true(httpd.server_address[1] != 8787, "La prueba debe funcionar con puerto dinamico")

        health = req(base, "GET", "/health")
        assert_true(health["status"] == "ok", "Health check no responde ok")
        assert_true(health["env"] == "demo", "Health check no refleja APP_ENV")
        assert_true(health["version"], "Health check no informa version")

        config = req(base, "GET", "/api/app-config")
        assert_true(config["base_url"] == "https://bitora-demo.example", "BASE_URL no se aplica")
        assert_true(config["demo"] is True, "Modo demo no se informa")
        assert_true(config["database"]["engine"] == "sqlite", "SQLite demo no informado")

        login_page = req(base, "GET", "/login.html", parse_json=False)
        assert_true(b"BITORA" in login_page[0], "Login no carga")

        login = req(base, "POST", "/api/auth/login", {"name": "Admin", "pin": "1234"}, parse_json=False)
        cookie = login[1].get("Set-Cookie").split(";", 1)[0]

        event = req(base, "POST", "/api/prepare-event", {"actor": "Admin", "name": "Deploy Demo", "capacity": 120}, session_cookie=cookie)
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
                "title": "Deploy Test",
                "starts_at": "2027-01-01T10:00",
                "ends_at": "2027-01-01T11:00",
                "capacity": 30,
                "reservation_mode": "optional",
            },
            201,
            session_cookie=cookie,
        )

        landing = req(base, "GET", f"/e.html?event_id={event_id}&source=qr_hall", parse_json=False)
        assert_true(b"Inscribirme" in landing[0], "Landing publica no carga")

        registration = req(
            base,
            "POST",
            "/api/register",
            {
                "actor": "public",
                "event_id": event_id,
                "first_name": "Deploy",
                "last_name": "Ready",
                "email": "deploy.ready@example.com",
                "type": "General",
                "source": "landing",
                "device_type": "desktop",
            },
            201,
        )
        assert_true(registration["portal_url"].startswith("https://bitora-demo.example/"), "Portal URL no usa BASE_URL")

        portal = req(base, "GET", f"/api/portal?token={registration['token']}")
        assert_true(portal["token"] == registration["token"], "Portal participante falla")

        qr = req(base, "GET", f"/api/qr.svg?token={registration['token']}", parse_json=False)
        assert_true(b"<svg" in qr[0], "QR no disponible")

        reservation = req(base, "POST", "/api/portal/reserve", {"token": registration["token"], "activity_id": activity["id"], "confirmed": True, "verification_answer": "7"}, 201)
        assert_true(reservation["reservation"]["ok"], "Reserva cloud no funciona")

        status = req(base, "GET", f"/api/system-status?event_id={event_id}", session_cookie=cookie)
        assert_true(status["env"] == "demo", "System status no informa entorno")
        assert_true(status["base_url"] == "https://bitora-demo.example", "System status no informa BASE_URL")
        assert_true(status["database"]["engine"] == "sqlite", "System status no informa SQLite")

        backup = req(base, "GET", f"/api/backup?event_id={event_id}", parse_json=False, session_cookie=cookie)
        assert_true(len(backup[0]) > 0, "Backup demo falla")

        headers_test = req(base, "GET", "/api/app-config", parse_json=False, headers={"X-Forwarded-Proto": "https"})
        assert_true(headers_test[1].get("X-Content-Type-Options") == "nosniff", "Falta X-Content-Type-Options")
        assert_true(headers_test[1].get("Strict-Transport-Security"), "Falta HSTS en modo HTTPS")

        print("OK: V4.6 deploy readiness")
    finally:
        if httpd:
            httpd.shutdown()
            httpd.server_close()
        for key, value in old_values.items():
            setattr(server, key, value)
        shutil.rmtree(tmp_path, ignore_errors=True)


if __name__ == "__main__":
    main()
