from __future__ import annotations

import json
import shutil
import statistics
import tempfile
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import server


STATIONS = 30
SCANS_PER_STATION_LEVELS = [1, 5, 10, 20, 40, 75, 100]
TIMEOUT_SECONDS = 20
BREAK_SUCCESS_RATE = 0.99
BREAK_P95_SECONDS = 5


def request(base: str, method: str, path: str, payload: dict | None = None) -> tuple[int, dict | str]:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as response:
            body = response.read().decode("utf-8", "ignore")
            if "application/json" in response.headers.get("Content-Type", ""):
                return response.status, json.loads(body) if body else {}
            return response.status, body
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "ignore")
        try:
            return exc.code, json.loads(body) if body else {}
        except json.JSONDecodeError:
            return exc.code, body
    except Exception as exc:
        return 0, str(exc)


def timed(call):
    start = time.perf_counter()
    status, body = call()
    return {"status": status, "body": body, "seconds": time.perf_counter() - start}


def summarize(results: list[dict], wall_seconds: float) -> dict:
    seconds = [item["seconds"] for item in results]
    ok = [item for item in results if 200 <= int(item["status"]) < 300 and item["body"].get("result") == "granted"]
    errors = [item for item in results if item not in ok]
    p95 = statistics.quantiles(seconds, n=20)[18] if len(seconds) >= 20 else max(seconds or [0])
    return {
        "total": len(results),
        "ok": len(ok),
        "errors": len(errors),
        "success_rate": len(ok) / len(results) if results else 0,
        "avg": statistics.mean(seconds) if seconds else 0,
        "p95": p95,
        "max": max(seconds or [0]),
        "wall": wall_seconds,
        "throughput": len(ok) / wall_seconds if wall_seconds else 0,
        "error_samples": [str(item["body"])[:120] for item in errors[:3]],
    }


def is_break(summary: dict) -> bool:
    return summary["success_rate"] < BREAK_SUCCESS_RATE or summary["p95"] > BREAK_P95_SECONDS or summary["errors"] > 0


def print_row(scans_per_station: int, summary: dict) -> None:
    error = " | ".join(summary["error_samples"]).replace("\n", " ")
    print(
        f"{STATIONS},{scans_per_station},{summary['total']},{summary['ok']},{summary['errors']},"
        f"{summary['success_rate']:.4f},{summary['avg']:.3f},{summary['p95']:.3f},"
        f"{summary['max']:.3f},{summary['wall']:.3f},{summary['throughput']:.1f},{error}"
    )


def format_break(value) -> str:
    if value is None:
        return "sin quiebre hasta el maximo probado"
    scans_per_station, summary = value
    return (
        f"{STATIONS} estaciones x {scans_per_station} lecturas "
        f"({summary['total']} QR); exito={summary['success_rate']:.1%}; "
        f"errores={summary['errors']}; p95={summary['p95']:.2f}s; "
        f"rendimiento={summary['throughput']:.1f} QR/s"
    )


def run_checks() -> None:
    tmp_path = Path(tempfile.mkdtemp(prefix="qr-stations-"))
    httpd = None
    try:
        server.DB_PATH = tmp_path / "stations.sqlite3"
        server.BACKUP_DIR = tmp_path / "backups"
        server.AppHandler.log_message = lambda self, format, *args: None
        server.init_db()
        server.seed_if_empty()

        httpd = server.OperationalHTTPServer(("127.0.0.1", 0), server.AppHandler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{httpd.server_address[1]}"

        prepared = request(
            base,
            "POST",
            "/api/prepare-event",
            {
                "actor": "Admin",
                "name": "30 Estaciones QR",
                "venue": "Prueba de acceso",
                "starts_at": "2026-09-01T09:00",
                "ends_at": "2026-09-01T18:00",
                "capacity": 50000,
                "description": "Prueba de puestos concurrentes",
            },
        )[1]
        event_id = int(prepared["event_id"])

        total_tokens = STATIONS * sum(SCANS_PER_STATION_LEVELS)
        tokens: list[str] = []
        for index in range(total_tokens):
            status, body = request(
                base,
                "POST",
                "/api/register",
                {
                    "actor": "Recepcion",
                    "event_id": event_id,
                    "first_name": f"QR{index}",
                    "last_name": "Estacion",
                    "email": f"station.{index}@example.test",
                    "phone": f"5491177{index:06d}",
                    "dni": str(45000000 + index),
                    "company": "Station Lab",
                    "type": "General",
                },
            )
            if status != 201:
                raise RuntimeError(f"No se pudo preparar token {index}: {status} {body}")
            tokens.append(body["token"])

        print("ESTACIONES,LECTURAS_POR_ESTACION,TOTAL_QR,OK,ERRORES,EXITO,AVG_S,P95_S,MAX_S,DURACION_S,QR_POR_SEG,MUESTRA_ERROR")
        first_break = None

        for scans_per_station in SCANS_PER_STATION_LEVELS:
            level_start = sum(STATIONS * previous for previous in SCANS_PER_STATION_LEVELS if previous < scans_per_station)
            level_tokens = tokens[level_start : level_start + STATIONS * scans_per_station]

            def station_worker(station_index: int) -> list[dict]:
                local_results = []
                start = station_index * scans_per_station
                end = start + scans_per_station
                for token in level_tokens[start:end]:
                    local_results.append(
                        timed(
                            lambda token=token: request(
                                base,
                                "POST",
                                "/api/validate",
                                {
                                    "operator": "Acceso",
                                    "checkpoint": f"Estacion {station_index + 1:02d}",
                                    "token": token,
                                },
                            )
                        )
                    )
                return local_results

            start_wall = time.perf_counter()
            results: list[dict] = []
            with ThreadPoolExecutor(max_workers=STATIONS) as pool:
                futures = [pool.submit(station_worker, station) for station in range(STATIONS)]
                for future in as_completed(futures):
                    results.extend(future.result())
            wall = time.perf_counter() - start_wall
            summary = summarize(results, wall)
            print_row(scans_per_station, summary)
            if first_break is None and is_break(summary):
                first_break = (scans_per_station, summary)

        print("")
        print("CORTE_30_ESTACIONES=" + format_break(first_break))

    finally:
        if httpd:
            httpd.shutdown()
            httpd.server_close()
        shutil.rmtree(tmp_path, ignore_errors=True)


if __name__ == "__main__":
    run_checks()
