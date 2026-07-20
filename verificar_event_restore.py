from __future__ import annotations

import json
import shutil
import sqlite3
import tempfile
import threading
import zipfile
from pathlib import Path

from backend.services.backup import EventBackupService, EventRestoreService


def now() -> str:
    return "2026-07-20T12:00:00+00:00"


def make_token_factory():
    counter = {"value": 0}

    def make_token() -> str:
        counter["value"] += 1
        return f"EVT-RESTORED{counter['value']:04d}"

    return make_token


def connect_to(path: Path):
    conn = sqlite3.connect(path, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def build_schema(path: Path) -> None:
    with connect_to(path) as db:
        db.executescript(
            """
            CREATE TABLE events (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'draft', created_at TEXT NOT NULL);
            CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, role TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL);
            CREATE TABLE user_event_roles (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, event_id INTEGER NOT NULL, role TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, UNIQUE(user_id, event_id));
            CREATE TABLE people (id INTEGER PRIMARY KEY AUTOINCREMENT, first_name TEXT, last_name TEXT, email TEXT UNIQUE, phone TEXT, dni TEXT, company TEXT, created_at TEXT);
            CREATE TABLE accreditation_types (id INTEGER PRIMARY KEY AUTOINCREMENT, event_id INTEGER NOT NULL, name TEXT, capacity INTEGER, access_enabled INTEGER, created_at TEXT);
            CREATE TABLE spaces (id INTEGER PRIMARY KEY AUTOINCREMENT, event_id INTEGER NOT NULL, name TEXT, capacity INTEGER, created_at TEXT);
            CREATE TABLE activities (id INTEGER PRIMARY KEY AUTOINCREMENT, event_id INTEGER NOT NULL, space_id INTEGER NOT NULL, title TEXT, starts_at TEXT, ends_at TEXT, capacity INTEGER, status TEXT, created_at TEXT);
            CREATE TABLE capacity_bags (id INTEGER PRIMARY KEY AUTOINCREMENT, event_id INTEGER NOT NULL, activity_id INTEGER NOT NULL, name TEXT, code TEXT, assigned_capacity INTEGER, status TEXT, created_at TEXT);
            CREATE TABLE accreditations (id INTEGER PRIMARY KEY AUTOINCREMENT, event_id INTEGER NOT NULL, person_id INTEGER NOT NULL, type TEXT, token TEXT UNIQUE, status TEXT, checked_in_at TEXT, checked_in_by TEXT, access_count INTEGER, created_at TEXT, UNIQUE(event_id, person_id));
            CREATE TABLE reservations (id INTEGER PRIMARY KEY AUTOINCREMENT, event_id INTEGER NOT NULL, activity_id INTEGER NOT NULL, bag_id INTEGER, accreditation_id INTEGER NOT NULL, status TEXT, created_at TEXT);
            CREATE TABLE activity_attendance (id INTEGER PRIMARY KEY AUTOINCREMENT, event_id INTEGER NOT NULL, activity_id INTEGER NOT NULL, accreditation_id INTEGER NOT NULL, reservation_id INTEGER, entry_at TEXT, status TEXT, created_at TEXT, updated_at TEXT);
            CREATE TABLE certificate_eligibility (id INTEGER PRIMARY KEY AUTOINCREMENT, event_id INTEGER NOT NULL, activity_id INTEGER NOT NULL, accreditation_id INTEGER NOT NULL, porcentaje INTEGER, estado TEXT, fecha_calculo TEXT);
            CREATE TABLE access_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, event_id INTEGER, activity_id INTEGER, accreditation_id INTEGER, token TEXT, result TEXT, reason TEXT, created_at TEXT);
            CREATE TABLE communication_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, event_id INTEGER NOT NULL, person_id INTEGER NOT NULL, accreditation_id INTEGER, canal TEXT, fecha TEXT, tipo TEXT, asunto TEXT, contenido TEXT, estado TEXT);
            CREATE TABLE communication_queue (id INTEGER PRIMARY KEY AUTOINCREMENT, event_id INTEGER NOT NULL, person_id INTEGER NOT NULL, accreditation_id INTEGER, channel TEXT, status TEXT, scheduled_at TEXT, processed_at TEXT, last_error TEXT, created_at TEXT);
            CREATE TABLE email_delivery_events (id INTEGER PRIMARY KEY AUTOINCREMENT, event_id INTEGER NOT NULL, queue_id INTEGER, provider TEXT, message_id TEXT, event_type TEXT, payload TEXT, created_at TEXT);
            CREATE TABLE jobs (id INTEGER PRIMARY KEY AUTOINCREMENT, event_id INTEGER, kind TEXT, priority TEXT, status TEXT, payload TEXT, result TEXT, retry_count INTEGER, max_retries INTEGER, retry_at TEXT, worker_id TEXT, error TEXT, created_by TEXT, created_at TEXT, updated_at TEXT);
            CREATE TABLE audit_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, actor TEXT, action TEXT, entity_type TEXT, entity_id INTEGER, payload TEXT, created_at TEXT);
            """
        )


def seed_event(path: Path) -> None:
    with connect_to(path) as db:
        db.execute("INSERT INTO users (name, role, active, created_at) VALUES ('Admin', 'Super Admin', 1, ?)", (now(),))
        db.execute("INSERT INTO events (name, status, created_at) VALUES ('Evento A', 'published', ?)", (now(),))
        db.execute("INSERT INTO user_event_roles (user_id, event_id, role, active, created_at) VALUES (1, 1, 'Super Admin', 1, ?)", (now(),))
        db.execute("INSERT INTO people (first_name, last_name, email, phone, dni, company, created_at) VALUES ('Ana', 'Demo', 'ana@demo.com', '111', '1', 'ACME', ?)", (now(),))
        db.execute("INSERT INTO accreditation_types (event_id, name, capacity, access_enabled, created_at) VALUES (1, 'General', 100, 1, ?)", (now(),))
        db.execute("INSERT INTO spaces (event_id, name, capacity, created_at) VALUES (1, 'Sala A', 50, ?)", (now(),))
        db.execute("INSERT INTO activities (event_id, space_id, title, starts_at, ends_at, capacity, status, created_at) VALUES (1, 1, 'Charla A', ?, ?, 30, 'published', ?)", (now(), now(), now()))
        db.execute("INSERT INTO capacity_bags (event_id, activity_id, name, code, assigned_capacity, status, created_at) VALUES (1, 1, 'Publico', 'public', 30, 'active', ?)", (now(),))
        db.execute("INSERT INTO accreditations (event_id, person_id, type, token, status, checked_in_at, checked_in_by, access_count, created_at) VALUES (1, 1, 'General', 'EVT-ORIGINAL', 'active', ?, 'Mesa 1', 1, ?)", (now(), now()))
        db.execute("INSERT INTO reservations (event_id, activity_id, bag_id, accreditation_id, status, created_at) VALUES (1, 1, 1, 1, 'confirmed', ?)", (now(),))
        db.execute("INSERT INTO activity_attendance (event_id, activity_id, accreditation_id, reservation_id, entry_at, status, created_at, updated_at) VALUES (1, 1, 1, 1, ?, 'Completa', ?, ?)", (now(), now(), now()))
        db.execute("INSERT INTO certificate_eligibility (event_id, activity_id, accreditation_id, porcentaje, estado, fecha_calculo) VALUES (1, 1, 1, 100, 'Elegible', ?)", (now(),))
        db.execute("INSERT INTO access_logs (event_id, activity_id, accreditation_id, token, result, reason, created_at) VALUES (1, 1, 1, 'EVT-ORIGINAL', 'ok', '', ?)", (now(),))
        db.execute("INSERT INTO communication_logs (event_id, person_id, accreditation_id, canal, fecha, tipo, asunto, contenido, estado) VALUES (1, 1, 1, 'email', ?, 'qr', 'QR', 'contenido', 'enviado')", (now(),))
        db.execute("INSERT INTO communication_queue (event_id, person_id, accreditation_id, channel, status, scheduled_at, processed_at, last_error, created_at) VALUES (1, 1, 1, 'whatsapp', 'pendiente', ?, NULL, '', ?)", (now(), now()))
        db.execute("INSERT INTO email_delivery_events (event_id, queue_id, provider, message_id, event_type, payload, created_at) VALUES (1, 1, 'demo', 'msg-1', 'sent', '{}', ?)", (now(),))
        db.execute("INSERT INTO jobs (event_id, kind, priority, status, payload, result, retry_count, max_retries, retry_at, worker_id, error, created_by, created_at, updated_at) VALUES (1, 'email.send', 'high', 'pending', '{}', '{}', 0, 3, ?, '', '', 'Admin', ?, ?)", (now(), now(), now()))


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="bitora-event-restore-"))
    try:
        db_path = tmp / "bitora.sqlite3"
        build_schema(db_path)
        seed_event(db_path)

        def connect():
            return connect_to(db_path)

        lock = threading.Lock()
        backup_service = EventBackupService(tmp / "backups", connect, lock, app_version="test")
        restore_service = EventRestoreService(connect, lock, make_token_factory(), now, app_version="test", backup_service=backup_service)
        bundle = backup_service.create_event_bundle(1, "QA")
        raw = bundle.read_bytes()

        preview = restore_service.inspect_bytes(raw, bundle.name)
        assert preview["ok"]
        assert preview["counts"]["participants"] == 1
        assert preview["counts"]["activities"] == 1
        assert preview["manifest"]["backup_type"] == "event"

        bad_bundle = tmp / "checksum-malo.zip"
        with zipfile.ZipFile(bundle) as source, zipfile.ZipFile(bad_bundle, "w") as target:
            manifest = json.loads(source.read("manifest.json"))
            target.writestr("manifest.json", json.dumps(manifest))
            target.writestr(manifest["payload"]["name"], "{}")
        try:
            restore_service.inspect_bytes(bad_bundle.read_bytes(), bad_bundle.name)
            raise AssertionError("checksum corrupto no rechazado")
        except ValueError as exc:
            assert "Checksum" in str(exc)

        try:
            restore_service.inspect_bytes(b"no-es-un-zip", "backup.zip")
            raise AssertionError("zip invalido no rechazado")
        except ValueError as exc:
            assert "ZIP invalido" in str(exc)

        raw = bundle.read_bytes()
        result = restore_service.restore_bytes(raw, mode="new_event", actor="Admin", new_event_name="Evento B")
        new_event_id = result["event_id"]
        assert new_event_id != 1
        assert result["token_regenerated"] == 1

        with connect() as db:
            event_b = db.execute("SELECT * FROM events WHERE id = ?", (new_event_id,)).fetchone()
            assert event_b["name"] == "Evento B"
            assert event_b["status"] == "draft"
            restored_acc = db.execute("SELECT * FROM accreditations WHERE event_id = ?", (new_event_id,)).fetchone()
            assert restored_acc["token"] != "EVT-ORIGINAL"
            assert restored_acc["checked_in_at"] is None
            restored_activity = db.execute("SELECT * FROM activities WHERE event_id = ?", (new_event_id,)).fetchone()
            restored_reservation = db.execute("SELECT * FROM reservations WHERE event_id = ?", (new_event_id,)).fetchone()
            assert restored_reservation["activity_id"] == restored_activity["id"]
            assert restored_reservation["accreditation_id"] == restored_acc["id"]
            restored_log = db.execute("SELECT * FROM access_logs WHERE event_id = ?", (new_event_id,)).fetchone()
            assert restored_log["token"] == restored_acc["token"]
            queue = db.execute("SELECT * FROM communication_queue WHERE event_id = ?", (new_event_id,)).fetchone()
            assert queue["status"] == "restored_inactive"
            job = db.execute("SELECT * FROM jobs WHERE event_id = ?", (new_event_id,)).fetchone()
            assert job["status"] == "cancelled"
            assert db.execute("SELECT COUNT(*) AS c FROM people WHERE email = 'ana@demo.com'").fetchone()["c"] == 1
            assert db.execute("SELECT COUNT(*) AS c FROM accreditations WHERE event_id = 1").fetchone()["c"] == 1
            assert db.execute("SELECT COUNT(*) AS c FROM accreditations WHERE event_id = ?", (new_event_id,)).fetchone()["c"] == 1
            audit_count = db.execute("SELECT COUNT(*) AS c FROM audit_logs WHERE action = 'backup.event_restored'").fetchone()["c"]
            assert audit_count == 1

        system_bundle = tmp / "system.zip"
        with zipfile.ZipFile(system_bundle, "w") as archive:
            payload = b"{}"
            archive.writestr("system.json", payload)
            archive.writestr("manifest.json", json.dumps({"backup_type": "system", "payload": {"name": "system.json", "sha256": "bad"}}))
        try:
            restore_service.inspect_bytes(system_bundle.read_bytes(), system_bundle.name)
            raise AssertionError("backup de sistema no rechazado")
        except ValueError:
            pass

        print("OK: restauracion controlada de backup de evento")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
