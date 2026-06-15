from __future__ import annotations

import json
import random
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


PY_TIMEOUT = 20


class SuiteFailed(Exception):
    pass


class Harness:
    def __init__(self) -> None:
        self.tmp_path = Path(tempfile.mkdtemp(prefix="qr-robustez-"))
        self.httpd: server.OperationalHTTPServer | None = None
        self.thread: threading.Thread | None = None
        self.base = ""

    def start(self) -> None:
        server.DB_PATH = self.tmp_path / "robustez.sqlite3"
        server.BACKUP_DIR = self.tmp_path / "backups"
        server.AppHandler.log_message = lambda self, format, *args: None
        server.init_db()
        server.seed_if_empty()
        self.httpd = server.OperationalHTTPServer(("127.0.0.1", 0), server.AppHandler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"

    def stop(self) -> None:
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None
        if self.thread:
            self.thread.join(timeout=5)
            self.thread = None

    def restart(self) -> None:
        self.stop()
        self.httpd = server.OperationalHTTPServer(("127.0.0.1", 0), server.AppHandler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"

    def cleanup(self) -> None:
        self.stop()
        shutil.rmtree(self.tmp_path, ignore_errors=True)


def request(base: str, method: str, path: str, payload: dict | None = None, parse_json: bool = True, timeout: int = PY_TIMEOUT) -> tuple[int, dict | str | bytes, str]:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            body = response.read()
            content_type = response.headers.get("Content-Type", "")
            if parse_json and "application/json" in content_type:
                return response.status, json.loads(body.decode("utf-8")) if body else {}, content_type
            return response.status, body, content_type
    except urllib.error.HTTPError as exc:
        body = exc.read()
        content_type = exc.headers.get("Content-Type", "")
        if parse_json and "application/json" in content_type:
            return exc.code, json.loads(body.decode("utf-8")) if body else {}, content_type
        return exc.code, body.decode("utf-8", "ignore"), content_type
    except Exception as exc:
        return 0, str(exc), ""


def expect(status: int, expected: int, body, label: str) -> None:
    if status != expected:
        raise SuiteFailed(f"{label}: esperado HTTP {expected}, recibido {status}: {body}")


def timed(call):
    start = time.perf_counter()
    status, body, content_type = call()
    return {"status": status, "body": body, "content_type": content_type, "seconds": time.perf_counter() - start}


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0
    values = sorted(values)
    index = min(len(values) - 1, int(round((len(values) - 1) * p)))
    return values[index]


def summarize(results: list[dict], success) -> dict:
    seconds = [row["seconds"] for row in results]
    ok = [row for row in results if success(row)]
    errors = [row for row in results if row not in ok]
    return {
        "total": len(results),
        "ok": len(ok),
        "errors": len(errors),
        "success_rate": len(ok) / len(results) if results else 0,
        "avg": statistics.mean(seconds) if seconds else 0,
        "p95": percentile(seconds, 0.95),
        "max": max(seconds or [0]),
        "samples": [str(row["body"])[:100] for row in errors[:3]],
    }


def print_metric(name: str, summary: dict) -> None:
    print(
        f"  {name}: total={summary['total']} ok={summary['ok']} errores={summary['errors']} "
        f"exito={summary['success_rate']:.1%} avg={summary['avg']:.3f}s "
        f"p95={summary['p95']:.3f}s max={summary['max']:.3f}s"
    )
    if summary["samples"]:
        print(f"    muestras_error={summary['samples']}")


def prepare_event(h: Harness, name: str = "Robustez") -> int:
    status, body, _ = request(
        h.base,
        "POST",
        "/api/prepare-event",
        {
            "actor": "Admin",
            "name": name,
            "venue": "Laboratorio",
            "starts_at": "2026-10-01T09:00",
            "ends_at": "2026-10-01T20:00",
            "capacity": 50000,
            "description": "Prueba automatica de robustez",
        },
    )
    expect(status, 200, body, "prepare-event")
    return int(body["event_id"])


def register_one(h: Harness, event_id: int, index: int, prefix: str = "persona") -> str:
    status, body, _ = request(
        h.base,
        "POST",
        "/api/register",
        {
            "actor": "Recepcion",
            "event_id": event_id,
            "first_name": f"Nombre{index}",
            "last_name": f"Apellido{index}",
            "email": f"{prefix}.{index}@example.test",
            "phone": f"5491160{index:06d}",
            "dni": str(30000000 + index),
            "company": "Robustez Lab",
            "type": "General",
        },
    )
    expect(status, 201, body, "register")
    return body["token"]


def seed_tokens(h: Harness, event_id: int, total: int, prefix: str) -> list[str]:
    return [register_one(h, event_id, index, prefix) for index in range(total)]


def validate_token(h: Harness, token: str, station: str = "Estacion") -> tuple[int, dict | str | bytes, str]:
    return request(
        h.base,
        "POST",
        "/api/validate",
        {"operator": "Acceso", "checkpoint": station, "token": token},
    )


def test_30_stations_spike(h: Harness) -> None:
    print("1) 30 estaciones de QR en paralelo")
    event_id = prepare_event(h, "30 estaciones")
    stations = 30
    scans_per_station = 100
    tokens = seed_tokens(h, event_id, stations * scans_per_station, "station")

    def station_worker(station_index: int) -> list[dict]:
        out = []
        start = station_index * scans_per_station
        end = start + scans_per_station
        for token in tokens[start:end]:
            out.append(timed(lambda token=token, station_index=station_index: validate_token(h, token, f"Estacion {station_index + 1:02d}")))
        return out

    started = time.perf_counter()
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=stations) as pool:
        futures = [pool.submit(station_worker, index) for index in range(stations)]
        for future in as_completed(futures):
            results.extend(future.result())
    wall = time.perf_counter() - started
    summary = summarize(results, lambda row: row["status"] == 200 and row["body"].get("result") == "granted")
    print_metric("30 estaciones x 100 lecturas", summary)
    print(f"  rendimiento={summary['ok'] / wall:.1f} QR/s duracion={wall:.2f}s")
    if summary["errors"] or summary["p95"] > 1.5:
        raise SuiteFailed("30 estaciones no mantuvo estabilidad operativa")


def test_mixed_operation(h: Harness) -> None:
    print("2) Operacion mixta: inscripcion + QR + busqueda + backup/export")
    event_id = prepare_event(h, "Mixta")
    tokens = seed_tokens(h, event_id, 1500, "mixed")
    results: list[dict] = []
    lock = threading.Lock()

    def add(row: dict) -> None:
        with lock:
            results.append(row)

    def qr_worker(station: int) -> None:
        for token in tokens[station::30][:40]:
            add(timed(lambda token=token, station=station: validate_token(h, token, f"Mixta {station + 1:02d}")))

    def registration_worker(worker: int) -> None:
        for i in range(40):
            unique = worker * 1000 + i
            add(
                timed(
                    lambda unique=unique: request(
                        h.base,
                        "POST",
                        "/api/register",
                        {
                            "actor": "public",
                            "event_id": event_id,
                            "first_name": f"Pub{unique}",
                            "last_name": "Mixta",
                            "email": f"public.mixta.{unique}@example.test",
                            "type": "General",
                        },
                    )
                )
            )

    def read_worker() -> None:
        for _ in range(60):
            q = random.choice(["", "mixed", "Nombre", "Pub", "Robustez"])
            add(timed(lambda q=q: request(h.base, "GET", f"/api/accreditations?event_id={event_id}&q={q}&limit=2000")))
            time.sleep(0.02)

    def export_worker() -> None:
        paths = ["/api/backup", f"/api/export.csv?event_id={event_id}", f"/api/export.json?event_id={event_id}", f"/api/summary?event_id={event_id}"]
        for path in paths * 3:
            add(timed(lambda path=path: request(h.base, "GET", path, parse_json=not path.endswith("backup"))))
            time.sleep(0.05)

    workers = []
    with ThreadPoolExecutor(max_workers=46) as pool:
        workers.extend(pool.submit(qr_worker, station) for station in range(30))
        workers.extend(pool.submit(registration_worker, worker) for worker in range(10))
        workers.extend(pool.submit(read_worker) for _ in range(5))
        workers.append(pool.submit(export_worker))
        for future in as_completed(workers):
            future.result()

    summary = summarize(results, lambda row: 200 <= row["status"] < 300)
    print_metric("mixta", summary)
    if summary["success_rate"] < 0.995 or summary["p95"] > 5:
        raise SuiteFailed("La operacion mixta degrado por debajo del umbral")


def test_duplicate_qr_race(h: Harness) -> None:
    print("3) Doble lectura simultanea del mismo QR")
    event_id = prepare_event(h, "QR duplicado")
    token = register_one(h, event_id, 1, "race")

    with ThreadPoolExecutor(max_workers=200) as pool:
        futures = [pool.submit(lambda: timed(lambda: validate_token(h, token, "Duplicado"))) for _ in range(1000)]
        results = [future.result() for future in as_completed(futures)]

    granted = sum(1 for row in results if row["status"] == 200 and row["body"].get("result") == "granted")
    used = sum(1 for row in results if row["status"] == 200 and row["body"].get("reason") == "QR ya utilizado")
    others = len(results) - granted - used
    print(f"  total=1000 concedidos={granted} rechazados_por_usado={used} otros={others}")
    if granted != 1 or used != 999 or others:
        raise SuiteFailed("La carrera de QR duplicado no fue atomica")


def test_large_base(h: Harness) -> None:
    print("4) Base grande: busqueda, validacion, resumen e impresion")
    event_id = prepare_event(h, "Base grande")
    total = 10000
    with server.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        for index in range(total):
            registration = server.register_accreditation(
                db,
                event_id,
                {
                    "first_name": f"Nombre{index}",
                    "last_name": f"Grande{index % 500}",
                    "email": f"large.{index}@example.test",
                    "phone": f"5491188{index:06d}",
                    "dni": str(50000000 + index),
                    "company": f"Empresa {index % 40}",
                    "type": "General",
                },
            )
            if not registration["ok"]:
                raise SuiteFailed(f"No se pudo sembrar base grande: {registration}")
        db.execute("COMMIT")

    checks = [
        timed(lambda: request(h.base, "GET", f"/api/accreditations?event_id={event_id}&q=Grande1&limit=2000")),
        timed(lambda: request(h.base, "GET", f"/api/summary?event_id={event_id}")),
        timed(lambda: request(h.base, "GET", f"/print.html?event_id={event_id}", parse_json=False)),
    ]
    first_token = request(h.base, "GET", f"/api/accreditations?event_id={event_id}&limit=1")[1][0]["token"]
    checks.append(timed(lambda: validate_token(h, first_token, "Base grande")))
    summary = summarize(checks, lambda row: 200 <= row["status"] < 300)
    print_metric("base 10000", summary)
    if summary["errors"] or summary["p95"] > 3:
        raise SuiteFailed("La base grande respondio fuera de umbral")


def test_backup_during_access(h: Harness) -> None:
    print("5) Backup y exportaciones durante acreditacion")
    event_id = prepare_event(h, "Backup bajo carga")
    tokens = seed_tokens(h, event_id, 900, "backup")
    results: list[dict] = []
    lock = threading.Lock()

    def add(row: dict) -> None:
        with lock:
            results.append(row)

    def qr_worker(station: int) -> None:
        for token in tokens[station::30]:
            add(timed(lambda token=token, station=station: validate_token(h, token, f"Backup {station + 1:02d}")))

    def export_worker() -> None:
        for path in ["/api/backup", f"/api/export.csv?event_id={event_id}", f"/api/export.json?event_id={event_id}"] * 4:
            add(timed(lambda path=path: request(h.base, "GET", path, parse_json=path.endswith(".json"))))

    with ThreadPoolExecutor(max_workers=31) as pool:
        futures = [pool.submit(qr_worker, station) for station in range(30)]
        futures.append(pool.submit(export_worker))
        for future in as_completed(futures):
            future.result()

    summary = summarize(results, lambda row: 200 <= row["status"] < 300)
    print_metric("backup bajo carga", summary)
    if summary["errors"] or summary["p95"] > 5:
        raise SuiteFailed("Backup/export bajo carga fallo o degrado demasiado")


def test_restart_recovery(h: Harness) -> None:
    print("6) Caida y recuperacion")
    event_id = prepare_event(h, "Recovery")
    token = register_one(h, event_id, 1, "recovery")
    status, body, _ = validate_token(h, token, "Antes reinicio")
    expect(status, 200, body, "validacion antes de reinicio")
    if body.get("result") != "granted":
        raise SuiteFailed("El QR no entro antes del reinicio")
    h.restart()
    status, body, _ = validate_token(h, token, "Despues reinicio")
    expect(status, 200, body, "validacion despues de reinicio")
    print(f"  respuesta_post_reinicio={body.get('reason')}")
    if body.get("reason") != "QR ya utilizado":
        raise SuiteFailed("El estado usado del QR no sobrevivio al reinicio")


def test_bad_data_and_roles(h: Harness) -> None:
    print("7) Datos malos y permisos")
    event_id = prepare_event(h, "Datos malos")
    token = register_one(h, event_id, 1, "roles")
    rows = request(h.base, "GET", f"/api/accreditations?event_id={event_id}&q={token}")[1]
    acc_id = rows[0]["id"]

    checks = [
        ("visualizador no cancela", request(h.base, "POST", "/api/accreditations/status", {"actor": "Visualizador", "id": acc_id, "status": "cancelled"})[0] == 403),
        ("token invalido rechaza", request(h.base, "POST", "/api/validate", {"operator": "Acceso", "checkpoint": "X", "token": "NO-EXISTE"})[1].get("reason") == "QR inexistente"),
        ("email duplicado no crea doble", request(h.base, "POST", "/api/register", {"actor": "Recepcion", "event_id": event_id, "first_name": "Otro", "last_name": "Duplicado", "email": "roles.1@example.test", "type": "General"})[1].get("existing") is True),
        ("csv vacio no importa", request(h.base, "POST", "/api/import-accreditations", {"actor": "Recepcion", "event_id": event_id, "rows": []})[1].get("created") == 0),
    ]
    for label, ok in checks:
        print(f"  {label}: {'OK' if ok else 'FALLO'}")
        if not ok:
            raise SuiteFailed(label)


def main() -> None:
    h = Harness()
    start = time.perf_counter()
    try:
        h.start()
        tests = [
            test_30_stations_spike,
            test_mixed_operation,
            test_duplicate_qr_race,
            test_large_base,
            test_backup_during_access,
            test_restart_recovery,
            test_bad_data_and_roles,
        ]
        for test in tests:
            test(h)
        print(f"\nRESULTADO_GENERAL=OK duracion={time.perf_counter() - start:.1f}s")
    finally:
        h.cleanup()


if __name__ == "__main__":
    main()
