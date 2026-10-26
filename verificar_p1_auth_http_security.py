from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import threading
import urllib.error
import urllib.request

import server


def call(base, path, payload, *, cookie="", csrf="", expected=200):
    headers = {"Content-Type": "application/json"}
    if cookie:
        headers["Cookie"] = cookie
    if csrf:
        headers["X-CSRF-Token"] = csrf
    request = urllib.request.Request(base + path, json.dumps(payload).encode(), headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            status, body, response_headers = response.status, response.read(), response.headers
    except urllib.error.HTTPError as exc:
        status, body, response_headers = exc.code, exc.read(), exc.headers
    if status != expected:
        raise AssertionError((path, expected, status, body))
    return json.loads(body.decode()), response_headers


def main() -> None:
    workspace_tmp = Path(__file__).resolve().parent / "tmp"
    workspace_tmp.mkdir(exist_ok=True)
    temp_root = Path(tempfile.mkdtemp(prefix="bitora-p1-auth-", dir=workspace_tmp))
    original_db_path = server.DB_PATH
    original_backup_dir = server.BACKUP_DIR
    httpd = None
    try:
        server.AUTH_SESSIONS.clear()
        server.DB_PATH = temp_root / "auth.sqlite3"
        server.BACKUP_DIR = temp_root / "backups"
        server.init_db()
        server.seed_if_empty()
        password = "ValidPass123!"
        legacy = hashlib.pbkdf2_hmac("sha256", password.encode(), b"qr-white-label-local", 120000).hex()
        with server.connect() as db:
            db.execute("UPDATE users SET pin_hash = ?, must_change_password = 0 WHERE name = 'Admin'", (legacy,))

        server.AppHandler.log_message = lambda self, format, *args: None
        httpd = server.OperationalHTTPServer(("127.0.0.1", 0), server.AppHandler)
        httpd.require_login = True
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{httpd.server_address[1]}"

        login, headers = call(base, "/api/auth/login", {"name": "Admin", "pin": password})
        cookie = headers.get("Set-Cookie", "").split(";", 1)[0]
        if not cookie or not login.get("csrf_token"):
            raise AssertionError((cookie, login))
        with server.connect() as db:
            upgraded = db.execute("SELECT pin_hash FROM users WHERE name = 'Admin'").fetchone()["pin_hash"]
        if not upgraded.startswith("argon2id$"):
            raise AssertionError("Legacy password was not upgraded")

        rejected, _ = call(base, "/api/prepare-event", {"name": "CSRF rejected"}, cookie=cookie, expected=403)
        if rejected.get("code") != "CSRF_REJECTED":
            raise AssertionError(rejected)
        accepted, _ = call(base, "/api/prepare-event", {"name": "CSRF accepted"}, cookie=cookie, csrf=login["csrf_token"])
        if not accepted.get("ok"):
            raise AssertionError(accepted)

        for _ in range(5):
            call(base, "/api/auth/login", {"name": "missing-user", "pin": "wrong"}, expected=403)
        limited, _ = call(base, "/api/auth/login", {"name": "missing-user", "pin": "wrong"}, expected=429)
        if limited.get("code") != "LOGIN_RATE_LIMITED":
            raise AssertionError(limited)

        original_env = server.APP_ENV
        try:
            server.APP_ENV = "production"
            if "Secure" not in server.session_cookie_header("token"):
                raise AssertionError("Production session cookie is not Secure")
        finally:
            server.APP_ENV = original_env
        print("P1 auth migration, CSRF, Secure cookie and persistent login rate limit: OK")
    finally:
        if httpd:
            httpd.shutdown()
            httpd.server_close()
        server.AUTH_SESSIONS.clear()
        server.DB_PATH = original_db_path
        server.BACKUP_DIR = original_backup_dir
        shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    main()
