from __future__ import annotations

import shutil
import sqlite3
import json
import hashlib
import tempfile
import zipfile
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


class ProductionBackupManager:
    """Creates a restorable bundle with database backup, storage and manifest."""

    def __init__(self, database_backup, backup_dir: Path, storage_root: Path) -> None:
        self.database_backup = database_backup
        self.backup_dir = Path(backup_dir)
        self.storage_root = Path(storage_root)

    def create_bundle(self) -> Path:
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        database_path = self.database_backup.create_backup()
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        bundle = self.backup_dir / f"bitora-production-{stamp}.zip"
        manifest = {
            "version": 1,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "database": {
                "name": database_path.name,
                "sha256": _sha256(database_path),
                "size": database_path.stat().st_size,
            },
            "storage": [],
        }
        with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(database_path, f"database/{database_path.name}")
            if self.storage_root.exists():
                for path in sorted(item for item in self.storage_root.rglob("*") if item.is_file()):
                    relative = path.relative_to(self.storage_root).as_posix()
                    manifest["storage"].append(
                        {"key": relative, "sha256": _sha256(path), "size": path.stat().st_size}
                    )
                    archive.write(path, f"storage/{relative}")
            archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        keep_last = getattr(self.database_backup, "keep_last", lambda: 24)()
        bundles = sorted(self.backup_dir.glob("bitora-production-*.zip"), key=lambda item: item.stat().st_mtime, reverse=True)
        for old_bundle in bundles[max(0, int(keep_last)):]:
            try:
                old_bundle.unlink()
            except OSError:
                pass
        return bundle

    def verify_bundle(self, bundle: Path) -> dict:
        try:
            with zipfile.ZipFile(bundle) as archive:
                names = set(archive.namelist())
                manifest = json.loads(archive.read("manifest.json"))
                db_name = f"database/{manifest['database']['name']}"
                if db_name not in names:
                    return {"ok": False, "detail": "falta backup de base"}
                if hashlib.sha256(archive.read(db_name)).hexdigest() != manifest["database"]["sha256"]:
                    return {"ok": False, "detail": "checksum de base invalido"}
                for item in manifest.get("storage", []):
                    name = f"storage/{item['key']}"
                    if name not in names or hashlib.sha256(archive.read(name)).hexdigest() != item["sha256"]:
                        return {"ok": False, "detail": f"storage invalido: {item['key']}"}
            return {
                "ok": True,
                "detail": f"base + {len(manifest.get('storage', []))} archivos",
                "manifest": manifest,
            }
        except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
            return {"ok": False, "detail": str(exc)}

    def restore_sqlite_bundle(self, bundle: Path, target_db: Path, target_storage: Path) -> dict:
        check = self.verify_bundle(bundle)
        if not check["ok"]:
            return check
        target_db = Path(target_db)
        target_storage = Path(target_storage)
        with tempfile.TemporaryDirectory(prefix="bitora-restore-") as temp:
            temp_root = Path(temp)
            with zipfile.ZipFile(bundle) as archive:
                for name in archive.namelist():
                    destination = (temp_root / name).resolve()
                    if temp_root.resolve() not in destination.parents and destination != temp_root.resolve():
                        raise ValueError("Ruta insegura dentro del backup")
                archive.extractall(temp_root)
            database_files = list((temp_root / "database").glob("*.sqlite3"))
            if not database_files:
                return {"ok": False, "detail": "el bundle no contiene SQLite"}
            target_db.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(database_files[0], target_db)
            with sqlite3.connect(target_db) as db:
                quick_check = db.execute("PRAGMA quick_check").fetchone()[0]
            if quick_check != "ok":
                return {"ok": False, "detail": quick_check}
            source_storage = temp_root / "storage"
            if source_storage.exists():
                target_storage.mkdir(parents=True, exist_ok=True)
                shutil.copytree(source_storage, target_storage, dirs_exist_ok=True)
        return {"ok": True, "detail": "restauracion SQLite y storage verificada"}


class EventBackupService:
    """Creates event-scoped export bundles without leaking other events."""

    EVENT_TABLES = [
        ("events", "SELECT * FROM events WHERE id = ?", lambda event_id: (event_id,)),
        ("accreditation_types", "SELECT * FROM accreditation_types WHERE event_id = ? ORDER BY id", lambda event_id: (event_id,)),
        ("spaces", "SELECT * FROM spaces WHERE event_id = ? ORDER BY id", lambda event_id: (event_id,)),
        ("activities", "SELECT * FROM activities WHERE event_id = ? ORDER BY id", lambda event_id: (event_id,)),
        ("capacity_bags", "SELECT * FROM capacity_bags WHERE event_id = ? ORDER BY id", lambda event_id: (event_id,)),
        ("public_display_config", "SELECT * FROM public_display_config WHERE event_id = ?", lambda event_id: (event_id,)),
        ("public_display_items", "SELECT * FROM public_display_items WHERE event_id = ? ORDER BY id", lambda event_id: (event_id,)),
        ("accreditations", "SELECT * FROM accreditations WHERE event_id = ? ORDER BY id", lambda event_id: (event_id,)),
        (
            "people",
            """
            SELECT DISTINCT p.*
            FROM people p
            JOIN accreditations a ON a.person_id = p.id
            WHERE a.event_id = ?
            ORDER BY p.id
            """,
            lambda event_id: (event_id,),
        ),
        (
            "participant_communication_preferences",
            """
            SELECT DISTINCT cp.*
            FROM participant_communication_preferences cp
            JOIN accreditations a ON a.person_id = cp.person_id
            WHERE a.event_id = ?
            ORDER BY cp.id
            """,
            lambda event_id: (event_id,),
        ),
        ("reservations", "SELECT * FROM reservations WHERE event_id = ? ORDER BY id", lambda event_id: (event_id,)),
        ("access_logs", "SELECT * FROM access_logs WHERE event_id = ? ORDER BY id", lambda event_id: (event_id,)),
        ("communication_logs", "SELECT * FROM communication_logs WHERE event_id = ? ORDER BY id", lambda event_id: (event_id,)),
        ("communication_queue", "SELECT * FROM communication_queue WHERE event_id = ? ORDER BY id", lambda event_id: (event_id,)),
        ("email_delivery_events", "SELECT * FROM email_delivery_events WHERE event_id = ? ORDER BY id", lambda event_id: (event_id,)),
        ("communication_assistant_history", "SELECT * FROM communication_assistant_history WHERE event_id = ? ORDER BY id", lambda event_id: (event_id,)),
        ("communication_tickets", "SELECT * FROM communication_tickets WHERE event_id = ? ORDER BY id", lambda event_id: (event_id,)),
        ("communication_templates", "SELECT * FROM communication_templates WHERE event_id = ? ORDER BY id", lambda event_id: (event_id,)),
        ("participant_announcements", "SELECT * FROM participant_announcements WHERE event_id = ? ORDER BY id", lambda event_id: (event_id,)),
        ("captation_events", "SELECT * FROM captation_events WHERE event_id = ? ORDER BY id", lambda event_id: (event_id,)),
        ("conversation_sources", "SELECT * FROM conversation_sources WHERE event_id = ? ORDER BY id", lambda event_id: (event_id,)),
        ("activity_attendance", "SELECT * FROM activity_attendance WHERE event_id = ? ORDER BY id", lambda event_id: (event_id,)),
        ("certificate_eligibility", "SELECT * FROM certificate_eligibility WHERE event_id = ? ORDER BY id", lambda event_id: (event_id,)),
        ("jobs", "SELECT * FROM jobs WHERE event_id = ? ORDER BY id", lambda event_id: (event_id,)),
        ("waiting_room_visitors", "SELECT * FROM waiting_room_visitors WHERE event_id = ? ORDER BY id", lambda event_id: (event_id,)),
        ("simulator_state", "SELECT * FROM simulator_state WHERE event_id = ?", lambda event_id: (event_id,)),
        ("visualization_layouts", "SELECT * FROM visualization_layouts WHERE event_id = ? ORDER BY id", lambda event_id: (event_id,)),
        (
            "audit_logs",
            """
            SELECT *
            FROM audit_logs
            WHERE (entity_type = 'event' AND entity_id = ?)
               OR payload LIKE ?
            ORDER BY id
            """,
            lambda event_id: (event_id, f'%"event_id": {event_id}%'),
        ),
    ]

    def __init__(self, backup_dir: Path, connect: Callable, lock, app_version: str = "") -> None:
        self.backup_dir = Path(backup_dir)
        self.connect = connect
        self.lock = lock
        self.app_version = app_version

    def create_event_bundle(self, event_id: int, actor: str = "system") -> Path:
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        bundle = self.backup_dir / f"bitora-event-{event_id}-{stamp}.zip"
        payload = self._event_payload(event_id, actor)
        data = json.dumps(payload, ensure_ascii=False, indent=2, default=str).encode("utf-8")
        manifest = {
            "version": 1,
            "scope": "event",
            "event_id": event_id,
            "created_at": payload["created_at"],
            "created_by": actor,
            "app_version": self.app_version,
            "database_engine": payload["database_engine"],
            "tables": {table: len(rows) for table, rows in payload["tables"].items()},
            "payload": {
                "name": f"event-{event_id}.json",
                "sha256": hashlib.sha256(data).hexdigest(),
                "size": len(data),
            },
            "notes": [
                "Backup acotado al evento solicitado.",
                "No incluye otros eventos ni usuarios globales fuera de asignaciones del evento.",
                "El backup global productivo sigue siendo necesario para recuperacion completa de plataforma.",
            ],
        }
        with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(f"event-{event_id}.json", data)
            archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        return bundle

    def verify_event_bundle(self, bundle: Path) -> dict:
        try:
            with zipfile.ZipFile(bundle) as archive:
                manifest = json.loads(archive.read("manifest.json"))
                payload_name = manifest["payload"]["name"]
                content = archive.read(payload_name)
                if hashlib.sha256(content).hexdigest() != manifest["payload"]["sha256"]:
                    return {"ok": False, "detail": "checksum de evento invalido"}
                payload = json.loads(content.decode("utf-8"))
                if int(payload.get("event_id") or 0) != int(manifest.get("event_id") or 0):
                    return {"ok": False, "detail": "event_id inconsistente"}
                if len(payload.get("tables", {}).get("events", [])) != 1:
                    return {"ok": False, "detail": "evento inexistente en payload"}
            return {"ok": True, "detail": f"evento {manifest['event_id']} + {len(manifest.get('tables', {}))} tablas", "manifest": manifest}
        except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
            return {"ok": False, "detail": str(exc)}

    def _event_payload(self, event_id: int, actor: str) -> dict:
        with self.lock, self.connect() as db:
            tables = {}
            for table, query, params_factory in self.EVENT_TABLES:
                try:
                    rows = db.execute(query, params_factory(event_id)).fetchall()
                except Exception:
                    rows = []
                tables[table] = [dict(row) for row in rows]
            if len(tables.get("events", [])) != 1:
                raise ValueError("Evento inexistente")
            user_rows = db.execute(
                """
                SELECT u.id, u.name, u.role, u.active, u.created_at, uer.event_id, uer.role AS event_role, uer.active AS assigned
                FROM user_event_roles uer
                JOIN users u ON u.id = uer.user_id
                WHERE uer.event_id = ?
                ORDER BY u.id
                """,
                (event_id,),
            ).fetchall()
            tables["event_users"] = [dict(row) for row in user_rows]
            return {
                "format": "bitora.event.backup",
                "version": 1,
                "event_id": event_id,
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "created_by": actor,
                "database_engine": getattr(db, "engine", "sqlite"),
                "tables": tables,
            }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
