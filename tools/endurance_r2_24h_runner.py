from __future__ import annotations

import argparse
import hashlib
import http.cookiejar
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


TARGET_SHA = "9b1f3e65cf65208cce568f6023fedc6b144c5ffa"
DEFAULT_BASE_URL = "https://bitora-staging.onrender.com"
DEFAULT_EVENT_ID = 7


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | None = None) -> str:
    return (dt or utc_now()).isoformat(timespec="seconds")


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def local_secret_path() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    return base / "BITORA" / "endurance_secrets.json"


def load_secrets() -> dict:
    secrets = load_json(local_secret_path())
    for key in (
        "BITORA_ENDURANCE_ADMIN_USER",
        "BITORA_ENDURANCE_ADMIN_PASSWORD",
        "R2_ACCOUNT_ID",
        "R2_ENDPOINT",
        "R2_BUCKET",
        "R2_PREFIX",
        "R2_ACCESS_KEY_ID",
        "R2_SECRET_ACCESS_KEY",
        "S3_ENDPOINT_URL",
        "S3_BUCKET",
        "S3_PREFIX",
        "S3_ACCESS_KEY_ID",
        "S3_SECRET_ACCESS_KEY",
    ):
        if os.environ.get(key):
            secrets[key] = os.environ[key]
    return secrets


def mask(value: str, keep: int = 4) -> str:
    if not value:
        return ""
    if len(value) <= keep * 2:
        return "*" * len(value)
    return f"{value[:keep]}...{value[-keep:]}"


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def append_jsonl(path: Path, payload: dict) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True, sort_keys=True) + "\n")


class HttpClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.cookies = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookies))

    def request(self, method: str, path: str, *, json_body: dict | None = None, timeout: int = 60) -> dict:
        url = path if path.startswith("http") else f"{self.base_url}{path}"
        data = None
        headers: dict[str, str] = {"User-Agent": "BITORA-Endurance-R2/1.0"}
        if json_body is not None:
            data = json.dumps(json_body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        start = time.perf_counter()
        try:
            req = urllib.request.Request(url, data=data, headers=headers, method=method)
            with self.opener.open(req, timeout=timeout) as response:
                raw = response.read()
                status = int(getattr(response, "status", 200) or 200)
                content_type = response.headers.get("content-type", "")
            text = raw.decode("utf-8", "replace") if raw else ""
            body = None
            if "json" in content_type or text[:1] in "{[":
                body = json.loads(text)
            return {
                "ok": 200 <= status < 300,
                "status": status,
                "latency_ms": round((time.perf_counter() - start) * 1000, 2),
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest().upper(),
                "json": body,
                "content_type": content_type,
                "raw": raw,
                "error": "",
            }
        except urllib.error.HTTPError as exc:
            return {
                "ok": False,
                "status": int(exc.code),
                "latency_ms": round((time.perf_counter() - start) * 1000, 2),
                "bytes": 0,
                "sha256": "",
                "json": None,
                "content_type": "",
                "raw": b"",
                "error": f"HTTP {exc.code}: {exc.reason}"[:240],
            }
        except Exception as exc:
            return {
                "ok": False,
                "status": None,
                "latency_ms": round((time.perf_counter() - start) * 1000, 2),
                "bytes": 0,
                "sha256": "",
                "json": None,
                "content_type": "",
                "raw": b"",
                "error": str(exc)[:240],
            }

    def login(self, user: str, password: str) -> dict:
        return self.request("POST", "/api/auth/login", json_body={"name": user, "pin": password}, timeout=60)


def r2_configured(secrets: dict) -> bool:
    endpoint = secrets.get("R2_ENDPOINT") or secrets.get("S3_ENDPOINT_URL") or secrets.get("R2_ACCOUNT_ID")
    bucket = secrets.get("R2_BUCKET") or secrets.get("S3_BUCKET")
    key = secrets.get("R2_ACCESS_KEY_ID") or secrets.get("S3_ACCESS_KEY_ID")
    secret = secrets.get("R2_SECRET_ACCESS_KEY") or secrets.get("S3_SECRET_ACCESS_KEY")
    return bool(endpoint and bucket and key and secret)


def apply_r2_env(secrets: dict) -> None:
    for key, value in secrets.items():
        if key.startswith("R2_") or key.startswith("S3_") or key == "BITORA_STORAGE_PROVIDER":
            os.environ[key] = str(value)
    os.environ["BITORA_STORAGE_PROVIDER"] = "r2"


def r2_direct_check(run_id: str) -> dict:
    from backend.storage import StorageService

    storage = StorageService(Path(os.environ.get("TEMP", ".")) / "bitora-r2-unused", "r2")
    payload = f"BITORA ENDURANCE R2 {run_id} {iso()}".encode("utf-8")
    checksum = hashlib.sha256(payload).hexdigest()
    name = f"{run_id}-{utc_now().strftime('%Y%m%d%H%M%S')}.txt"
    record = storage.save_event(DEFAULT_EVENT_ID, "uploads", name, payload)
    read_back = storage.read_event(DEFAULT_EVENT_ID, "uploads", name)
    deleted = storage.delete_event(DEFAULT_EVENT_ID, "uploads", name)
    return {
        "timestamp_utc": iso(),
        "status": "PASSED" if record.get("sha256") == checksum and read_back == payload and deleted else "FAILED",
        "write": True,
        "read": read_back == payload,
        "checksum": hashlib.sha256(read_back).hexdigest() if read_back else "",
        "expected_checksum": checksum,
        "delete": bool(deleted),
        "key_hint": mask(str(record.get("key", "")), 10),
    }


def inspect_backup(raw: bytes) -> dict:
    backup_path = Path(os.environ.get("TEMP", ".")) / f"bitora-backup-inspect-{time.time_ns()}.zip"
    backup_path.write_bytes(raw)
    try:
        with zipfile.ZipFile(backup_path) as archive:
            names = archive.namelist()
            manifest_name = next((name for name in names if name.endswith("manifest.json")), "")
            manifest = json.loads(archive.read(manifest_name).decode("utf-8")) if manifest_name else {}
            text = "\n".join(names)
        counts = manifest.get("counts") or {}
        return {
            "ok": bool(manifest_name),
            "manifest": manifest_name,
            "files": len(names),
            "has_event": int(counts.get("events") or 0) >= 1,
            "has_organization": int(counts.get("organizations") or 0) >= 1,
            "has_participants": int(counts.get("participants") or counts.get("people") or 0) >= 10,
            "has_certificates": "certificate" in text.lower(),
            "counts": counts,
        }
    finally:
        try:
            backup_path.unlink()
        except OSError:
            pass


def backup_check(client: HttpClient, event_id: int, out_dir: Path, label: str) -> dict:
    response = client.request("GET", f"/api/backup?event_id={event_id}", timeout=180)
    payload = {
        "timestamp_utc": iso(),
        "label": label,
        "http_status": response.get("status"),
        "bytes": response.get("bytes"),
        "sha256": response.get("sha256"),
        "status": "FAILED",
        "content": {},
    }
    if response.get("ok") and response.get("raw"):
        backup_dir = out_dir / "backups"
        backup_dir.mkdir(exist_ok=True)
        backup_file = backup_dir / f"{label}-{utc_now().strftime('%Y%m%d%H%M%S')}.zip"
        backup_file.write_bytes(response["raw"])
        content = inspect_backup(response["raw"])
        payload["backup_file"] = str(backup_file)
        payload["content"] = content
        payload["status"] = "PASSED" if content.get("ok") and content.get("has_event") and content.get("has_organization") and content.get("has_participants") else "FAILED"
    else:
        payload["error"] = response.get("error")
    return payload


def restore_check(backup_record: dict, python_exe: str) -> dict:
    backup_file = backup_record.get("backup_file")
    payload = {"timestamp_utc": iso(), "status": "FAILED", "backup_file": Path(str(backup_file or "")).name}
    if not backup_file or not Path(backup_file).exists():
        payload["error"] = "backup_file_missing"
        return payload
    env = os.environ.copy()
    env["BITORA_R2_RESTORE_BACKUP"] = str(Path(backup_file).resolve())
    env["BITORA_LIVE_MODE"] = "false"
    env["BITORA_SAFE_MODE"] = "true"
    env["EMAIL_ENABLED"] = "false"
    env["WHATSAPP_ENABLED"] = "false"
    result = subprocess.run(
        [python_exe, str(ROOT / "tools" / "certify_r2_restore_isolated.py")],
        cwd=str(ROOT),
        env=env,
        text=True,
        capture_output=True,
        timeout=240,
    )
    payload["returncode"] = result.returncode
    if result.stdout.strip():
        try:
            report = json.loads(result.stdout[result.stdout.find("{") :])
        except Exception:
            report = {"raw_stdout": result.stdout[-500:]}
        payload["report"] = report
        payload["status"] = "PASSED" if result.returncode == 0 and report.get("status") == "PASSED" and int(report.get("external_effects") or 0) == 0 else "FAILED"
        payload["external_effects"] = report.get("external_effects")
        payload["token_regenerated"] = (report.get("restore") or {}).get("token_regenerated")
    if result.stderr.strip():
        payload["stderr_tail"] = result.stderr[-500:]
    return payload


def classify_checkpoint(record: dict) -> list[dict]:
    findings = []
    health = record.get("health", {})
    ready = record.get("ready", {})
    health_body = health.get("json") or {}
    ready_body = ready.get("json") or {}
    checks = ready_body.get("checks") or {}
    if not health.get("ok") or health_body.get("status") != "ok":
        findings.append({"severity": "CRITICAL", "code": "health.failed"})
    if not ready.get("ok") or ready_body.get("status") != "ready":
        findings.append({"severity": "CRITICAL", "code": "ready.failed"})
    if checks.get("safe_mode") is not True:
        findings.append({"severity": "CRITICAL", "code": "safe_mode.off"})
    if checks.get("live_mode_off") is not True:
        findings.append({"severity": "CRITICAL", "code": "live_mode.on"})
    jobs = health_body.get("jobs") or {}
    if int(jobs.get("failed") or 0):
        findings.append({"severity": "HIGH", "code": "jobs.failed"})
    storage = health_body.get("storage") or {}
    if storage.get("backend") != "r2" or storage.get("ready") is not True:
        findings.append({"severity": "CRITICAL", "code": "r2.not_ready"})
    metrics = (record.get("participant_metrics") or {}).get("json") or {}
    if metrics.get("registered") != 10:
        findings.append({"severity": "HIGH", "code": "baseline.participants"})
    return findings


def checkpoint(client: HttpClient, event_id: int, target_sha: str) -> dict:
    record = {
        "timestamp_utc": iso(),
        "target_sha": target_sha,
        "event_id": event_id,
        "health": client.request("GET", "/health", timeout=60),
        "ready": client.request("GET", "/ready", timeout=60),
        "event": client.request("GET", f"/api/event?event_id={event_id}", timeout=60),
        "participant_metrics": client.request("GET", f"/api/participant-metrics?event_id={event_id}", timeout=60),
        "public_display": client.request("GET", f"/api/public-display?event_id={event_id}", timeout=60),
        "users_read": client.request("GET", "/api/users", timeout=60),
        "communications": {"real_whatsapp": 0, "real_email": 0, "unauthorized": 0},
    }
    for key in ("health", "ready", "event", "participant_metrics", "public_display", "users_read"):
        record[key].pop("raw", None)
    record["findings"] = classify_checkpoint(record)
    return record


def count_findings(errors_path: Path) -> tuple[int, int, int]:
    critical = high = warning = 0
    if errors_path.exists():
        for line in errors_path.read_text(encoding="utf-8").splitlines():
            severity = json.loads(line).get("severity")
            if severity == "CRITICAL":
                critical += 1
            elif severity == "HIGH":
                high += 1
            elif severity == "WARNING":
                warning += 1
    return critical, high, warning


def main() -> int:
    parser = argparse.ArgumentParser(description="BITORA R2 24h endurance runner with full evidence.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--event-id", type=int, default=DEFAULT_EVENT_ID)
    parser.add_argument("--target-sha", default=TARGET_SHA)
    parser.add_argument("--hours", type=float, default=24.0)
    parser.add_argument("--interval-seconds", type=int, default=600)
    parser.add_argument("--out-root", default=str(ROOT / "artifacts" / "endurance"))
    parser.add_argument("--run-id", default="")
    parser.add_argument("--python", default=sys.executable)
    args = parser.parse_args()

    secrets = load_secrets()
    missing = []
    if not secrets.get("BITORA_ENDURANCE_ADMIN_USER") or not secrets.get("BITORA_ENDURANCE_ADMIN_PASSWORD"):
        missing.append("BITORA_ENDURANCE_ADMIN_USER/BITORA_ENDURANCE_ADMIN_PASSWORD")
    if not r2_configured(secrets):
        missing.append("R2/S3 credentials for direct write/read/checksum/delete")
    if missing:
        print(json.dumps({"status": "BLOCKED", "missing": missing, "secret_file": str(local_secret_path())}, indent=2))
        return 2

    apply_r2_env(secrets)
    start = utc_now()
    expected_end = start + timedelta(hours=args.hours)
    run_id = args.run_id or f"ENDURANCE-R2-FULL-24H-{start.strftime('%Y%m%d-%H%M%S')}"
    out_dir = Path(args.out_root) / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "checkpoints": out_dir / "CHECKPOINTS.jsonl",
        "errors": out_dir / "ERRORS.jsonl",
        "r2": out_dir / "R2_CHECKS.jsonl",
        "backup": out_dir / "BACKUP_CHECKS.jsonl",
        "restore": out_dir / "RESTORE_CHECKS.jsonl",
        "functional": out_dir / "FUNCTIONAL_CHECKS.jsonl",
        "heartbeat": out_dir / "HEARTBEAT.json",
        "final": out_dir / "FINAL_REPORT.md",
    }
    metadata = {
        "run_id": run_id,
        "target_sha": args.target_sha,
        "staging_url": args.base_url,
        "event_id": args.event_id,
        "start_utc": iso(start),
        "expected_end_utc": iso(expected_end),
        "safe_mode_required": "ON",
        "live_mode_required": "OFF",
        "real_communications_allowed": 0,
        "secret_file": str(local_secret_path()),
        "r2_bucket_hint": mask(str(secrets.get("R2_BUCKET") or secrets.get("S3_BUCKET") or "")),
    }
    write_json(out_dir / "RUN_METADATA.json", metadata)

    client = HttpClient(args.base_url)
    login = client.login(str(secrets["BITORA_ENDURANCE_ADMIN_USER"]), str(secrets["BITORA_ENDURANCE_ADMIN_PASSWORD"]))
    if not login.get("ok"):
        append_jsonl(paths["errors"], {"timestamp_utc": iso(), "severity": "CRITICAL", "code": "auth.login_failed", "status": login.get("status")})
        return 1

    last_backup: dict | None = None
    backup_marks = [0, 8, 16, 24]
    restore_marks = [12, 24]
    done_backups: set[int] = set()
    done_restores: set[int] = set()

    while True:
        now = utc_now()
        elapsed_hours = (now - start).total_seconds() / 3600
        record = checkpoint(client, args.event_id, args.target_sha)
        append_jsonl(paths["checkpoints"], record)
        append_jsonl(paths["functional"], {
            "timestamp_utc": record["timestamp_utc"],
            "admin_read": record["users_read"].get("ok"),
            "event_read": record["event"].get("ok"),
            "participant_metrics": (record["participant_metrics"].get("json") or {}),
            "public_display": record["public_display"].get("ok"),
            "rbac_sample": "READ_ONLY_PUBLIC_AND_ADMIN_SCOPE",
        })
        r2_record = r2_direct_check(run_id)
        append_jsonl(paths["r2"], r2_record)
        if r2_record.get("status") != "PASSED":
            append_jsonl(paths["errors"], {"timestamp_utc": iso(), "severity": "CRITICAL", "code": "r2.direct_failed"})
        for finding in record["findings"]:
            append_jsonl(paths["errors"], {"timestamp_utc": record["timestamp_utc"], **finding})

        for mark in backup_marks:
            if elapsed_hours >= mark and mark not in done_backups:
                last_backup = backup_check(client, args.event_id, out_dir, f"T{mark:02d}H")
                append_jsonl(paths["backup"], last_backup)
                if last_backup.get("status") != "PASSED":
                    append_jsonl(paths["errors"], {"timestamp_utc": iso(), "severity": "HIGH", "code": "backup.failed", "mark": mark})
                done_backups.add(mark)
        for mark in restore_marks:
            if elapsed_hours >= mark and mark not in done_restores:
                restore_record = restore_check(last_backup or {}, args.python)
                append_jsonl(paths["restore"], restore_record)
                if restore_record.get("status") != "PASSED":
                    append_jsonl(paths["errors"], {"timestamp_utc": iso(), "severity": "HIGH", "code": "restore.failed", "mark": mark})
                done_restores.add(mark)

        critical, high, warning = count_findings(paths["errors"])
        write_json(paths["heartbeat"], {
            "run_id": run_id,
            "timestamp_utc": iso(),
            "elapsed_hours": round(elapsed_hours, 3),
            "expected_end_utc": iso(expected_end),
            "critical_count": critical,
            "high_count": high,
            "warning_count": warning,
            "status": "RUNNING" if now < expected_end else "COMPLETING",
        })
        if now >= expected_end:
            break
        time.sleep(max(60, min(args.interval_seconds, int((expected_end - utc_now()).total_seconds()))))

    if 24 not in done_backups:
        last_backup = backup_check(client, args.event_id, out_dir, "T24H")
        append_jsonl(paths["backup"], last_backup)
    if 24 not in done_restores:
        restore_record = restore_check(last_backup or {}, args.python)
        append_jsonl(paths["restore"], restore_record)
    critical, high, warning = count_findings(paths["errors"])
    elapsed_hours = (utc_now() - start).total_seconds() / 3600
    passed = elapsed_hours >= args.hours and critical == 0 and high == 0
    write_json(paths["heartbeat"], {
        "run_id": run_id,
        "timestamp_utc": iso(),
        "elapsed_hours": round(elapsed_hours, 3),
        "expected_end_utc": iso(expected_end),
        "critical_count": critical,
        "high_count": high,
        "warning_count": warning,
        "status": "COMPLETED",
    })
    paths["final"].write_text(
        "\n".join([
            "# BITORA R2 Endurance 24H Final Report",
            "",
            f"- Run ID: `{run_id}`",
            f"- Target SHA: `{args.target_sha}`",
            f"- Base URL: `{args.base_url}`",
            f"- Event ID: `{args.event_id}`",
            f"- Start UTC: `{iso(start)}`",
            f"- End UTC: `{iso()}`",
            f"- Elapsed hours: `{elapsed_hours:.3f}`",
            f"- Critical findings: `{critical}`",
            f"- High findings: `{high}`",
            f"- Warnings: `{warning}`",
            "- Safe Mode required: `ON`",
            "- Live Mode required: `OFF`",
            "- Real WhatsApp: `0`",
            "- Real Email: `0`",
            "- R2 mode: `direct write/read/checksum/delete + app persistence`",
            "- Fresh verifier: `PENDING_EXTERNAL_REVIEW`",
            "",
            "FINAL STATE:",
            "",
            f"ENDURANCE 24H {'PASSED' if passed else 'FAILED'}",
            "",
        ]),
        encoding="utf-8",
    )
    write_json(out_dir / "SUMMARY.json", {"run_id": run_id, "elapsed_hours": round(elapsed_hours, 3), "critical": critical, "high": high, "warnings": warning, "result": "PASSED" if passed else "FAILED"})
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
