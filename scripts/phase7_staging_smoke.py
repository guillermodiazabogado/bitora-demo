#!/usr/bin/env python3
"""Deterministic local Phase 7 smoke test through the TLS reverse proxy."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import http.cookiejar
import json
import os
from pathlib import Path
import socket
import ssl
import subprocess
import tempfile
import time
import urllib.error
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
RESULT_PREFIX = "BITORA_OPERATIONAL_RESULT="


class SmokeError(RuntimeError):
    pass


def atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def run(command: list[str], *, timeout: int = 300, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=timeout)
    if check and result.returncode != 0:
        tail = (result.stderr or result.stdout)[-1200:].replace("\n", " | ")
        raise SmokeError(f"COMMAND_FAILED:{command[0]}:{result.returncode}:{tail}")
    return result


def fixture(compose: list[str], *arguments: str) -> dict:
    result = run([*compose, "exec", "-T", "app-1", "python", "scripts/operational_multiinstance_fixture.py", *arguments])
    for line in reversed(result.stdout.splitlines()):
        if line.startswith(RESULT_PREFIX):
            return json.loads(line[len(RESULT_PREFIX) :])
    raise SmokeError("FIXTURE_RESULT_MISSING")


class Client:
    def __init__(self) -> None:
        self.cookies = http.cookiejar.CookieJar()
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookies),
            urllib.request.HTTPSHandler(context=context),
        )
        self.csrf = ""
        self.last_headers: dict[str, str] = {}

    def request(
        self,
        base: str,
        path: str,
        payload: dict | None = None,
        *,
        expected: set[int] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 30,
    ) -> tuple[int, dict]:
        request_headers = {"Accept": "application/json", "Host": "bitora.localhost", **(headers or {})}
        body = None
        method = "GET"
        if payload is not None:
            method = "POST"
            body = json.dumps(payload).encode("utf-8")
            request_headers["Content-Type"] = "application/json"
            if self.csrf:
                request_headers["X-CSRF-Token"] = self.csrf
        request = urllib.request.Request(base + path, body, request_headers, method=method)
        raw = b""
        try:
            with self.opener.open(request, timeout=timeout) as response:
                status = response.status
                raw = response.read()
                self.last_headers = {key.lower(): value for key, value in response.headers.items()}
                set_cookie = response.headers.get_all("Set-Cookie") or []
                if set_cookie:
                    self.last_headers["set-cookie-all"] = "\n".join(set_cookie)
        except urllib.error.HTTPError as exc:
            status = exc.code
            raw = exc.read()
            self.last_headers = {key.lower(): value for key, value in exc.headers.items()}
        except (TimeoutError, urllib.error.URLError) as exc:
            raise SmokeError(f"HTTP_UNAVAILABLE:{path}:{type(exc).__name__}") from exc
        try:
            decoded = json.loads(raw.decode("utf-8")) if raw else {}
        except json.JSONDecodeError:
            decoded = {"raw": raw.decode("utf-8", errors="replace")[:300]}
        if expected is not None and status not in expected:
            raise SmokeError(f"HTTP_STATUS:{path}:{status}:{decoded}")
        return status, decoded

    def login(self, base: str, name: str, password: str) -> dict:
        _, result = self.request(base, "/api/auth/login", {"name": name, "pin": password}, expected={200})
        self.csrf = str(result.get("csrf_token") or "")
        if not self.csrf:
            raise SmokeError("LOGIN_WITHOUT_CSRF")
        return result


def wait_ready(base: str, seconds: int = 120) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            status, _ = Client().request(base, "/ready", expected={200}, timeout=5)
            if status == 200:
                return
        except SmokeError:
            pass
        time.sleep(1)
    raise SmokeError("PROXY_NOT_READY")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--compose-file", type=Path, required=True)
    parser.add_argument("--base-url", default="https://127.0.0.1:9443")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    compose_file = args.compose_file.resolve()
    compose = ["docker", "compose", "-f", str(compose_file)]
    report: dict = {"ok": False, "checks": {}, "base_url": args.base_url, "limitations": []}
    try:
        wait_ready(args.base_url)
        client = Client()
        for endpoint in ("/health", "/ready"):
            status, _ = client.request(args.base_url, endpoint, expected={200})
            report["checks"][endpoint] = status == 200
        headers = client.last_headers
        report["checks"]["security_headers"] = (
            "strict-transport-security" in headers
            and headers.get("x-content-type-options", "").lower() == "nosniff"
        )
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        with socket.create_connection(("127.0.0.1", int(args.base_url.rsplit(":", 1)[1])), timeout=10) as raw:
            with context.wrap_socket(raw, server_hostname="bitora.localhost") as wrapped:
                report["tls_version"] = wrapped.version()
        report["checks"]["tls_1_2_or_newer"] = report["tls_version"] in {"TLSv1.2", "TLSv1.3"}

        setup = fixture(compose, "setup")
        report["synthetic_event_id"] = int(setup["event_id"])
        bootstrap = Client()
        bootstrap.login(
            args.base_url,
            os.environ["BITORA_ADMIN_BOOTSTRAP_USER"],
            os.environ["BITORA_ADMIN_BOOTSTRAP_PASSWORD"],
        )
        _, bootstrap_me = bootstrap.request(args.base_url, "/api/auth/me", expected={200})
        report["checks"]["bootstrap_authentication"] = bootstrap_me.get("authenticated") is True
        admin = Client()
        admin.login(args.base_url, "Admin", "Operational-Admin-582!")
        cookie_headers = admin.last_headers.get("set-cookie-all", "").lower()
        report["checks"]["secure_session_cookie"] = all(
            marker in cookie_headers for marker in ("secure", "httponly", "samesite=lax")
        )
        _, me = admin.request(args.base_url, "/api/auth/me", expected={200})
        report["checks"]["authentication"] = me.get("authenticated") is True

        registration_key = "phase7-registration-smoke-0001"
        registration = {
            "event_id": int(setup["event_id"]),
            "first_name": "Phase7",
            "last_name": "Smoke",
            "email": "phase7-smoke@bitora.test",
            "type": "General",
            "actor": "phase7-smoke",
            "source": "staging-local",
            "device_type": "desktop",
        }
        first_status, first = Client().request(
            args.base_url, "/api/register", registration, expected={200, 201},
            headers={"Idempotency-Key": registration_key},
        )
        second_status, second = Client().request(
            args.base_url, "/api/register", registration, expected={200, 201},
            headers={"Idempotency-Key": registration_key},
        )
        report["checks"]["registration_idempotency"] = (
            sorted((first_status, second_status)) == [200, 201]
            and first.get("token") == second.get("token")
            and bool(second.get("idempotent_replay"))
        )

        operator = Client()
        operator.login(args.base_url, "multi-access", "Operational-Access-582!")
        _, events = operator.request(args.base_url, "/api/events", expected={200})
        forbidden, _ = operator.request(
            args.base_url, f"/api/events/{setup['isolated_event_id']}/command-center-v5", expected={403}
        )
        visible = {int(item["id"]) for item in events}
        report["checks"]["event_isolation"] = (
            int(setup["event_id"]) in visible
            and int(setup["isolated_event_id"]) not in visible
            and forbidden == 403
        )

        def validate(index: int) -> dict:
            access = Client()
            access.login(args.base_url, "Admin", "Operational-Admin-582!")
            _, payload = access.request(
                args.base_url,
                "/api/validate",
                {
                    "token": setup["access_token"],
                    "operator": "Admin",
                    "checkpoint": "Phase7 Gate",
                    "direction": "ENTRY",
                    "correlation_id": f"phase7-concurrent-{index}",
                    "idempotency_key": f"phase7-entry-{index}",
                },
                expected={200},
            )
            return payload

        with ThreadPoolExecutor(max_workers=2) as pool:
            decisions = list(pool.map(validate, range(2)))
        granted = [item for item in decisions if item.get("result") == "granted"]
        rejected = [item for item in decisions if item.get("reason_code") == "ANTI_PASSBACK"]
        report["checks"]["concurrent_anti_passback"] = len(granted) == 1 and len(rejected) == 1

        fixture(compose, "revoke-fixture-credential", str(setup["event_id"]))
        revocation_client = Client()
        revocation_client.login(args.base_url, "Admin", "Operational-Admin-582!")
        _, revoked = revocation_client.request(
            args.base_url,
            "/api/validate",
            {
                "token": setup["access_token"], "operator": "Admin", "checkpoint": "Phase7 Gate",
                "direction": "EXIT", "correlation_id": "phase7-revoked",
                "idempotency_key": "phase7-revoked",
            },
            expected={200},
        )
        report["checks"]["credential_revocation"] = revoked.get("reason_code") == "REVOKED"

        continuity = Client()
        continuity.login(args.base_url, "Admin", "Operational-Admin-582!")
        run([*compose, "stop", "app-1"], timeout=90)
        wait_ready(args.base_url, 60)
        _, after_stop = continuity.request(args.base_url, "/api/auth/me", expected={200})
        report["checks"]["single_instance_continuity"] = after_stop.get("authenticated") is True
        run([*compose, "up", "-d", "--no-build", "app-1"], timeout=180)
        deadline = time.monotonic() + 120
        app_healthy = False
        while time.monotonic() < deadline:
            status = run([*compose, "ps", "--status", "running", "-q", "app-1"], check=False).stdout.strip()
            if status:
                inspect = run(["docker", "inspect", "--format", "{{.State.Health.Status}}", status], check=False)
                if inspect.stdout.strip() == "healthy":
                    app_healthy = True
                    break
            time.sleep(2)
        report["checks"]["instance_recovery"] = app_healthy
        admin.request(args.base_url, "/api/auth/logout", {}, expected={200})
        _, logged_out = admin.request(args.base_url, "/api/auth/me", expected={200})
        report["checks"]["logout_revocation"] = logged_out.get("authenticated") is False

        inspection = fixture(compose, "inspect", str(setup["event_id"]))
        report["fixture_inspection"] = inspection
        report["checks"]["audit_persisted"] = bool(inspection.get("access_events"))
        report["ok"] = all(report["checks"].values())
        if not report["ok"]:
            raise SmokeError("SMOKE_CHECK_FAILED")
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}:{exc}"
    atomic_json(args.report.resolve(), report)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
