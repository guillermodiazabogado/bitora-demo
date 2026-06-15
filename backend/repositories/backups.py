from __future__ import annotations

from pathlib import Path


class BackupRepository:
    """Filesystem boundary for backup artifacts."""

    def __init__(self, backup_dir: Path) -> None:
        self.backup_dir = backup_dir

    def list_backups(self) -> list[Path]:
        if not self.backup_dir.exists():
            return []
        return sorted(self.backup_dir.glob("*.sqlite3"), key=lambda p: p.stat().st_mtime, reverse=True)
