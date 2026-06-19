from __future__ import annotations

import json
import statistics
import time
import tracemalloc
from pathlib import Path

import server
from qa2_utils import Harness, percentile, request


class RC1Harness:
    def __init__(self, prefix: str) -> None:
        self.harness = Harness(prefix)
        self.worker = None
        self.event_id = 0

    @property
    def base(self) -> str:
        return self.harness.base

    def start(self) -> None:
        self.harness.start()
        self.worker = server.start_job_worker()
        status, result = request(
            self.base,
            "POST",
            "/api/demo-real",
            {"actor": "Admin", "confirm": "DEMO"},
            timeout=120,
        )
        if status != 201:
            raise AssertionError(f"No se pudo crear Demo 1000: {status} {result}")
        self.event_id = int(result["event_id"])
        with server.connect() as db:
            for index in range(1, 31):
                db.execute(
                    """
                    INSERT INTO users (name, role, pin_hash, active, created_at)
                    VALUES (?, 'Operador de acceso', '', 1, ?)
                    ON CONFLICT(name) DO UPDATE SET role = 'Operador de acceso', active = 1
                    """,
                    (f"Terminal-{index}", server.now_iso()),
                )
            db.execute(
                """
                INSERT INTO users (name, role, pin_hash, active, created_at)
                VALUES ('Terminal-Rechazos', 'Operador de acceso', '', 1, ?)
                ON CONFLICT(name) DO UPDATE SET role = 'Operador de acceso', active = 1
                """,
                (server.now_iso(),),
            )

    def cleanup(self) -> None:
        if self.worker:
            self.worker.stop()
            self.worker = None
        self.harness.cleanup()

    def unused_tokens(self) -> list[str]:
        with server.connect() as db:
            return [
                row["token"]
                for row in db.execute(
                    """
                    SELECT a.token
                    FROM accreditations a
                    WHERE a.event_id = ?
                      AND a.status <> 'cancelled'
                      AND NOT EXISTS (
                        SELECT 1 FROM access_logs l
                        WHERE l.accreditation_id = a.id AND l.result = 'granted'
                      )
                    ORDER BY a.id
                    """,
                    (self.event_id,),
                ).fetchall()
            ]


def timed_request(base: str, method: str, path: str, payload: dict | None = None, timeout: int = 60) -> dict:
    started = time.perf_counter()
    status, body = request(base, method, path, payload, timeout=timeout)
    return {"status": status, "body": body, "seconds": time.perf_counter() - started, "path": path}


def timing_summary(samples: list[dict]) -> dict:
    values = [float(item["seconds"]) for item in samples]
    return {
        "count": len(values),
        "average_seconds": round(statistics.mean(values), 4) if values else 0,
        "p95_seconds": round(percentile(values, 0.95), 4) if values else 0,
        "max_seconds": round(max(values), 4) if values else 0,
        "errors": sum(1 for item in samples if not 200 <= int(item["status"]) < 300),
    }


def start_memory() -> tuple[int, int]:
    tracemalloc.start()
    return tracemalloc.get_traced_memory()


def memory_snapshot() -> dict:
    current, peak = tracemalloc.get_traced_memory()
    return {"current_bytes": current, "peak_bytes": peak}


def wait_for_jobs(timeout_seconds: float = 20) -> dict:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        with server.connect() as db:
            row = db.execute(
                """
                SELECT
                    SUM(CASE WHEN status IN ('pending', 'processing', 'retrying') THEN 1 ELSE 0 END) AS pending,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed
                FROM jobs
                """
            ).fetchone()
        result = {key: int(row[key] or 0) for key in row.keys()}
        if result["pending"] == 0:
            return result
        time.sleep(0.1)
    return result


def write_json(path: str | Path, payload: dict) -> None:
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
