"""Isolated capacity benchmark for BITORA HTTP, PostgreSQL and access flows.

The harness builds the current checkout, creates uniquely named Docker
resources, and removes only those resources on exit.  It measures complete
public registrations (event -> register -> portal -> QR), authenticated access
validation, anti-passback, PostgreSQL and Docker telemetry.  It never targets a
remote service and never accepts a database DSN from the command line.

This is a laboratory benchmark.  Virtual clients are not physical readers and
the observed capacity must not be presented as production capacity.
"""

from __future__ import annotations

import argparse
from collections import Counter
import copy
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

from operational_multiinstance import (
    Client,
    HarnessError,
    container_metrics,
    docker,
    mapped_url,
    parse_fixture,
    postgres_metrics,
    wait_postgres,
    wait_ready,
)


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "bitora.capacity.benchmark.v1"
ADMIN_PASSWORD = "Operational-Admin-582!"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = min(len(ordered) - 1, max(0, math.ceil(len(ordered) * fraction) - 1))
    return round(ordered[position], 3)


def latency_summary(values: list[float]) -> dict:
    if not values:
        return {"samples": 0, "p50": None, "p95": None, "p99": None, "mean": None, "max": None}
    return {
        "samples": len(values),
        "p50": percentile(values, 0.50),
        "p95": percentile(values, 0.95),
        "p99": percentile(values, 0.99),
        "mean": round(statistics.fmean(values), 3),
        "max": round(max(values), 3),
    }


def atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def git_identity() -> tuple[str, bool]:
    # Windows-managed worktrees contain a Windows gitdir path that Linux Git in
    # WSL cannot resolve.  Prefer native Git, then the interoperable git.exe.
    for executable in ("git", "git.exe"):
        try:
            result = subprocess.run(
                [executable, "rev-parse", "HEAD"], cwd=ROOT, text=True,
                capture_output=True, timeout=15,
            )
        except FileNotFoundError:
            continue
        sha = result.stdout.strip()
        if result.returncode == 0 and len(sha) == 40 and all(char in "0123456789abcdef" for char in sha.lower()):
            status = subprocess.run(
                [executable, "status", "--porcelain"], cwd=ROOT, text=True,
                capture_output=True, timeout=15,
            )
            return sha, bool(status.stdout.strip()) if status.returncode == 0 else True
    raise HarnessError("GIT_SHA_UNAVAILABLE")


def clone_client(source: Client) -> Client:
    """Create a thread-confined HTTP client carrying the same session cookies."""
    target = Client()
    for cookie in source.cookies:
        target.cookies.set_cookie(copy.copy(cookie))
    target.csrf = source.csrf
    return target


def raw_get(base: str, path: str, *, timeout: float = 20) -> tuple[int, bytes, str]:
    request = urllib.request.Request(base + path, headers={"Accept": "*/*"}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read(), response.headers.get("Content-Type", "")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(), exc.headers.get("Content-Type", "")
    except (TimeoutError, urllib.error.URLError):
        return 0, b"", ""


def sql_scalar(container: str, sql: str) -> int:
    result = docker(
        "exec", container, "psql", "-U", "bitora", "-d", "bitora", "-At", "-c", sql,
        check=False, timeout=30,
    )
    if result.returncode:
        raise HarnessError("POSTGRES_INTEGRITY_QUERY_FAILED")
    try:
        return int(result.stdout.strip().splitlines()[-1])
    except (IndexError, ValueError) as exc:
        raise HarnessError("POSTGRES_INTEGRITY_RESULT_INVALID") from exc


def start_application(name: str, network: str, image: str, env: list[str]) -> str:
    docker(
        "run", "-d", "--name", name, "--network", network,
        "-p", "127.0.0.1::8787", *env, image,
    )
    base = mapped_url(name)
    wait_ready(base)
    return base


class SafeCounter:
    def __init__(self) -> None:
        self.value = 0
        self.peak = 0
        self.lock = threading.Lock()

    def next(self) -> int:
        with self.lock:
            self.value += 1
            self.peak = max(self.peak, self.value)
            return self.value

    def acquire(self, limit: int) -> bool:
        """Atomically reserve one bounded operation slot."""
        with self.lock:
            if limit and self.value >= limit:
                return False
            self.value += 1
            self.peak = max(self.peak, self.value)
            return True

    def decrement(self) -> None:
        with self.lock:
            self.value -= 1


def registration_flow(
    client: Client, base: str, event_id: int, run_id: str, cell_id: str, sequence: int,
) -> dict:
    email = f"capacity-{run_id}-{cell_id}-{sequence}@bitora.test"
    idempotency_key = f"registration-{run_id}-{cell_id}-{sequence}"
    started = time.perf_counter()
    steps: dict[str, float] = {}
    transport_timeouts = 0
    try:
        step = time.perf_counter()
        event_status, event = client.request(base, f"/api/event?event_id={event_id}", expected={200})
        steps["event_get_ms"] = (time.perf_counter() - step) * 1000
        if event_status != 200 or int(event.get("id") or 0) != event_id:
            raise HarnessError("PUBLIC_EVENT_CONTRACT")

        step = time.perf_counter()
        register_payload = {
            "event_id": event_id,
            "first_name": "Capacity",
            "last_name": f"User {sequence}",
            "email": email,
            "type": "General",
            "actor": "public",
            "source": "capacity-benchmark",
            "device_type": "desktop",
            "session_id": f"capacity-{run_id}-{cell_id}-{sequence}",
        }
        register_status, registered = 0, {}
        for _attempt in range(3):
            register_status, registered = client.request(
                base,
                "/api/register",
                register_payload,
                expected={0, 200, 201},
                headers={"Idempotency-Key": idempotency_key},
            )
            if register_status != 0:
                break
            transport_timeouts += 1
        steps["register_post_ms"] = (time.perf_counter() - step) * 1000
        token = str(registered.get("token") or "")
        if register_status not in {200, 201} or not registered.get("ok") or not token or registered.get("existing"):
            raise HarnessError("REGISTRATION_CONTRACT")

        step = time.perf_counter()
        portal_status, portal = client.request(
            base, "/api/portal?" + urllib.parse.urlencode({"token": token}), expected={200}
        )
        steps["portal_get_ms"] = (time.perf_counter() - step) * 1000
        if portal_status != 200 or portal.get("email") != email or str(portal.get("token") or "") != token:
            raise HarnessError("PORTAL_CONTRACT")

        step = time.perf_counter()
        qr_status, qr, content_type = raw_get(
            base, "/api/qr.svg?" + urllib.parse.urlencode({"token": token})
        )
        steps["qr_get_ms"] = (time.perf_counter() - step) * 1000
        if qr_status != 200 or b"<svg" not in qr.lower() or "image/svg+xml" not in content_type:
            raise HarnessError("QR_CONTRACT")
        return {
            "ok": True,
            "status": 200,
            "latency_ms": (time.perf_counter() - started) * 1000,
            "steps_ms": steps,
            "token": token,
            "qr_sha256": hashlib.sha256(qr).hexdigest(),
            "transport_timeouts": transport_timeouts,
            "idempotent_recovery": bool(registered.get("idempotent_replay")),
        }
    except Exception as exc:
        return {
            "ok": False,
            "status": 0,
            "latency_ms": (time.perf_counter() - started) * 1000,
            "steps_ms": steps,
            "error": type(exc).__name__,
            "error_detail": str(exc)[:240],
            "transport_timeouts": transport_timeouts,
        }


def run_registration_level(
    bases: list[str], event_id: int, run_id: str, cell_id: str, *, workers: int,
    duration: float, warmup_seconds: float, maximum_operations: int,
    sequence_counter: SafeCounter, app_names: list[str], postgres: str,
    sample_seconds: float,
) -> tuple[dict, list[str]]:
    results: list[dict] = []
    warmup_attempted = SafeCounter()
    warmup_completed = SafeCounter()
    issued = SafeCounter()
    in_flight = SafeCounter()
    result_lock = threading.Lock()
    warmup_barrier = threading.Barrier(workers + 1)
    start_barrier = threading.Barrier(workers + 1)
    timing: dict[str, float] = {}
    telemetry: list[dict] = []
    telemetry_stop = threading.Event()

    def worker(worker_index: int) -> None:
        client = Client()
        warmup_deadline = time.monotonic() + warmup_seconds
        local = 0
        while time.monotonic() < warmup_deadline:
            sequence = sequence_counter.next()
            warmup_attempted.next()
            warmup_result = registration_flow(
                client, bases[(worker_index + local) % len(bases)], event_id,
                run_id, f"{cell_id}-warmup", sequence,
            )
            if warmup_result.get("ok"):
                warmup_completed.next()
            local += 1
        warmup_barrier.wait()
        start_barrier.wait()
        while time.monotonic() < timing["deadline"]:
            if not issued.acquire(maximum_operations):
                break
            sequence = sequence_counter.next()
            in_flight.next()
            result = registration_flow(
                client, bases[(worker_index + local) % len(bases)], event_id,
                run_id, cell_id, sequence,
            )
            in_flight.decrement()
            with result_lock:
                results.append(result)
            local += 1

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(worker, index) for index in range(workers)]
        warmup_barrier.wait()
        timing["started"] = time.monotonic()
        timing["deadline"] = timing["started"] + duration
        start_barrier.wait()

        def sample() -> None:
            while not telemetry_stop.is_set():
                telemetry.append({
                    "timestamp": utc_now(),
                    "elapsed_seconds": round(time.monotonic() - timing["started"], 3),
                    "in_flight": in_flight.value,
                    "completed": len(results),
                    "containers": container_metrics(tuple(app_names + [postgres])),
                    "postgres": postgres_metrics(postgres),
                })
                telemetry_stop.wait(sample_seconds)

        sampler = threading.Thread(target=sample, name=f"capacity-telemetry-{cell_id}", daemon=True)
        sampler.start()
        for future in futures:
            future.result()
        telemetry_stop.set()
        sampler.join(timeout=sample_seconds + 5)
    elapsed = time.monotonic() - timing["started"]
    succeeded = [item for item in results if item["ok"]]
    failed = [item for item in results if not item["ok"]]
    step_names = ("event_get_ms", "register_post_ms", "portal_get_ms", "qr_get_ms")
    tokens = [str(item["token"]) for item in succeeded]
    qr_hashes = [str(item["qr_sha256"]) for item in succeeded]
    return ({
        "model": "closed",
        "closed_workers": workers,
        "peak_active_operations": in_flight.peak,
        "warmup_seconds_requested": warmup_seconds,
        "warmup_operations_attempted": warmup_attempted.value,
        "warmup_operations_excluded": warmup_completed.value,
        "warmup_failures": warmup_attempted.value - warmup_completed.value,
        "duration_seconds": round(elapsed, 3),
        "attempted": len(results),
        "completed": len(succeeded),
        "failed": len(failed),
        "success_rate": round(len(succeeded) * 100 / len(results), 5) if results else 0,
        "completed_per_second": round(len(succeeded) / elapsed, 3) if elapsed else 0,
        "transport_timeouts": sum(int(item.get("transport_timeouts") or 0) for item in results),
        "idempotent_recoveries": sum(bool(item.get("idempotent_recovery")) for item in succeeded),
        "latency_ms": latency_summary([float(item["latency_ms"]) for item in results]),
        "step_latency_ms": {
            step: latency_summary([
                float(item["steps_ms"][step]) for item in results if step in item.get("steps_ms", {})
            ]) for step in step_names
        },
        "unique_tokens": len(set(tokens)),
        "unique_qr_payloads": len(set(qr_hashes)),
        "recent_failure_types": sorted({str(item.get("error")) for item in failed})[:20],
        "recent_failure_details": sorted({str(item.get("error_detail")) for item in failed})[:20],
        "qr_requests_completed": len(succeeded),
        "telemetry_samples": telemetry,
        "telemetry_peaks": {
            "in_flight": max((int(item["in_flight"]) for item in telemetry), default=0),
            "postgres_connections": max((
                int(item["postgres"].get("connections_total") or 0) for item in telemetry
            ), default=0),
            "postgres_locks_waiting": max((
                int(item["postgres"].get("locks_waiting") or 0) for item in telemetry
            ), default=0),
            "container_cpu_percent": max((
                float(metric.get("cpu_percent") or 0)
                for item in telemetry for metric in item["containers"].values()
            ), default=0),
            "container_memory_percent": max((
                float(metric.get("memory_percent") or 0)
                for item in telemetry for metric in item["containers"].values()
            ), default=0),
        },
    }, tokens)


def access_request(
    client: Client, base: str, token: str, index: int, direction: str, idempotency_key: str,
) -> dict:
    started = time.perf_counter()
    try:
        status, payload = client.request(
            base,
            "/api/validate",
            {
                "token": token,
                "operator": "Admin",
                "checkpoint": "Capacity Gate",
                "direction": direction,
                "correlation_id": f"capacity-access-{idempotency_key}-{index}",
                "idempotency_key": idempotency_key,
            },
            expected={200},
        )
        return {
            "ok": status == 200,
            "latency_ms": (time.perf_counter() - started) * 1000,
            "result": payload.get("result"),
            "reason_code": payload.get("reason_code"),
            "idempotent_replay": bool(payload.get("idempotent_replay")),
        }
    except Exception as exc:
        return {
            "ok": False,
            "latency_ms": (time.perf_counter() - started) * 1000,
            "error": type(exc).__name__,
        }


def access_checks(
    bases: list[str], tokens: list[str], concurrency: int, *, run_id: str,
    cell_id: str, duration: float, sustained_mode: str = "legacy",
) -> dict:
    if not tokens:
        raise HarnessError("ACCESS_TOKENS_MISSING")
    # Reserve the final credential for the same-credential race so its state is
    # OUTSIDE when that invariant is exercised.
    distinct = tokens[:-1][: min(max(0, len(tokens) - 1), concurrency)]
    if not distinct:
        raise HarnessError("ACCESS_REQUIRES_AT_LEAST_TWO_TOKENS")
    # One authenticated session is deliberately reused across instances.  BITORA
    # may revoke older sessions for the same user on login, so authenticating
    # once per virtual reader would benchmark session churn instead of access.
    access_client = Client()
    access_client.login(bases[0], "Admin", ADMIN_PASSWORD)
    thread_clients = [clone_client(access_client) for _ in range(concurrency)]
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=len(distinct)) as pool:
        futures = [
            pool.submit(
                access_request, thread_clients[i], bases[i % len(bases)], token, i, "ENTRY",
                f"{run_id}-{cell_id}-distinct-{i}",
            )
            for i, token in enumerate(distinct)
        ]
        distinct_results = [future.result() for future in futures]
    distinct_elapsed = time.monotonic() - started

    same_token = tokens[-1]
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [
            pool.submit(
                access_request, thread_clients[i], bases[i % len(bases)], same_token,
                100000 + i, "ENTRY", f"{run_id}-{cell_id}-same-{i}",
            )
            for i in range(concurrency)
        ]
        same_results = [future.result() for future in futures]
    same_elapsed = time.monotonic() - started
    granted = sum(item.get("result") == "granted" for item in same_results)
    anti_passback = sum(item.get("reason_code") == "ANTI_PASSBACK" for item in same_results)

    replay_key = f"{run_id}-{cell_id}-replay"
    first = access_request(access_client, bases[0], tokens[0], 200000, "EXIT", replay_key)
    replay = access_request(access_client, bases[-1], tokens[0], 200000, "EXIT", replay_key)
    def outcomes(items: list[dict]) -> dict:
        return dict(sorted(Counter(
            f"{item.get('result')}:{item.get('reason_code')}" for item in items
        ).items()))
    # Sustained QR validation is measured separately from the one-shot
    # invariants above.  It deliberately reports business rejections apart from
    # technical failures; repeated ENTRY attempts can legitimately anti-passback.
    sustained_results: list[dict] = []
    sustained_lock = threading.Lock()
    barrier = threading.Barrier(concurrency + 1)
    sustained_started = 0.0
    sustained_deadline = 0.0
    profile_tokens = tokens[concurrency: concurrency * 2]
    if sustained_mode in {"valid", "antipassback"} and len(profile_tokens) < concurrency:
        raise HarnessError("ACCESS_PROFILE_REQUIRES_UNIQUE_TOKENS")
    seed_results: list[dict] = []
    if sustained_mode == "antipassback":
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = [
                pool.submit(
                    access_request,
                    thread_clients[index],
                    bases[index % len(bases)],
                    profile_tokens[index],
                    250000 + index,
                    "ENTRY",
                    f"{run_id}-{cell_id}-antipassback-seed-{index}",
                )
                for index in range(concurrency)
            ]
            seed_results = [future.result() for future in futures]
        if any(not item.get("ok") or item.get("result") != "granted" for item in seed_results):
            raise HarnessError("ACCESS_ANTIPASSBACK_SEED_FAILED")

    def sustained_worker(index: int) -> None:
        nonlocal sustained_started, sustained_deadline
        client = thread_clients[index]
        local = 0
        barrier.wait()
        while time.monotonic() < sustained_deadline:
            if sustained_mode == "valid":
                token = profile_tokens[index]
                direction = "ENTRY" if local % 2 == 0 else "EXIT"
            elif sustained_mode == "antipassback":
                token = profile_tokens[index]
                direction = "ENTRY"
            else:
                token = tokens[(index + local) % len(tokens)]
                direction = "ENTRY"
            operation = access_request(
                client, bases[(index + local) % len(bases)], token,
                300000 + index * 1000000 + local, direction,
                f"{run_id}-{cell_id}-sustained-{index}-{local}",
            )
            with sustained_lock:
                sustained_results.append(operation)
            local += 1

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        sustained_futures = [pool.submit(sustained_worker, index) for index in range(concurrency)]
        sustained_started = time.monotonic()
        sustained_deadline = sustained_started + duration
        barrier.wait()
        for future in sustained_futures:
            future.result()
    sustained_elapsed = time.monotonic() - sustained_started
    sustained_authorized = sum(item.get("result") == "granted" for item in sustained_results)
    sustained_rejected = sum(item.get("result") == "rejected" for item in sustained_results)
    sustained_technical_errors = sum(not item.get("ok") for item in sustained_results)
    sustained_outcomes = outcomes(sustained_results)
    profile_pass = sustained_technical_errors == 0
    if sustained_mode == "valid":
        profile_pass = profile_pass and sustained_authorized == len(sustained_results)
    elif sustained_mode == "antipassback":
        profile_pass = (
            profile_pass
            and sustained_authorized == 0
            and sustained_rejected == len(sustained_results)
            and sustained_outcomes == {"rejected:ANTI_PASSBACK": len(sustained_results)}
        )
    return {
        "distinct_credentials": {
            "attempted": len(distinct_results),
            "authorized": sum(item.get("result") == "granted" for item in distinct_results),
            "errors": sum(not item.get("ok") for item in distinct_results),
            "throughput_per_second": round(len(distinct_results) / distinct_elapsed, 3),
            "latency_ms": latency_summary([float(item["latency_ms"]) for item in distinct_results]),
            "outcomes": outcomes(distinct_results),
        },
        "same_credential": {
            "attempted": len(same_results),
            "authorized": granted,
            "anti_passback": anti_passback,
            "errors": sum(not item.get("ok") for item in same_results),
            "throughput_per_second": round(len(same_results) / same_elapsed, 3),
            "latency_ms": latency_summary([float(item["latency_ms"]) for item in same_results]),
            "outcomes": outcomes(same_results),
            "invariant_pass": granted == 1 and anti_passback == len(same_results) - 1,
        },
        "idempotent_replay_pass": first.get("result") == "granted" and replay.get("idempotent_replay") is True,
        "sustained_qr_validation": {
            "model": "closed",
            "profile": sustained_mode,
            "closed_workers": concurrency,
            "duration_seconds": round(sustained_elapsed, 3),
            "attempted": len(sustained_results),
            "authorized": sustained_authorized,
            "business_rejected": sustained_rejected,
            "technical_errors": sustained_technical_errors,
            "responses_per_second": round(len(sustained_results) / sustained_elapsed, 3),
            "latency_ms": latency_summary([float(item["latency_ms"]) for item in sustained_results]),
            "outcomes": sustained_outcomes,
            "seed_operations": len(seed_results),
            "profile_pass": profile_pass,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="BITORA isolated capacity benchmark")
    parser.add_argument("--report", type=Path, default=ROOT / "artifacts" / "capacity-benchmark.json")
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--levels", default="1,2,4", help="Comma-separated application instance counts")
    parser.add_argument("--workers", default="10,25,50", help="Worker levels crossed with every instance count")
    parser.add_argument("--duration-seconds", type=float, default=30)
    parser.add_argument("--warmup-seconds", type=float, default=3)
    parser.add_argument("--sample-seconds", type=float, default=5)
    parser.add_argument("--max-operations", type=int, default=0, help="Per-cell registration safety cap; zero is unlimited")
    parser.add_argument("--access-concurrency", type=int, default=30)
    parser.add_argument(
        "--access-mode", choices=("legacy", "valid", "antipassback"), default="legacy",
        help="Sustained QR profile: historical mixed state, valid ENTRY/EXIT, or anti-passback rejects",
    )
    parser.add_argument("--smoke", action="store_true", help="Use 1/2 instances, <=4 workers and a short bounded run")
    parser.add_argument("--keep", action="store_true", help="Keep only this run's isolated resources")
    args = parser.parse_args()

    try:
        levels = [int(item) for item in args.levels.split(",") if item.strip()]
        workers = [int(item) for item in args.workers.split(",") if item.strip()]
    except ValueError:
        parser.error("--levels and --workers must contain integers")
    if not levels or any(level not in {1, 2, 4} for level in levels) or levels != sorted(set(levels)):
        parser.error("--levels must be an ordered unique subset of 1,2,4")
    if not workers or workers != sorted(set(workers)) or any(item <= 0 for item in workers):
        parser.error("--workers must be an ordered unique list of positive integers")
    if (
        args.duration_seconds <= 0 or args.warmup_seconds < 0 or args.sample_seconds <= 0
        or args.max_operations < 0 or args.access_concurrency < 2
    ):
        parser.error("durations/sample must be valid; max operations non-negative; access concurrency >=2")
    if args.smoke:
        levels = [level for level in levels if level <= 2] or [1]
        workers = sorted(set(min(4, item) for item in workers))
        args.duration_seconds = min(args.duration_seconds, 3)
        args.warmup_seconds = min(args.warmup_seconds, 0.5)
        args.sample_seconds = min(args.sample_seconds, 1)
        args.max_operations = min(args.max_operations or 12, 12)
        args.access_concurrency = min(args.access_concurrency, 6)

    run_id = uuid.uuid4().hex[:10]
    prefix = f"bitora-cap-{run_id}"
    network = prefix
    postgres = f"{prefix}-postgres"
    image = f"{prefix}:test"
    app_names = [f"{prefix}-app-{index + 1}" for index in range(max(levels))]
    dsn = "postgresql://bitora:capacity-temporary@postgres:5432/bitora?connect_timeout=2"
    env = [
        "-e", "APP_ENV=development", "-e", "BITORA_ENV=development",
        "-e", "BITORA_SAFE_MODE=true", "-e", "BITORA_LIVE_MODE=false",
        "-e", "QR_DB_ENGINE=postgres", "-e", f"QR_POSTGRES_DSN={dsn}",
        "-e", f"DATABASE_URL={dsn}", "-e", "QR_REQUIRE_LOGIN=true",
        "-e", "QR_HOST=0.0.0.0", "-e", "QR_PORT=8787",
        "-e", "BITORA_DISABLE_EMBEDDED_WORKER=1", "-e", "QR_AUTO_BACKUP_MINUTES=0",
        "-e", "DB_CONNECTION_TIMEOUT=2", "-e", "EMAIL_ENABLED=false",
        "-e", "WHATSAPP_ENABLED=false",
    ]
    report: dict = {
        "schema": SCHEMA,
        "ok": False,
        "run_id": run_id,
        "sha": "",
        "started_at": utc_now(),
        "configuration": {
            "levels": levels,
            "worker_levels": workers,
            "matrix_cells": len(levels) * len(workers),
            "duration_seconds_per_cell": args.duration_seconds,
            "warmup_seconds_per_cell": args.warmup_seconds,
            "telemetry_sample_seconds": args.sample_seconds,
            "max_operations_per_cell": args.max_operations,
            "access_concurrency": args.access_concurrency,
            "access_mode": args.access_mode,
            "smoke": args.smoke,
            "postgres": "16-alpine",
        },
        "levels": [],
        "checks": {},
        "limitations": [
            "Laboratory Docker loopback is not venue networking or production infrastructure.",
            "Virtual access clients are not certification of physical QR readers or Edge hardware.",
            "Closed-model workers include application response time and do not establish a maximum arrival rate.",
        ],
    }
    resources_created = False
    started_apps: list[str] = []
    counter = SafeCounter()
    all_tokens: list[str] = []
    initial_participants = 0
    try:
        report["sha"], report["workspace_dirty"] = git_identity()
        if docker("info", check=False, timeout=30).returncode:
            raise HarnessError("DOCKER_DAEMON_UNAVAILABLE")
        docker("network", "create", network)
        resources_created = True
        docker(
            "run", "-d", "--name", postgres, "--network", network, "--network-alias", "postgres",
            "-e", "POSTGRES_DB=bitora", "-e", "POSTGRES_USER=bitora",
            "-e", "POSTGRES_PASSWORD=capacity-temporary", "postgres:16-alpine",
        )
        wait_postgres(postgres)
        docker("build", "-t", image, ".", timeout=1200)
        fixture = docker(
            "run", "--rm", "--network", network, *env, image,
            "python", "scripts/operational_multiinstance_fixture.py", "setup", timeout=300,
        )
        setup = parse_fixture(fixture.stdout)
        # The operational fixture models a 3,000-person event. Capacity tests
        # must not turn that business limit into a false infrastructure error,
        # so only the disposable synthetic event is expanded.
        docker(
            "exec", postgres, "psql", "-U", "bitora", "-d", "bitora",
            "-v", "ON_ERROR_STOP=1", "-c",
            f"UPDATE events SET capacity = 100000 WHERE id = {int(setup['event_id'])};",
        )
        initial_participants = sql_scalar(postgres, "SELECT count(*) FROM accreditations;")

        for level in levels:
            while len(started_apps) < level:
                name = app_names[len(started_apps)]
                start_application(name, network, image, env)
                started_apps.append(name)
            bases = [mapped_url(name) for name in started_apps[:level]]
            for worker_count in workers:
                cell_id = f"i{level}-w{worker_count}"
                before = {
                    "containers": container_metrics(tuple(started_apps[:level] + [postgres])),
                    "postgres": postgres_metrics(postgres),
                    "participants": sql_scalar(postgres, "SELECT count(*) FROM accreditations;"),
                }
                level_result, tokens = run_registration_level(
                    bases, int(setup["event_id"]), run_id, cell_id,
                    workers=worker_count, duration=args.duration_seconds,
                    warmup_seconds=args.warmup_seconds,
                    maximum_operations=args.max_operations, sequence_counter=counter,
                    app_names=started_apps[:level], postgres=postgres,
                    sample_seconds=args.sample_seconds,
                )
                all_tokens.extend(tokens)
                access = access_checks(
                    bases, tokens or all_tokens, args.access_concurrency,
                    run_id=run_id, cell_id=cell_id, duration=args.duration_seconds,
                    sustained_mode=args.access_mode,
                )
                after = {
                    "containers": container_metrics(tuple(started_apps[:level] + [postgres])),
                    "postgres": postgres_metrics(postgres),
                    "participants": sql_scalar(postgres, "SELECT count(*) FROM accreditations;"),
                }
                level_result.update({
                    "cell_id": cell_id,
                    "instances": level,
                    "access": access,
                    "telemetry_before": before,
                    "telemetry_after": after,
                    "database_rows_added": after["participants"] - before["participants"],
                    "integrity_pass": after["participants"] - before["participants"] == (
                        level_result["warmup_operations_excluded"] + level_result["completed"]
                    ),
                })
                report["levels"].append(level_result)
                if args.checkpoint:
                    atomic_json(args.checkpoint, {
                        "schema": SCHEMA, "status": "running", "run_id": run_id,
                        "sha": report["sha"], "workspace_dirty": report["workspace_dirty"],
                        "completed_cells": len(report["levels"]),
                        "total_cells": len(levels) * len(workers), "last_cell": level_result,
                    })

        recovery_name = started_apps[0]
        recovery_started = time.perf_counter()
        docker("restart", recovery_name, timeout=90)
        recovery_base = mapped_url(recovery_name)
        wait_ready(recovery_base)
        recovery_seconds = time.perf_counter() - recovery_started
        recovery_result = registration_flow(
            Client(), recovery_base, int(setup["event_id"]), run_id, "recovery", counter.next()
        )
        if recovery_result.get("ok"):
            all_tokens.append(str(recovery_result["token"]))
        final_participants = sql_scalar(postgres, "SELECT count(*) FROM accreditations;")
        duplicate_tokens = sql_scalar(
            postgres,
            "SELECT count(*) FROM (SELECT lower(token) FROM accreditations GROUP BY lower(token) HAVING count(*) > 1) d;",
        )
        duplicate_emails = sql_scalar(
            postgres,
            "SELECT count(*) FROM (SELECT a.event_id, lower(p.email) FROM accreditations a JOIN people p ON p.id=a.person_id GROUP BY a.event_id, lower(p.email) HAVING count(*) > 1) d;",
        )
        expected_added = sum(
            int(item["warmup_operations_excluded"]) + int(item["completed"])
            for item in report["levels"]
        ) + int(bool(recovery_result.get("ok")))
        report["recovery"] = {
            "instance_restart_seconds": round(recovery_seconds, 3),
            "post_restart_complete_registration": bool(recovery_result.get("ok")),
        }
        report["integrity"] = {
            "initial_participants": initial_participants,
            "final_participants": final_participants,
            "expected_added": expected_added,
            "observed_added": final_participants - initial_participants,
            "duplicate_tokens": duplicate_tokens,
            "duplicate_emails_within_event": duplicate_emails,
            "postgres": postgres_metrics(postgres),
        }
        report["checks"] = {
            "all_registration_levels_succeeded": all(
                item["attempted"] > 0 and item["failed"] == 0 and item["integrity_pass"]
                for item in report["levels"]
            ),
            "tokens_and_qr_unique": all(
                item["unique_tokens"] == item["completed"]
                and item["unique_qr_payloads"] == item["completed"]
                for item in report["levels"]
            ),
            "anti_passback_preserved": all(
                item["access"]["same_credential"]["invariant_pass"] for item in report["levels"]
            ),
            "idempotency_preserved": all(
                item["access"]["idempotent_replay_pass"] for item in report["levels"]
            ),
            "sustained_access_profile_pass": all(
                item["access"]["sustained_qr_validation"]["profile_pass"] for item in report["levels"]
            ),
            "restart_recovers": bool(recovery_result.get("ok")),
            "database_integrity": (
                final_participants - initial_participants == expected_added
                and duplicate_tokens == 0 and duplicate_emails == 0
            ),
            "postgres_no_deadlocks": int(report["integrity"]["postgres"].get("deadlocks") or 0) == 0,
            "containers_no_oom_or_restart": all(
                not metric.get("oom_killed") and (metric.get("restart_count") or 0) == 0
                for item in report["levels"]
                for metric in item["telemetry_after"]["containers"].values()
            ),
        }
        # The intentional recovery restart occurs after the level telemetry and is
        # reported separately; it does not invalidate the unplanned-restart check.
        report["ok"] = all(report["checks"].values())
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}:{exc}"
    finally:
        if resources_created and not args.keep:
            for name in reversed(app_names + [postgres]):
                docker("rm", "-f", name, check=False, timeout=60)
            docker("network", "rm", network, check=False, timeout=60)
            docker("image", "rm", image, check=False, timeout=120)
        report["finished_at"] = utc_now()
        report["resources_removed"] = bool(resources_created and not args.keep)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if args.checkpoint:
            atomic_json(args.checkpoint, {
                "schema": SCHEMA, "status": "complete" if report.get("ok") else "failed",
                "run_id": run_id, "sha": report.get("sha"), "checks": report.get("checks", {}),
                "report": str(args.report),
            })
    print("BITORA_CAPACITY_RESULT=" + json.dumps({
        "ok": report.get("ok"), "run_id": run_id, "sha": report.get("sha"),
        "levels": len(report.get("levels", [])), "report": str(args.report),
        "error": report.get("error"),
    }, sort_keys=True))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
