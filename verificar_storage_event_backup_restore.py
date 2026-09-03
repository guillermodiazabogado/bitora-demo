from __future__ import annotations

import json
import shutil
import sqlite3
import tempfile
import threading
import zipfile
from pathlib import Path

from backend.services.backup import EventBackupService, EventRestoreService
from backend.storage import StorageService


def now() -> str:
    return "2026-07-20T18:00:00"


def token_factory():
    counter = {"value": 0}

    def make_token() -> str:
        counter["value"] += 1
        return f"EVT-STORAGE{counter['value']:04d}"

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
            CREATE TABLE accreditations (id INTEGER PRIMARY KEY AUTOINCREMENT, event_id INTEGER NOT NULL, person_id INTEGER NOT NULL, type TEXT, token TEXT UNIQUE, status TEXT, checked_in_at TEXT, checked_in_by TEXT, access_count INTEGER, created_at TEXT, UNIQUE(event_id, person_id));
            CREATE TABLE reservations (id INTEGER PRIMARY KEY AUTOINCREMENT, event_id INTEGER NOT NULL, activity_id INTEGER NOT NULL, accreditation_id INTEGER NOT NULL, status TEXT, created_at TEXT);
            CREATE TABLE access_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, event_id INTEGER, activity_id INTEGER, accreditation_id INTEGER, token TEXT, result TEXT, reason TEXT, created_at TEXT);
            CREATE TABLE communication_queue (id INTEGER PRIMARY KEY AUTOINCREMENT, event_id INTEGER NOT NULL, person_id INTEGER NOT NULL, accreditation_id INTEGER, channel TEXT, status TEXT, scheduled_at TEXT, processed_at TEXT, last_error TEXT, created_at TEXT);
            CREATE TABLE jobs (id INTEGER PRIMARY KEY AUTOINCREMENT, event_id INTEGER, kind TEXT, priority TEXT, status TEXT, payload TEXT, result TEXT, retry_count INTEGER, max_retries INTEGER, retry_at TEXT, worker_id TEXT, error TEXT, created_by TEXT, created_at TEXT, updated_at TEXT);
            CREATE TABLE audit_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, event_id INTEGER, actor TEXT, action TEXT, entity_type TEXT, entity_id INTEGER, payload TEXT, created_at TEXT);
            CREATE TABLE networking_organizations (id INTEGER PRIMARY KEY AUTOINCREMENT, canonical_key TEXT NOT NULL UNIQUE, name TEXT NOT NULL, website TEXT NOT NULL DEFAULT '', logo_url TEXT NOT NULL DEFAULT '', description TEXT NOT NULL DEFAULT '', visibility TEXT NOT NULL DEFAULT 'VISIBLE', activity TEXT NOT NULL DEFAULT '', specialty TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
            CREATE TABLE networking_event_participations (id INTEGER PRIMARY KEY AUTOINCREMENT, event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE, person_id INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE, accreditation_id INTEGER REFERENCES accreditations(id) ON DELETE SET NULL, organization_id INTEGER REFERENCES networking_organizations(id) ON DELETE SET NULL, source_system TEXT NOT NULL DEFAULT 'BITORA', source_external_id TEXT NOT NULL DEFAULT '', source_fingerprint TEXT NOT NULL DEFAULT '', participation_state TEXT NOT NULL DEFAULT 'PASSIVE', public_profile_id TEXT NOT NULL UNIQUE, owner_token_hash TEXT NOT NULL DEFAULT '', owner_token_hint TEXT NOT NULL DEFAULT '', title TEXT NOT NULL DEFAULT '', normalized_function TEXT NOT NULL DEFAULT 'OTHER', normalized_seniority TEXT NOT NULL DEFAULT 'PROFESSIONAL', profile_photo_url TEXT NOT NULL DEFAULT '', organization_logo_url TEXT NOT NULL DEFAULT '', source_payload_json TEXT NOT NULL DEFAULT '{}', imported_at TEXT NOT NULL DEFAULT '', onboarded_at TEXT, revoked_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, UNIQUE(event_id, person_id), UNIQUE(event_id, source_system, source_external_id));
            """
        )


def seed(path: Path) -> None:
    with connect_to(path) as db:
        db.execute("INSERT INTO users (name, role, active, created_at) VALUES ('Admin', 'Super Admin', 1, ?)", (now(),))
        db.execute("INSERT INTO events (name, status, created_at) VALUES ('Evento Storage', 'published', ?)", (now(),))
        db.execute("INSERT INTO events (name, status, created_at) VALUES ('Evento Ajeno', 'published', ?)", (now(),))
        db.execute("INSERT INTO user_event_roles (user_id, event_id, role, active, created_at) VALUES (1, 1, 'Super Admin', 1, ?)", (now(),))
        db.execute("INSERT INTO people (first_name, last_name, email, phone, dni, company, created_at) VALUES ('Lia', 'Storage', 'lia@demo.com', '111', '1', 'Demo', ?)", (now(),))
        db.execute("INSERT INTO people (first_name, last_name, email, phone, dni, company, created_at) VALUES ('Nico', 'Networking', 'nico-networking@demo.com', '222', '2', 'Networking Demo', ?)", (now(),))
        db.execute("INSERT INTO accreditation_types (event_id, name, capacity, access_enabled, created_at) VALUES (1, 'General', 100, 1, ?)", (now(),))
        db.execute("INSERT INTO spaces (event_id, name, capacity, created_at) VALUES (1, 'Sala A', 100, ?)", (now(),))
        db.execute("INSERT INTO activities (event_id, space_id, title, starts_at, ends_at, capacity, status, created_at) VALUES (1, 1, 'Charla Storage', ?, ?, 80, 'published', ?)", (now(), now(), now()))
        db.execute("INSERT INTO accreditations (event_id, person_id, type, token, status, checked_in_at, checked_in_by, access_count, created_at) VALUES (1, 1, 'General', 'EVT-ORIGINAL-STORAGE', 'active', ?, 'Mesa', 1, ?)", (now(), now()))
        db.execute("INSERT INTO reservations (event_id, activity_id, accreditation_id, status, created_at) VALUES (1, 1, 1, 'confirmed', ?)", (now(),))
        db.execute("INSERT INTO access_logs (event_id, activity_id, accreditation_id, token, result, reason, created_at) VALUES (1, 1, 1, 'EVT-ORIGINAL-STORAGE', 'ok', '', ?)", (now(),))
        db.execute("INSERT INTO communication_queue (event_id, person_id, accreditation_id, channel, status, scheduled_at, processed_at, last_error, created_at) VALUES (1, 1, 1, 'email', 'pending', ?, NULL, '', ?)", (now(), now()))
        db.execute("INSERT INTO jobs (event_id, kind, priority, status, payload, result, retry_count, max_retries, retry_at, worker_id, error, created_by, created_at, updated_at) VALUES (1, 'export.csv', 'low', 'pending', '{}', '{}', 0, 3, ?, '', '', 'Admin', ?, ?)", (now(), now(), now()))
        db.execute("INSERT INTO audit_logs (event_id, actor, action, entity_type, entity_id, payload, created_at) VALUES (1, 'Admin', 'event.seeded', 'event', 1, '{\"event_id\": 1}', ?)", (now(),))
        db.execute("INSERT INTO networking_organizations (canonical_key, name, website, logo_url, description, visibility, created_at, updated_at) VALUES ('networking-demo', 'Networking Demo', '', '', '', 'VISIBLE', ?, ?)", (now(), now()))
        db.execute("INSERT INTO networking_event_participations (event_id, person_id, accreditation_id, organization_id, source_system, source_external_id, source_fingerprint, participation_state, public_profile_id, owner_token_hash, owner_token_hint, title, imported_at, created_at, updated_at) VALUES (1, 2, NULL, 1, 'EXTERNAL_FORM', 'nico-networking@demo.com', 'networking-fingerprint', 'ACTIVE', 'NET-STORAGE-001', 'owner-hash', 'owner', 'Networking sin acreditacion', ?, ?, ?)", (now(), now(), now()))


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="bitora-storage-restore-"))
    try:
        db_path = tmp / "bitora.sqlite3"
        storage = StorageService(tmp / "storage")
        storage.ensure()
        build_schema(db_path)
        seed(db_path)
        storage.save_event(1, "images", "landing.webp", b"landing-event-1")
        storage.save_event(1, "certificates", "sample.pdf", b"certificate-event-1")
        storage.save_event(2, "images", "other.webp", b"landing-event-2")

        def connect():
            return connect_to(db_path)

        lock = threading.Lock()
        backup_service = EventBackupService(tmp / "backups", connect, lock, app_version="test", storage=storage)
        restore_service = EventRestoreService(connect, lock, token_factory(), now, app_version="test", backup_service=backup_service, storage=storage)
        bundle = backup_service.create_event_bundle(1, "QA")
        check = backup_service.verify_event_bundle(bundle)
        assert check["ok"], check

        with zipfile.ZipFile(bundle) as archive:
            manifest = json.loads(archive.read("manifest.json"))
            names = set(archive.namelist())
        assert len(manifest["storage"]) == 2
        assert "storage/events/1/images/landing.webp" in names
        assert "storage/events/1/certificates/sample.pdf" in names
        assert "storage/events/2/images/other.webp" not in names

        preview = restore_service.inspect_bytes(bundle.read_bytes(), bundle.name)
        assert preview["ok"]
        assert preview["counts"]["files"] == 2
        assert preview["counts"]["files_size"] == len(b"landing-event-1") + len(b"certificate-event-1")

        result = restore_service.restore_bytes(bundle.read_bytes(), mode="new_event", actor="Admin", new_event_name="Evento Storage Restaurado")
        new_event_id = int(result["event_id"])
        assert new_event_id != 1
        assert result["files_restored"] == 2
        assert storage.read_event(new_event_id, "images", "landing.webp") == b"landing-event-1"
        assert storage.read_event(new_event_id, "certificates", "sample.pdf") == b"certificate-event-1"

        with connect() as db:
            restored = db.execute("SELECT * FROM accreditations WHERE event_id = ?", (new_event_id,)).fetchone()
            assert restored["token"] != "EVT-ORIGINAL-STORAGE"
            assert db.execute("SELECT COUNT(*) AS c FROM people WHERE email = 'lia@demo.com'").fetchone()["c"] == 1
            assert db.execute("SELECT COUNT(*) AS c FROM people WHERE email = 'nico-networking@demo.com'").fetchone()["c"] == 1
            assert db.execute("SELECT COUNT(*) AS c FROM networking_event_participations WHERE event_id = ?", (new_event_id,)).fetchone()["c"] == 1
            audit = db.execute("SELECT * FROM audit_logs WHERE event_id = ? AND action = 'backup.event_restored'", (new_event_id,)).fetchone()
            assert audit is not None
            payload = json.loads(audit["payload"])
            assert payload["files_restored"] == 2

        print("OK: storage por evento incluido en backup y restauracion")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
