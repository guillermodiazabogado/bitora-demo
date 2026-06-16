from __future__ import annotations

import json
import shutil
import sqlite3
import statistics
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

import server


class QA2Error(Exception):
    pass


class Harness:
    def __init__(self, prefix: str) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix=prefix))
        self.httpd: server.OperationalHTTPServer | None = None
        self.thread: threading.Thread | None = None
        self.base = ""

    def start(self) -> None:
        server.DB_PATH = self.tmp / "bitora-qa2.sqlite3"
        server.BACKUP_DIR = self.tmp / "backups"
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
        shutil.rmtree(self.tmp, ignore_errors=True)


def request(base: str, method: str, path: str, payload: dict | None = None, timeout: int = 30, parse_json: bool = True):
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
                return response.status, json.loads(body.decode("utf-8")) if body else {}
            return response.status, body
    except urllib.error.HTTPError as exc:
        body = exc.read()
        content_type = exc.headers.get("Content-Type", "")
        if parse_json and "application/json" in content_type:
            return exc.code, json.loads(body.decode("utf-8")) if body else {}
        return exc.code, body.decode("utf-8", "ignore")
    except Exception as exc:
        return 0, {"error": str(exc)}


def expect(status: int, expected: int | tuple[int, ...], body, label: str) -> None:
    expected_tuple = expected if isinstance(expected, tuple) else (expected,)
    if status not in expected_tuple:
        raise QA2Error(f"{label}: HTTP {status}, esperado {expected_tuple}, body={body}")


def timed(fn):
    start = time.perf_counter()
    status, body = fn()
    return {"status": status, "body": body, "seconds": time.perf_counter() - start}


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round((len(ordered) - 1) * p)))
    return ordered[index]


def summarize(results: list[dict], ok_fn) -> dict:
    seconds = [r["seconds"] for r in results]
    ok = [r for r in results if ok_fn(r)]
    errors = [r for r in results if r not in ok]
    return {
        "total": len(results),
        "ok": len(ok),
        "errors": len(errors),
        "success_rate": len(ok) / len(results) if results else 0,
        "avg": statistics.mean(seconds) if seconds else 0,
        "p95": percentile(seconds, 0.95),
        "max": max(seconds or [0]),
        "samples": [str(r["body"])[:140] for r in errors[:5]],
    }


def parallel(workers: int, items, fn) -> list[dict]:
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(fn, item) for item in items]
        for future in as_completed(futures):
            results.append(future.result())
    return results


def create_event(base: str, name: str = "QA2", capacity: int = 50000, waitlist: bool = True) -> int:
    status, body = request(
        base,
        "POST",
        "/api/events",
        {
            "actor": "Admin",
            "name": name,
            "status": "published",
            "venue": "QA Lab",
            "capacity": capacity,
            "waitlist_enabled": waitlist,
            "activity_access_open_minutes_before": 999999,
        },
    )
    expect(status, 201, body, "crear evento")
    return int(body["id"])


def first_space_id(base: str, event_id: int) -> int:
    status, body = request(base, "GET", f"/api/spaces?event_id={event_id}")
    expect(status, 200, body, "listar espacios")
    return int(body[0]["id"])


def create_activity(base: str, event_id: int, space_id: int, title: str, capacity: int = 100, start: str = "2026-12-10T10:00") -> int:
    end = (datetime.fromisoformat(start) + timedelta(hours=1)).isoformat(timespec="minutes")
    status, body = request(
        base,
        "POST",
        "/api/activities",
        {
            "actor": "Admin",
            "event_id": event_id,
            "space_id": space_id,
            "title": title,
            "starts_at": start,
            "ends_at": end,
            "capacity": capacity,
            "reservation_mode": "required",
        },
    )
    expect(status, 201, body, "crear actividad")
    return int(body["id"])


def register(base: str, event_id: int, index: int, prefix: str = "qa2") -> dict:
    status, body = request(
        base,
        "POST",
        "/api/register",
        {
            "actor": "Recepcion",
            "event_id": event_id,
            "first_name": f"Nombre{index}",
            "last_name": f"Apellido{index}",
            "email": f"{prefix}.{index}@example.test",
            "phone": f"5491100{index:06d}",
            "dni": str(50000000 + index),
            "company": "QA2",
            "type": "General",
        },
    )
    expect(status, 201, body, "registrar")
    return body


def accreditation_id_for(token: str) -> int:
    with server.connect() as db:
        row = db.execute("SELECT id FROM accreditations WHERE token = ?", (token,)).fetchone()
        if not row:
            raise QA2Error("token no encontrado")
        return int(row["id"])


def reservation_id_for(activity_id: int, accreditation_id: int) -> int:
    with server.connect() as db:
        row = db.execute(
            "SELECT id FROM reservations WHERE activity_id = ? AND accreditation_id = ?",
            (activity_id, accreditation_id),
        ).fetchone()
        if not row:
            raise QA2Error("reserva no encontrada")
        return int(row["id"])


def reserve(base: str, event_id: int, activity_id: int, accreditation_id: int, expected: int | tuple[int, ...] = 201):
    status, body = request(
        base,
        "POST",
        "/api/reservations",
        {"actor": "Recepcion", "event_id": event_id, "activity_id": activity_id, "accreditation_id": accreditation_id},
    )
    expect(status, expected, body, "reservar")
    return body


def validate(base: str, token: str, activity_id: int | None = None, checkpoint: str = "QA2"):
    payload = {"operator": "Acceso", "checkpoint": checkpoint, "token": token}
    if activity_id:
        payload["activity_id"] = activity_id
    return request(base, "POST", "/api/validate", payload)


def bulk_seed(event_id: int, participants: int, rooms: int = 10, activities: int = 50) -> dict:
    now = server.now_iso()
    tokens: list[str] = []
    activity_ids: list[int] = []
    space_ids: list[int] = []
    with server.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        for room in range(rooms):
            cur = db.execute(
                "INSERT INTO spaces (event_id, name, capacity, responsible, transition_minutes, status, created_at) VALUES (?, ?, ?, '', 10, 'active', ?)",
                (event_id, f"Sala QA2 {room + 1}", 500, now),
            )
            space_ids.append(int(cur.lastrowid))
        for index in range(activities):
            hour = 9 + (index % 10)
            cur = db.execute(
                """
                INSERT INTO activities (
                    event_id, space_id, title, description, speaker, activity_type,
                    starts_at, ends_at, capacity, reservation_mode, access_open_minutes_before, status, created_at
                ) VALUES (?, ?, ?, '', '', 'Charla', ?, ?, ?, 'required', 999999, 'published', ?)
                """,
                (
                    event_id,
                    space_ids[index % len(space_ids)],
                    f"Actividad QA2 {index + 1}",
                    f"2026-12-10T{hour:02d}:00",
                    f"2026-12-10T{hour:02d}:45",
                    200,
                    now,
                ),
            )
            activity_ids.append(int(cur.lastrowid))
        people_rows = []
        acc_rows = []
        seen_tokens = set()
        for index in range(participants):
            token = server.make_token()
            while token in seen_tokens:
                token = server.make_token()
            seen_tokens.add(token)
            tokens.append(token)
            people_rows.append((f"Nombre{index}", f"Apellido{index}", f"qa2.bulk.{index}@example.test", f"5491100{index:06d}", str(60000000 + index), "QA2 Bulk", now))
        db.executemany(
            "INSERT INTO people (first_name, last_name, email, phone, dni, company, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            people_rows,
        )
        first_person = int(db.execute("SELECT MIN(id) AS id FROM people WHERE email LIKE 'qa2.bulk.%@example.test'").fetchone()["id"])
        for index, token in enumerate(tokens):
            acc_rows.append((event_id, first_person + index, "General", token, "active", None, None, 0, 0, now))
        db.executemany(
            """
            INSERT INTO accreditations (
                event_id, person_id, type, token, status, checked_in_at, checked_in_by,
                access_count, max_reentries, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            acc_rows,
        )
        server.ensure_capacity_bags(db, event_id=event_id)
        db.execute("COMMIT")
    return {"tokens": tokens, "activities": activity_ids, "spaces": space_ids}


def db_counts() -> dict:
    with server.connect() as db:
        return {
            "people": db.execute("SELECT COUNT(*) AS c FROM people").fetchone()["c"],
            "accreditations": db.execute("SELECT COUNT(*) AS c FROM accreditations").fetchone()["c"],
            "activities": db.execute("SELECT COUNT(*) AS c FROM activities").fetchone()["c"],
            "access_granted": db.execute("SELECT COUNT(*) AS c FROM access_logs WHERE result = 'granted'").fetchone()["c"],
            "duplicate_tokens": db.execute("SELECT COUNT(*) AS c FROM (SELECT token FROM accreditations GROUP BY token HAVING COUNT(*) > 1)").fetchone()["c"],
        }


def integrity_check() -> None:
    with server.connect() as db:
        result = db.execute("PRAGMA integrity_check").fetchone()[0]
        if result != "ok":
            raise QA2Error(f"integrity_check fallo: {result}")


def quote(value: str) -> str:
    return urllib.parse.quote(value, safe="")
