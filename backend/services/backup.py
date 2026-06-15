from __future__ import annotations

import shutil
import sqlite3
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
