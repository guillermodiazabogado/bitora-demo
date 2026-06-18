from __future__ import annotations

import json
import shutil
import tempfile
import threading
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import server
from backend.services.demo_real import DemoRealService


def req(base: str, method: str, path: str, payload=None, expect: int = 200):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read()
            status = response.status
    except urllib.error.HTTPError as exc:
        body = exc.read()
        status = exc.code
    if status != expect:
        raise AssertionError(f"{method} {path}: esperado {expect}, recibido {status}: {body!r}")
    return json.loads(body.decode("utf-8")) if body else {}


def assert_found(base: str, event_id: int, query: str, token: str) -> None:
    encoded = urllib.parse.quote(query)
    rows = req(base, "GET", f"/api/accreditations?event_id={event_id}&q={encoded}&limit=20")
    tokens = {row["token"] for row in rows}
    if token not in tokens:
        raise AssertionError(f"No encontro {token} buscando por {query!r}")


def assert_any(base: str, event_id: int, query: str, field: str, expected: str) -> None:
    encoded = urllib.parse.quote(query)
    rows = req(base, "GET", f"/api/accreditations?event_id={event_id}&q={encoded}&limit=50")
    if not any(str(row.get(field) or "").lower() == expected.lower() for row in rows):
        raise AssertionError(f"No encontro ningun resultado con {field}={expected!r} buscando por {query!r}")


def main() -> None:
    tmp_path = Path(tempfile.mkdtemp(prefix="qr-search-"))
    httpd = None
    try:
        server.DB_PATH = tmp_path / "demo.sqlite3"
        server.BACKUP_DIR = tmp_path / "backups"
        server.AppHandler.log_message = lambda self, format, *args: None
        server.init_db()
        server.seed_if_empty()
        httpd = server.OperationalHTTPServer(("127.0.0.1", 0), server.AppHandler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{httpd.server_address[1]}"

        result = req(base, "POST", "/api/demo-real", {"actor": "Admin", "confirm": "DEMO"}, 201)
        event_id = int(result["event_id"])
        assert result["event_name"] == DemoRealService.EVENT_NAME
        sample = req(base, "GET", f"/api/accreditations?event_id={event_id}&q=Luis%20Perez%20002&limit=5")[0]
        token = sample["token"]

        assert_any(base, event_id, sample["first_name"], "first_name", sample["first_name"])
        assert_any(base, event_id, sample["last_name"], "last_name", sample["last_name"])
        full_name = f"{sample['first_name']} {sample['last_name']}"
        assert_found(base, event_id, full_name, token)
        exact_rows = req(base, "GET", f"/api/accreditations?event_id={event_id}&q={urllib.parse.quote(full_name)}&limit=5")
        if exact_rows[0]["token"] != token:
            raise AssertionError("La busqueda por nombre completo no prioriza el resultado exacto")
        assert_found(base, event_id, f"{sample['last_name']} {sample['first_name']}", token)
        assert_found(base, event_id, sample["dni"], token)
        assert_any(base, event_id, sample["company"], "company", sample["company"])
        assert_found(base, event_id, sample["email"], token)

        print("OK: busqueda por nombre, apellido, DNI y empresa")
    finally:
        if httpd:
            httpd.shutdown()
            httpd.server_close()
        shutil.rmtree(tmp_path, ignore_errors=True)


if __name__ == "__main__":
    main()
