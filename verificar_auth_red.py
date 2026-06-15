from __future__ import annotations

import json
import shutil
import tempfile
import threading
import urllib.error
import urllib.request
from pathlib import Path

import server


class Jar:
    def __init__(self) -> None:
        self.cookie = ""

    def request(self, base: str, method: str, path: str, payload: dict | None = None, expect: int = 200):
        data = None
        headers = {}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if self.cookie:
            headers["Cookie"] = self.cookie
        req = urllib.request.Request(base + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                body = response.read()
                status = response.status
                cookie = response.headers.get("Set-Cookie")
        except urllib.error.HTTPError as exc:
            body = exc.read()
            status = exc.code
            cookie = exc.headers.get("Set-Cookie")
        if cookie:
            self.cookie = cookie.split(";", 1)[0]
        if status != expect:
            raise AssertionError(f"{method} {path}: esperado {expect}, recibido {status}: {body!r}")
        return json.loads(body.decode("utf-8")) if body else {}


def main() -> None:
    tmp_path = Path(tempfile.mkdtemp(prefix="qr-auth-"))
    httpd = None
    try:
        server.DB_PATH = tmp_path / "auth.sqlite3"
        server.BACKUP_DIR = tmp_path / "backups"
        server.AppHandler.log_message = lambda self, format, *args: None
        server.init_db()
        server.seed_if_empty()

        httpd = server.OperationalHTTPServer(("127.0.0.1", 0), server.AppHandler)
        httpd.require_login = True
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{httpd.server_address[1]}"

        anon = Jar()
        anon.request(base, "GET", "/api/events", expect=401)
        public_event = anon.request(base, "GET", "/api/event?event_id=1")
        if not public_event.get("name"):
            raise AssertionError("El evento publico no respondio")

        jar = Jar()
        jar.request(base, "POST", "/api/auth/login", {"name": "Admin", "pin": "1234"})
        me = jar.request(base, "GET", "/api/auth/me")
        if not me["authenticated"] or me["user"]["name"] != "Admin":
            raise AssertionError("Login no dejo sesion Admin")
        events = jar.request(base, "GET", "/api/events")
        if not events:
            raise AssertionError("API protegida no respondio con sesion")
        info = jar.request(base, "GET", "/api/network-info")
        if not info["require_login"]:
            raise AssertionError("network-info no informa login requerido")
        jar.request(base, "POST", "/api/auth/logout", {})
        jar.request(base, "GET", "/api/events", expect=401)
        print("OK: auth/red protegida")
    finally:
        if httpd:
            httpd.shutdown()
            httpd.server_close()
        shutil.rmtree(tmp_path, ignore_errors=True)


if __name__ == "__main__":
    main()
