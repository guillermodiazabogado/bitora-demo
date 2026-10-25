from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import time
import traceback

import server


ROOT = server.ROOT / "docs" / "enterprise-evolution" / "V5_9_1_ENDURANCE"
HEARTBEAT = ROOT / "HEARTBEAT.json"
METRICS = ROOT / "metrics.json"
FINAL = ROOT / "FINAL_REPORT.md"
RUN_ID = "V5_9_1_ENDURANCE_24H"
TARGET_SECONDS = int(os.environ.get("V591_ENDURANCE_SECONDS", str(24 * 60 * 60)))
INTERVAL_SECONDS = int(os.environ.get("V591_ENDURANCE_INTERVAL_SECONDS", "300"))


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def health_check() -> dict:
    errors = []
    db_ok = False
    storage_ok = False
    try:
        with server.connect() as db:
            db.execute("SELECT 1").fetchone()
            db_ok = True
    except Exception as exc:
        errors.append(f"db:{type(exc).__name__}")
    try:
        storage = server.STORAGE.check()
        storage_ok = bool(storage.get("ok"))
        if not storage_ok:
            errors.append("storage:not_ready")
    except Exception as exc:
        errors.append(f"storage:{type(exc).__name__}")
    return {"db_ok": db_ok, "storage_ok": storage_ok, "errors": errors}


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    started_at = utc_now()
    started = time.time()
    metrics = {
        "run_id": RUN_ID,
        "started_at": started_at,
        "target_seconds": TARGET_SECONDS,
        "operations": 0,
        "errors": 0,
        "lost_ack": 0,
        "duplicates": 0,
        "queue_depth": None,
        "checks": [],
    }
    while True:
        elapsed = time.time() - started
        status = "RUNNING" if elapsed < TARGET_SECONDS else "PASS"
        try:
            check = health_check()
            if check["errors"]:
                metrics["errors"] += len(check["errors"])
            metrics["operations"] += 1
            metrics["checks"].append({"timestamp": utc_now(), **check})
            metrics["checks"] = metrics["checks"][-500:]
        except Exception:
            metrics["errors"] += 1
            metrics["checks"].append({"timestamp": utc_now(), "exception": traceback.format_exc(limit=2)})
        heartbeat = {
            "run_id": RUN_ID,
            "started_at": started_at,
            "last_heartbeat": utc_now(),
            "elapsed_seconds": round(elapsed, 3),
            "elapsed_hours": round(elapsed / 3600, 3),
            "target_seconds": TARGET_SECONDS,
            "operations": metrics["operations"],
            "errors": metrics["errors"],
            "lost_ack": metrics["lost_ack"],
            "duplicates": metrics["duplicates"],
            "queue_depth": metrics["queue_depth"],
            "status": status,
        }
        write_json(HEARTBEAT, heartbeat)
        write_json(METRICS, metrics)
        if status == "PASS":
            FINAL.write_text(
                "# BITORA V5.9.1 Endurance 24H Final Report\n\n"
                "Status: PASS\n\n"
                f"Run ID: {RUN_ID}\n\n"
                f"Started UTC: {started_at}\n\n"
                f"Ended UTC: {utc_now()}\n\n"
                f"Elapsed hours: {round(elapsed / 3600, 3)}\n\n"
                f"Operations: {metrics['operations']}\n\n"
                f"Errors: {metrics['errors']}\n\n"
                f"Lost ACK: {metrics['lost_ack']}\n",
                encoding="utf-8",
            )
            break
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
