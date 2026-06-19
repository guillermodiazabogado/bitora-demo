from __future__ import annotations

import argparse
import json
import time

import server
from rc1_utils import RC1Harness, memory_snapshot, start_memory, timed_request


def main() -> None:
    parser = argparse.ArgumentParser(description="Soak test real y liviano de BITORA")
    parser.add_argument("--minutes", type=float, default=480, help="Duracion real; por defecto 8 horas")
    parser.add_argument("--interval", type=float, default=5, help="Segundos entre ciclos")
    args = parser.parse_args()
    run = RC1Harness("bitora-rc1-soak-")
    try:
        run.start()
        start_memory()
        initial = memory_snapshot()
        deadline = time.time() + max(1, args.minutes * 60)
        cycles = 0
        errors = 0
        response_times = []
        log_start = 0
        with server.connect() as db:
            log_start = int(db.execute("SELECT COUNT(*) AS c FROM technical_logs").fetchone()["c"] or 0)
        while time.time() < deadline:
            for path in (
                f"/api/summary?event_id={run.event_id}",
                f"/api/reports/visual-summary?event_id={run.event_id}",
                f"/api/data-visualization?event_id={run.event_id}&period=today",
                f"/api/public-display?event_id={run.event_id}",
                "/health",
            ):
                sample = timed_request(run.base, "GET", path)
                response_times.append(sample["seconds"])
                if sample["status"] != 200:
                    errors += 1
            cycles += 1
            time.sleep(max(0.05, args.interval))
        final = memory_snapshot()
        with server.connect() as db:
            log_end = int(db.execute("SELECT COUNT(*) AS c FROM technical_logs").fetchone()["c"] or 0)
            jobs = dict(
                db.execute(
                    """
                    SELECT
                      SUM(CASE WHEN status IN ('pending','processing','retrying') THEN 1 ELSE 0 END) AS pending,
                      SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed
                    FROM jobs
                    """
                ).fetchone()
            )
        result = {
            "real_minutes": args.minutes,
            "cycles": cycles,
            "errors": errors,
            "average_response_seconds": round(sum(response_times) / max(len(response_times), 1), 4),
            "memory_growth_bytes": final["current_bytes"] - initial["current_bytes"],
            "technical_log_growth": log_end - log_start,
            "cache": server.cache_snapshot(),
            "jobs": {key: int(value or 0) for key, value in jobs.items()},
        }
        assert errors == 0
        assert result["memory_growth_bytes"] < 64 * 1024 * 1024
        assert result["jobs"]["pending"] == 0 and result["jobs"]["failed"] == 0
        print("OK: soak test continuo")
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        run.cleanup()


if __name__ == "__main__":
    main()
