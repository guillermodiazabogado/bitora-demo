from __future__ import annotations

import shutil
import sqlite3
import tempfile
import threading
from pathlib import Path

from backend.services.backup import BackupService, ProductionBackupManager
from backend.storage import StorageService


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="bitora-backup-restore-"))
    try:
        db_path = tmp / "source.sqlite3"
        with sqlite3.connect(db_path) as db:
            db.execute("CREATE TABLE proof (id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
            db.execute("INSERT INTO proof (value) VALUES ('BITORA-RESTORE-OK')")
        storage_root = tmp / "storage"
        storage = StorageService(storage_root)
        storage.ensure()
        storage.save("landing", "event-cover.txt", b"landing-productiva")

        def connect():
            connection = sqlite3.connect(db_path, isolation_level=None)
            connection.row_factory = sqlite3.Row
            return connection

        backups = tmp / "backups"
        service = BackupService(db_path, backups, connect, threading.Lock())
        manager = ProductionBackupManager(service, backups, storage_root)
        bundle = manager.create_bundle()
        check = manager.verify_bundle(bundle)
        assert check["ok"] and check["manifest"]["storage"]

        restored_db = tmp / "restored" / "bitora.sqlite3"
        restored_storage = tmp / "restored-storage"
        restored = manager.restore_sqlite_bundle(bundle, restored_db, restored_storage)
        assert restored["ok"]
        with sqlite3.connect(restored_db) as db:
            assert db.execute("SELECT value FROM proof").fetchone()[0] == "BITORA-RESTORE-OK"
        assert (restored_storage / "landing" / "event-cover.txt").read_bytes() == b"landing-productiva"
        print("OK: backup productivo con base, storage, checksums y restauracion")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
