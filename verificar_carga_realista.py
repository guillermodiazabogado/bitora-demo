from __future__ import annotations

import json
import time

import server
from rc1_utils import RC1Harness, memory_snapshot, start_memory, timed_request, timing_summary, wait_for_jobs


def main() -> None:
    run = RC1Harness("bitora-rc1-realistic-")
    qr_samples: list[dict] = []
    read_samples: list[dict] = []
    try:
        run.start()
        tokens = run.unused_tokens()
        start_memory()
        initial = memory_snapshot()
        index = 0
        # Ocho franjas operativas: apertura, pico, valle, actividades y cierre.
        load_pattern = [1, 2, 4, 6, 3, 1, 4, 2]
        for hour, scans_per_cycle in enumerate(load_pattern):
            for cycle in range(12):
                if cycle % 3 == 0:
                    read_samples.append(timed_request(run.base, "GET", f"/api/summary?event_id={run.event_id}"))
                    read_samples.append(timed_request(run.base, "GET", f"/api/summary?event_id={run.event_id}"))
                if cycle % 6 == 0:
                    read_samples.append(timed_request(run.base, "GET", f"/api/reports/visual-summary?event_id={run.event_id}"))
                    read_samples.append(timed_request(run.base, "GET", f"/api/reports/visual-summary?event_id={run.event_id}"))
                    read_samples.append(timed_request(run.base, "GET", f"/api/data-visualization?event_id={run.event_id}&period=today"))
                    read_samples.append(timed_request(run.base, "GET", f"/api/data-visualization?event_id={run.event_id}&period=today"))
                for local in range(scans_per_cycle):
                    if index >= len(tokens):
                        break
                    qr_samples.append(
                        timed_request(
                            run.base,
                            "POST",
                            "/api/validate",
                            {
                                "operator": f"Terminal-{(hour * 4 + local) % 12 + 1}",
                                "checkpoint": "Ingreso",
                                "token": tokens[index],
                            },
                        )
                    )
                    index += 1
            if hour in {2, 6}:
                server.job_queue_service().enqueue(
                    "export.generate",
                    {"event_id": run.event_id},
                    actor="rc1-realistic",
                    event_id=run.event_id,
                )
        jobs = wait_for_jobs()
        final = memory_snapshot()
        result = {
            "hours_simulated": 8,
            "qr": timing_summary(qr_samples),
            "reads": timing_summary(read_samples),
            "cache": server.cache_snapshot(),
            "jobs": jobs,
            "memory_growth_bytes": final["current_bytes"] - initial["current_bytes"],
        }
        assert result["qr"]["errors"] == 0
        assert result["qr"]["average_seconds"] < 0.5 and result["qr"]["p95_seconds"] < 1
        assert jobs["pending"] == 0 and jobs["failed"] == 0
        assert result["memory_growth_bytes"] < 48 * 1024 * 1024
        print("OK: carga realista intermitente equivalente a 8 horas")
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        run.cleanup()


if __name__ == "__main__":
    main()
