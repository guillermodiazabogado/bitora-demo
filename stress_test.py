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


LEVELS = [100, 200, 400, 600, 800, 1000]
TIMEOUT_SECONDS = 20
BREAK_SUCCESS_RATE = 0.99
BREAK_P95_SECONDS = 10


def request(base: str, method: str, path: str, payload: dict | None = None, timeout: int = TIMEOUT_SECONDS) -> tuple[int, dict | str]:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
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
    return {
        "status": status,
        "body": body,
        "seconds": time.perf_counter() - start,
    }


def summarize(results: list[dict]) -> dict:
    seconds = [item["seconds"] for item in results]
    ok = [item for item in results if 200 <= int(item["status"]) < 300]
    errors = [item for item in results if not (200 <= int(item["status"]) < 300)]
    p95 = statistics.quantiles(seconds, n=20)[18] if len(seconds) >= 20 else max(seconds or [0])
    return {
        "total": len(results),
        "ok": len(ok),
        "errors": len(errors),
        "success_rate": len(ok) / len(results) if results else 0,
        "avg": statistics.mean(seconds) if seconds else 0,
        "p95": p95,
        "max": max(seconds or [0]),
        "error_samples": [str(item["body"])[:120] for item in errors[:3]],
    }


def run_parallel(total: int, worker):
    with ThreadPoolExecutor(max_workers=total) as pool:
        futures = [pool.submit(worker, index) for index in range(total)]
        return [future.result() for future in as_completed(futures)]


def run_checks() -> None:
    tmp_path = Path(tempfile.mkdtemp(prefix="qr-stress-"))
    httpd = None
    try:
        server.DB_PATH = tmp_path / "stress.sqlite3"
        server.BACKUP_DIR = tmp_path / "backups"
        server.AppHandler.log_message = lambda self, format, *args: None
        server.init_db()
        server.seed_if_empty()

        httpd = server.OperationalHTTPServer(("127.0.0.1", 0), server.AppHandler)
        port = httpd.server_address[1]
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{port}"

        prepared = request(
            base,
            "POST",
            "/api/prepare-event",
            {
                "actor": "Admin",
                "name": "Stress Test",
                "venue": "Banco de prueba",
                "starts_at": "2026-09-01T09:00",
                "ends_at": "2026-09-01T18:00",
                "capacity": 100000,
                "description": "Carga concurrente",
            },
        )[1]
        event_id = int(prepared["event_id"])

        print("NIVEL,OPERACION,TOTAL,OK,ERRORES,EXITO,AVG_S,P95_S,MAX_S,MUESTRA_ERROR")
        registration_break = None
        validation_break = None

        token_pool: list[str] = []
        email_counter = 0

        for level in LEVELS:
            base_email = email_counter
            email_counter += level

            def register_worker(index: int):
                unique = base_email + index
                return timed(
                    lambda: request(
                        base,
                        "POST",
                        "/api/register",
                        {
                            "actor": "public",
                            "event_id": event_id,
                            "first_name": f"Nombre{unique}",
                            "last_name": f"Carga{unique}",
                            "email": f"stress.{unique}@example.test",
                            "phone": f"5491161{unique:06d}",
                            "dni": str(40000000 + unique),
                            "company": "Stress Lab",
                            "type": "General",
                        },
                    )
                )

            reg_results = run_parallel(level, register_worker)
            reg_summary = summarize(reg_results)
            token_pool.extend([item["body"].get("token") for item in reg_results if item["status"] == 201 and isinstance(item["body"], dict)])
            print_row(level, "inscripcion", reg_summary)
            if registration_break is None and is_break(reg_summary):
                registration_break = (level, reg_summary)

            validation_tokens = token_pool[-level:]

            def validate_worker(index: int):
                token = validation_tokens[index]
                return timed(
                    lambda: request(
                        base,
                        "POST",
                        "/api/validate",
                        {
                            "operator": "Acceso",
                            "checkpoint": "Stress",
                            "token": token,
                        },
                    )
                )

            val_results = run_parallel(len(validation_tokens), validate_worker)
            val_summary = summarize(val_results)
            print_row(level, "validacion_qr", val_summary)
            if validation_break is None and is_break(val_summary):
                validation_break = (level, val_summary)

        print("")
        print("CORTE_INSCRIPCION=" + format_break(registration_break))
        print("CORTE_VALIDACION_QR=" + format_break(validation_break))

    finally:
        if httpd:
            httpd.shutdown()
            httpd.server_close()
        shutil.rmtree(tmp_path, ignore_errors=True)


def is_break(summary: dict) -> bool:
    return summary["success_rate"] < BREAK_SUCCESS_RATE or summary["p95"] > BREAK_P95_SECONDS or summary["errors"] > 0


def format_break(value) -> str:
    if value is None:
        return "sin quiebre hasta el maximo probado"
    level, summary = value
    return f"{level} concurrentes; exito={summary['success_rate']:.1%}; errores={summary['errors']}; p95={summary['p95']:.2f}s"


def print_row(level: int, operation: str, summary: dict) -> None:
    error = " | ".join(summary["error_samples"]).replace("\n", " ")
    print(
        f"{level},{operation},{summary['total']},{summary['ok']},{summary['errors']},"
        f"{summary['success_rate']:.4f},{summary['avg']:.3f},{summary['p95']:.3f},{summary['max']:.3f},{error}"
    )


if __name__ == "__main__":
    run_checks()
