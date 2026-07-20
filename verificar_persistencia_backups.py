from __future__ import annotations

import json
import shutil
import sqlite3
import tempfile
import threading
import zipfile
from pathlib import Path

from backend.services.backup import EventBackupService
from server import BACKUP_PERMISSION_CODES, PERMISSION_MATRIX


def connect_to(path: Path):
    conn = sqlite3.connect(path, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def build_db(path: Path) -> None:
    with connect_to(path) as db:
        db.executescript(
            """
            CREATE TABLE events (id INTEGER PRIMARY KEY, name TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE people (id INTEGER PRIMARY KEY, first_name TEXT, last_name TEXT, email TEXT, phone TEXT, dni TEXT, company TEXT, created_at TEXT);
            CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, role TEXT, active INTEGER, created_at TEXT);
            CREATE TABLE user_event_roles (id INTEGER PRIMARY KEY, user_id INTEGER, event_id INTEGER, role TEXT, active INTEGER, created_at TEXT);
            CREATE TABLE accreditations (id INTEGER PRIMARY KEY, event_id INTEGER, person_id INTEGER, token TEXT, type TEXT, status TEXT, created_at TEXT);
            CREATE TABLE reservations (id INTEGER PRIMARY KEY, event_id INTEGER, activity_id INTEGER, accreditation_id INTEGER, status TEXT, created_at TEXT);
            CREATE TABLE access_logs (id INTEGER PRIMARY KEY, event_id INTEGER, accreditation_id INTEGER, token TEXT, result TEXT, reason TEXT, created_at TEXT);
            CREATE TABLE communication_queue (id INTEGER PRIMARY KEY, event_id INTEGER, person_id INTEGER, accreditation_id INTEGER, channel TEXT, status TEXT, created_at TEXT);
            CREATE TABLE audit_logs (id INTEGER PRIMARY KEY, actor TEXT, action TEXT, entity_type TEXT, entity_id INTEGER, payload TEXT, created_at TEXT);
            """
        )
        db.execute("INSERT INTO events VALUES (1, 'IA Week', '2026-07-20')")
        db.execute("INSERT INTO events VALUES (2, 'Edificas', '2026-07-20')")
        db.execute("INSERT INTO people VALUES (1, 'Ana', 'Evento1', 'ana@demo.com', '111', '1', 'Demo', '2026-07-20')")
        db.execute("INSERT INTO people VALUES (2, 'Beto', 'Evento2', 'beto@demo.com', '222', '2', 'Demo', '2026-07-20')")
        db.execute("INSERT INTO users VALUES (1, 'Productor IA', 'Productor', 1, '2026-07-20')")
        db.execute("INSERT INTO user_event_roles VALUES (1, 1, 1, 'Productor', 1, '2026-07-20')")
        db.execute("INSERT INTO accreditations VALUES (1, 1, 1, 'EVT-UNO', 'General', 'active', '2026-07-20')")
        db.execute("INSERT INTO accreditations VALUES (2, 2, 2, 'EVT-DOS', 'General', 'active', '2026-07-20')")
        db.execute("INSERT INTO reservations VALUES (1, 1, 10, 1, 'confirmed', '2026-07-20')")
        db.execute("INSERT INTO reservations VALUES (2, 2, 20, 2, 'confirmed', '2026-07-20')")
        db.execute("INSERT INTO access_logs VALUES (1, 1, 1, 'EVT-UNO', 'ok', '', '2026-07-20')")
        db.execute("INSERT INTO access_logs VALUES (2, 2, 2, 'EVT-DOS', 'ok', '', '2026-07-20')")
        db.execute("INSERT INTO communication_queue VALUES (1, 1, 1, 1, 'whatsapp', 'pendiente', '2026-07-20')")
        db.execute("INSERT INTO communication_queue VALUES (2, 2, 2, 2, 'whatsapp', 'pendiente', '2026-07-20')")
        db.execute("INSERT INTO audit_logs VALUES (1, 'system', 'event.created', 'event', 1, '{\"event_id\": 1}', '2026-07-20')")
        db.execute("INSERT INTO audit_logs VALUES (2, 'system', 'event.created', 'event', 2, '{\"event_id\": 2}', '2026-07-20')")


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="bitora-persistencia-"))
    try:
        db_path = tmp / "bitora.sqlite3"
        build_db(db_path)

        def connect():
            return connect_to(db_path)

        service = EventBackupService(tmp / "backups", connect, threading.Lock(), app_version="test")
        bundle = service.create_event_bundle(1, "QA")
        check = service.verify_event_bundle(bundle)
        assert check["ok"], check

        with zipfile.ZipFile(bundle) as archive:
            manifest = json.loads(archive.read("manifest.json"))
            payload = json.loads(archive.read(manifest["payload"]["name"]))

        assert manifest["scope"] == "event"
        assert manifest["event_id"] == 1
        assert payload["tables"]["events"][0]["name"] == "IA Week"
        assert {row["token"] for row in payload["tables"]["accreditations"]} == {"EVT-UNO"}
        assert {row["email"] for row in payload["tables"]["people"]} == {"ana@demo.com"}
        assert all(row["event_id"] == 1 for row in payload["tables"]["reservations"])
        assert all(row["event_id"] == 1 for row in payload["tables"]["access_logs"])
        assert all(row["event_id"] == 1 for row in payload["tables"]["communication_queue"])
        assert "EVT-DOS" not in json.dumps(payload, ensure_ascii=False)
        assert "beto@demo.com" not in json.dumps(payload, ensure_ascii=False)

        super_admin_actions = set(PERMISSION_MATRIX["Super Admin"]["actions"])
        producer_actions = set(PERMISSION_MATRIX["Productor"]["actions"])
        assert set(BACKUP_PERMISSION_CODES).issubset(super_admin_actions)
        assert {"backups.create_event", "backups.download", "backups.verify"}.issubset(producer_actions)
        assert "backups.create_full" not in producer_actions
        assert "backups.restore_full" not in producer_actions

        print("OK: persistencia multi-evento y backup por evento aislado")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
