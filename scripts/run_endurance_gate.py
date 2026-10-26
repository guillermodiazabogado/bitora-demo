from __future__ import annotations

import argparse
import json
import shutil
import tempfile
import time
import tracemalloc
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import server


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="BITORA wall-clock access endurance gate")
    duration = parser.add_mutually_exclusive_group(required=True)
    duration.add_argument("--hours", type=float)
    duration.add_argument("--seconds", type=float)
    parser.add_argument("--participants", type=int, default=20)
    parser.add_argument("--pause-ms", type=int, default=50)
    parser.add_argument("--report", type=Path, required=True)
    return parser.parse_args()


def run(args: argparse.Namespace) -> dict:
    duration_seconds = float(args.seconds if args.seconds is not None else args.hours * 3600)
    if duration_seconds <= 0 or args.participants <= 0 or args.pause_ms < 0:
        raise ValueError("duration, participants and pause must be valid positive values")
    workspace_tmp = ROOT / "tmp"
    workspace_tmp.mkdir(exist_ok=True)
    temp_root = Path(tempfile.mkdtemp(prefix="bitora-endurance-", dir=workspace_tmp))
    original_db_path = server.DB_PATH
    original_backup_dir = server.BACKUP_DIR
    started_at = utc_now()
    started = time.monotonic()
    operations = 0
    failures: list[dict] = []
    tracemalloc.start()
    try:
        server.DB_PATH = temp_root / "endurance.sqlite3"
        server.BACKUP_DIR = temp_root / "backups"
        server.init_db()
        server.seed_if_empty()
        tokens: list[str] = []
        with server.connect() as db:
            event_id = int(db.execute("SELECT id FROM events ORDER BY id LIMIT 1").fetchone()["id"])
            for index in range(args.participants):
                registered = server.register_accreditation(
                    db,
                    event_id,
                    {
                        "first_name": "Endurance",
                        "last_name": str(index),
                        "email": f"endurance-{index}@bitora.test",
                        "type": "General",
                        "actor": "endurance-gate",
                    },
                )
                if not registered.get("ok"):
                    raise RuntimeError(f"participant seed failed: {registered}")
                tokens.append(str(registered["token"]))
            activated = server.set_access_state_enforcement(db, event_id, enabled=True, actor="endurance-gate")
            if not activated.get("ok"):
                raise RuntimeError(f"access activation failed: {activated}")

        states = {token: "OUTSIDE" for token in tokens}
        index = 0
        while time.monotonic() - started < duration_seconds:
            token = tokens[index % len(tokens)]
            direction = "ENTRY" if states[token] == "OUTSIDE" else "EXIT"
            try:
                with server.DB_LOCK, server.connect() as db:
                    db.execute("BEGIN IMMEDIATE")
                    scope = server.access_event_scope(db, token)
                    result = server.enforced_access_validation(
                        db,
                        token=token,
                        operator="Endurance Gate",
                        checkpoint="Endurance",
                        activity_id=0,
                        direction=direction,
                        correlation_id=f"endurance-{operations}",
                        idempotency_key=f"endurance-{operations}",
                        data={},
                        event_scope=scope,
                    )
                    if result.get("result") != "granted":
                        raise RuntimeError(f"unexpected decision: {result}")
                    db.execute("COMMIT")
                states[token] = "INSIDE" if direction == "ENTRY" else "OUTSIDE"
                operations += 1
            except Exception as exc:
                failures.append({"operation": operations, "error": type(exc).__name__, "detail": str(exc)[:300]})
                if len(failures) >= 10:
                    break
            index += 1
            if args.pause_ms:
                time.sleep(args.pause_ms / 1000)

        elapsed = time.monotonic() - started
        current_memory, peak_memory = tracemalloc.get_traced_memory()
        with server.connect() as db:
            integrity = str(db.execute("PRAGMA integrity_check").fetchone()[0])
            persisted = int(db.execute("SELECT COUNT(*) AS c FROM enterprise_access_events").fetchone()["c"])
        return {
            "ok": not failures and integrity == "ok" and persisted == operations,
            "started_at": started_at,
            "finished_at": utc_now(),
            "requested_duration_seconds": duration_seconds,
            "elapsed_seconds": round(elapsed, 3),
            "participants": len(tokens),
            "operations": operations,
            "persisted_access_events": persisted,
            "database_integrity": integrity,
            "memory_current_bytes": current_memory,
            "memory_peak_bytes": peak_memory,
            "failures": failures,
            "scope": "isolated SQLite wall-clock endurance; no external services",
        }
    finally:
        tracemalloc.stop()
        server.DB_PATH = original_db_path
        server.BACKUP_DIR = original_backup_dir
        shutil.rmtree(temp_root, ignore_errors=True)


def main() -> None:
    args = parse_args()
    report = run(args)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    if not report["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
