from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def os_tokens() -> str:
    return os.environ.get("BITORA_ENDURANCE_PUBLIC_TOKENS", "")


def get_json(url: str, timeout: int = 60) -> tuple[bool, dict, float, str, int | None]:
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            raw = response.read()
            status_code = int(getattr(response, "status", 200) or 200)
        elapsed = round((time.perf_counter() - start) * 1000, 2)
        return True, json.loads(raw.decode("utf-8")), elapsed, "", status_code
    except urllib.error.HTTPError as exc:
        elapsed = round((time.perf_counter() - start) * 1000, 2)
        return False, {}, elapsed, f"HTTP Error {exc.code}: {exc.reason}"[:240], int(exc.code)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        elapsed = round((time.perf_counter() - start) * 1000, 2)
        return False, {}, elapsed, str(exc)[:240], None


def classify(record: dict) -> list[dict]:
    findings: list[dict] = []
    health = record.get("health", {})
    ready = record.get("ready", {})
    if not health.get("ok"):
        severity = "AVAILABILITY" if health.get("http_status") in {502, 503, 504} else "CRITICAL"
        findings.append({"severity": severity, "code": "health.unavailable", "detail": health.get("error", "")})
    if not ready.get("ok"):
        severity = "AVAILABILITY" if ready.get("http_status") in {502, 503, 504} else "CRITICAL"
        findings.append({"severity": severity, "code": "ready.unavailable", "detail": ready.get("error", "")})
    health_body = health.get("body") or {}
    ready_body = ready.get("body") or {}
    if health.get("ok") and health_body.get("status") != "ok":
        findings.append({"severity": "CRITICAL", "code": "health.status", "detail": str(health_body.get("status"))})
    checks = ready_body.get("checks") or {}
    if checks.get("safe_mode") is not True:
        findings.append({"severity": "CRITICAL", "code": "safe_mode.off", "detail": "Safe Mode is not true"})
    if checks.get("live_mode_off") is not True:
        findings.append({"severity": "CRITICAL", "code": "live_mode.on", "detail": "Live Mode is not off"})
    jobs = health_body.get("jobs") or {}
    if int(jobs.get("failed") or 0) > 0:
        findings.append({"severity": "HIGH", "code": "jobs.failed", "detail": str(jobs)})
    if not record.get("portal_checks_ok"):
        findings.append({"severity": "HIGH", "code": "portal.check_failed", "detail": "One or more public portal fixtures failed"})
    return findings


def run_once(base_url: str, public_tokens: list[str]) -> dict:
    base_url = base_url.rstrip("/")
    health_ok, health, health_ms, health_error, health_status = get_json(f"{base_url}/health")
    ready_ok, ready, ready_ms, ready_error, ready_status = get_json(f"{base_url}/ready")
    portals = []
    for token in public_tokens:
        ok, body, ms, error, status = get_json(f"{base_url}/api/portal?token={token}")
        portals.append(
            {
                "ok": ok and int(body.get("event_id") or 0) == 7,
                "token_hint": token[:8],
                "event_id": body.get("event_id"),
                "surveys": len(body.get("surveys") or []),
                "certificates": len(body.get("certificates") or []),
                "latency_ms": ms,
                "http_status": status,
                "error": error,
            }
        )
    record = {
        "timestamp_utc": iso(utc_now()),
        "health": {"ok": health_ok, "latency_ms": health_ms, "http_status": health_status, "body": health, "error": health_error},
        "ready": {"ok": ready_ok, "latency_ms": ready_ms, "http_status": ready_status, "body": ready, "error": ready_error},
        "portal_checks": portals,
        "portal_checks_ok": all(item["ok"] for item in portals),
    }
    record["findings"] = classify(record)
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description="BITORA 24h endurance runner for staging.")
    parser.add_argument("--base-url", default="https://bitora-staging.onrender.com")
    parser.add_argument("--hours", type=float, default=24.0)
    parser.add_argument("--interval-seconds", type=int, default=900)
    parser.add_argument("--out-dir", default="artifacts/endurance")
    parser.add_argument("--public-token", action="append", default=[], help="Optional participant portal token for non-destructive checks.")
    args = parser.parse_args()
    public_tokens = args.public_token or [item.strip() for item in os_tokens().split(",") if item.strip()]

    start = utc_now()
    expected_end = start + timedelta(hours=args.hours)
    run_id = f"ENDURANCE-24H-{start.strftime('%Y%m%d-%H%M%S')}"
    out_dir = Path(args.out_dir) / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    start_payload = {
        "run_id": run_id,
        "base_url": args.base_url,
        "event_id": 7,
        "start_timestamp_utc": iso(start),
        "expected_end_timestamp_utc": iso(expected_end),
        "interval_seconds": args.interval_seconds,
        "safe_mode_required": True,
        "live_mode_required": False,
        "real_communications_allowed": 0,
        "status": "RUNNING",
    }
    (out_dir / "BITORA_ENDURANCE_24H_START.json").write_text(json.dumps(start_payload, indent=2), encoding="utf-8")
    checkpoints_path = out_dir / "BITORA_ENDURANCE_24H_CHECKPOINTS.jsonl"

    critical = 0
    high = 0
    availability = 0
    iterations = 0
    while utc_now() < expected_end:
        record = run_once(args.base_url, public_tokens)
        iterations += 1
        for finding in record["findings"]:
            if finding["severity"] == "CRITICAL":
                critical += 1
            if finding["severity"] == "HIGH":
                high += 1
            if finding["severity"] == "AVAILABILITY":
                availability += 1
        with checkpoints_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=True, sort_keys=True) + "\n")
        time.sleep(max(60, args.interval_seconds))

    final_record = run_once(args.base_url, public_tokens)
    for finding in final_record["findings"]:
        if finding["severity"] == "CRITICAL":
            critical += 1
        if finding["severity"] == "HIGH":
            high += 1
        if finding["severity"] == "AVAILABILITY":
            availability += 1
    elapsed = utc_now() - start
    passed = elapsed >= timedelta(hours=args.hours) and critical == 0 and high == 0 and availability == 0
    report = f"""# BITORA Endurance 24H Final Report

- Run ID: `{run_id}`
- Base URL: `{args.base_url}`
- Event ID: `7`
- Start UTC: `{iso(start)}`
- End UTC: `{iso(utc_now())}`
- Elapsed hours: `{round(elapsed.total_seconds() / 3600, 2)}`
- Iterations: `{iterations + 1}`
- Critical findings: `{critical}`
- High findings: `{high}`
- Availability events: `{availability}`
- Safe Mode required: `ON`
- Live Mode required: `OFF`
- Real communications allowed: `0`
- Result: `{'PASSED' if passed else 'FAILED'}`

Endurance is valid only if elapsed time is at least 24 real hours.
"""
    (out_dir / "BITORA_ENDURANCE_24H_FINAL_REPORT.md").write_text(report, encoding="utf-8")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
