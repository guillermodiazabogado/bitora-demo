"""Destructive-only-to-itself Docker harness for BITORA multi-instance checks.

It creates uniquely named Docker resources, never mounts repository data, and
removes every container/network it created on exit.  The resulting JSON report
contains no database or application credentials.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import http.cookiejar
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid


ROOT = Path(__file__).resolve().parents[1]
RESULT_PREFIX = "BITORA_OPERATIONAL_RESULT="


class HarnessError(RuntimeError):
    pass


def run(command: list[str], *, check: bool = True, timeout: int = 600) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=timeout)
    if check and result.returncode:
        safe = (result.stderr or result.stdout)[-3000:]
        raise HarnessError(f"COMMAND_FAILED:{command[0]}:{result.returncode}:{safe}")
    return result


def docker(*args: str, check: bool = True, timeout: int = 600) -> subprocess.CompletedProcess[str]:
    return run(["docker", *args], check=check, timeout=timeout)


def parse_fixture(output: str) -> dict:
    for line in reversed(output.splitlines()):
        if line.startswith(RESULT_PREFIX):
            return json.loads(line[len(RESULT_PREFIX) :])
    raise HarnessError("FIXTURE_RESULT_MISSING")


class Client:
    def __init__(self) -> None:
        self.cookies = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookies))
        self.csrf = ""

    def request(self, base: str, path: str, payload: dict | None = None, *, expected: set[int] | None = None) -> tuple[int, dict]:
        headers = {"Accept": "application/json"}
        body = None
        method = "GET"
        if payload is not None:
            method = "POST"
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
            if self.csrf:
                headers["X-CSRF-Token"] = self.csrf
        request = urllib.request.Request(base + path, body, headers, method=method)
        try:
            with self.opener.open(request, timeout=20) as response:
                status, raw = response.status, response.read()
        except urllib.error.HTTPError as exc:
            status, raw = exc.code, exc.read()
        try:
            decoded = json.loads(raw.decode("utf-8")) if raw else {}
        except json.JSONDecodeError:
            decoded = {"raw": raw.decode("utf-8", errors="replace")[:500]}
        if expected is not None and status not in expected:
            raise HarnessError(f"HTTP_STATUS:{path}:{status}:{decoded}")
        return status, decoded

    def login(self, base: str, name: str, pin: str) -> dict:
        status, result = self.request(base, "/api/auth/login", {"name": name, "pin": pin}, expected={200})
        self.csrf = str(result.get("csrf_token") or "")
        if status != 200 or not self.csrf:
            raise HarnessError("LOGIN_WITHOUT_CSRF")
        return result


def wait_postgres(container: str, deadline_seconds: int = 90) -> None:
    deadline = time.monotonic() + deadline_seconds
    while time.monotonic() < deadline:
        if docker("exec", container, "pg_isready", "-U", "bitora", "-d", "bitora", check=False, timeout=10).returncode == 0:
            return
        time.sleep(1)
    raise HarnessError("POSTGRES_NOT_READY")


def mapped_url(container: str) -> str:
    result = docker("port", container, "8787/tcp")
    address = result.stdout.strip().splitlines()[0]
    port = address.rsplit(":", 1)[1]
    return f"http://127.0.0.1:{port}"


def wait_ready(base: str, deadline_seconds: int = 90) -> None:
    deadline = time.monotonic() + deadline_seconds
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(base + "/ready", timeout=4) as response:
                if response.status == 200:
                    return
        except Exception:
            pass
        time.sleep(1)
    raise HarnessError(f"APP_NOT_READY:{base}")


def main() -> int:
    parser = argparse.ArgumentParser(description="BITORA PostgreSQL multi-instance operational harness")
    parser.add_argument("--report", type=Path, default=ROOT / "artifacts" / "operational-multiinstance.json")
    parser.add_argument("--endurance-seconds", type=int, default=10, help="Sustained HTTP ENTRY/EXIT duration")
    parser.add_argument("--keep", action="store_true", help="Keep isolated Docker resources for debugging")
    args = parser.parse_args()
    run_id = uuid.uuid4().hex[:10]
    prefix = f"bitora-op-{run_id}"
    network = prefix
    postgres = f"{prefix}-postgres"
    app_a = f"{prefix}-app-a"
    app_b = f"{prefix}-app-b"
    image = f"{prefix}:test"
    dsn = "postgresql://bitora:operational-temporary@postgres:5432/bitora"
    env = [
        "-e", "APP_ENV=development",
        "-e", "BITORA_ENV=development",
        "-e", "BITORA_SAFE_MODE=true",
        "-e", "BITORA_LIVE_MODE=false",
        "-e", "QR_DB_ENGINE=postgres",
        "-e", f"QR_POSTGRES_DSN={dsn}",
        "-e", f"DATABASE_URL={dsn}",
        "-e", "QR_REQUIRE_LOGIN=true",
        "-e", "QR_HOST=0.0.0.0",
        "-e", "QR_PORT=8787",
        "-e", "BITORA_DISABLE_EMBEDDED_WORKER=1",
        "-e", "QR_AUTO_BACKUP_MINUTES=0",
    ]
    report: dict = {
        "ok": False,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "checks": {},
        "limitations": ["Docker loopback networking is simulated infrastructure, not an event venue network."],
    }
    resources_created = False
    try:
        if docker("info", check=False, timeout=30).returncode != 0:
            raise HarnessError("DOCKER_DAEMON_UNAVAILABLE")
        docker("network", "create", network)
        resources_created = True
        docker(
            "run", "-d", "--name", postgres, "--network", network, "--network-alias", "postgres",
            "-e", "POSTGRES_DB=bitora", "-e", "POSTGRES_USER=bitora",
            "-e", "POSTGRES_PASSWORD=operational-temporary", "postgres:16-alpine",
        )
        wait_postgres(postgres)
        docker("build", "-t", image, ".", timeout=1200)
        fixture = docker(
            "run", "--rm", "--network", network, *env, image,
            "python", "scripts/operational_multiinstance_fixture.py", "setup", timeout=300,
        )
        setup = parse_fixture(fixture.stdout)

        for name in (app_a, app_b):
            docker(
                "run", "-d", "--name", name, "--network", network, "-p", "127.0.0.1::8787",
                *env, image,
            )
        base_a, base_b = mapped_url(app_a), mapped_url(app_b)
        wait_ready(base_a)
        wait_ready(base_b)
        report["checks"]["two_distinct_instances_ready"] = base_a != base_b

        admin = Client()
        admin.login(base_a, "Admin", "Operational-Admin-582!")
        status, me = admin.request(base_b, "/api/auth/me", expected={200})
        report["checks"]["session_cross_instance"] = status == 200 and me.get("user", {}).get("name") == "Admin"

        docker(
            "run", "--rm", "--network", network, *env, image,
            "python", "scripts/operational_multiinstance_fixture.py", "set-admin-role", "Visualizador",
        )
        status, revoked_me = admin.request(base_b, "/api/auth/me", expected={200})
        report["checks"]["role_change_invalidates_session"] = (
            status == 200 and revoked_me.get("authenticated") is False
        )
        docker(
            "run", "--rm", "--network", network, *env, image,
            "python", "scripts/operational_multiinstance_fixture.py", "set-admin-role", "Super Admin",
        )

        admin = Client()
        admin.login(base_a, "Admin", "Operational-Admin-582!")
        admin.request(base_b, "/api/auth/logout", {}, expected={200})
        status, logged_out_me = admin.request(base_a, "/api/auth/me", expected={200})
        report["checks"]["logout_cross_instance_revokes"] = (
            status == 200 and logged_out_me.get("authenticated") is False
        )

        continuity = Client()
        continuity.login(base_b, "Admin", "Operational-Admin-582!")
        docker("restart", app_a, timeout=90)
        wait_ready(base_a)
        status, me = continuity.request(base_a, "/api/auth/me", expected={200})
        report["checks"]["restart_preserves_shared_session"] = status == 200 and me.get("user", {}).get("name") == "Admin"

        operator = Client()
        operator.login(base_a, "multi-access", "Operational-Access-582!")
        status, events = operator.request(base_b, "/api/events", expected={200})
        visible = {int(item["id"]) for item in events.get("items", [])}
        isolation_status, _ = operator.request(
            base_b, f"/api/events/{setup['isolated_event_id']}/command-center-v5", expected={403}
        )
        report["checks"]["multievent_isolation"] = (
            status == 200 and int(setup["event_id"]) in visible
            and int(setup["isolated_event_id"]) not in visible and isolation_status == 403
        )

        access = Client()
        access.login(base_a, "Admin", "Operational-Admin-582!")
        bases = [base_a, base_b]

        def entry(index: int) -> dict:
            _, payload = access.request(
                bases[index % 2],
                "/api/validate",
                {
                    "token": setup["access_token"], "operator": "Admin", "checkpoint": "Multi Gate",
                    "direction": "ENTRY", "correlation_id": f"multi-{index}",
                    "idempotency_key": f"multi-entry-{index}",
                },
                expected={200},
            )
            return payload

        with ThreadPoolExecutor(max_workers=30) as pool:
            results = list(pool.map(entry, range(30)))
        allowed = [item for item in results if item.get("result") == "granted"]
        denied = [item for item in results if item.get("reason_code") == "ANTI_PASSBACK"]
        report["checks"]["concurrent_entry_anti_passback"] = len(allowed) == 1 and len(denied) == 29
        replay_index = results.index(allowed[0]) if allowed else 0
        _, replay = access.request(
            bases[(replay_index + 1) % 2], "/api/validate",
            {
                "token": setup["access_token"], "operator": "Admin", "checkpoint": "Multi Gate",
                "direction": "ENTRY", "correlation_id": f"multi-{replay_index}",
                "idempotency_key": f"multi-entry-{replay_index}",
            }, expected={200},
        )
        report["checks"]["cross_instance_idempotent_replay"] = bool(replay.get("idempotent_replay"))

        endurance_started = time.monotonic()
        endurance_latencies: list[float] = []
        endurance_attempted = 0
        endurance_succeeded = 0
        endurance_failures: list[dict] = []
        direction = "EXIT"
        while time.monotonic() - endurance_started < max(3, args.endurance_seconds):
            index = endurance_attempted
            started = time.perf_counter()
            try:
                _, payload = access.request(
                    bases[index % 2], "/api/validate",
                    {
                        "token": setup["access_token"], "operator": "Admin", "checkpoint": "Endurance Gate",
                        "direction": direction, "correlation_id": f"endurance-{index}",
                        "idempotency_key": f"endurance-{index}",
                    }, expected={200},
                )
                if payload.get("result") == "granted":
                    endurance_succeeded += 1
                    direction = "ENTRY" if direction == "EXIT" else "EXIT"
                else:
                    endurance_failures.append({"index": index, "reason_code": payload.get("reason_code")})
            except Exception as exc:
                endurance_failures.append({"index": index, "error": type(exc).__name__})
            endurance_latencies.append((time.perf_counter() - started) * 1000)
            endurance_attempted += 1
        ordered = sorted(endurance_latencies)
        percentile = lambda fraction: round(ordered[min(len(ordered) - 1, int((len(ordered) - 1) * fraction))], 3)
        report["endurance"] = {
            "requested_seconds": max(3, args.endurance_seconds),
            "elapsed_seconds": round(time.monotonic() - endurance_started, 3),
            "attempted": endurance_attempted,
            "succeeded": endurance_succeeded,
            "failures": endurance_failures[:20],
            "latency_ms": {
                "p50": percentile(0.50), "p95": percentile(0.95), "p99": percentile(0.99),
                "mean": round(statistics.fmean(endurance_latencies), 3),
            },
        }
        report["checks"]["integrated_http_postgres_endurance"] = (
            endurance_attempted > 0 and endurance_succeeded == endurance_attempted and not endurance_failures
        )

        inspection_result = docker(
            "run", "--rm", "--network", network, *env, image,
            "python", "scripts/operational_multiinstance_fixture.py", "inspect", str(setup["event_id"]),
        )
        inspection = parse_fixture(inspection_result.stdout)
        report["observed"] = {
            "instances": 2,
            "entry_attempts": 30,
            "entry_allowed": len(allowed),
            "entry_anti_passback": len(denied),
            **inspection,
        }
        event_total = sum(int(item["count"]) for item in inspection["access_events"])
        report["checks"]["idempotency_preserved_event_count"] = event_total == 30 + endurance_succeeded
        expected_state = "INSIDE" if direction == "EXIT" else "OUTSIDE"
        report["checks"]["database_state_consistent"] = inspection["snapshots"] == [{"count": 1, "current_state": expected_state}]
        report["ok"] = all(report["checks"].values())
    except Exception as exc:
        report["error"] = str(exc)
    finally:
        if resources_created and not args.keep:
            for name in (app_a, app_b, postgres):
                docker("rm", "-f", name, check=False, timeout=60)
            docker("network", "rm", network, check=False, timeout=60)
            docker("image", "rm", image, check=False, timeout=120)
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        report["resources_removed"] = bool(resources_created and not args.keep)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
