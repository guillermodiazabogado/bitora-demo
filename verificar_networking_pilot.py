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
from verificar_networking_v2_4 import activate_event_targets, assert_true, complete_discovery, concept_setup, import_profiles, onboard, pilot_rows, register, request, target_profiles


class PilotFailed(Exception):
    pass


def timed_call(base: str, method: str, path: str, payload: dict | None = None, expect: int = 200) -> dict:
    started = time.perf_counter()
    result = request(base, method, path, payload, expect=expect)
    return {"seconds": time.perf_counter() - started, "result": result}


def run_concurrent(calls: list[tuple[str, str, str, dict | None, int]], *, workers: int) -> tuple[list[dict], list[str]]:
    results: list[dict] = []
    errors: list[str] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(timed_call, *call) for call in calls]
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception as exc:  # noqa: BLE001 - verifier reports all pilot failures.
                errors.append(str(exc))
    return results, errors


def latency_summary(results: list[dict]) -> dict:
    values = sorted(item["seconds"] for item in results)
    if not values:
        return {"count": 0}
    p95_index = min(len(values) - 1, int(len(values) * 0.95))
    return {
        "count": len(values),
        "min_ms": round(values[0] * 1000, 1),
        "median_ms": round(statistics.median(values) * 1000, 1),
        "p95_ms": round(values[p95_index] * 1000, 1),
        "max_ms": round(values[-1] * 1000, 1),
    }


def main() -> None:
    tmp_path = Path(tempfile.mkdtemp(prefix="qr-networking-pilot-"))
    httpd = None
    try:
        server.DB_PATH = tmp_path / "networking_pilot.sqlite3"
        server.BACKUP_DIR = tmp_path / "backups"
        server.AppHandler.log_message = lambda self, format, *args: None
        server.init_db()
        server.seed_if_empty()

        httpd = server.OperationalHTTPServer(("127.0.0.1", 0), server.AppHandler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{httpd.server_address[1]}"

        event = request(base, "POST", "/api/events", {"actor": "Admin", "name": "Pilot Load 500", "status": "published"}, 201)
        event_id = int(event["id"])
        request(base, "POST", "/api/networking/config", {"actor": "Admin", "event_id": event_id, "networking_profile_mode": "ORGANIZATION_FIRST", "networking_discovery_enabled": 1, "networking_discovery_batch_size": 5, "networking_discovery_exploration_frequency": 4})
        request(base, "POST", "/api/networking/brand", {"actor": "Admin", "event_id": event_id, "networking_public_base_url": "https://pilot-load.example.test", "networking_brand_title": "Pilot Load 500"})
        concept_setup(base, event_id)
        owner_reg = register(base, event_id, "pilot-load-owner", email="pilotload.owner.v24@example.test")

        import_started = time.perf_counter()
        import_profiles(base, event_id, pilot_rows(event_id, 500, include_owner=True, prefix="pilotload"))
        import_seconds = time.perf_counter() - import_started
        activate_event_targets(event_id)
        owner = onboard(base, owner_reg["token"], event_id)
        owner_discovery = complete_discovery(base, owner_reg["token"], event_id, diversity=True)
        assert_true(owner_discovery["participation"]["discovery"]["ready"], "Pilot Discovery owner no quedo listo")
        request(base, "POST", "/api/networking/launch", {"actor": "Admin", "event_id": event_id, "action": "launch"})

        owner_id = int(owner["participation"]["participation_id"])
        targets = target_profiles(event_id, owner_id, 100)
        assert_true(len(targets) >= 80, "Fixture 500 no genero suficientes candidatos activos")

        credential_calls = [(base, "GET", f"/api/networking/session?token={owner_reg['token']}&event_id={event_id}", None, 200) for _ in range(50)]
        profile_calls = [(base, "GET", f"/api/networking/profile?profile_id={targets[index % len(targets)]['public_profile_id']}", None, 200) for index in range(100)]
        discovery_calls = [(base, "GET", f"/api/networking/discovery?token={owner_reg['token']}&limit=5", None, 200) for _ in range(100)]
        scan_target = targets[0]["public_profile_id"]
        scan_calls = [(base, "POST", "/api/networking/scan", {"token": owner_reg["token"], "public_profile_id": scan_target}, 200) for _ in range(40)]

        credential_results, credential_errors = run_concurrent(credential_calls, workers=25)
        profile_results, profile_errors = run_concurrent(profile_calls, workers=50)
        discovery_results, discovery_errors = run_concurrent(discovery_calls, workers=50)
        scan_results, scan_errors = run_concurrent(scan_calls, workers=40)
        errors = credential_errors + profile_errors + discovery_errors + scan_errors
        assert_true(not errors, f"Errores concurrentes en pilot: {errors[:3]}")

        with server.connect() as db:
            participant_count = db.execute("SELECT COUNT(*) AS c FROM networking_event_participations WHERE event_id = ?", (event_id,)).fetchone()["c"]
            contact_count = db.execute("SELECT COUNT(*) AS c FROM networking_contacts WHERE event_id = ? AND owner_participation_id = ? AND target_participation_id = (SELECT id FROM networking_event_participations WHERE public_profile_id = ?)", (event_id, owner_id, scan_target)).fetchone()["c"]
            lock_mode = db.execute("PRAGMA journal_mode").fetchone()[0]
        assert_true(participant_count == 501, f"Fixture esperado 501 participaciones, recibio {participant_count}")
        assert_true(contact_count == 1, "Concurrent scan duplico contacto logico")

        ops_started = time.perf_counter()
        ops = request(base, "GET", f"/api/networking/operations?actor=Admin&event_id={event_id}")
        ops_seconds = time.perf_counter() - ops_started
        assert_true(ops["participants"]["total"] == participant_count and ops["networking"]["contacts_total"] >= 1, "Operaciones post-load no reflejan estado canonico")

        evidence = {
            "db": "sqlite",
            "journal_mode": lock_mode,
            "participants": participant_count,
            "organizations_estimated": 80,
            "import_seconds": round(import_seconds, 3),
            "credential": latency_summary(credential_results),
            "public_profile": latency_summary(profile_results),
            "discovery_next": latency_summary(discovery_results),
            "duplicate_scan": latency_summary(scan_results),
            "operations_summary_ms": round(ops_seconds * 1000, 1),
            "errors": len(errors),
            "duplicate_contacts": contact_count - 1,
        }
        print("OK: networking pilot 500 load")
        print(json.dumps(evidence, sort_keys=True))
    finally:
        if httpd:
            httpd.shutdown()
            httpd.server_close()
        shutil.rmtree(tmp_path, ignore_errors=True)


if __name__ == "__main__":
    main()
