#!/usr/bin/env python3
"""Deterministic autonomous certification supervisor for BITORA phase 6.2."""

from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import hashlib
import json
import os
import pathlib
import signal
import subprocess
import sys
import time
from typing import Any


HERE = pathlib.Path(__file__).resolve().parent
DEFAULT_CONFIG = HERE / "phase62_campaign_config.json"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def atomic_json(path: pathlib.Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def load_json(path: pathlib.Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON object required: {path}")
    return value


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run_text(*command: str, cwd: pathlib.Path | None = None) -> str:
    commands = [command]
    if command and command[0] == "git":
        # Worktrees created by native Windows Git store a Windows gitdir path.
        # Linux Git inside WSL cannot resolve that pointer, while git.exe can.
        commands = [command, ("git.exe", *command[1:])]
    failures: list[str] = []
    for candidate in commands:
        try:
            result = subprocess.run(
                candidate, cwd=cwd, check=False, text=True,
                capture_output=True, timeout=60,
            )
        except FileNotFoundError:
            failures.append(f"{candidate[0]}:not-found")
            continue
        if result.returncode == 0:
            return result.stdout.strip()
        failures.append(f"{candidate[0]}:exit-{result.returncode}")
    raise RuntimeError("COMMAND_FAILED:" + ",".join(failures))


def verify_frozen_source(config: dict[str, Any]) -> pathlib.Path:
    expected = str(config["expected_sha"])
    if expected.startswith("__"):
        raise RuntimeError("Candidate SHA has not been frozen in configuration")
    root = pathlib.Path(config["cert_root"]).resolve()
    actual = run_text("git", "rev-parse", "HEAD", cwd=root)
    if actual != expected:
        raise RuntimeError(f"SHA_MISMATCH:{actual}:{expected}")
    dirty = run_text("git", "status", "--porcelain", "--untracked-files=all", cwd=root)
    if dirty:
        raise RuntimeError("CERT_ROOT_NOT_CLEAN")
    return root


def stages() -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for repetition in range(1, 4):
        result.append({"id": f"qr-valid-24-r{repetition}", "mode": "valid", "readers": 24})
    for repetition in range(1, 4):
        result.append({"id": f"qr-antipassback-16-r{repetition}", "mode": "antipassback", "readers": 16})
    for repetition in range(1, 4):
        result.append({"id": f"qr-antipassback-24-r{repetition}", "mode": "antipassback", "readers": 24})
    return result


def validate_report(
    report_path: pathlib.Path, expected_sha: str, mode: str, readers: int
) -> dict[str, bool]:
    data = load_json(report_path)
    profile = data["levels"][0]["access"]["sustained_qr_validation"]
    authorized = int(profile.get("authorized") or 0)
    rejected = int(profile.get("business_rejected") or 0)
    attempted = int(profile.get("attempted") or 0)
    semantic_pass = authorized == attempted if mode == "valid" else (
        authorized == 0 and rejected == attempted
    )
    return {
        "report_ok": data.get("ok") is True,
        "sha_exact": data.get("sha") == expected_sha,
        "workspace_clean": data.get("workspace_dirty") is False,
        "profile_exact": profile.get("profile") == mode,
        "readers_exact": profile.get("closed_workers") == readers,
        "duration_at_least_600s": float(profile.get("duration_seconds") or 0) >= 600,
        "attempted_positive": attempted > 0,
        "semantic_integrity": semantic_pass,
        "profile_integrity": profile.get("profile_pass") is True,
        "zero_technical_errors": profile.get("technical_errors") == 0,
        "p95_under_500ms": float(profile.get("latency_ms", {}).get("p95") or 999999) <= 500,
        "database_integrity": data.get("checks", {}).get("database_integrity") is True,
        "zero_deadlocks": data.get("integrity", {}).get("postgres", {}).get("deadlocks") == 0,
        "no_oom_or_restart": data.get("checks", {}).get("containers_no_oom_or_restart") is True,
    }


def healthy_container(name: str) -> bool:
    result = subprocess.run(
        ["docker", "inspect", "--format", "{{.State.Running}} {{if .State.Health}}{{.State.Health.Status}}{{end}}", name],
        text=True, capture_output=True, timeout=30,
    )
    if result.returncode:
        return False
    parts = result.stdout.strip().split()
    return bool(parts) and parts[0] == "true" and (len(parts) == 1 or parts[1] == "healthy")


def stop_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=30)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=10)


def monitor(process: subprocess.Popen[str], lifecycle_path: pathlib.Path) -> str | None:
    while process.poll() is None:
        if lifecycle_path.exists():
            lifecycle = load_json(lifecycle_path)
            if lifecycle.get("phase") == "RUNNING":
                prefix = lifecycle.get("resource_prefix")
                names = [f"{prefix}-postgres", f"{prefix}-app-1", f"{prefix}-app-2"]
                if not prefix or not all(healthy_container(name) for name in names):
                    stop_process(process)
                    return "INFRASTRUCTURE_LOST_DURING_RUNNING"
        time.sleep(5)
    return None


def initial_state(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "bitora.phase62.campaign.v1",
        "campaign_id": config["campaign_id"],
        "expected_sha": config["expected_sha"],
        "status": "RUNNING",
        "phase": "STARTING",
        "started_at": utc_now(),
        "updated_at": utc_now(),
        "supervisor_pid": os.getpid(),
        "completed": [],
        "current": None,
        "next_authorized_test": stages()[0]["id"],
        "stop_reason": None,
    }


def persist(path: pathlib.Path, state: dict[str, Any]) -> None:
    state["updated_at"] = utc_now()
    state["supervisor_pid"] = os.getpid()
    atomic_json(path, state)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=pathlib.Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    config = load_json(args.config)
    cert_root = verify_frozen_source(config)
    campaign_root = HERE / "evidence" / str(config["campaign_id"])
    campaign_root.mkdir(parents=True, exist_ok=True)
    checkpoint = campaign_root / "checkpoint.json"
    lock_path = campaign_root / "campaign.lock"
    with lock_path.open("a+", encoding="utf-8") as lock_handle:
        try:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("SECOND_SUPERVISOR_REJECTED")
        state = load_json(checkpoint) if checkpoint.exists() else initial_state(config)
        if state.get("expected_sha") != config["expected_sha"]:
            raise RuntimeError("CHECKPOINT_SHA_MISMATCH")
        if state.get("status") in {"PASS", "FAIL", "BLOCKED", "INCOMPLETE"}:
            return 0 if state.get("status") == "PASS" else 1
        completed = {item["id"] for item in state.get("completed", [])}
        for index, stage in enumerate(stages()):
            if stage["id"] in completed:
                continue
            verify_frozen_source(config)
            attempt_root = campaign_root / stage["id"]
            attempt_root.mkdir(parents=True, exist_ok=False)
            report = attempt_root / "report.json"
            harness_checkpoint = attempt_root / "harness-checkpoint.json"
            lifecycle = attempt_root / "lifecycle.json"
            stdout_path = attempt_root / "stdout.log"
            stderr_path = attempt_root / "stderr.log"
            command = [
                sys.executable, str(HERE / "phase62_lifecycle.py"),
                "--cert-root", str(cert_root), "--lifecycle-file", str(lifecycle),
                "--attempt-id", stage["id"], "--campaign-id", config["campaign_id"],
                "--expected-sha", config["expected_sha"],
                "--report", str(report), "--checkpoint", str(harness_checkpoint),
                "--levels", "2", "--workers", "25", "--duration-seconds", "600",
                "--warmup-seconds", "5", "--sample-seconds", "10",
                "--max-operations", "100", "--access-concurrency", str(stage["readers"]),
                "--access-mode", stage["mode"],
            ]
            state["phase"] = "STARTING"
            state["current"] = {**stage, "started_at": utc_now(), "command": command}
            state["next_authorized_test"] = stage["id"]
            persist(checkpoint, state)
            with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open("w", encoding="utf-8") as stderr:
                process = subprocess.Popen(
                    command, cwd=cert_root, stdout=stdout, stderr=stderr, text=True,
                    start_new_session=True,
                )
                state["current"]["pid"] = process.pid
                persist(checkpoint, state)
                monitor_failure = monitor(process, lifecycle)
                return_code = process.wait()
            if monitor_failure or return_code or not report.exists():
                state.update(status="FAIL", phase="FINISHED", stop_reason=(monitor_failure or f"HARNESS_EXIT_{return_code}"))
                persist(checkpoint, state)
                return 1
            checks = validate_report(report, config["expected_sha"], stage["mode"], stage["readers"])
            result = {
                "id": stage["id"], "status": "PASS" if all(checks.values()) else "FAIL",
                "finished_at": utc_now(), "report": str(report), "report_sha256": sha256(report),
                "lifecycle": str(lifecycle), "lifecycle_sha256": sha256(lifecycle), "checks": checks,
            }
            if not all(checks.values()):
                state["current"] = result
                state.update(status="FAIL", phase="FINISHED", stop_reason=f"GATE_FAILED:{stage['id']}")
                persist(checkpoint, state)
                return 1
            state["completed"].append(result)
            state["current"] = None
            state["next_authorized_test"] = stages()[index + 1]["id"] if index + 1 < len(stages()) else None
            state["phase"] = "STOPPING"
            persist(checkpoint, state)
        state.update(status="PASS", phase="FINISHED", next_authorized_test=None, stop_reason=None)
        persist(checkpoint, state)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
