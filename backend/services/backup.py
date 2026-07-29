from __future__ import annotations

import shutil
import sqlite3
import json
import hashlib
import tempfile
import zipfile
from collections.abc import Callable
from datetime import datetime
from io import BytesIO
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
        ("attendance_records", "SELECT * FROM attendance_records WHERE event_id = ? ORDER BY id", lambda event_id: (event_id,)),
        ("attendance_events", "SELECT * FROM attendance_events WHERE event_id = ? ORDER BY id", lambda event_id: (event_id,)),
        ("attendance_corrections", "SELECT * FROM attendance_corrections WHERE event_id = ? ORDER BY id", lambda event_id: (event_id,)),
        ("attendance_rule_sets", "SELECT * FROM attendance_rule_sets WHERE event_id = ? ORDER BY id", lambda event_id: (event_id,)),
        ("attendance_rule_set_versions", "SELECT * FROM attendance_rule_set_versions WHERE event_id = ? ORDER BY id", lambda event_id: (event_id,)),
        ("attendance_closures", "SELECT * FROM attendance_closures WHERE event_id = ? ORDER BY id", lambda event_id: (event_id,)),
        ("attendance_evaluations", "SELECT * FROM attendance_evaluations WHERE event_id = ? ORDER BY id", lambda event_id: (event_id,)),
        ("attendance_evaluation_items", "SELECT * FROM attendance_evaluation_items WHERE event_id = ? ORDER BY id", lambda event_id: (event_id,)),
        ("attendance_eligibility_decisions", "SELECT * FROM attendance_eligibility_decisions WHERE event_id = ? ORDER BY id", lambda event_id: (event_id,)),
        ("attendance_overrides", "SELECT * FROM attendance_overrides WHERE event_id = ? ORDER BY id", lambda event_id: (event_id,)),
        ("attendance_reopenings", "SELECT * FROM attendance_reopenings WHERE event_id = ? ORDER BY id", lambda event_id: (event_id,)),
        ("certificate_eligibility", "SELECT * FROM certificate_eligibility WHERE event_id = ? ORDER BY id", lambda event_id: (event_id,)),
        ("certificate_types", "SELECT * FROM certificate_types WHERE event_id = ? OR (event_id IS NULL AND organization_id = (SELECT organization_id FROM events WHERE id = ?)) ORDER BY id", lambda event_id: (event_id, event_id)),
        ("certificate_templates", "SELECT * FROM certificate_templates WHERE event_id = ? OR (event_id IS NULL AND organization_id = (SELECT organization_id FROM events WHERE id = ?)) ORDER BY id", lambda event_id: (event_id, event_id)),
        ("certificate_template_versions", "SELECT * FROM certificate_template_versions WHERE event_id = ? OR (event_id IS NULL AND organization_id = (SELECT organization_id FROM events WHERE id = ?)) ORDER BY id", lambda event_id: (event_id, event_id)),
        ("certificate_number_sequences", "SELECT * FROM certificate_number_sequences WHERE event_id = ? OR (event_id IS NULL AND organization_id = (SELECT organization_id FROM events WHERE id = ?)) ORDER BY id", lambda event_id: (event_id, event_id)),
        ("certificate_batches", "SELECT * FROM certificate_batches WHERE event_id = ? ORDER BY id", lambda event_id: (event_id,)),
        ("certificate_issuances", "SELECT * FROM certificate_issuances WHERE event_id = ? ORDER BY id", lambda event_id: (event_id,)),
        ("certificate_documents", "SELECT * FROM certificate_documents WHERE event_id = ? ORDER BY id", lambda event_id: (event_id,)),
        ("certificate_verification_tokens", "SELECT * FROM certificate_verification_tokens WHERE event_id = ? ORDER BY id", lambda event_id: (event_id,)),
        ("certificate_revocations", "SELECT * FROM certificate_revocations WHERE event_id = ? ORDER BY id", lambda event_id: (event_id,)),
        ("certificate_reissuances", "SELECT * FROM certificate_reissuances WHERE event_id = ? ORDER BY id", lambda event_id: (event_id,)),
        ("survey_types", "SELECT * FROM survey_types WHERE event_id = ? OR (event_id IS NULL AND organization_id = (SELECT organization_id FROM events WHERE id = ?)) ORDER BY id", lambda event_id: (event_id, event_id)),
        ("surveys", "SELECT * FROM surveys WHERE event_id = ? ORDER BY id", lambda event_id: (event_id,)),
        ("survey_versions", "SELECT * FROM survey_versions WHERE event_id = ? ORDER BY id", lambda event_id: (event_id,)),
        ("survey_questions", "SELECT * FROM survey_questions WHERE event_id = ? ORDER BY id", lambda event_id: (event_id,)),
        ("survey_question_options", "SELECT * FROM survey_question_options WHERE event_id = ? ORDER BY id", lambda event_id: (event_id,)),
        ("survey_assignments", "SELECT * FROM survey_assignments WHERE event_id = ? ORDER BY id", lambda event_id: (event_id,)),
        ("survey_access_tokens", "SELECT * FROM survey_access_tokens WHERE event_id = ? ORDER BY id", lambda event_id: (event_id,)),
        ("survey_response_sessions", "SELECT * FROM survey_response_sessions WHERE event_id = ? ORDER BY id", lambda event_id: (event_id,)),
        ("survey_answers", "SELECT * FROM survey_answers WHERE event_id = ? ORDER BY id", lambda event_id: (event_id,)),
        ("survey_answer_options", "SELECT * FROM survey_answer_options WHERE event_id = ? ORDER BY id", lambda event_id: (event_id,)),
        ("event_zones", "SELECT * FROM event_zones WHERE event_id = ? ORDER BY id", lambda event_id: (event_id,)),
        ("zone_access_assignments", "SELECT * FROM zone_access_assignments WHERE event_id = ? ORDER BY id", lambda event_id: (event_id,)),
        ("zone_access_validations", "SELECT * FROM zone_access_validations WHERE event_id = ? ORDER BY id", lambda event_id: (event_id,)),
        ("zone_access_overrides", "SELECT * FROM zone_access_overrides WHERE event_id = ? ORDER BY id", lambda event_id: (event_id,)),
        ("duplicate_resolution_decisions", "SELECT * FROM duplicate_resolution_decisions WHERE event_id = ? ORDER BY id", lambda event_id: (event_id,)),
        (
            "speaker_profiles",
            """
            SELECT DISTINCT sp.*
            FROM speaker_profiles sp
            JOIN speaker_event_assignments sea ON sea.speaker_profile_id = sp.id
            WHERE sea.event_id = ?
            ORDER BY sp.id
            """,
            lambda event_id: (event_id,),
        ),
        (
            "speaker_private_details",
            """
            SELECT DISTINCT spd.*
            FROM speaker_private_details spd
            JOIN speaker_event_assignments sea ON sea.speaker_profile_id = spd.speaker_profile_id
            WHERE sea.event_id = ?
            ORDER BY spd.id
            """,
            lambda event_id: (event_id,),
        ),
        (
            "speaker_profile_versions",
            """
            SELECT DISTINCT spv.*
            FROM speaker_profile_versions spv
            JOIN speaker_event_assignments sea ON sea.speaker_profile_id = spv.speaker_profile_id
            WHERE sea.event_id = ?
            ORDER BY spv.id
            """,
            lambda event_id: (event_id,),
        ),
        ("speaker_event_assignments", "SELECT * FROM speaker_event_assignments WHERE event_id = ? ORDER BY id", lambda event_id: (event_id,)),
        ("speaker_activity_assignments", "SELECT * FROM speaker_activity_assignments WHERE event_id = ? ORDER BY id", lambda event_id: (event_id,)),
        ("speaker_documents", "SELECT * FROM speaker_documents WHERE event_id = ? ORDER BY id", lambda event_id: (event_id,)),
        (
            "speaker_access_tokens",
            """
            SELECT DISTINCT sat.*
            FROM speaker_access_tokens sat
            JOIN speaker_event_assignments sea ON sea.speaker_profile_id = sat.speaker_profile_id
            WHERE sea.event_id = ?
            ORDER BY sat.id
            """,
            lambda event_id: (event_id,),
        ),
        ("jobs", "SELECT * FROM jobs WHERE event_id = ? ORDER BY id", lambda event_id: (event_id,)),
        ("waiting_room_visitors", "SELECT * FROM waiting_room_visitors WHERE event_id = ? ORDER BY id", lambda event_id: (event_id,)),
        ("simulator_state", "SELECT * FROM simulator_state WHERE event_id = ?", lambda event_id: (event_id,)),
        ("visualization_layouts", "SELECT * FROM visualization_layouts WHERE event_id = ? ORDER BY id", lambda event_id: (event_id,)),
        (
            "audit_logs",
            """
            SELECT *
            FROM audit_logs
            WHERE event_id = ?
               OR (entity_type = 'event' AND entity_id = ?)
               OR payload LIKE ?
            ORDER BY id
            """,
            lambda event_id: (event_id, event_id, f'%"event_id": {event_id}%'),
        ),
    ]

    def __init__(self, backup_dir: Path, connect: Callable, lock, app_version: str = "", storage=None) -> None:
        self.backup_dir = Path(backup_dir)
        self.connect = connect
        self.lock = lock
        self.app_version = app_version
        self.storage = storage

    def create_event_bundle(self, event_id: int, actor: str = "system") -> Path:
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        bundle = self.backup_dir / f"bitora-event-{event_id}-{stamp}.zip"
        payload = self._event_payload(event_id, actor)
        data = json.dumps(payload, ensure_ascii=False, indent=2, default=str).encode("utf-8")
        storage_files = self._event_storage_files(event_id)
        manifest = {
            "version": 1,
            "schema_version": 1,
            "scope": "event",
            "backup_type": "event",
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
            "storage": storage_files,
            "notes": [
                "Backup acotado al evento solicitado.",
                "Incluye solo archivos fisicos bajo storage/events/{event_id}.",
                "No incluye otros eventos ni usuarios globales fuera de asignaciones del evento.",
                "El backup global productivo sigue siendo necesario para recuperacion completa de plataforma.",
            ],
        }
        with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(f"event-{event_id}.json", data)
            if self.storage:
                for item in storage_files:
                    key = item.get("key") or ""
                    path = (self.storage.root / key).resolve()
                    root = self.storage.root.resolve()
                    if root not in path.parents:
                        raise ValueError("Archivo de storage fuera de raiz")
                    archive.write(path, f"storage/{key}")
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
                for item in manifest.get("storage", []):
                    name = f"storage/{item['key']}"
                    if name not in archive.namelist():
                        return {"ok": False, "detail": f"falta storage: {item['key']}"}
                    if hashlib.sha256(archive.read(name)).hexdigest() != item["sha256"]:
                        return {"ok": False, "detail": f"checksum storage invalido: {item['key']}"}
            return {"ok": True, "detail": f"evento {manifest['event_id']} + {len(manifest.get('tables', {}))} tablas", "manifest": manifest}
        except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
            return {"ok": False, "detail": str(exc)}

    def _event_storage_files(self, event_id: int) -> list[dict]:
        if not self.storage:
            return []
        try:
            return self.storage.event_inventory(event_id)
        except Exception:
            return []

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
                "schema_version": 1,
                "event_id": event_id,
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "created_by": actor,
                "database_engine": getattr(db, "engine", "sqlite"),
                "tables": tables,
            }


class EventRestoreService:
    """Validates and restores event backup bundles with ID remapping."""

    MAX_BACKUP_BYTES = 25 * 1024 * 1024
    SUPPORTED_SCHEMA_VERSIONS = {1}
    INSERT_ORDER = [
        "accreditation_types",
        "spaces",
        "activities",
        "capacity_bags",
        "public_display_config",
        "public_display_items",
        "participant_announcements",
        "communication_templates",
        "people",
        "participant_communication_preferences",
        "accreditations",
        "reservations",
        "activity_attendance",
        "attendance_records",
        "attendance_events",
        "attendance_corrections",
        "attendance_rule_sets",
        "attendance_rule_set_versions",
        "attendance_closures",
        "attendance_evaluations",
        "attendance_evaluation_items",
        "attendance_eligibility_decisions",
        "attendance_overrides",
        "attendance_reopenings",
        "certificate_eligibility",
        "certificate_types",
        "certificate_templates",
        "certificate_template_versions",
        "certificate_number_sequences",
        "certificate_batches",
        "certificate_issuances",
        "certificate_documents",
        "certificate_verification_tokens",
        "certificate_revocations",
        "certificate_reissuances",
        "survey_types",
        "surveys",
        "survey_versions",
        "survey_questions",
        "survey_question_options",
        "survey_assignments",
        "survey_access_tokens",
        "survey_response_sessions",
        "survey_answers",
        "survey_answer_options",
        "event_zones",
        "zone_access_assignments",
        "zone_access_validations",
        "zone_access_overrides",
        "duplicate_resolution_decisions",
        "speaker_profiles",
        "speaker_private_details",
        "speaker_profile_versions",
        "speaker_event_assignments",
        "speaker_activity_assignments",
        "speaker_documents",
        "speaker_access_tokens",
        "access_logs",
        "communication_logs",
        "communication_queue",
        "email_delivery_events",
        "communication_assistant_history",
        "communication_tickets",
        "captation_events",
        "conversation_sources",
        "jobs",
        "waiting_room_visitors",
        "simulator_state",
        "visualization_layouts",
        "audit_logs",
        "event_users",
    ]

    def __init__(
        self,
        connect: Callable,
        lock,
        token_factory: Callable[[], str],
        now: Callable[[], str],
        *,
        app_version: str = "",
        backup_service: EventBackupService | None = None,
        storage=None,
    ) -> None:
        self.connect = connect
        self.lock = lock
        self.token_factory = token_factory
        self.now = now
        self.app_version = app_version
        self.backup_service = backup_service
        self.storage = storage

    def inspect_bytes(self, raw: bytes, filename: str = "backup.zip") -> dict:
        manifest, payload, warnings = self._read_bundle(raw, filename)
        tables = payload.get("tables") or {}
        event = (tables.get("events") or [{}])[0]
        conflicts = []
        with self.connect() as db:
            existing_event = db.execute("SELECT id, name FROM events WHERE id = ?", (int(payload.get("event_id") or 0),)).fetchone()
            if existing_event:
                conflicts.append({"type": "source_event_exists", "event_id": existing_event["id"], "name": existing_event["name"]})
            for person in tables.get("people") or []:
                email = str(person.get("email") or "").strip().lower()
                if email:
                    existing = db.execute("SELECT id, first_name, last_name, email FROM people WHERE LOWER(email) = LOWER(?)", (email,)).fetchone()
                    if existing:
                        conflicts.append({"type": "person_reused", "email": _mask_email(email), "existing_id": existing["id"]})
        counts = {name: len(rows) for name, rows in tables.items()}
        return {
            "ok": True,
            "restore_id": "",
            "recommended_mode": "new_event",
            "compatible": True,
            "event": {
                "source_event_id": payload.get("event_id"),
                "name": event.get("name") or "Evento restaurado",
                "status": event.get("status") or "",
                "created_at": event.get("created_at") or "",
            },
            "manifest": {
                "version": manifest.get("version"),
                "schema_version": manifest.get("schema_version", payload.get("schema_version", 1)),
                "backup_type": manifest.get("backup_type") or manifest.get("scope"),
                "created_at": manifest.get("created_at"),
                "created_by": manifest.get("created_by"),
                "app_version": manifest.get("app_version"),
                "database_engine": manifest.get("database_engine"),
                "sha256": (manifest.get("payload") or {}).get("sha256"),
            },
            "counts": {
                "participants": counts.get("people", 0),
                "accreditations": counts.get("accreditations", 0),
                "activities": counts.get("activities", 0),
                "reservations": counts.get("reservations", 0),
                "accesses": counts.get("access_logs", 0),
                "attendance": counts.get("activity_attendance", 0) + counts.get("attendance_records", 0),
                "attendance_closures": counts.get("attendance_closures", 0),
                "certificates": counts.get("certificate_eligibility", 0) + counts.get("certificate_issuances", 0),
                "communications": counts.get("communication_logs", 0) + counts.get("communication_queue", 0),
                "templates": counts.get("communication_templates", 0),
                "users_assigned": counts.get("event_users", 0),
                "files": len(manifest.get("storage") or []),
                "files_size": sum(int(item.get("size") or 0) for item in (manifest.get("storage") or [])),
                "tables": counts,
            },
            "warnings": warnings,
            "conflicts": conflicts,
            "personal_data_masked": True,
        }

    def restore_bytes(
        self,
        raw: bytes,
        *,
        mode: str = "new_event",
        actor: str = "system",
        new_event_name: str = "",
        target_event_id: int = 0,
        confirm_text: str = "",
    ) -> dict:
        manifest, payload, warnings = self._read_bundle(raw, "restore.zip")
        mode = str(mode or "new_event").strip()
        if mode not in {"new_event", "overwrite"}:
            raise ValueError("Modo de restauracion invalido")
        if mode == "overwrite" and confirm_text != "RESTAURAR EVENTO":
            raise ValueError("Confirmacion reforzada invalida")
        started = datetime.now()
        preventive_backup = None
        if mode == "overwrite":
            if not target_event_id:
                raise ValueError("Falta evento destino")
            if self.backup_service is None:
                raise ValueError("Backup preventivo no disponible")
            preventive_backup = self.backup_service.create_event_bundle(target_event_id, actor)
        with self.lock, self.connect() as db:
            try:
                db.execute("BEGIN IMMEDIATE")
            except Exception:
                db.execute("BEGIN")
            new_event_id = 0
            try:
                if mode == "overwrite":
                    new_event_id = target_event_id
                    self._delete_event_scope(db, target_event_id)
                    self._restore_event_row(db, payload, new_event_id, actor, new_event_name, overwrite=True)
                else:
                    new_event_id = self._create_event_row(db, payload, actor, new_event_name)

                maps: dict[str, dict[int, int]] = {
                    "events": {int(payload.get("event_id") or 0): new_event_id},
                    "people": {},
                    "spaces": {},
                    "activities": {},
                    "capacity_bags": {},
                    "accreditations": {},
                    "reservations": {},
                    "attendance_records": {},
                    "attendance_rule_sets": {},
                    "attendance_rule_set_versions": {},
                    "attendance_closures": {},
                    "attendance_evaluations": {},
                    "attendance_eligibility_decisions": {},
                    "attendance_overrides": {},
                    "attendance_reopenings": {},
                    "certificate_types": {},
                    "certificate_templates": {},
                    "certificate_template_versions": {},
                    "certificate_number_sequences": {},
                    "certificate_batches": {},
                    "certificate_issuances": {},
                    "certificate_documents": {},
                    "certificate_verification_tokens": {},
                    "certificate_revocations": {},
                    "certificate_reissuances": {},
                    "survey_types": {},
                    "surveys": {},
                    "survey_versions": {},
                    "survey_questions": {},
                    "survey_question_options": {},
                    "survey_assignments": {},
                    "survey_access_tokens": {},
                    "survey_response_sessions": {},
                    "survey_answers": {},
                    "survey_answer_options": {},
                    "event_zones": {},
                    "zone_access_assignments": {},
                    "zone_access_validations": {},
                    "zone_access_overrides": {},
                    "duplicate_resolution_decisions": {},
                    "speaker_profiles": {},
                    "speaker_private_details": {},
                    "speaker_profile_versions": {},
                    "speaker_event_assignments": {},
                    "speaker_activity_assignments": {},
                    "speaker_documents": {},
                    "speaker_access_tokens": {},
                    "communication_queue": {},
                }
                token_map: dict[str, str] = {}
                conflicts: list[dict] = []
                for table in self.INSERT_ORDER:
                    if table == "people":
                        self._restore_people(db, payload, maps, conflicts)
                    elif table == "event_users":
                        self._restore_event_users(db, payload, maps, conflicts)
                    elif table in {"audit_logs"}:
                        self._restore_generic(db, table, payload, maps, token_map, actor, audit=True)
                    elif table not in {"people", "event_users"}:
                        self._restore_generic(db, table, payload, maps, token_map, actor)

                self._repair_certificate_template_versions(db, payload, maps)
                self._repair_survey_versions(db, payload, maps)
                self._repair_speaker_versions(db, payload, maps)
                self._validate_restored(db, payload, new_event_id)
                files_restored = self._restore_storage_files(raw, manifest, int(payload.get("event_id") or 0), new_event_id)
                duration_ms = int((datetime.now() - started).total_seconds() * 1000)
                self._audit(
                    db,
                    actor,
                    "backup.event_restored",
                    "event",
                    new_event_id,
                    {
                        "mode": mode,
                        "source_event_id": payload.get("event_id"),
                        "target_event_id": target_event_id or None,
                        "new_event_id": new_event_id,
                        "checksum": (manifest.get("payload") or {}).get("sha256"),
                        "preventive_backup": preventive_backup.name if preventive_backup else "",
                        "warnings": warnings,
                        "conflicts": conflicts,
                        "files_restored": files_restored,
                        "duration_ms": duration_ms,
                    },
                )
                db.execute("COMMIT")
                return {
                    "ok": True,
                    "mode": mode,
                    "event_id": new_event_id,
                    "source_event_id": payload.get("event_id"),
                    "name": self._event_name(db, new_event_id),
                    "warnings": warnings,
                    "conflicts": conflicts,
                    "token_regenerated": len(token_map),
                    "files_restored": files_restored,
                    "preventive_backup": preventive_backup.name if preventive_backup else "",
                    "duration_ms": duration_ms,
                }
            except Exception:
                db.execute("ROLLBACK")
                if mode == "new_event":
                    try:
                        self._delete_event_files(new_event_id)
                    except Exception:
                        pass
                raise

    def _read_bundle(self, raw: bytes, filename: str) -> tuple[dict, dict, list[str]]:
        if not raw or len(raw) > self.MAX_BACKUP_BYTES:
            raise ValueError("Tamano de backup invalido")
        if not str(filename or "").lower().endswith(".zip"):
            raise ValueError("Solo se aceptan archivos ZIP")
        warnings: list[str] = []
        try:
            with zipfile.ZipFile(BytesIO(raw)) as archive:
                names = archive.namelist()
                if len(names) > 5000:
                    raise ValueError("El ZIP contiene demasiados archivos")
                for name in names:
                    normalized = name.replace("\\", "/")
                    if normalized.startswith("/") or ".." in normalized.split("/") or normalized.endswith((".exe", ".bat", ".cmd", ".ps1", ".sh")):
                        raise ValueError("El ZIP contiene rutas o archivos no permitidos")
                if "manifest.json" not in names:
                    raise ValueError("Falta manifest.json")
                manifest = json.loads(archive.read("manifest.json"))
                payload_meta = manifest.get("payload") or {}
                payload_name = payload_meta.get("name") or f"event-{manifest.get('event_id')}.json"
                if payload_name not in names:
                    raise ValueError("Falta payload de evento")
                content = archive.read(payload_name)
                checksum = hashlib.sha256(content).hexdigest()
                if checksum != payload_meta.get("sha256"):
                    raise ValueError("Checksum invalido")
                payload = json.loads(content.decode("utf-8"))
                for item in manifest.get("storage") or []:
                    key = str(item.get("key") or "").replace("\\", "/")
                    archive_name = f"storage/{key}"
                    if not key.startswith(f"events/{manifest.get('event_id')}/"):
                        raise ValueError("El storage del backup no pertenece al evento")
                    if archive_name not in names:
                        raise ValueError(f"Falta archivo de storage: {key}")
                    if hashlib.sha256(archive.read(archive_name)).hexdigest() != item.get("sha256"):
                        raise ValueError(f"Checksum storage invalido: {key}")
        except zipfile.BadZipFile as exc:
            raise ValueError("ZIP invalido o corrupto") from exc
        backup_type = manifest.get("backup_type") or manifest.get("scope")
        if backup_type != "event":
            raise ValueError("El backup no es de evento")
        schema_version = int(manifest.get("schema_version", payload.get("schema_version", 1)) or 0)
        if schema_version not in self.SUPPORTED_SCHEMA_VERSIONS:
            raise ValueError("Version de esquema no compatible")
        if payload.get("format") != "bitora.event.backup":
            raise ValueError("Formato de backup no compatible")
        if int(payload.get("event_id") or 0) != int(manifest.get("event_id") or 0):
            raise ValueError("event_id inconsistente")
        if not (payload.get("tables") or {}).get("events"):
            raise ValueError("El backup no contiene evento")
        if not manifest.get("schema_version"):
            warnings.append("Backup anterior sin schema_version explicito; se asume version 1")
        return manifest, payload, warnings

    def _restore_storage_files(self, raw: bytes, manifest: dict, source_event_id: int, target_event_id: int) -> int:
        items = manifest.get("storage") or []
        if not items:
            return 0
        if self.storage is None:
            raise ValueError("Storage de eventos no disponible")
        restored = 0
        prefix = f"events/{source_event_id}/"
        with zipfile.ZipFile(BytesIO(raw)) as archive:
            for item in items:
                key = str(item.get("key") or "").replace("\\", "/")
                if not key.startswith(prefix):
                    raise ValueError("Archivo de storage fuera del evento origen")
                relative = key[len(prefix):]
                content = archive.read(f"storage/{key}")
                record = self.storage.restore_event_file(target_event_id, relative, content)
                if record["sha256"] != item.get("sha256"):
                    raise ValueError(f"Storage restaurado con checksum invalido: {relative}")
                restored += 1
        return restored

    def _delete_event_files(self, event_id: int) -> None:
        if self.storage is not None and event_id:
            self.storage.delete_event_files(event_id)

    def _create_event_row(self, db, payload: dict, actor: str, new_event_name: str) -> int:
        source = dict((payload.get("tables") or {}).get("events", [{}])[0])
        source.pop("id", None)
        source["name"] = str(new_event_name or source.get("name") or "Evento restaurado").strip()
        source["status"] = "draft"
        source["created_at"] = self.now()
        return self._insert_row(db, "events", source)

    def _restore_event_row(self, db, payload: dict, event_id: int, actor: str, new_event_name: str, overwrite: bool) -> None:
        source = dict((payload.get("tables") or {}).get("events", [{}])[0])
        source.pop("id", None)
        source["name"] = str(new_event_name or source.get("name") or "Evento restaurado").strip()
        source["status"] = "draft"
        source["created_at"] = self.now()
        columns = [name for name in source if name in self._columns(db, "events")]
        assignments = ", ".join(f"{name} = ?" for name in columns)
        db.execute(f"UPDATE events SET {assignments} WHERE id = ?", [source[name] for name in columns] + [event_id])

    def _restore_people(self, db, payload: dict, maps: dict, conflicts: list[dict]) -> None:
        for row in (payload.get("tables") or {}).get("people", []):
            old_id = int(row.get("id") or 0)
            email = str(row.get("email") or "").strip().lower() or f"restored-{old_id}@bitora.local"
            existing = db.execute("SELECT id FROM people WHERE LOWER(email) = LOWER(?)", (email,)).fetchone()
            if existing:
                maps["people"][old_id] = int(existing["id"])
                conflicts.append({"type": "person_reused", "old_id": old_id, "person_id": int(existing["id"]), "email": _mask_email(email)})
                continue
            values = dict(row)
            values.pop("id", None)
            values["email"] = email
            values["created_at"] = values.get("created_at") or self.now()
            maps["people"][old_id] = self._insert_row(db, "people", values)

    def _restore_event_users(self, db, payload: dict, maps: dict, conflicts: list[dict]) -> None:
        new_event_id = next(iter(maps["events"].values()))
        for row in (payload.get("tables") or {}).get("event_users", []):
            user = db.execute("SELECT id FROM users WHERE name = ? AND active = 1", (row.get("name") or "",)).fetchone()
            if not user:
                conflicts.append({"type": "missing_user_assignment", "name": row.get("name") or "", "role": row.get("event_role") or row.get("role") or ""})
                continue
            db.execute(
                """
                INSERT INTO user_event_roles (user_id, event_id, role, active, created_at)
                VALUES (?, ?, ?, 1, ?)
                ON CONFLICT(user_id, event_id) DO UPDATE SET role = excluded.role, active = 1
                """,
                (int(user["id"]), new_event_id, row.get("event_role") or row.get("role") or "Visualizador", self.now()),
            )

    def _restore_generic(self, db, table: str, payload: dict, maps: dict, token_map: dict, actor: str, audit: bool = False) -> None:
        rows = (payload.get("tables") or {}).get(table) or []
        for source_row in rows:
            row = dict(source_row)
            old_id = int(row.get("id") or 0)
            row.pop("id", None)
            if "event_id" in row:
                row["event_id"] = maps["events"].get(int(row.get("event_id") or 0), next(iter(maps["events"].values())))
            if "space_id" in row and row.get("space_id") is not None:
                row["space_id"] = maps["spaces"].get(int(row["space_id"]), row["space_id"])
            if "activity_id" in row and row.get("activity_id") is not None:
                row["activity_id"] = maps["activities"].get(int(row["activity_id"]), row["activity_id"])
            if "bag_id" in row and row.get("bag_id") is not None:
                row["bag_id"] = maps["capacity_bags"].get(int(row["bag_id"]), row["bag_id"])
            if "person_id" in row and row.get("person_id") is not None:
                row["person_id"] = maps["people"].get(int(row["person_id"]), row["person_id"])
            if "participant_id" in row and row.get("participant_id") is not None:
                row["participant_id"] = maps["people"].get(int(row["participant_id"]), row["participant_id"])
            if "candidate_person_id" in row and row.get("candidate_person_id") is not None:
                row["candidate_person_id"] = maps["people"].get(int(row["candidate_person_id"]), row["candidate_person_id"])
            if "accreditation_id" in row and row.get("accreditation_id") is not None:
                row["accreditation_id"] = maps["accreditations"].get(int(row["accreditation_id"]), row["accreditation_id"])
            if "attendance_id" in row and row.get("attendance_id") is not None:
                row["attendance_id"] = maps["attendance_records"].get(int(row["attendance_id"]), row["attendance_id"])
            if "rule_set_id" in row and row.get("rule_set_id") is not None:
                row["rule_set_id"] = maps["attendance_rule_sets"].get(int(row["rule_set_id"]), row["rule_set_id"])
            if table == "certificate_templates" and "current_version_id" in row and row.get("current_version_id") is not None:
                row["current_version_id"] = maps["certificate_template_versions"].get(int(row["current_version_id"]), row["current_version_id"])
            elif table == "surveys" and "current_version_id" in row and row.get("current_version_id") is not None:
                row["current_version_id"] = maps["survey_versions"].get(int(row["current_version_id"]), row["current_version_id"])
            elif "current_version_id" in row and row.get("current_version_id") is not None:
                row["current_version_id"] = maps["attendance_rule_set_versions"].get(int(row["current_version_id"]), row["current_version_id"])
            if "rule_set_version_id" in row and row.get("rule_set_version_id") is not None:
                row["rule_set_version_id"] = maps["attendance_rule_set_versions"].get(int(row["rule_set_version_id"]), row["rule_set_version_id"])
            if "closure_id" in row and row.get("closure_id") is not None:
                row["closure_id"] = maps["attendance_closures"].get(int(row["closure_id"]), row["closure_id"])
            if "supersedes_closure_id" in row and row.get("supersedes_closure_id") is not None:
                row["supersedes_closure_id"] = maps["attendance_closures"].get(int(row["supersedes_closure_id"]), row["supersedes_closure_id"])
            if "evaluation_id" in row and row.get("evaluation_id") is not None:
                row["evaluation_id"] = maps["attendance_evaluations"].get(int(row["evaluation_id"]), row["evaluation_id"])
            if "override_id" in row and row.get("override_id") is not None:
                row["override_id"] = maps["attendance_overrides"].get(int(row["override_id"]), row["override_id"])
            if "attendance_record_id" in row and row.get("attendance_record_id") is not None:
                row["attendance_record_id"] = maps["attendance_records"].get(int(row["attendance_record_id"]), row["attendance_record_id"])
            if "reservation_id" in row and row.get("reservation_id") is not None:
                row["reservation_id"] = maps["reservations"].get(int(row["reservation_id"]), row["reservation_id"])
            if "queue_id" in row and row.get("queue_id") is not None:
                row["queue_id"] = maps["communication_queue"].get(int(row["queue_id"]), row["queue_id"])
            if "certificate_type_id" in row and row.get("certificate_type_id") is not None:
                row["certificate_type_id"] = maps["certificate_types"].get(int(row["certificate_type_id"]), row["certificate_type_id"])
            if "template_id" in row and row.get("template_id") is not None:
                row["template_id"] = maps["certificate_templates"].get(int(row["template_id"]), row["template_id"])
            if "template_version_id" in row and row.get("template_version_id") is not None:
                row["template_version_id"] = maps["certificate_template_versions"].get(int(row["template_version_id"]), row["template_version_id"])
            if "eligibility_decision_id" in row and row.get("eligibility_decision_id") is not None:
                row["eligibility_decision_id"] = maps["attendance_eligibility_decisions"].get(int(row["eligibility_decision_id"]), row["eligibility_decision_id"])
            if "attendance_closure_id" in row and row.get("attendance_closure_id") is not None:
                row["attendance_closure_id"] = maps["attendance_closures"].get(int(row["attendance_closure_id"]), row["attendance_closure_id"])
            if "batch_id" in row and row.get("batch_id") is not None:
                row["batch_id"] = maps["certificate_batches"].get(int(row["batch_id"]), row["batch_id"])
            if "issuance_id" in row and row.get("issuance_id") is not None:
                row["issuance_id"] = maps["certificate_issuances"].get(int(row["issuance_id"]), row["issuance_id"])
            if "supersedes_issuance_id" in row and row.get("supersedes_issuance_id") is not None:
                row["supersedes_issuance_id"] = maps["certificate_issuances"].get(int(row["supersedes_issuance_id"]), row["supersedes_issuance_id"])
            if "previous_issuance_id" in row and row.get("previous_issuance_id") is not None:
                row["previous_issuance_id"] = maps["certificate_issuances"].get(int(row["previous_issuance_id"]), row["previous_issuance_id"])
            if "new_issuance_id" in row and row.get("new_issuance_id") is not None:
                row["new_issuance_id"] = maps["certificate_issuances"].get(int(row["new_issuance_id"]), row["new_issuance_id"])
            if "survey_type_id" in row and row.get("survey_type_id") is not None:
                row["survey_type_id"] = maps["survey_types"].get(int(row["survey_type_id"]), row["survey_type_id"])
            if "survey_id" in row and row.get("survey_id") is not None:
                row["survey_id"] = maps["surveys"].get(int(row["survey_id"]), row["survey_id"])
            if "version_id" in row and row.get("version_id") is not None:
                row["version_id"] = maps["survey_versions"].get(int(row["version_id"]), row["version_id"])
            if "question_id" in row and row.get("question_id") is not None:
                row["question_id"] = maps["survey_questions"].get(int(row["question_id"]), row["question_id"])
            if "option_id" in row and row.get("option_id") is not None:
                row["option_id"] = maps["survey_question_options"].get(int(row["option_id"]), row["option_id"])
            if "assignment_id" in row and row.get("assignment_id") is not None:
                row["assignment_id"] = maps["survey_assignments"].get(int(row["assignment_id"]), row["assignment_id"])
            if "session_id" in row and row.get("session_id") is not None:
                row["session_id"] = maps["survey_response_sessions"].get(int(row["session_id"]), row["session_id"])
            if "answer_id" in row and row.get("answer_id") is not None:
                row["answer_id"] = maps["survey_answers"].get(int(row["answer_id"]), row["answer_id"])
            if "zone_id" in row and row.get("zone_id") is not None:
                row["zone_id"] = maps["event_zones"].get(int(row["zone_id"]), row["zone_id"])
            if "parent_zone_id" in row and row.get("parent_zone_id") is not None:
                row["parent_zone_id"] = maps["event_zones"].get(int(row["parent_zone_id"]), row["parent_zone_id"])
            if "speaker_profile_id" in row and row.get("speaker_profile_id") is not None:
                row["speaker_profile_id"] = maps["speaker_profiles"].get(int(row["speaker_profile_id"]), row["speaker_profile_id"])
            if table == "certificate_number_sequences" and row.get("scope_key"):
                source_event_id = int(payload.get("event_id") or 0)
                target_event_id = next(iter(maps["events"].values()))
                row["scope_key"] = str(row["scope_key"]).replace(f"EVT-{source_event_id}-", f"EVT-{target_event_id}-", 1)
            if table in {"attendance_records", "attendance_rule_set_versions", "attendance_closures", "attendance_overrides", "attendance_reopenings"} and row.get("idempotency_key"):
                row["idempotency_key"] = f"{row['idempotency_key']}:restored:{next(iter(maps['events'].values()))}"
            if table in {"certificate_batches", "certificate_issuances"} and row.get("idempotency_key"):
                row["idempotency_key"] = f"{row['idempotency_key']}:restored:{next(iter(maps['events'].values()))}"
            if table == "certificate_verification_tokens":
                regenerated = self.token_factory()
                row["token_hash"] = hashlib.sha256(regenerated.encode("utf-8")).hexdigest()
                row["token_hint"] = regenerated[:8]
            if table == "survey_access_tokens":
                regenerated = self.token_factory()
                row["token_hash"] = hashlib.sha256(regenerated.encode("utf-8")).hexdigest()
                row["token_hint"] = regenerated[:8]
                row["status"] = "RESTORED_INACTIVE"
                row["used_at"] = None
            if table == "speaker_access_tokens":
                regenerated = self.token_factory()
                row["token_hash"] = hashlib.sha256(regenerated.encode("utf-8")).hexdigest()
                row["token_hint"] = regenerated[:8]
                row["status"] = "RESTORED_INACTIVE"
                row["used_at"] = None
                row["revoked_at"] = None
            if table in {"speaker_profiles"} and "current_version_id" in row and row.get("current_version_id") is not None:
                row["current_version_id"] = maps["speaker_profile_versions"].get(int(row["current_version_id"]), row["current_version_id"])
            if table == "speaker_documents" and row.get("storage_key"):
                source_event_id = int(payload.get("event_id") or 0)
                target_event_id = next(iter(maps["events"].values()))
                row["storage_key"] = str(row["storage_key"]).replace(f"events/{source_event_id}/", f"events/{target_event_id}/", 1)
            if table == "speaker_profiles" and row.get("public_id"):
                base_public_id = str(row["public_id"])
                public_id = base_public_id
                suffix = 1
                while db.execute("SELECT id FROM speaker_profiles WHERE organization_id = ? AND public_id = ?", (row.get("organization_id"), public_id)).fetchone():
                    suffix += 1
                    public_id = f"{base_public_id}-restored-{suffix}"
                row["public_id"] = public_id
            if table == "survey_response_sessions" and row.get("idempotency_key"):
                row["idempotency_key"] = f"{row['idempotency_key']}:restored:{next(iter(maps['events'].values()))}"
            if table == "zone_access_validations" and row.get("idempotency_key"):
                row["idempotency_key"] = f"{row['idempotency_key']}:restored:{next(iter(maps['events'].values()))}"
            if table == "certificate_documents" and row.get("storage_key"):
                source_event_id = int(payload.get("event_id") or 0)
                target_event_id = next(iter(maps["events"].values()))
                row["storage_key"] = str(row["storage_key"]).replace(f"events/{source_event_id}/", f"events/{target_event_id}/", 1)
            if table == "accreditations":
                original = str(source_row.get("token") or "")
                row["token"] = self._unique_token(db)
                if original:
                    token_map[original] = row["token"]
                row["checked_in_at"] = None
                row["checked_in_by"] = ""
                row["access_count"] = 0
                row["status"] = "active" if row.get("status") != "cancelled" else "cancelled"
            elif "token" in row and str(row.get("token") or "") in token_map:
                row["token"] = token_map[str(row["token"])]
            if table == "communication_queue":
                row["status"] = "restored_inactive"
                row["scheduled_at"] = None
                row["processed_at"] = None
                row["last_error"] = "Restaurado inactivo: requiere revision manual"
                if "idempotency_key" in row:
                    row["idempotency_key"] = ""
            if table == "participant_communication_preferences" and row.get("person_id") is not None:
                existing_preference = db.execute(
                    "SELECT id FROM participant_communication_preferences WHERE person_id = ?",
                    (row["person_id"],),
                ).fetchone()
                if existing_preference:
                    if table in maps and old_id:
                        maps[table][old_id] = int(existing_preference["id"])
                    continue
            if table == "jobs":
                row["status"] = "cancelled"
                row["retry_at"] = None
                row["error"] = "Restaurado inactivo: requiere revision manual"
                row["worker_id"] = ""
            if table == "waiting_room_visitors":
                row["status"] = "expired"
                row["access_token"] = ""
            if table == "audit_logs":
                row["actor"] = actor
                row["action"] = "backup.restored_original_audit"
                row["created_at"] = self.now()
            new_id = self._insert_row(db, table, row)
            if table in maps and old_id:
                maps[table][old_id] = new_id

    def _repair_certificate_template_versions(self, db, payload: dict, maps: dict) -> None:
        for source_row in (payload.get("tables") or {}).get("certificate_templates", []):
            old_template_id = int(source_row.get("id") or 0)
            old_version_id = int(source_row.get("current_version_id") or 0)
            new_template_id = maps.get("certificate_templates", {}).get(old_template_id)
            new_version_id = maps.get("certificate_template_versions", {}).get(old_version_id)
            if new_template_id and new_version_id:
                db.execute("UPDATE certificate_templates SET current_version_id = ? WHERE id = ?", (new_version_id, new_template_id))

    def _repair_survey_versions(self, db, payload: dict, maps: dict) -> None:
        for source_row in (payload.get("tables") or {}).get("surveys", []):
            old_survey_id = int(source_row.get("id") or 0)
            old_version_id = int(source_row.get("current_version_id") or 0)
            new_survey_id = maps.get("surveys", {}).get(old_survey_id)
            new_version_id = maps.get("survey_versions", {}).get(old_version_id)
            if new_survey_id and new_version_id:
                db.execute("UPDATE surveys SET current_version_id = ? WHERE id = ?", (new_version_id, new_survey_id))

    def _repair_speaker_versions(self, db, payload: dict, maps: dict) -> None:
        for source_row in (payload.get("tables") or {}).get("speaker_profiles", []):
            old_profile_id = int(source_row.get("id") or 0)
            old_version_id = int(source_row.get("current_version_id") or 0)
            new_profile_id = maps.get("speaker_profiles", {}).get(old_profile_id)
            new_version_id = maps.get("speaker_profile_versions", {}).get(old_version_id)
            if new_profile_id and new_version_id:
                db.execute("UPDATE speaker_profiles SET current_version_id = ? WHERE id = ?", (new_version_id, new_profile_id))

    def _delete_event_scope(self, db, event_id: int) -> None:
        db.execute("DELETE FROM user_event_roles WHERE event_id = ?", (event_id,))
        for table in reversed([item for item in self.INSERT_ORDER if item not in {"people", "event_users", "audit_logs"}]):
            if table == "participant_communication_preferences":
                continue
            if self._has_column(db, table, "event_id"):
                db.execute(f"DELETE FROM {table} WHERE event_id = ?", (event_id,))

    def _validate_restored(self, db, payload: dict, event_id: int) -> None:
        event = db.execute("SELECT id FROM events WHERE id = ?", (event_id,)).fetchone()
        if not event:
            raise ValueError("No se creo el evento restaurado")
        source_tables = payload.get("tables") or {}
        for table in ["activities", "accreditations", "reservations"]:
            if not self._has_column(db, table, "event_id"):
                continue
            expected = len(source_tables.get(table) or [])
            restored = db.execute(f"SELECT COUNT(*) AS c FROM {table} WHERE event_id = ?", (event_id,)).fetchone()["c"]
            if int(restored or 0) != expected:
                raise ValueError(f"Conteo inconsistente en {table}: {restored}/{expected}")

    def _insert_row(self, db, table: str, values: dict) -> int:
        columns = [name for name in values if name in self._columns(db, table)]
        if not columns:
            return 0
        placeholders = ", ".join(["?"] * len(columns))
        sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
        try:
            cur = db.execute(sql, [values[name] for name in columns])
        except Exception as exc:
            raise ValueError(f"No se pudo insertar {table}: {exc}") from exc
        return int(getattr(cur, "lastrowid", 0) or 0)

    def _columns(self, db, table: str) -> list[str]:
        try:
            return [row["name"] for row in db.execute(f"PRAGMA table_info({table})").fetchall()]
        except Exception:
            rows = db.execute(
                """
                SELECT column_name AS name
                FROM information_schema.columns
                WHERE table_name = ?
                ORDER BY ordinal_position
                """,
                (table,),
            ).fetchall()
            return [row["name"] for row in rows]

    def _has_column(self, db, table: str, column: str) -> bool:
        return column in self._columns(db, table)

    def _unique_token(self, db) -> str:
        token = self.token_factory()
        while db.execute("SELECT 1 FROM accreditations WHERE token = ?", (token,)).fetchone():
            token = self.token_factory()
        return token

    def _event_name(self, db, event_id: int) -> str:
        row = db.execute("SELECT name FROM events WHERE id = ?", (event_id,)).fetchone()
        return row["name"] if row else ""

    def _audit(self, db, actor: str, action: str, entity_type: str, entity_id: int | None, payload: dict) -> None:
        if not self._has_column(db, "audit_logs", "payload"):
            return
        event_id = payload.get("event_id") or payload.get("new_event_id") or (entity_id if entity_type == "event" else None)
        if self._has_column(db, "audit_logs", "event_id"):
            db.execute(
                "INSERT INTO audit_logs (event_id, actor, action, entity_type, entity_id, payload, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (event_id, actor, action, entity_type, entity_id, json.dumps(payload, ensure_ascii=False), self.now()),
            )
            return
        db.execute(
            "INSERT INTO audit_logs (actor, action, entity_type, entity_id, payload, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (actor, action, entity_type, entity_id, json.dumps(payload, ensure_ascii=False), self.now()),
        )


def _mask_email(value: str) -> str:
    text = str(value or "")
    if "@" not in text:
        return ""
    local, domain = text.split("@", 1)
    return f"{local[:3]}***@{domain}"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
