from __future__ import annotations

import shutil
import sqlite3
import json
from collections.abc import Callable
from datetime import datetime
from pathlib import Path


class BackupService:
    def __init__(
        self,
        db_path: Path,
        backup_dir: Path,
        connect: Callable,
        lock,
        keep_last: Callable[[], int] | None = None,
    ) -> None:
        self.db_path = db_path
        self.backup_dir = backup_dir
        self.connect = connect
        self.lock = lock
        self.keep_last = keep_last or (lambda: 24)

    def create_backup(self) -> Path:
        self.backup_dir.mkdir(exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = self.backup_dir / f"acreditaciones-{stamp}.sqlite3"
        index = 1
        while backup_path.exists():
            backup_path = self.backup_dir / f"acreditaciones-{stamp}-{index}.sqlite3"
            index += 1
        with self.lock, self.connect() as db:
            db.execute("PRAGMA wal_checkpoint(FULL)")
        shutil.copy2(self.db_path, backup_path)
        self.prune()
        return backup_path

    def prune(self) -> None:
        keep = self.keep_last()
        if keep <= 0 or not self.backup_dir.exists():
            return
        backups = sorted(self.backup_dir.glob("*.sqlite3"), key=lambda p: p.stat().st_mtime, reverse=True)
        for path in backups[keep:]:
            try:
                path.unlink()
            except OSError:
                pass

    def verify_backup(self, path: Path) -> dict:
        if not path.exists():
            return {"ok": False, "detail": "archivo inexistente"}
        try:
            with sqlite3.connect(path) as db:
                result = db.execute("PRAGMA quick_check").fetchone()[0]
            return {"ok": result == "ok", "detail": result}
        except sqlite3.DatabaseError as exc:
            return {"ok": False, "detail": str(exc)}


class PostgresBackupService:
    """Portable logical backup for initial PostgreSQL production.

    Provider snapshots or pg_dump remain recommended for disaster recovery.
    This JSON backup is useful for operational exports and validation.
    """

    def __init__(self, backup_dir: Path, connect: Callable, lock, keep_last: Callable[[], int] | None = None) -> None:
        self.backup_dir = backup_dir
        self.connect = connect
        self.lock = lock
        self.keep_last = keep_last or (lambda: 24)

    def create_backup(self) -> Path:
        self.backup_dir.mkdir(exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = self.backup_dir / f"bitora-postgres-{stamp}.json"
        with self.lock, self.connect() as db:
            tables = [
                row["table_name"]
                for row in db.execute(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_type = 'BASE TABLE'
                      AND table_name <> 'schema_migrations'
                    ORDER BY table_name
                    """
                ).fetchall()
            ]
            payload = {
                "engine": "postgres",
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "tables": {table: [dict(row) for row in db.execute(f'SELECT * FROM "{table}" ORDER BY 1').fetchall()] for table in tables},
            }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        self.prune()
        return path

    def prune(self) -> None:
        keep = self.keep_last()
        files = sorted(self.backup_dir.glob("bitora-postgres-*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
        for path in files[max(keep, 0):]:
            try:
                path.unlink()
            except OSError:
                pass

    def verify_backup(self, path: Path) -> dict:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            tables = payload.get("tables") or {}
            return {"ok": payload.get("engine") == "postgres" and bool(tables), "detail": f"{len(tables)} tablas"}
        except (OSError, ValueError) as exc:
            return {"ok": False, "detail": str(exc)}
