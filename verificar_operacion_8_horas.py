from __future__ import annotations

import json
import time
from pathlib import Path

import server
from rc1_utils import RC1Harness, memory_snapshot, start_memory, timed_request, timing_summary, wait_for_jobs, write_json


REPORT_JSON = Path("output/rc1_operation_8h.json")


def main() -> None:
    run = RC1Harness("bitora-rc1-8h-")
    qr_samples: list[dict] = []
    dashboard_samples: list[dict] = []
    visual_samples: list[dict] = []
    noc_samples: list[dict] = []
    errors: list[str] = []
    started_wall = time.perf_counter()
    started_cpu = time.process_time()
    try:
        run.start()
        tokens = run.unused_tokens()
        start_memory()
        memory_initial = memory_snapshot()
        token_index = 0

        # 96 bloques de 5 minutos equivalen a 8 horas operativas.
        for block in range(96):
            dashboard_samples.append(timed_request(run.base, "GET", f"/api/summary?event_id={run.event_id}"))
            dashboard_samples.append(timed_request(run.base, "GET", f"/api/summary?event_id={run.event_id}"))
            if block % 2 == 0:
                visual_samples.append(timed_request(run.base, "GET", f"/api/reports/visual-summary?event_id={run.event_id}"))
                visual_samples.append(timed_request(run.base, "GET", f"/api/reports/visual-summary?event_id={run.event_id}"))
                visual_samples.append(timed_request(run.base, "GET", f"/api/data-visualization?event_id={run.event_id}&period=today&dashboard=operational"))
                visual_samples.append(timed_request(run.base, "GET", f"/api/data-visualization?event_id={run.event_id}&period=today&dashboard=operational"))
            if block % 3 == 0:
                noc_samples.append(timed_request(run.base, "GET", "/api/diagnostics/status"))
                noc_samples.append(timed_request(run.base, "GET", f"/api/public-display?event_id={run.event_id}"))

            scans = 6 if 30 <= block <= 54 else 3
            for local_index in range(scans):
                if token_index >= len(tokens):
                    break
                sample = timed_request(
                    run.base,
                    "POST",
                    "/api/validate",
                    {
                        "operator": f"Terminal-{(block + local_index) % 30 + 1}",
                        "checkpoint": "Acceso general",
                        "token": tokens[token_index],
                    },
                )
                token_index += 1
                qr_samples.append(sample)
                if sample["status"] != 200 or sample["body"].get("result") != "granted":
                    errors.append(f"QR: {sample['status']} {sample['body']}")

            if block % 8 == 0:
                timed_request(
                    run.base,
                    "POST",
                    "/api/validate",
                    {"operator": "Terminal-Rechazos", "checkpoint": "Acceso general", "token": f"INVALIDO-{block}"},
                )
                with server.connect() as db:
                    person = db.execute(
                        """
                        SELECT a.person_id, a.id AS accreditation_id
                        FROM accreditations a WHERE a.event_id = ? ORDER BY a.id LIMIT 1
                        """,
                        (run.event_id,),
                    ).fetchone()
                    db.execute(
                        """
                        INSERT INTO communication_logs (
                            event_id, person_id, accreditation_id, canal, fecha, tipo,
                            asunto, contenido, estado
                        ) VALUES (?, ?, ?, 'email', ?, 'recordatorio', 'RC1',
                                  'Comunicacion demo sostenida', 'demo')
                        """,
                        (run.event_id, person["person_id"], person["accreditation_id"], server.now_iso()),
                    )
            if block in {24, 72}:
                server.job_queue_service().enqueue(
                    "backup.create",
                    {},
                    priority="low",
                    actor="rc1",
                    event_id=run.event_id,
                )
            if block in {12, 48, 84}:
                server.job_queue_service().enqueue(
                    "export.generate",
                    {"event_id": run.event_id},
                    priority="low",
                    actor="rc1",
                    event_id=run.event_id,
                )

        jobs = wait_for_jobs()
        memory_final = memory_snapshot()
        cache = server.cache_snapshot()
        runtime = server.RUNTIME_METRICS.snapshot()
        with server.connect() as db:
            db_state = dict(
                db.execute(
                    """
                    SELECT
                        COUNT(*) AS access_logs,
                        SUM(CASE WHEN result = 'granted' THEN 1 ELSE 0 END) AS granted,
                        SUM(CASE WHEN result = 'rejected' THEN 1 ELSE 0 END) AS rejected
                    FROM access_logs WHERE event_id = ?
                    """,
                    (run.event_id,),
                ).fetchone()
            )
            technical_errors = int(
                db.execute("SELECT COUNT(*) AS c FROM technical_logs WHERE level IN ('error', 'critical')").fetchone()["c"] or 0
            )
            duplicate_tokens = int(
                db.execute(
                    "SELECT COUNT(*) AS c FROM (SELECT token FROM accreditations GROUP BY token HAVING COUNT(*) > 1)"
                ).fetchone()["c"]
                or 0
            )

        result = {
            "simulated_hours": 8,
            "participants": 1000,
            "terminals": 30,
            "wall_seconds": round(time.perf_counter() - started_wall, 2),
            "cpu_seconds": round(time.process_time() - started_cpu, 2),
            "memory_initial": memory_initial,
            "memory_final": memory_final,
            "memory_growth_bytes": memory_final["current_bytes"] - memory_initial["current_bytes"],
            "qr": timing_summary(qr_samples),
            "dashboard": timing_summary(dashboard_samples),
            "visualization": timing_summary(visual_samples),
            "noc": timing_summary(noc_samples),
            "cache": cache,
            "jobs": jobs,
            "database": db_state,
            "runtime": runtime,
            "technical_errors": technical_errors,
            "duplicate_tokens": duplicate_tokens,
            "errors": errors,
        }
        REPORT_JSON.parent.mkdir(exist_ok=True)
        write_json(REPORT_JSON, result)
        assert result["qr"]["average_seconds"] < 0.5
        assert result["qr"]["p95_seconds"] < 1
        assert not errors and technical_errors == 0
        assert jobs["pending"] == 0 and jobs["failed"] == 0
        assert duplicate_tokens == 0
        assert result["memory_growth_bytes"] < 64 * 1024 * 1024
        assert cache["hits"] > 0 and cache["hit_rate"] >= 40
        print("OK: operacion acelerada equivalente a 8 horas")
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        run.cleanup()


if __name__ == "__main__":
    main()
