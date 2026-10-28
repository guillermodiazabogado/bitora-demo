"""Destructive-only-to-itself Docker harness for BITORA multi-instance checks.

It creates uniquely named Docker resources, never mounts repository data, and
removes every container/network it created on exit.  The resulting JSON report
contains no database or application credentials.
"""

from __future__ import annotations

import argparse
from collections import deque
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
TELEMETRY_SCHEMA = "bitora.operational.telemetry.v1"


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


def atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _number(value: str) -> float | None:
    try:
        return float(value.strip().rstrip("%"))
    except (AttributeError, TypeError, ValueError):
        return None


def container_metrics(names: tuple[str, ...]) -> dict:
    """Return sanitised Docker counters; never container environment/config."""
    result: dict[str, dict] = {}
    for name in names:
        stats = docker("stats", "--no-stream", "--format", "{{json .}}", name, check=False, timeout=15)
        inspect = docker(
            "inspect", "--format",
            "{{.State.Status}}|{{.State.OOMKilled}}|{{.RestartCount}}|{{.State.Pid}}",
            name, check=False, timeout=15,
        )
        item: dict = {"available": False}
        if stats.returncode == 0:
            try:
                raw = json.loads(stats.stdout.strip().splitlines()[-1])
                item.update({
                    "available": True,
                    "cpu_percent": _number(raw.get("CPUPerc", "")),
                    "memory_usage": raw.get("MemUsage"),
                    "memory_percent": _number(raw.get("MemPerc", "")),
                    "pids": int(raw["PIDs"]) if str(raw.get("PIDs", "")).isdigit() else None,
                    "network_io": raw.get("NetIO"),
                    "block_io": raw.get("BlockIO"),
                })
            except (IndexError, json.JSONDecodeError, ValueError):
                item["error"] = "DOCKER_STATS_PARSE_FAILED"
        if inspect.returncode == 0:
            fields = inspect.stdout.strip().split("|")
            if len(fields) == 4:
                item.update({
                    "state": fields[0],
                    "oom_killed": fields[1].lower() == "true",
                    "restart_count": int(fields[2]) if fields[2].isdigit() else None,
                    "pid_present": fields[3].isdigit() and int(fields[3]) > 0,
                })
        result[name.rsplit("-", 1)[-1]] = item
    return result


def postgres_metrics(container: str) -> dict:
    """Collect one aggregate row. No query text, credentials or row data leave PostgreSQL."""
    sql = """
SELECT pg_database_size(current_database()),
       current_setting('max_connections')::int,
       (SELECT count(*) FROM pg_stat_activity WHERE datname=current_database()),
       (SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND state='active'),
       (SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND wait_event IS NOT NULL),
       (SELECT count(*) FROM pg_locks WHERE NOT granted),
       xact_commit,xact_rollback,deadlocks,temp_bytes
FROM pg_stat_database WHERE datname=current_database();
"""
    output = docker(
        "exec", container, "psql", "-U", "bitora", "-d", "bitora",
        "-At", "-F", "|", "-c", sql, check=False, timeout=15,
    )
    if output.returncode != 0:
        return {"available": False, "error": "POSTGRES_METRICS_UNAVAILABLE"}
    fields = output.stdout.strip().splitlines()[-1].split("|")
    if len(fields) != 10:
        return {"available": False, "error": "POSTGRES_METRICS_PARSE_FAILED"}
    keys = (
        "database_size_bytes", "max_connections", "connections_total", "connections_active",
        "sessions_waiting", "locks_waiting", "xact_commit", "xact_rollback", "deadlocks", "temp_bytes",
    )
    try:
        return {"available": True, **{key: int(value) for key, value in zip(keys, fields)}}
    except ValueError:
        return {"available": False, "error": "POSTGRES_METRICS_PARSE_FAILED"}


def readiness_metrics(bases: tuple[str, ...]) -> list[dict]:
    values = []
    for base in bases:
        started = time.perf_counter()
        status, payload = Client().request(base, "/ready", expected={0, 200, 503}, timeout=3)
        values.append({
            "status": status,
            "latency_ms": round((time.perf_counter() - started) * 1000, 3),
            "database_ready": payload.get("checks", {}).get("database"),
        })
    return values


def telemetry_summary(samples: list[dict]) -> dict:
    def series(path: tuple[str, ...]) -> list[float]:
        values = []
        for sample in samples:
            current = sample
            for key in path:
                current = current.get(key) if isinstance(current, dict) else None
            if isinstance(current, (int, float)) and not isinstance(current, bool):
                values.append(float(current))
        return values

    def trend(values: list[float]) -> dict:
        if not values:
            return {"samples": 0, "first": None, "last": None, "maximum": None, "change_percent": None}
        change = None if values[0] == 0 else round((values[-1] - values[0]) * 100 / values[0], 3)
        return {"samples": len(values), "first": values[0], "last": values[-1], "maximum": max(values), "change_percent": change}

    ready = [probe for sample in samples for probe in sample.get("readiness", [])]
    return {
        "samples": len(samples),
        "readiness_200": sum(probe.get("status") == 200 for probe in ready),
        "readiness_total": len(ready),
        "readiness_latency_ms": trend([float(probe["latency_ms"]) for probe in ready if isinstance(probe.get("latency_ms"), (int, float))]),
        "postgres_connections": trend(series(("postgres", "connections_total"))),
        "postgres_locks_waiting": trend(series(("postgres", "locks_waiting"))),
        "postgres_database_size_bytes": trend(series(("postgres", "database_size_bytes"))),
        "app_a_cpu_percent": trend(series(("containers", "a", "cpu_percent"))),
        "app_b_cpu_percent": trend(series(("containers", "b", "cpu_percent"))),
        "postgres_cpu_percent": trend(series(("containers", "postgres", "cpu_percent"))),
        "oom_or_restart_observed": any(
            item.get("oom_killed") or (item.get("restart_count") or 0) > 0
            for sample in samples for item in sample.get("containers", {}).values()
        ),
    }


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

    def request(self, base: str, path: str, payload: dict | None = None, *, expected: set[int] | None = None, timeout: float = 20) -> tuple[int, dict]:
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
            with self.opener.open(request, timeout=timeout) as response:
                status, raw = response.status, response.read()
        except urllib.error.HTTPError as exc:
            status, raw = exc.code, exc.read()
        except (TimeoutError, urllib.error.URLError) as exc:
            status, raw = 0, json.dumps({"error": type(exc).__name__}).encode("utf-8")
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


def wait_not_ready(base: str, deadline_seconds: int = 30) -> dict:
    client = Client()
    deadline = time.monotonic() + deadline_seconds
    last: dict = {}
    while time.monotonic() < deadline:
        status, payload = client.request(base, "/ready", expected={0, 200, 503}, timeout=5)
        last = {"status": status, "payload": payload}
        if status == 0 or (status == 503 and payload.get("checks", {}).get("database") is False):
            return last
        time.sleep(0.5)
    raise HarnessError(f"DATABASE_DEGRADATION_NOT_OBSERVED:{last}")


def main() -> int:
    parser = argparse.ArgumentParser(description="BITORA PostgreSQL multi-instance operational harness")
    parser.add_argument("--report", type=Path, default=ROOT / "artifacts" / "operational-multiinstance.json")
    parser.add_argument("--endurance-seconds", type=int, default=10, help="Sustained HTTP ENTRY/EXIT duration")
    parser.add_argument("--checkpoint", type=Path, help="Atomic progress evidence for persistent runners")
    parser.add_argument("--sample-seconds", type=float, default=30, help="Telemetry interval")
    parser.add_argument("--keep", action="store_true", help="Keep isolated Docker resources for debugging")
    args = parser.parse_args()
    if args.sample_seconds <= 0:
        parser.error("--sample-seconds must be positive")
    run_id = uuid.uuid4().hex[:10]
    prefix = f"bitora-op-{run_id}"
    network = prefix
    postgres = f"{prefix}-postgres"
    app_a = f"{prefix}-app-a"
    app_b = f"{prefix}-app-b"
    image = f"{prefix}:test"
    dsn = "postgresql://bitora:operational-temporary@postgres:5432/bitora?connect_timeout=1"
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
        "-e", "DB_CONNECTION_TIMEOUT=1",
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
        base_a = mapped_url(app_a)
        try:
            wait_ready(base_a)
        except HarnessError as exc:
            state = docker(
                "inspect", "--format",
                "{{.State.Status}}|{{.State.ExitCode}}|{{.State.OOMKilled}}|{{.RestartCount}}",
                app_a, check=False,
            ).stdout.strip()
            logs = docker("logs", "--tail", "40", app_a, check=False).stderr[-2000:]
            raise HarnessError(f"{exc}:STATE={state}:LOGS={logs}") from exc
        status, me = continuity.request(base_a, "/api/auth/me", expected={200})
        report["checks"]["restart_preserves_shared_session"] = status == 200 and me.get("user", {}).get("name") == "Admin"

        operator = Client()
        operator.login(base_a, "multi-access", "Operational-Access-582!")
        status, events = operator.request(base_b, "/api/events", expected={200})
        if not isinstance(events, list):
            raise HarnessError(f"EVENTS_CONTRACT:{type(events).__name__}")
        visible = {int(item["id"]) for item in events}
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

        docker("restart", postgres, timeout=90)
        wait_postgres(postgres)
        wait_ready(base_a)
        wait_ready(base_b)
        status, me = continuity.request(base_a, "/api/auth/me", expected={200})
        report["checks"]["postgres_restart_recovers"] = (
            status == 200 and me.get("authenticated") is True
        )

        docker("network", "disconnect", network, postgres)
        degraded_a = wait_not_ready(base_a)
        degraded_b = wait_not_ready(base_b)
        docker("network", "connect", "--alias", "postgres", network, postgres)
        wait_postgres(postgres)
        wait_ready(base_a)
        wait_ready(base_b)
        status, me = continuity.request(base_b, "/api/auth/me", expected={200})
        report["checks"]["database_disconnect_observable"] = all(
            item["status"] in {0, 503} for item in (degraded_a, degraded_b)
        )
        report["checks"]["database_reconnect_recovers"] = (
            status == 200 and me.get("authenticated") is True
        )
        report["observed_failures"] = {
            "database_disconnect": {
                "app_a_ready_status": degraded_a["status"],
                "app_b_ready_status": degraded_b["status"],
            }
        }
        if 0 in {degraded_a["status"], degraded_b["status"]}:
            report["limitations"].append(
                "During a total database network cut, readiness was externally observable as a bounded timeout rather than an HTTP 503."
            )

        endurance_started = time.monotonic()
        endurance_latencies: list[float] = []
        endurance_attempted = 0
        endurance_succeeded = 0
        endurance_failures: deque[dict] = deque(maxlen=20)
        endurance_failures_total = 0
        telemetry_samples: list[dict] = []
        next_sample = endurance_started
        direction = "EXIT"
        while time.monotonic() - endurance_started < max(3, args.endurance_seconds):
            now = time.monotonic()
            if now >= next_sample:
                sample = {
                    "schema": TELEMETRY_SCHEMA,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "elapsed_seconds": round(now - endurance_started, 3),
                    "containers": container_metrics((app_a, app_b, postgres)),
                    "postgres": postgres_metrics(postgres),
                    "readiness": readiness_metrics((base_a, base_b)),
                    "operations_attempted": endurance_attempted,
                    "operations_succeeded": endurance_succeeded,
                    "failures_total": endurance_failures_total,
                }
                telemetry_samples.append(sample)
                if args.checkpoint:
                    atomic_json(args.checkpoint, {
                        "status": "running",
                        "schema": TELEMETRY_SCHEMA,
                        "run_id": run_id,
                        "requested_seconds": max(3, args.endurance_seconds),
                        "last_sample": sample,
                        "samples_collected": len(telemetry_samples),
                    })
                next_sample = now + args.sample_seconds
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
                    endurance_failures_total += 1
            except Exception as exc:
                endurance_failures.append({"index": index, "error": type(exc).__name__})
                endurance_failures_total += 1
            endurance_latencies.append((time.perf_counter() - started) * 1000)
            endurance_attempted += 1
        ordered = sorted(endurance_latencies)
        percentile = lambda fraction: round(ordered[min(len(ordered) - 1, int((len(ordered) - 1) * fraction))], 3)
        report["endurance"] = {
            "requested_seconds": max(3, args.endurance_seconds),
            "elapsed_seconds": round(time.monotonic() - endurance_started, 3),
            "attempted": endurance_attempted,
            "succeeded": endurance_succeeded,
            "failures_total": endurance_failures_total,
            "recent_failures": list(endurance_failures),
            "latency_ms": {
                "p50": percentile(0.50), "p95": percentile(0.95), "p99": percentile(0.99),
                "mean": round(statistics.fmean(endurance_latencies), 3),
            },
        }
        report["checks"]["integrated_http_postgres_endurance"] = (
            endurance_attempted > 0 and endurance_succeeded == endurance_attempted and endurance_failures_total == 0
        )
        report["telemetry"] = {
            "schema": TELEMETRY_SCHEMA,
            "sample_interval_seconds": args.sample_seconds,
            "samples": telemetry_samples,
            "summary": telemetry_summary(telemetry_samples),
        }

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
        if args.checkpoint:
            atomic_json(args.checkpoint, {
                "status": "complete" if report["ok"] else "failed",
                "schema": TELEMETRY_SCHEMA,
                "run_id": run_id,
                "endurance": report["endurance"],
                "telemetry_summary": report["telemetry"]["summary"],
                "checks": report["checks"],
            })
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
        if args.checkpoint and not report.get("ok"):
            atomic_json(args.checkpoint, {
                "status": "failed", "schema": TELEMETRY_SCHEMA, "run_id": run_id,
                "error": report.get("error", "HARNESS_CHECK_FAILED"),
            })
        print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
