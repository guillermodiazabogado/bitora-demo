from __future__ import annotations

import argparse
import json
import os
import sys
from http.cookiejar import CookieJar
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener


EXPECTED_CARDS = 12
MUST_HAVE_STATIC_MARKERS = [
    "producer-mode",
    "producerHomeAllowed",
    "producerHomeGrid",
    "Seleccioná usuario",
    "body.producer-mode .topbar nav button:not(#homeNav)",
]


class CheckFailure(RuntimeError):
    pass


def request(opener, method: str, url: str, payload: dict | None = None) -> tuple[int, str, dict | None]:
    body = None
    headers = {"User-Agent": "BITORA online home verifier"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(url, data=body, method=method, headers=headers)
    try:
        with opener.open(req, timeout=60) as response:
            text = response.read().decode("utf-8", errors="replace")
            data = None
            if response.headers.get("Content-Type", "").startswith("application/json"):
                data = json.loads(text)
            return response.status, text, data
    except HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        data = None
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            pass
        return exc.code, text, data
    except URLError as exc:
        raise CheckFailure(f"request failed: {exc}") from exc


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def check_static(base_url: str, opener) -> dict:
    results = {}
    for path in ("/login.html", "/app.js", "/styles.css"):
        status, text, _ = request(opener, "GET", base_url + path)
        require(status == 200, f"{path} no responde 200")
        results[path] = {"status": status, "bytes": len(text)}
        if path == "/login.html":
            require("Seleccioná usuario" in text, "login no inicia con seleccion manual de usuario")
        if path in {"/app.js", "/styles.css"}:
            for marker in MUST_HAVE_STATIC_MARKERS:
                if marker in {"Seleccioná usuario"}:
                    continue
                if marker in text:
                    results.setdefault("markers", {})[marker] = True
    for marker in [item for item in MUST_HAVE_STATIC_MARKERS if item != "Seleccioná usuario"]:
        require(results.get("markers", {}).get(marker), f"falta marker static: {marker}")
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=os.environ.get("BITORA_ONLINE_BASE_URL", "https://bitora-staging.onrender.com").rstrip("/"))
    parser.add_argument("--user", default=os.environ.get("BITORA_ONLINE_TEST_USER", ""))
    parser.add_argument("--pin", default=os.environ.get("BITORA_ONLINE_TEST_PIN", ""))
    args = parser.parse_args()

    opener = build_opener(HTTPCookieProcessor(CookieJar()))
    report: dict = {"base_url": args.base_url, "checks": {}}

    status, _, health = request(opener, "GET", args.base_url + "/health")
    require(status == 200 and health, "health no responde JSON 200")
    require(health.get("status") == "ok", "health status no es ok")
    require(health.get("env") == "staging", "health env no es staging")
    require(health.get("db") == "online", "health no confirma PostgreSQL online")
    report["checks"]["health"] = "PASSED"

    status, _, ready = request(opener, "GET", args.base_url + "/ready")
    require(status == 200 and ready, "ready no responde JSON 200")
    require(ready.get("status") == "ready", "ready status no es ready")
    checks = ready.get("checks") or {}
    require(checks.get("safe_mode") is True, "safe mode no esta activo")
    require(checks.get("live_mode_off") is True, "live mode no esta desactivado")
    require(checks.get("database") is True, "database no esta ready")
    report["checks"]["ready"] = "PASSED"

    report["checks"]["static"] = check_static(args.base_url, opener)

    if args.user and args.pin:
        status, _, login = request(opener, "POST", args.base_url + "/api/auth/login", {"name": args.user, "pin": args.pin})
        require(status == 200 and login and login.get("ok"), "login de usuario online fallo")
        require((login.get("user") or {}).get("role") == "Productor", "usuario online no es Productor")
        report["checks"]["producer_login"] = "PASSED"
    else:
        report["checks"]["producer_login"] = "OMITTED_NO_CREDENTIALS"

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CheckFailure as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1)
