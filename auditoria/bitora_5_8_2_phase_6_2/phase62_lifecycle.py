#!/usr/bin/env python3
"""Lifecycle adapter for the frozen BITORA capacity harness.

The adapter adds atomic STARTING/READY/RUNNING/STOPPING/FINISHED evidence
without changing the application or the benchmark implementation.
"""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import os
import pathlib
import sys
import time
from typing import Any, Callable


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def atomic_json(path: pathlib.Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def parse_args() -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--cert-root", type=pathlib.Path, required=True)
    parser.add_argument("--lifecycle-file", type=pathlib.Path, required=True)
    parser.add_argument("--attempt-id", required=True)
    parser.add_argument("--campaign-id", required=True)
    parser.add_argument("--expected-sha", required=True)
    return parser.parse_known_args()


def load_benchmark(root: pathlib.Path):
    benchmark_path = root / "scripts/capacity_benchmark.py"
    sys.path.insert(0, str(benchmark_path.parent))
    spec = importlib.util.spec_from_file_location("bitora_capacity_benchmark", benchmark_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load capacity benchmark: {benchmark_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, benchmark_path


def main() -> int:
    wrapper, remaining = parse_args()
    lifecycle: dict[str, Any] = {
        "schema": "bitora.phase62.lifecycle.v1",
        "campaign_id": wrapper.campaign_id,
        "attempt_id": wrapper.attempt_id,
        "expected_sha": wrapper.expected_sha,
        "wrapper_pid": os.getpid(),
        "phase": "STARTING",
        "started_at": utc_now(),
        "updated_at": utc_now(),
        "resource_prefix": None,
        "postgres_ready": False,
        "healthy_apps": [],
        "history": [],
    }

    def transition(phase: str, reason: str, **extra: Any) -> None:
        timestamp = utc_now()
        lifecycle.update(extra)
        lifecycle["phase"] = phase
        lifecycle["updated_at"] = timestamp
        lifecycle["history"].append(
            {"phase": phase, "at": timestamp, "reason": reason, **extra}
        )
        atomic_json(wrapper.lifecycle_file, lifecycle)

    transition("STARTING", "wrapper-started")
    benchmark, benchmark_path = load_benchmark(wrapper.cert_root)
    original_docker: Callable[..., Any] = benchmark.docker
    original_wait_postgres: Callable[..., Any] = benchmark.wait_postgres
    original_start_application: Callable[..., Any] = benchmark.start_application
    original_access: Callable[..., Any] = benchmark.access_checks

    def docker_instrumented(*args: Any, **kwargs: Any):
        if len(args) >= 3 and args[0] == "network" and args[1] == "create":
            transition("STARTING", "docker-project-created", resource_prefix=str(args[2]))
        return original_docker(*args, **kwargs)

    def wait_postgres_instrumented(container: str, *args: Any, **kwargs: Any):
        result = original_wait_postgres(container, *args, **kwargs)
        transition("STARTING", "postgres-ready", postgres_ready=True)
        return result

    def start_application_instrumented(name: str, *args: Any, **kwargs: Any):
        result = original_start_application(name, *args, **kwargs)
        deadline = time.monotonic() + 120
        status = "unknown"
        while time.monotonic() < deadline:
            inspected = original_docker(
                "inspect", "--format",
                "{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}",
                name, check=False, timeout=30,
            )
            status = inspected.stdout.strip()
            if inspected.returncode == 0 and status in {"healthy", "running"}:
                break
            time.sleep(1)
        else:
            raise RuntimeError(f"CONTAINER_HEALTH_TIMEOUT:{name}:{status}")
        healthy = list(lifecycle.get("healthy_apps", []))
        if name not in healthy:
            healthy.append(name)
        transition(
            "READY" if len(healthy) >= 2 else "STARTING",
            "application-ready", healthy_apps=healthy,
        )
        return result

    access_started = False

    def access_instrumented(*args: Any, **kwargs: Any):
        nonlocal access_started
        if not access_started:
            access_started = True
            transition("RUNNING", "measured-access-load-started")
        return original_access(*args, **kwargs)

    benchmark.docker = docker_instrumented
    benchmark.wait_postgres = wait_postgres_instrumented
    benchmark.start_application = start_application_instrumented
    benchmark.access_checks = access_instrumented
    sys.argv = [str(benchmark_path), *remaining]
    return_code = 1
    try:
        return_code = int(benchmark.main())
        return return_code
    except BaseException as exc:
        transition("STOPPING", f"wrapper-exception:{type(exc).__name__}")
        raise
    finally:
        transition("FINISHED", "harness-exited", exit_code=return_code)


if __name__ == "__main__":
    raise SystemExit(main())
