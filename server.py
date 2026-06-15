from __future__ import annotations

import csv
import hashlib
import hmac
import os
import shutil
import json
import secrets
import socket
import sqlite3
import threading
import time
from io import BytesIO
from datetime import datetime, timedelta, timezone
from html import escape
from http import HTTPStatus
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from PIL import Image, ImageDraw, ImageFont

from backend.database import load_database_config
from backend.repositories import SQLiteRepository
from backend.services.access_validation import AccessValidationService
from backend.services.attendance import AttendanceService
from backend.services.audit import AuditService
from backend.services.backup import BackupService
from backend.services.capacity_buckets import CapacityBucketService
from backend.services.demo_real import DemoRealService
from backend.services.qr import QRService
from backend.services.qrcodegen import QrCode
from backend.services.reservations import ReservationService


ROOT = Path(__file__).resolve().parent
DB_CONFIG = load_database_config()
DB_PATH = Path(DB_CONFIG.sqlite_path)
if not DB_PATH.is_absolute():
    DB_PATH = ROOT / DB_PATH
FRONTEND_DIR = ROOT / "frontend"
LEGACY_STATIC_DIR = ROOT / "static"
STATIC_DIR = FRONTEND_DIR if FRONTEND_DIR.exists() else LEGACY_STATIC_DIR
BACKUP_DIR = ROOT / "backups"
DB_LOCK = threading.Lock()
BACKUP_STOP = threading.Event()
AUTO_BACKUP_MINUTES = int(os.environ.get("QR_AUTO_BACKUP_MINUTES", "10"))
BACKUP_KEEP_LAST = int(os.environ.get("QR_BACKUP_KEEP_LAST", "24"))
APP_VERSION = "4.6-deploy-ready"
APP_ENV = os.environ.get("APP_ENV", os.environ.get("QR_APP_ENV", "development")).strip().lower() or "development"
BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/")
HTTPS_REQUIRED = os.environ.get("HTTPS_REQUIRED", "").lower() in {"1", "true", "si", "yes"}
STARTED_AT = now_iso() if "now_iso" in globals() else datetime.now(timezone.utc).isoformat(timespec="seconds")
AUTH_SESSIONS: dict[str, dict] = {}
REQUIRE_LOGIN = os.environ.get("QR_REQUIRE_LOGIN", "").lower() in {"1", "true", "si", "yes"}
QR_ALPHANUM = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ $%*+-./:"
ADMIN_ROLES = {"Super Admin"}
CONFIG_ROLES = {"Super Admin", "Productor", "Coordinador"}
RECEPTION_ROLES = {"Super Admin", "Productor", "Coordinador", "Operador de recepcion"}
ACCESS_ROLES = {"Super Admin", "Productor", "Coordinador", "Operador de recepcion", "Operador de acceso"}
REPOSITORY = SQLiteRepository()


def audit_service() -> AuditService:
    return AuditService(repository=REPOSITORY, now=now_iso)


def capacity_bucket_service() -> CapacityBucketService:
    return CapacityBucketService(repository=REPOSITORY, now=now_iso)


def reservation_service() -> ReservationService:
    return ReservationService(repository=REPOSITORY, capacity_service=capacity_bucket_service(), now=now_iso)


def access_validation_service() -> AccessValidationService:
    return AccessValidationService(repository=REPOSITORY, audit_service=audit_service(), now=now_iso)


def attendance_service() -> AttendanceService:
    return AttendanceService(audit_service=audit_service(), now=now_iso)


def qr_service() -> QRService:
    return QRService()


def backup_service() -> BackupService:
    return BackupService(DB_PATH, BACKUP_DIR, connect, DB_LOCK, keep_last=lambda: BACKUP_KEEP_LAST)


def verify_backup_file(path: Path) -> dict:
    return backup_service().verify_backup(path)


def demo_real_service() -> DemoRealService:
    return DemoRealService(now=now_iso, make_token=make_token, hash_pin=hash_pin)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def configured_base_url(handler: SimpleHTTPRequestHandler | None = None) -> str:
    if BASE_URL:
        return BASE_URL
    if handler:
        proto = handler.headers.get("X-Forwarded-Proto") or ("https" if HTTPS_REQUIRED else "http")
        host = handler.headers.get("X-Forwarded-Host") or handler.headers.get("Host")
        if host:
            return f"{proto}://{host}".rstrip("/")
    port = int(os.environ.get("PORT") or os.environ.get("QR_PORT") or "8787")
    return f"http://localhost:{port}"


def absolute_url(path: str, handler: SimpleHTTPRequestHandler | None = None) -> str:
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return f"{configured_base_url(handler)}{path if path.startswith('/') else '/' + path}"


def public_link(path: str, handler: SimpleHTTPRequestHandler | None = None) -> str:
    if BASE_URL:
        return absolute_url(path, handler)
    return path if path.startswith("/") else "/" + path


def runtime_config(handler: SimpleHTTPRequestHandler | None = None) -> dict:
    return {
        "app": "BITORA",
        "version": APP_VERSION,
        "env": APP_ENV,
        "demo": APP_ENV == "demo",
        "base_url": configured_base_url(handler),
        "https_required": HTTPS_REQUIRED,
        "database": {"engine": DB_CONFIG.engine, "sqlite_path": str(DB_PATH)},
        "started_at": STARTED_AT,
    }


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 30000")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def init_db() -> None:
    with connect() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                venue TEXT NOT NULL DEFAULT '',
                starts_at TEXT NOT NULL DEFAULT '',
                ends_at TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'draft',
                capacity INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS people (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                email TEXT NOT NULL,
                phone TEXT NOT NULL DEFAULT '',
                dni TEXT NOT NULL DEFAULT '',
                company TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                UNIQUE(email)
            );

            CREATE TABLE IF NOT EXISTS accreditations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
                person_id INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
                type TEXT NOT NULL DEFAULT 'General',
                token TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL DEFAULT 'active',
                checked_in_at TEXT,
                checked_in_by TEXT,
                access_count INTEGER NOT NULL DEFAULT 0,
                max_reentries INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                UNIQUE(event_id, person_id)
            );

            CREATE TABLE IF NOT EXISTS accreditation_types (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                capacity INTEGER NOT NULL DEFAULT 0,
                access_enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                UNIQUE(event_id, name)
            );

            CREATE TABLE IF NOT EXISTS spaces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                capacity INTEGER NOT NULL DEFAULT 0,
                responsible TEXT NOT NULL DEFAULT '',
                transition_minutes INTEGER NOT NULL DEFAULT 15,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL,
                UNIQUE(event_id, name)
            );

            CREATE TABLE IF NOT EXISTS activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
                space_id INTEGER NOT NULL REFERENCES spaces(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                speaker TEXT NOT NULL DEFAULT '',
                activity_type TEXT NOT NULL DEFAULT 'Charla',
                starts_at TEXT NOT NULL,
                ends_at TEXT NOT NULL,
                capacity INTEGER NOT NULL DEFAULT 0,
                reservation_mode TEXT NOT NULL DEFAULT 'free',
                status TEXT NOT NULL DEFAULT 'published',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS reservations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
                activity_id INTEGER NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
                bag_id INTEGER REFERENCES capacity_bags(id) ON DELETE SET NULL,
                accreditation_id INTEGER NOT NULL REFERENCES accreditations(id) ON DELETE CASCADE,
                status TEXT NOT NULL DEFAULT 'confirmed',
                created_at TEXT NOT NULL,
                UNIQUE(activity_id, accreditation_id)
            );

            CREATE TABLE IF NOT EXISTS capacity_bags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
                activity_id INTEGER NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                code TEXT NOT NULL,
                assigned_capacity INTEGER NOT NULL DEFAULT 0,
                priority INTEGER NOT NULL DEFAULT 100,
                public_visible INTEGER NOT NULL DEFAULT 0,
                public_registration INTEGER NOT NULL DEFAULT 0,
                reception_enabled INTEGER NOT NULL DEFAULT 1,
                release_enabled INTEGER NOT NULL DEFAULT 1,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL,
                UNIQUE(activity_id, code)
            );

            CREATE TABLE IF NOT EXISTS public_display_config (
                event_id INTEGER PRIMARY KEY REFERENCES events(id) ON DELETE CASCADE,
                mode TEXT NOT NULL DEFAULT 'airport',
                refresh_seconds INTEGER NOT NULL DEFAULT 10,
                paused INTEGER NOT NULL DEFAULT 0,
                message TEXT NOT NULL DEFAULT '',
                room_filter TEXT NOT NULL DEFAULT '',
                status_filter TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS public_display_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
                activity_id INTEGER NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
                sort_order INTEGER NOT NULL DEFAULT 0,
                visible INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                UNIQUE(event_id, activity_id)
            );

            CREATE TABLE IF NOT EXISTS access_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                accreditation_id INTEGER REFERENCES accreditations(id) ON DELETE SET NULL,
                event_id INTEGER REFERENCES events(id) ON DELETE SET NULL,
                token TEXT NOT NULL,
                operator TEXT NOT NULL DEFAULT '',
                checkpoint TEXT NOT NULL DEFAULT '',
                result TEXT NOT NULL,
                reason TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor TEXT NOT NULL DEFAULT '',
                action TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id INTEGER,
                payload TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                role TEXT NOT NULL,
                pin_hash TEXT NOT NULL DEFAULT '',
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS participant_communication_preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                person_id INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
                email TEXT NOT NULL DEFAULT '',
                phone TEXT NOT NULL DEFAULT '',
                acepta_email INTEGER NOT NULL DEFAULT 0,
                acepta_whatsapp INTEGER NOT NULL DEFAULT 0,
                canal_preferido TEXT NOT NULL DEFAULT 'email',
                fecha_consentimiento TEXT,
                ultimo_contacto TEXT,
                updated_at TEXT NOT NULL,
                UNIQUE(person_id)
            );

            CREATE TABLE IF NOT EXISTS communication_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
                person_id INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
                accreditation_id INTEGER REFERENCES accreditations(id) ON DELETE SET NULL,
                canal TEXT NOT NULL,
                fecha TEXT NOT NULL,
                tipo TEXT NOT NULL,
                asunto TEXT NOT NULL DEFAULT '',
                contenido TEXT NOT NULL DEFAULT '',
                estado TEXT NOT NULL DEFAULT 'demo'
            );

            CREATE TABLE IF NOT EXISTS communication_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL DEFAULT 0,
                code TEXT NOT NULL,
                name TEXT NOT NULL,
                tipo TEXT NOT NULL,
                asunto TEXT NOT NULL DEFAULT '',
                contenido TEXT NOT NULL DEFAULT '',
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                UNIQUE(event_id, code)
            );

            CREATE TABLE IF NOT EXISTS participant_announcements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                content TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'published',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS captation_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
                source TEXT NOT NULL DEFAULT 'landing',
                source_detail TEXT NOT NULL DEFAULT '',
                device_type TEXT NOT NULL DEFAULT 'desktop',
                action TEXT NOT NULL,
                session_id TEXT NOT NULL DEFAULT '',
                accreditation_id INTEGER REFERENCES accreditations(id) ON DELETE SET NULL,
                person_id INTEGER REFERENCES people(id) ON DELETE SET NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS conversation_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
                person_id INTEGER REFERENCES people(id) ON DELETE SET NULL,
                accreditation_id INTEGER REFERENCES accreditations(id) ON DELETE SET NULL,
                source TEXT NOT NULL DEFAULT '',
                channel TEXT NOT NULL DEFAULT '',
                device_type TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS activity_attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
                activity_id INTEGER NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
                accreditation_id INTEGER NOT NULL REFERENCES accreditations(id) ON DELETE CASCADE,
                reservation_id INTEGER REFERENCES reservations(id) ON DELETE SET NULL,
                entry_at TEXT,
                entry_operator TEXT NOT NULL DEFAULT '',
                exit_at TEXT,
                exit_operator TEXT NOT NULL DEFAULT '',
                attended_minutes INTEGER NOT NULL DEFAULT 0,
                attendance_percentage INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'Pendiente',
                eligibility_status TEXT NOT NULL DEFAULT 'Pendiente',
                corrected_by TEXT NOT NULL DEFAULT '',
                correction_reason TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(activity_id, accreditation_id)
            );

            CREATE TABLE IF NOT EXISTS certificate_eligibility (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
                activity_id INTEGER NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
                accreditation_id INTEGER NOT NULL REFERENCES accreditations(id) ON DELETE CASCADE,
                porcentaje INTEGER NOT NULL DEFAULT 0,
                elegible INTEGER NOT NULL DEFAULT 0,
                estado TEXT NOT NULL DEFAULT 'Pendiente',
                fecha_calculo TEXT NOT NULL,
                certificate_generated_at TEXT,
                UNIQUE(activity_id, accreditation_id)
            );
            """
        )
        ensure_event_v3_columns(db)
        ensure_v4_1_columns(db)
        ensure_v4_2_columns(db)
        ensure_v4_4_columns(db)
        ensure_user_pin_column(db)
        ensure_reservation_bag_column(db)
        ensure_v3_tables(db)
        ensure_indexes(db)
        ensure_default_users(db)
        ensure_default_types(db)
        ensure_default_spaces(db)
        ensure_capacity_bags(db)
        ensure_communication_templates(db)


def ensure_indexes(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_people_email ON people(email);
        CREATE INDEX IF NOT EXISTS idx_people_dni ON people(dni);
        CREATE INDEX IF NOT EXISTS idx_people_name ON people(last_name, first_name);
        CREATE INDEX IF NOT EXISTS idx_accreditations_event_status ON accreditations(event_id, status);
        CREATE INDEX IF NOT EXISTS idx_accreditations_event_type ON accreditations(event_id, type);
        CREATE INDEX IF NOT EXISTS idx_accreditations_token ON accreditations(token);
        CREATE INDEX IF NOT EXISTS idx_reservations_event_status ON reservations(event_id, status);
        CREATE INDEX IF NOT EXISTS idx_reservations_activity_status ON reservations(activity_id, status);
        CREATE INDEX IF NOT EXISTS idx_access_logs_event_created ON access_logs(event_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_access_logs_token ON access_logs(token);
        CREATE INDEX IF NOT EXISTS idx_activities_event_start ON activities(event_id, starts_at);
        CREATE INDEX IF NOT EXISTS idx_audit_logs_created ON audit_logs(created_at);
        CREATE INDEX IF NOT EXISTS idx_communication_logs_event ON communication_logs(event_id, fecha);
        CREATE INDEX IF NOT EXISTS idx_preferences_person ON participant_communication_preferences(person_id);
        CREATE INDEX IF NOT EXISTS idx_attendance_event_activity ON activity_attendance(event_id, activity_id);
        CREATE INDEX IF NOT EXISTS idx_attendance_accreditation ON activity_attendance(accreditation_id);
        CREATE INDEX IF NOT EXISTS idx_certificate_event ON certificate_eligibility(event_id, estado);
        CREATE INDEX IF NOT EXISTS idx_captation_event_source ON captation_events(event_id, source, action);
        CREATE INDEX IF NOT EXISTS idx_conversation_source_event ON conversation_sources(event_id, source);
        """
    )


def ensure_v4_1_columns(db: sqlite3.Connection) -> None:
    people_columns = [row["name"] for row in db.execute("PRAGMA table_info(people)").fetchall()]
    if "position" not in people_columns:
        db.execute("ALTER TABLE people ADD COLUMN position TEXT NOT NULL DEFAULT ''")
    acc_columns = [row["name"] for row in db.execute("PRAGMA table_info(accreditations)").fetchall()]
    if "requiere_asistencia" not in acc_columns:
        db.execute("ALTER TABLE accreditations ADD COLUMN requiere_asistencia INTEGER NOT NULL DEFAULT 0")
    if "porcentaje_minimo" not in acc_columns:
        db.execute("ALTER TABLE accreditations ADD COLUMN porcentaje_minimo INTEGER NOT NULL DEFAULT 0")
    if "elegible_certificado" not in acc_columns:
        db.execute("ALTER TABLE accreditations ADD COLUMN elegible_certificado INTEGER NOT NULL DEFAULT 0")


def ensure_event_v3_columns(db: sqlite3.Connection) -> None:
    columns = [row["name"] for row in db.execute("PRAGMA table_info(events)").fetchall()]
    if "activity_selection_mode" not in columns:
        db.execute("ALTER TABLE events ADD COLUMN activity_selection_mode TEXT NOT NULL DEFAULT 'optional_later'")
    if "permitir_reserva_actividades_desde_landing" not in columns:
        db.execute("ALTER TABLE events ADD COLUMN permitir_reserva_actividades_desde_landing INTEGER NOT NULL DEFAULT 0")
    if "permitir_reserva_actividades_desde_portal" not in columns:
        db.execute("ALTER TABLE events ADD COLUMN permitir_reserva_actividades_desde_portal INTEGER NOT NULL DEFAULT 1")
    if "reserva_requiere_confirmacion" not in columns:
        db.execute("ALTER TABLE events ADD COLUMN reserva_requiere_confirmacion INTEGER NOT NULL DEFAULT 1")
    if "reserva_cooldown_segundos" not in columns:
        db.execute("ALTER TABLE events ADD COLUMN reserva_cooldown_segundos INTEGER NOT NULL DEFAULT 5")
    if "reserva_requiere_verificacion_simple" not in columns:
        db.execute("ALTER TABLE events ADD COLUMN reserva_requiere_verificacion_simple INTEGER NOT NULL DEFAULT 1")


def ensure_v4_2_columns(db: sqlite3.Connection) -> None:
    event_columns = [row["name"] for row in db.execute("PRAGMA table_info(events)").fetchall()]
    if "generar_certificados" not in event_columns:
        db.execute("ALTER TABLE events ADD COLUMN generar_certificados INTEGER NOT NULL DEFAULT 1")
    if "controlar_asistencia" not in event_columns:
        db.execute("ALTER TABLE events ADD COLUMN controlar_asistencia INTEGER NOT NULL DEFAULT 1")
    if "attendance_mode" not in event_columns:
        db.execute("ALTER TABLE events ADD COLUMN attendance_mode TEXT NOT NULL DEFAULT 'entry_only'")
    if "porcentaje_minimo_asistencia" not in event_columns:
        db.execute("ALTER TABLE events ADD COLUMN porcentaje_minimo_asistencia INTEGER NOT NULL DEFAULT 80")

    activity_columns = [row["name"] for row in db.execute("PRAGMA table_info(activities)").fetchall()]
    if "requiere_asistencia" not in activity_columns:
        db.execute("ALTER TABLE activities ADD COLUMN requiere_asistencia INTEGER NOT NULL DEFAULT 1")
    if "porcentaje_minimo_asistencia" not in activity_columns:
        db.execute("ALTER TABLE activities ADD COLUMN porcentaje_minimo_asistencia INTEGER NOT NULL DEFAULT 80")
    if "habilita_certificado" not in activity_columns:
        db.execute("ALTER TABLE activities ADD COLUMN habilita_certificado INTEGER NOT NULL DEFAULT 1")
    if "attendance_mode" not in activity_columns:
        db.execute("ALTER TABLE activities ADD COLUMN attendance_mode TEXT NOT NULL DEFAULT ''")

    certificate_columns = [row["name"] for row in db.execute("PRAGMA table_info(certificate_eligibility)").fetchall()]
    if "certificate_generated_at" not in certificate_columns:
        db.execute("ALTER TABLE certificate_eligibility ADD COLUMN certificate_generated_at TEXT")


def ensure_v4_4_columns(db: sqlite3.Connection) -> None:
    event_columns = [row["name"] for row in db.execute("PRAGMA table_info(events)").fetchall()]
    if "captation_mode" not in event_columns:
        db.execute("ALTER TABLE events ADD COLUMN captation_mode TEXT NOT NULL DEFAULT 'MIXTO'")
    if "primary_action_label" not in event_columns:
        db.execute("ALTER TABLE events ADD COLUMN primary_action_label TEXT NOT NULL DEFAULT ''")
    if "secondary_action_label" not in event_columns:
        db.execute("ALTER TABLE events ADD COLUMN secondary_action_label TEXT NOT NULL DEFAULT ''")
    if "whatsapp_number" not in event_columns:
        db.execute("ALTER TABLE events ADD COLUMN whatsapp_number TEXT NOT NULL DEFAULT ''")

    person_columns = [row["name"] for row in db.execute("PRAGMA table_info(people)").fetchall()]
    if "source" not in person_columns:
        db.execute("ALTER TABLE people ADD COLUMN source TEXT NOT NULL DEFAULT ''")
    if "device_type" not in person_columns:
        db.execute("ALTER TABLE people ADD COLUMN device_type TEXT NOT NULL DEFAULT ''")

    acc_columns = [row["name"] for row in db.execute("PRAGMA table_info(accreditations)").fetchall()]
    if "source" not in acc_columns:
        db.execute("ALTER TABLE accreditations ADD COLUMN source TEXT NOT NULL DEFAULT ''")
    if "source_detail" not in acc_columns:
        db.execute("ALTER TABLE accreditations ADD COLUMN source_detail TEXT NOT NULL DEFAULT ''")
    if "device_type" not in acc_columns:
        db.execute("ALTER TABLE accreditations ADD COLUMN device_type TEXT NOT NULL DEFAULT ''")


def ensure_user_pin_column(db: sqlite3.Connection) -> None:
    columns = [row["name"] for row in db.execute("PRAGMA table_info(users)").fetchall()]
    if "pin_hash" not in columns:
        db.execute("ALTER TABLE users ADD COLUMN pin_hash TEXT NOT NULL DEFAULT ''")


def ensure_reservation_bag_column(db: sqlite3.Connection) -> None:
    columns = [row["name"] for row in db.execute("PRAGMA table_info(reservations)").fetchall()]
    if "bag_id" not in columns:
        db.execute("ALTER TABLE reservations ADD COLUMN bag_id INTEGER REFERENCES capacity_bags(id) ON DELETE SET NULL")


def ensure_v3_tables(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS participant_communication_preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
            email TEXT NOT NULL DEFAULT '',
            phone TEXT NOT NULL DEFAULT '',
            acepta_email INTEGER NOT NULL DEFAULT 0,
            acepta_whatsapp INTEGER NOT NULL DEFAULT 0,
            canal_preferido TEXT NOT NULL DEFAULT 'email',
            fecha_consentimiento TEXT,
            ultimo_contacto TEXT,
            updated_at TEXT NOT NULL,
            UNIQUE(person_id)
        );

        CREATE TABLE IF NOT EXISTS communication_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
            person_id INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
            accreditation_id INTEGER REFERENCES accreditations(id) ON DELETE SET NULL,
            canal TEXT NOT NULL,
            fecha TEXT NOT NULL,
            tipo TEXT NOT NULL,
            asunto TEXT NOT NULL DEFAULT '',
            contenido TEXT NOT NULL DEFAULT '',
            estado TEXT NOT NULL DEFAULT 'demo'
        );

        CREATE TABLE IF NOT EXISTS communication_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL DEFAULT 0,
            code TEXT NOT NULL,
            name TEXT NOT NULL,
            tipo TEXT NOT NULL,
            asunto TEXT NOT NULL DEFAULT '',
            contenido TEXT NOT NULL DEFAULT '',
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            UNIQUE(event_id, code)
        );

        CREATE TABLE IF NOT EXISTS participant_announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            content TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'published',
            created_at TEXT NOT NULL
        );
        """
    )


def ensure_communication_templates(db: sqlite3.Connection) -> None:
    templates = [
        ("registration_confirmation", "Confirmacion de inscripcion", "confirmacion", "Inscripcion confirmada", "Tu inscripcion fue confirmada. Accede a tu portal personal para ver credencial, agenda y reservas."),
        ("reminder", "Recordatorio", "recordatorio", "Recordatorio del evento", "Te recordamos revisar tu agenda personal antes de asistir."),
        ("room_change", "Cambio de sala", "cambio de sala", "Cambio de sala", "Una actividad de tu agenda cambio de sala. Revisa tu portal personal."),
        ("time_change", "Cambio de horario", "cambio de horario", "Cambio de horario", "Una actividad de tu agenda cambio de horario. Revisa tu portal personal."),
        ("certificate_available", "Certificado disponible", "certificado", "Certificado disponible", "Tu certificado estara disponible desde el portal personal."),
    ]
    for code, name, tipo, asunto, contenido in templates:
        db.execute(
            """
            INSERT OR IGNORE INTO communication_templates (event_id, code, name, tipo, asunto, contenido, active, created_at)
            VALUES (0, ?, ?, ?, ?, ?, 1, ?)
            """,
            (code, name, tipo, asunto, contenido, now_iso()),
        )


def seed_if_empty() -> None:
    with connect() as db:
        count = db.execute("SELECT COUNT(*) AS c FROM events").fetchone()["c"]
        if count:
            return
        created = now_iso()
        cur = db.execute(
            """
            INSERT INTO events (name, description, venue, starts_at, ends_at, status, capacity, activity_selection_mode, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "Demo Congreso Operativo",
                "Evento de prueba para validar inscripcion, acreditacion y acceso.",
                "Auditorio principal",
                "2026-07-01T09:00",
                "2026-07-01T18:00",
                "published",
                3000,
                "optional_later",
                created,
            ),
        )
        audit(db, "system", "event.created", "event", cur.lastrowid, {"seed": True})
        ensure_default_types(db)
        ensure_default_spaces(db)


def ensure_default_types(db: sqlite3.Connection, event_id: int | None = None) -> None:
    defaults = [
        ("General", 0, 1),
        ("VIP", 0, 1),
        ("Prensa", 0, 1),
        ("Staff", 0, 1),
        ("Sponsor", 0, 1),
        ("Disertante", 0, 1),
    ]
    if event_id:
        rows = [{"id": event_id}]
    else:
        rows = db.execute("SELECT id FROM events").fetchall()
    for event in rows:
        for name, capacity, enabled in defaults:
            db.execute(
                """
                INSERT OR IGNORE INTO accreditation_types (event_id, name, capacity, access_enabled, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (event["id"], name, capacity, enabled, now_iso()),
            )


def ensure_default_spaces(db: sqlite3.Connection, event_id: int | None = None) -> None:
    if event_id:
        rows = [{"id": event_id}]
    else:
        rows = db.execute("SELECT id FROM events").fetchall()
    for event in rows:
        db.execute(
            """
            INSERT OR IGNORE INTO spaces (event_id, name, capacity, responsible, transition_minutes, status, created_at)
            VALUES (?, 'Auditorio principal', 0, '', 15, 'active', ?)
            """,
            (event["id"], now_iso()),
        )


def ensure_capacity_bags(db: sqlite3.Connection, event_id: int | None = None, activity_id: int | None = None) -> None:
    return capacity_bucket_service().ensure_for_event(db, event_id=event_id, activity_id=activity_id)
    params: list[object] = []
    where = "1 = 1"
    if event_id:
        where += " AND event_id = ?"
        params.append(event_id)
    if activity_id:
        where += " AND id = ?"
        params.append(activity_id)
    activities = db.execute(f"SELECT * FROM activities WHERE {where}", params).fetchall()
    for activity in activities:
        existing = db.execute("SELECT COUNT(*) AS c FROM capacity_bags WHERE activity_id = ?", (activity["id"],)).fetchone()["c"]
        if existing:
            continue
        capacity = int(activity["capacity"] or 0)
        if capacity <= 0:
            capacity = 0
        db.execute(
            """
            INSERT OR IGNORE INTO capacity_bags (
                event_id, activity_id, name, code, assigned_capacity, priority,
                public_visible, public_registration, reception_enabled, release_enabled, status, created_at
            )
            VALUES (?, ?, 'Online', 'online', ?, 10, 1, 1, 1, 1, 'active', ?)
            """,
            (activity["event_id"], activity["id"], capacity, now_iso()),
        )
        for priority, name, code in [
            (20, "Mostrador", "mostrador"),
            (30, "Empresas", "empresas"),
            (40, "Invitaciones", "invitaciones"),
            (50, "Sponsors", "sponsors"),
            (60, "Prensa", "prensa"),
            (70, "Protocolo", "protocolo"),
            (80, "Staff", "staff"),
            (90, "Backup operativo", "backup_operativo"),
        ]:
            db.execute(
                """
                INSERT OR IGNORE INTO capacity_bags (
                    event_id, activity_id, name, code, assigned_capacity, priority,
                    public_visible, public_registration, reception_enabled, release_enabled, status, created_at
                )
                VALUES (?, ?, ?, ?, 0, ?, 0, 0, 1, 1, 'active', ?)
                """,
                (activity["event_id"], activity["id"], name, code, priority, now_iso()),
            )


def bag_usage(db: sqlite3.Connection, bag_id: int) -> int:
    return capacity_bucket_service().bag_usage(db, bag_id)
    return int(
        db.execute(
            "SELECT COUNT(*) AS c FROM reservations WHERE bag_id = ? AND status = 'confirmed'",
            (bag_id,),
        ).fetchone()["c"]
        or 0
    )


def activity_bag_total(db: sqlite3.Connection, activity_id: int) -> int:
    return int(
        db.execute(
            "SELECT SUM(assigned_capacity) AS total FROM capacity_bags WHERE activity_id = ?",
            (activity_id,),
        ).fetchone()["total"]
        or 0
    )


def public_availability(db: sqlite3.Connection, activity_id: int) -> dict:
    return capacity_bucket_service().public_availability(db, activity_id)
    ensure_capacity_bags(db, activity_id=activity_id)
    row = db.execute(
        """
        SELECT SUM(assigned_capacity) AS capacity
        FROM capacity_bags
        WHERE activity_id = ? AND public_visible = 1 AND status = 'active'
        """,
        (activity_id,),
    ).fetchone()
    capacity = int(row["capacity"] or 0)
    used = int(
        db.execute(
            """
            SELECT COUNT(*) AS c
            FROM reservations r
            JOIN capacity_bags b ON b.id = r.bag_id
            WHERE r.activity_id = ? AND r.status = 'confirmed'
              AND b.public_visible = 1 AND b.status = 'active'
            """,
            (activity_id,),
        ).fetchone()["c"]
        or 0
    )
    remaining = max(capacity - used, 0)
    if capacity == 0 or remaining == 0:
        label, color = "Completa", "red"
    elif remaining / capacity <= 0.2:
        label, color = f"Ultimos lugares ({remaining})", "yellow"
    else:
        label, color = f"Quedan {remaining} lugares", "green"
    return {"capacity": capacity, "used": used, "remaining": remaining, "label": label, "color": color}


def pick_bag(db: sqlite3.Connection, event_id: int, activity_id: int, source: str) -> sqlite3.Row | None:
    return capacity_bucket_service().pick_bucket(db, event_id, activity_id, source)
    ensure_capacity_bags(db, event_id=event_id, activity_id=activity_id)
    activity = db.execute("SELECT capacity FROM activities WHERE id = ?", (activity_id,)).fetchone()
    physical_capacity = int(activity["capacity"] or 0) if activity else 0
    if source == "public":
        condition = "public_registration = 1"
    else:
        condition = "reception_enabled = 1"
    bags = db.execute(
        f"""
        SELECT *
        FROM capacity_bags
        WHERE event_id = ? AND activity_id = ? AND status = 'active' AND {condition}
        ORDER BY priority, id
        """,
        (event_id, activity_id),
    ).fetchall()
    for bag in bags:
        assigned = int(bag["assigned_capacity"] or 0)
        if (assigned == 0 and physical_capacity == 0) or (assigned > 0 and bag_usage(db, bag["id"]) < assigned):
            return bag
    return None


def ensure_public_display_config(db: sqlite3.Connection, event_id: int) -> dict:
    row = db.execute("SELECT * FROM public_display_config WHERE event_id = ?", (event_id,)).fetchone()
    if not row:
        db.execute(
            """
            INSERT INTO public_display_config (event_id, mode, refresh_seconds, paused, message, room_filter, status_filter, updated_at)
            VALUES (?, 'airport', 10, 0, '', '', '', ?)
            """,
            (event_id, now_iso()),
        )
        row = db.execute("SELECT * FROM public_display_config WHERE event_id = ?", (event_id,)).fetchone()
    return dict(row)


def public_activity_status(activity: dict) -> str:
    try:
        now = datetime.now()
        start = parse_local_datetime(activity["starts_at"])
        end = parse_local_datetime(activity["ends_at"])
        if now < start:
            return "Disponible"
        if start <= now <= end:
            return "En curso"
        return "Finalizada"
    except Exception:
        return "Disponible"


def ensure_default_users(db: sqlite3.Connection) -> None:
    defaults = [
        ("Admin", "Super Admin", "1234"),
        ("Productor", "Productor", "2000"),
        ("Coordinador", "Coordinador", "3000"),
        ("Recepcion", "Operador de recepcion", "2222"),
        ("Acceso", "Operador de acceso", "3333"),
        ("Visualizador", "Visualizador", "4444"),
    ]
    for name, role, pin in defaults:
        db.execute(
            """
            INSERT OR IGNORE INTO users (name, role, pin_hash, active, created_at)
            VALUES (?, ?, ?, 1, ?)
            """,
            (name, role, hash_pin(pin), now_iso()),
        )
        row = db.execute("SELECT pin_hash FROM users WHERE name = ?", (name,)).fetchone()
        if row and not row["pin_hash"]:
            db.execute("UPDATE users SET pin_hash = ? WHERE name = ?", (hash_pin(pin), name))


def hash_pin(pin: str) -> str:
    salt = "qr-white-label-local"
    digest = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt.encode("utf-8"), 120000)
    return digest.hex()


def verify_pin(pin: str, stored: str) -> bool:
    return hmac.compare_digest(hash_pin(pin), stored or "")


def parse_local_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


def validate_activity_schedule(
    db: sqlite3.Connection,
    event_id: int,
    space_id: int,
    starts_at: str,
    ends_at: str,
    exclude_activity_id: int | None = None,
) -> str | None:
    start = parse_local_datetime(starts_at)
    end = parse_local_datetime(ends_at)
    if end <= start:
        return "La hora de fin debe ser posterior al inicio"
    space = db.execute("SELECT * FROM spaces WHERE id = ? AND event_id = ?", (space_id, event_id)).fetchone()
    if not space:
        return "Espacio inexistente"
    transition = max(int(space["transition_minutes"] or 15), 15)
    params: list[object] = [event_id, space_id]
    extra = ""
    if exclude_activity_id:
        extra = "AND id <> ?"
        params.append(exclude_activity_id)
    rows = db.execute(
        f"""
        SELECT * FROM activities
        WHERE event_id = ? AND space_id = ? AND status <> 'cancelled' {extra}
        """,
        params,
    ).fetchall()
    for row in rows:
        other_start = parse_local_datetime(row["starts_at"])
        other_end = parse_local_datetime(row["ends_at"])
        separated = end + timedelta(minutes=transition) <= other_start or start >= other_end + timedelta(minutes=transition)
        if not separated:
            return f"Conflicto con {row['title']} en {space['name']}. Transicion minima: {transition} minutos"
    return None


def validate_reservation_overlap(
    db: sqlite3.Connection,
    accreditation_id: int,
    activity_id: int,
) -> str | None:
    target = db.execute("SELECT * FROM activities WHERE id = ?", (activity_id,)).fetchone()
    if not target:
        return "Actividad inexistente"
    target_start = parse_local_datetime(target["starts_at"])
    target_end = parse_local_datetime(target["ends_at"])
    rows = db.execute(
        """
        SELECT a.*
        FROM reservations r
        JOIN activities a ON a.id = r.activity_id
        WHERE r.accreditation_id = ? AND r.status = 'confirmed' AND r.activity_id <> ?
        """,
        (accreditation_id, activity_id),
    ).fetchall()
    for row in rows:
        start = parse_local_datetime(row["starts_at"])
        end = parse_local_datetime(row["ends_at"])
        if target_start < end and target_end > start:
            return f"Solapa con {row['title']}"
    return None


def reservation_status_for_capacity(db: sqlite3.Connection, activity_id: int) -> str:
    activity = db.execute("SELECT capacity FROM activities WHERE id = ?", (activity_id,)).fetchone()
    if not activity:
        raise ValueError("Actividad inexistente")
    capacity = int(activity["capacity"] or 0)
    if not capacity:
        return "confirmed"
    used = db.execute(
        "SELECT COUNT(*) AS c FROM reservations WHERE activity_id = ? AND status = 'confirmed'",
        (activity_id,),
    ).fetchone()["c"]
    return "waitlisted" if used >= capacity else "confirmed"


def create_reservation(
    db: sqlite3.Connection,
    event_id: int,
    activity_id: int,
    accreditation_id: int,
    source: str = "reception",
) -> dict:
    return reservation_service().create(
        db,
        event_id,
        activity_id,
        accreditation_id,
        source,
        overlap_validator=validate_reservation_overlap,
    )
    acc = db.execute(
        "SELECT * FROM accreditations WHERE id = ? AND event_id = ? AND status = 'active'",
        (accreditation_id, event_id),
    ).fetchone()
    activity = db.execute(
        "SELECT * FROM activities WHERE id = ? AND event_id = ? AND status <> 'cancelled'",
        (activity_id, event_id),
    ).fetchone()
    if not acc or not activity:
        return {"ok": False, "error": "Acreditacion o actividad invalida", "status_code": 404}
    existing = db.execute(
        "SELECT * FROM reservations WHERE activity_id = ? AND accreditation_id = ?",
        (activity_id, accreditation_id),
    ).fetchone()
    if existing:
        return {"ok": True, "status": existing["status"], "existing": True, "activity_id": activity_id, "title": activity["title"]}
    overlap = validate_reservation_overlap(db, accreditation_id, activity_id)
    if overlap:
        return {"ok": False, "error": overlap, "status_code": 409, "activity_id": activity_id, "title": activity["title"]}
    bag = pick_bag(db, event_id, activity_id, source)
    status = "confirmed" if bag else "waitlisted"
    cur = db.execute(
        """
        INSERT INTO reservations (event_id, activity_id, bag_id, accreditation_id, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (event_id, activity_id, bag["id"] if bag else None, accreditation_id, status, now_iso()),
    )
    return {"ok": True, "id": cur.lastrowid, "status": status, "activity_id": activity_id, "title": activity["title"]}


def activity_has_capacity(db: sqlite3.Connection, activity_id: int) -> bool:
    return reservation_service().activity_has_capacity(db, activity_id)
    activity = db.execute("SELECT * FROM activities WHERE id = ?", (activity_id,)).fetchone()
    if not activity:
        return False
    return pick_bag(db, activity["event_id"], activity_id, "reception") is not None


def promote_next_waitlisted(db: sqlite3.Connection, event_id: int, activity_id: int) -> dict | None:
    return reservation_service().promote_next_waitlisted(db, event_id, activity_id)
    bag = pick_bag(db, event_id, activity_id, "reception")
    if not bag:
        return None
    row = db.execute(
        """
        SELECT *
        FROM reservations
        WHERE event_id = ? AND activity_id = ? AND status = 'waitlisted'
        ORDER BY id
        LIMIT 1
        """,
        (event_id, activity_id),
    ).fetchone()
    if not row:
        return None
    db.execute("UPDATE reservations SET status = 'confirmed', bag_id = ? WHERE id = ?", (bag["id"], row["id"]))
    promoted = dict(row)
    promoted["bag_id"] = bag["id"]
    return promoted


def register_accreditation(db: sqlite3.Connection, event_id: int, data: dict) -> dict:
    event = db.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    if not event:
        return {"ok": False, "error": "Evento inexistente", "status_code": 404}
    used = db.execute("SELECT COUNT(*) AS c FROM accreditations WHERE event_id = ?", (event_id,)).fetchone()["c"]
    capacity = int(event["capacity"] or 0)
    if capacity and used >= capacity:
        return {"ok": False, "error": "Cupo completo", "status_code": 409}

    email = data.get("email", "").strip().lower()
    first_name = data.get("first_name", "").strip()
    last_name = data.get("last_name", "").strip()
    if not first_name or not last_name or not email:
        return {"ok": False, "error": "Faltan nombre, apellido o email", "status_code": 400}
    source = normalize_source(data.get("source"), "recepcion" if data.get("actor") != "public" else "landing")
    source_detail = str(data.get("source_detail") or data.get("utm_campaign") or data.get("qr_source") or "").strip()
    device_type = normalize_device(data.get("device_type"))

    person = db.execute("SELECT * FROM people WHERE email = ?", (email,)).fetchone()
    if person:
        person_id = person["id"]
        db.execute(
            """
            UPDATE people
            SET first_name = ?, last_name = ?, phone = ?, dni = ?, company = ?, position = ?,
                source = COALESCE(NULLIF(source, ''), ?),
                device_type = COALESCE(NULLIF(device_type, ''), ?)
            WHERE id = ?
            """,
            (
                first_name,
                last_name,
                data.get("phone", "").strip(),
                data.get("dni", "").strip(),
                data.get("company", "").strip(),
                data.get("position", "").strip(),
                source,
                device_type,
                person_id,
            ),
        )
    else:
        cur = db.execute(
            """
            INSERT INTO people (first_name, last_name, email, phone, dni, company, position, source, device_type, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                first_name,
                last_name,
                email,
                data.get("phone", "").strip(),
                data.get("dni", "").strip(),
                data.get("company", "").strip(),
                data.get("position", "").strip(),
                source,
                device_type,
                now_iso(),
            ),
        )
        person_id = cur.lastrowid

    acc_type = data.get("type", "General").strip() or "General"
    type_row = db.execute(
        "SELECT * FROM accreditation_types WHERE event_id = ? AND name = ?",
        (event_id, acc_type),
    ).fetchone()
    if not type_row:
        db.execute(
            """
            INSERT INTO accreditation_types (event_id, name, capacity, access_enabled, created_at)
            VALUES (?, ?, 0, 1, ?)
            """,
            (event_id, acc_type, now_iso()),
        )
        type_row = db.execute(
            "SELECT * FROM accreditation_types WHERE event_id = ? AND name = ?",
            (event_id, acc_type),
        ).fetchone()
    type_capacity = int(type_row["capacity"] or 0)
    if type_capacity:
        type_used = db.execute(
            "SELECT COUNT(*) AS c FROM accreditations WHERE event_id = ? AND type = ?",
            (event_id, acc_type),
        ).fetchone()["c"]
        if type_used >= type_capacity:
            return {"ok": False, "error": f"Cupo completo para {acc_type}", "status_code": 409}

    existing = db.execute(
        "SELECT * FROM accreditations WHERE event_id = ? AND person_id = ?",
        (event_id, person_id),
    ).fetchone()
    if existing:
        db.execute(
            """
            UPDATE accreditations
            SET source = COALESCE(NULLIF(source, ''), ?),
                source_detail = COALESCE(NULLIF(source_detail, ''), ?),
                device_type = COALESCE(NULLIF(device_type, ''), ?)
            WHERE id = ?
            """,
            (source, source_detail, device_type, existing["id"]),
        )
        upsert_communication_preference(db, person_id, data)
        return {"ok": True, "id": existing["id"], "token": existing["token"], "existing": True, "person_id": person_id}

    token = make_token()
    while db.execute("SELECT 1 FROM accreditations WHERE token = ?", (token,)).fetchone():
        token = make_token()
    cur = db.execute(
        """
        INSERT INTO accreditations (event_id, person_id, type, token, status, source, source_detail, device_type, created_at)
        VALUES (?, ?, ?, ?, 'active', ?, ?, ?, ?)
        """,
        (event_id, person_id, acc_type, token, source, source_detail, device_type, now_iso()),
    )
    upsert_communication_preference(db, person_id, data)
    upsert_conversation_source(db, event_id, person_id, int(cur.lastrowid), source, data.get("channel") or ("whatsapp" if source == "whatsapp" else "web"), device_type)
    return {"ok": True, "id": cur.lastrowid, "token": token, "existing": False, "person_id": person_id}


def truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "si", "sí", "yes", "on"}


SOURCE_VALUES = {"landing", "whatsapp", "qr_fisico", "linkedin", "instagram", "facebook", "email", "empresa", "sponsor", "invitacion", "recepcion", "manual", "otro"}
DEVICE_VALUES = {"mobile", "tablet", "desktop"}


def normalize_source(value: object, default: str = "landing") -> str:
    source = str(value or "").strip().lower() or default
    return source if source in SOURCE_VALUES or source.startswith("qr_") else "otro"


def normalize_device(value: object) -> str:
    device = str(value or "").strip().lower()
    return device if device in DEVICE_VALUES else "desktop"


def record_captation_event(
    db: sqlite3.Connection,
    event_id: int,
    action: str,
    source: str,
    device_type: str,
    *,
    source_detail: str = "",
    session_id: str = "",
    accreditation_id: int | None = None,
    person_id: int | None = None,
) -> None:
    db.execute(
        """
        INSERT INTO captation_events (
            event_id, source, source_detail, device_type, action,
            session_id, accreditation_id, person_id, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_id,
            normalize_source(source),
            str(source_detail or "").strip(),
            normalize_device(device_type),
            action,
            str(session_id or "").strip(),
            accreditation_id,
            person_id,
            now_iso(),
        ),
    )


def upsert_conversation_source(
    db: sqlite3.Connection,
    event_id: int,
    person_id: int | None,
    accreditation_id: int | None,
    source: str,
    channel: str,
    device_type: str,
) -> None:
    db.execute(
        """
        INSERT INTO conversation_sources (
            event_id, person_id, accreditation_id, source, channel, device_type, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (event_id, person_id, accreditation_id, normalize_source(source), str(channel or "").strip() or "web", normalize_device(device_type), now_iso()),
    )


def upsert_communication_preference(db: sqlite3.Connection, person_id: int, data: dict) -> None:
    email = data.get("email", "").strip().lower()
    phone = data.get("phone", "").strip()
    acepta_email = 1 if truthy(data.get("acepta_email")) else 0
    acepta_whatsapp = 1 if truthy(data.get("acepta_whatsapp")) else 0
    preferred = data.get("canal_preferido", "").strip() or ("whatsapp" if acepta_whatsapp else "email")
    consent_at = now_iso() if acepta_email or acepta_whatsapp else None
    existing = db.execute(
        "SELECT * FROM participant_communication_preferences WHERE person_id = ?",
        (person_id,),
    ).fetchone()
    if existing:
        db.execute(
            """
            UPDATE participant_communication_preferences
            SET email = ?, phone = ?, acepta_email = ?, acepta_whatsapp = ?,
                canal_preferido = ?, fecha_consentimiento = COALESCE(?, fecha_consentimiento),
                updated_at = ?
            WHERE person_id = ?
            """,
            (email, phone, acepta_email, acepta_whatsapp, preferred, consent_at, now_iso(), person_id),
        )
    else:
        db.execute(
            """
            INSERT INTO participant_communication_preferences (
                person_id, email, phone, acepta_email, acepta_whatsapp,
                canal_preferido, fecha_consentimiento, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (person_id, email, phone, acepta_email, acepta_whatsapp, preferred, consent_at, now_iso()),
        )


def communication_log(
    db: sqlite3.Connection,
    event_id: int,
    person_id: int,
    accreditation_id: int | None,
    canal: str,
    tipo: str,
    asunto: str,
    contenido: str,
    estado: str = "demo",
) -> int:
    cur = db.execute(
        """
        INSERT INTO communication_logs (event_id, person_id, accreditation_id, canal, fecha, tipo, asunto, contenido, estado)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (event_id, person_id, accreditation_id, canal, now_iso(), tipo, asunto, contenido, estado),
    )
    db.execute(
        "UPDATE participant_communication_preferences SET ultimo_contacto = ?, updated_at = ? WHERE person_id = ?",
        (now_iso(), now_iso(), person_id),
    )
    return int(cur.lastrowid)


def portal_payload(db: sqlite3.Connection, token: str) -> dict | None:
    row = db.execute(
        """
        SELECT a.*, p.first_name, p.last_name, p.email, p.phone, p.dni, p.company, p.position,
               COALESCE(a.source, p.source, '') AS participant_source,
               COALESCE(a.device_type, p.device_type, '') AS participant_device_type,
               e.name AS event_name, e.description AS event_description, e.venue, e.starts_at, e.ends_at,
               e.activity_selection_mode, e.permitir_reserva_actividades_desde_portal,
               e.reserva_requiere_confirmacion, e.reserva_cooldown_segundos,
               e.reserva_requiere_verificacion_simple
        FROM accreditations a
        JOIN people p ON p.id = a.person_id
        JOIN events e ON e.id = a.event_id
        WHERE a.token = ?
        """,
        (token,),
    ).fetchone()
    if not row:
        return None
    data = dict(row)
    attendance_service().ensure_absences(db, int(data["event_id"]))
    release_available_certificates(db, int(data["event_id"]))
    reservations = [
        dict(r)
        for r in db.execute(
            """
            SELECT r.*, a.title, a.starts_at, a.ends_at, a.activity_type, s.name AS space_name
            FROM reservations r
            JOIN activities a ON a.id = r.activity_id
            JOIN spaces s ON s.id = a.space_id
            WHERE r.accreditation_id = ?
            ORDER BY a.starts_at
            """,
            (data["id"],),
        ).fetchall()
    ]
    current_dt = datetime.now()
    next_activity = None
    current_activity = None
    for item in reservations:
        try:
            starts = datetime.fromisoformat(str(item["starts_at"]).replace("Z", "+00:00")).replace(tzinfo=None)
            ends = datetime.fromisoformat(str(item["ends_at"]).replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            starts = ends = None
        item["participant_status"] = "Finalizada" if ends and ends < current_dt and item["status"] != "cancelled" else reservation_status_label(item["status"])
        if item["status"] == "cancelled":
            continue
        if starts and ends and starts <= current_dt <= ends:
            current_activity = current_activity or item
        if starts and starts >= current_dt:
            next_activity = next_activity or item
    active_reservations_by_activity = {
        int(r["activity_id"]): r
        for r in reservations
        if r["status"] != "cancelled"
    }
    reserved_ids = set(active_reservations_by_activity)
    activities = []
    for activity in db.execute(
        """
        SELECT a.*, s.name AS space_name
        FROM activities a
        JOIN spaces s ON s.id = a.space_id
        WHERE a.event_id = ? AND a.status = 'published'
        ORDER BY a.starts_at
        """,
        (data["event_id"],),
    ).fetchall():
        item = dict(activity)
        availability = public_availability(db, item["id"])
        item["public_availability"] = availability["label"]
        item["public_availability_color"] = availability["color"]
        item["public_remaining"] = availability["remaining"]
        item["reserved"] = int(item["id"]) in reserved_ids
        reservation = active_reservations_by_activity.get(int(item["id"]))
        if reservation:
            item["reservation_id"] = reservation["id"]
            item["reservation_status"] = reservation["status"]
            item["reservation_label"] = reservation_status_label(reservation["status"])
        item.pop("capacity", None)
        activities.append(item)
    preference = row_to_dict(
        db.execute(
            "SELECT * FROM participant_communication_preferences WHERE person_id = ?",
            (data["person_id"],),
        ).fetchone()
    ) or {
        "email": data["email"],
        "phone": data["phone"],
        "acepta_email": 0,
        "acepta_whatsapp": 0,
        "canal_preferido": "email",
    }
    communications = [
        dict(r)
        for r in db.execute(
            """
            SELECT *
            FROM communication_logs
            WHERE person_id = ? AND event_id = ?
            ORDER BY id DESC
            LIMIT 20
            """,
            (data["person_id"], data["event_id"]),
        ).fetchall()
    ]
    announcements = [
        dict(r)
        for r in db.execute(
            """
            SELECT *
            FROM participant_announcements
            WHERE event_id = ? AND status = 'published'
            ORDER BY id DESC
            LIMIT 20
            """,
            (data["event_id"],),
        ).fetchall()
    ]
    attendances = [
        dict(r)
        for r in db.execute(
            """
            SELECT at.*, a.title, a.starts_at, a.ends_at, s.name AS space_name,
                   ce.id AS certificate_id, ce.certificate_generated_at
            FROM activity_attendance at
            JOIN activities a ON a.id = at.activity_id
            JOIN spaces s ON s.id = a.space_id
            LEFT JOIN certificate_eligibility ce ON ce.activity_id = at.activity_id AND ce.accreditation_id = at.accreditation_id
            WHERE at.accreditation_id = ?
            ORDER BY a.starts_at
            """,
            (data["id"],),
        ).fetchall()
    ]
    data["portal_url"] = f"/p.html?token={data['token']}"
    data["qr_payload"] = data["token"]
    data["reservations"] = reservations
    data["activities"] = activities
    data["communication_preference"] = preference
    data["communications"] = communications
    data["announcements"] = announcements
    data["attendances"] = attendances
    data["certificates"] = [
        {
            "id": item["certificate_id"],
            "activity_id": item["activity_id"],
            "title": item["title"],
            "percentage": item["attendance_percentage"],
            "url": f"/api/certificate.pdf?token={data['token']}&activity_id={item['activity_id']}",
        }
        for item in attendances
        if item.get("certificate_generated_at")
    ]
    data["next_activity"] = next_activity
    data["current_activity"] = current_activity
    data["certificate"] = {
        "requiere_asistencia": int(data.get("requiere_asistencia") or 0),
        "porcentaje_minimo": int(data.get("porcentaje_minimo") or 0),
        "elegible_certificado": int(data.get("elegible_certificado") or 0),
    }
    data["reservation_config"] = {
        "permitir_reserva_actividades_desde_portal": int(data.get("permitir_reserva_actividades_desde_portal", 1) or 0),
        "reserva_requiere_confirmacion": int(data.get("reserva_requiere_confirmacion", 1) or 0),
        "reserva_cooldown_segundos": max(10, int(data.get("reserva_cooldown_segundos", 10) or 0)),
        "reserva_bloque_cada": 5,
        "reserva_bloque_segundos": 300,
        "reserva_requiere_verificacion_simple": int(data.get("reserva_requiere_verificacion_simple", 1) or 0),
    }
    return data


def reservation_status_label(status: str) -> str:
    if status == "confirmed":
        return "Confirmada"
    if status == "cancelled":
        return "Cancelada"
    return "Lista de espera"


def certificate_activity_finished(ends_at: str) -> bool:
    try:
        end_dt = datetime.fromisoformat(str(ends_at).replace("Z", "+00:00"))
        if end_dt.tzinfo is None:
            end_dt = end_dt.replace(tzinfo=timezone.utc)
        return end_dt <= datetime.now(timezone.utc)
    except ValueError:
        return False


def release_available_certificates(db: sqlite3.Connection, event_id: int | None = None) -> int:
    where = "ce.elegible = 1 AND ce.estado = 'Elegible' AND ce.certificate_generated_at IS NULL"
    params: list[object] = []
    if event_id:
        where += " AND ce.event_id = ?"
        params.append(event_id)
    rows = db.execute(
        f"""
        SELECT ce.id, ce.event_id, ce.activity_id, ce.accreditation_id, a.ends_at
        FROM certificate_eligibility ce
        JOIN activities a ON a.id = ce.activity_id
        WHERE {where}
        """,
        params,
    ).fetchall()
    released = 0
    stamp = now_iso()
    for row in rows:
        if not certificate_activity_finished(row["ends_at"]):
            continue
        db.execute("UPDATE certificate_eligibility SET certificate_generated_at = ? WHERE id = ?", (stamp, row["id"]))
        audit(
            db,
            "system",
            "certificate.generated",
            "certificate_eligibility",
            row["id"],
            {"event_id": row["event_id"], "activity_id": row["activity_id"], "accreditation_id": row["accreditation_id"], "automatic": True},
        )
        released += 1
    return released


def certificate_payload(db: sqlite3.Connection, token: str, activity_id: int | None = None, manual: bool = False) -> dict | None:
    release_available_certificates(db)
    params: list[object] = [token.strip().upper()]
    where = "ac.token = ?"
    if activity_id:
        where += " AND ce.activity_id = ?"
        params.append(activity_id)
    if not manual:
        where += " AND ce.elegible = 1 AND ce.estado = 'Elegible' AND ce.certificate_generated_at IS NOT NULL"
    row = db.execute(
        f"""
        SELECT ce.id AS certificate_id, ce.activity_id, ce.porcentaje, ce.elegible, ce.estado, ce.fecha_calculo,
               ce.certificate_generated_at,
               e.name AS event_name, e.venue,
               a.title AS activity_title, a.starts_at, a.ends_at,
               s.name AS space_name,
               ac.id AS accreditation_id, ac.token, ac.type,
               p.first_name, p.last_name, p.email, p.company, p.dni
        FROM certificate_eligibility ce
        JOIN events e ON e.id = ce.event_id
        JOIN activities a ON a.id = ce.activity_id
        JOIN spaces s ON s.id = a.space_id
        JOIN accreditations ac ON ac.id = ce.accreditation_id
        JOIN people p ON p.id = ac.person_id
        WHERE {where}
        ORDER BY ce.certificate_generated_at DESC, ce.fecha_calculo DESC, a.starts_at
        LIMIT 1
        """,
        params,
    ).fetchone()
    return dict(row) if row else None


def participant_metrics(db: sqlite3.Connection, event_id: int) -> dict:
    row = db.execute(
        """
        SELECT
            COUNT(a.id) AS registered,
            SUM(CASE WHEN EXISTS (
                SELECT 1 FROM reservations r WHERE r.accreditation_id = a.id AND r.status <> 'cancelled'
            ) THEN 1 ELSE 0 END) AS with_reservations,
            SUM(CASE WHEN EXISTS (
                SELECT 1 FROM reservations r WHERE r.accreditation_id = a.id AND r.status = 'confirmed'
            ) THEN 1 ELSE 0 END) AS with_agenda,
            SUM(CASE WHEN cp.acepta_email = 1 THEN 1 ELSE 0 END) AS consent_email,
            SUM(CASE WHEN cp.acepta_whatsapp = 1 THEN 1 ELSE 0 END) AS consent_whatsapp,
            SUM(CASE WHEN cp.acepta_email = 1 AND cp.acepta_whatsapp = 1 THEN 1 ELSE 0 END) AS consent_both
        FROM accreditations a
        JOIN people p ON p.id = a.person_id
        LEFT JOIN participant_communication_preferences cp ON cp.person_id = p.id
        WHERE a.event_id = ? AND a.status <> 'cancelled'
        """,
        (event_id,),
    ).fetchone()
    return {key: int(row[key] or 0) for key in row.keys()}


def audit(db: sqlite3.Connection, actor: str, action: str, entity_type: str, entity_id: int | None, payload: dict) -> None:
    return audit_service().record(db, actor, action, entity_type, entity_id, payload)
    db.execute(
        """
        INSERT INTO audit_logs (actor, action, entity_type, entity_id, payload, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (actor, action, entity_type, entity_id, json.dumps(payload, ensure_ascii=True), now_iso()),
    )


def actor_role(db: sqlite3.Connection, actor: str) -> str:
    row = db.execute("SELECT role FROM users WHERE lower(name) = lower(?) AND active = 1", (actor,)).fetchone()
    if row:
        return row["role"]
    if actor.lower() in ("admin", "system"):
        return "Super Admin"
    if actor.lower() == "public":
        return "Publico"
    return ""


def can_actor(db: sqlite3.Connection, actor: str, allowed_roles: set[str]) -> bool:
    return actor_role(db, actor) in allowed_roles


def deny_message(actor: str) -> dict:
    return {"error": f"El usuario {actor or 'sin identificar'} no tiene permiso para esta accion"}


def make_token() -> str:
    return "EVT-" + secrets.token_urlsafe(9).replace("-", "").replace("_", "").upper()[:12]


def gf_mul(x: int, y: int) -> int:
    result = 0
    while y:
        if y & 1:
            result ^= x
        x <<= 1
        if x & 0x100:
            x ^= 0x11D
        y >>= 1
    return result


def rs_generator(degree: int) -> list[int]:
    poly = [1]
    root = 1
    for _ in range(degree):
        next_poly = [0] * (len(poly) + 1)
        for i, coef in enumerate(poly):
            next_poly[i] ^= coef
            next_poly[i + 1] ^= gf_mul(coef, root)
        poly = next_poly
        root = gf_mul(root, 2)
    return poly[1:]


def rs_remainder(data: list[int], degree: int) -> list[int]:
    generator = rs_generator(degree)
    result = [0] * degree
    for value in data:
        factor = value ^ result.pop(0)
        result.append(0)
        for i, coef in enumerate(generator):
            result[i] ^= gf_mul(coef, factor)
    return result


class BitBuffer:
    def __init__(self) -> None:
        self.bits: list[int] = []

    def append(self, value: int, length: int) -> None:
        for i in range(length - 1, -1, -1):
            self.bits.append((value >> i) & 1)

    def to_codewords(self) -> list[int]:
        return [
            sum(bit << (7 - i) for i, bit in enumerate(self.bits[pos : pos + 8]))
            for pos in range(0, len(self.bits), 8)
        ]


def encode_qr_payload(text: str) -> list[int]:
    if not text or any(ch not in QR_ALPHANUM for ch in text):
        raise ValueError("El token solo puede usar caracteres QR alfanumericos")
    if len(text) > 25:
        raise ValueError("Token demasiado largo para QR version 1")

    data_capacity_bits = 19 * 8
    bits = BitBuffer()
    bits.append(0b0010, 4)
    bits.append(len(text), 9)
    i = 0
    while i + 1 < len(text):
        bits.append(QR_ALPHANUM.index(text[i]) * 45 + QR_ALPHANUM.index(text[i + 1]), 11)
        i += 2
    if i < len(text):
        bits.append(QR_ALPHANUM.index(text[i]), 6)
    bits.append(0, min(4, data_capacity_bits - len(bits.bits)))
    while len(bits.bits) % 8:
        bits.append(0, 1)
    data = bits.to_codewords()
    pad = 0xEC
    while len(data) < 19:
        data.append(pad)
        pad = 0x11 if pad == 0xEC else 0xEC
    return data + rs_remainder(data, 7)


def draw_finder(modules: list[list[int | None]], reserved: list[list[bool]], x: int, y: int) -> None:
    for dy in range(-1, 8):
        for dx in range(-1, 8):
            xx, yy = x + dx, y + dy
            if 0 <= xx < 21 and 0 <= yy < 21:
                reserved[yy][xx] = True
                modules[yy][xx] = 0
    for dy in range(7):
        for dx in range(7):
            xx, yy = x + dx, y + dy
            modules[yy][xx] = 1 if dx in (0, 6) or dy in (0, 6) or (2 <= dx <= 4 and 2 <= dy <= 4) else 0


def format_bits(mask: int) -> int:
    data = (0b01 << 3) | mask
    value = data << 10
    generator = 0x537
    for i in range(14, 9, -1):
        if (value >> i) & 1:
            value ^= generator << (i - 10)
    return ((data << 10) | value) ^ 0x5412


def make_qr_matrix(text: str) -> list[list[int]]:
    size = 21
    modules: list[list[int | None]] = [[None for _ in range(size)] for _ in range(size)]
    reserved = [[False for _ in range(size)] for _ in range(size)]

    draw_finder(modules, reserved, 0, 0)
    draw_finder(modules, reserved, size - 7, 0)
    draw_finder(modules, reserved, 0, size - 7)
    for i in range(8, size - 8):
        bit = 1 if i % 2 == 0 else 0
        modules[6][i] = bit
        modules[i][6] = bit
        reserved[6][i] = True
        reserved[i][6] = True
    modules[13][8] = 1
    reserved[13][8] = True
    for i in range(9):
        reserved[8][i] = True
        reserved[i][8] = True
    for i in range(8):
        reserved[8][size - 1 - i] = True
        reserved[size - 1 - i][8] = True

    codewords = encode_qr_payload(text)
    data_bits = [(cw >> i) & 1 for cw in codewords for i in range(7, -1, -1)]
    bit_index = 0
    upward = True
    col = size - 1
    while col > 0:
        if col == 6:
            col -= 1
        rows = range(size - 1, -1, -1) if upward else range(size)
        for row in rows:
            for c in (col, col - 1):
                if reserved[row][c]:
                    continue
                bit = data_bits[bit_index] if bit_index < len(data_bits) else 0
                bit_index += 1
                if (row + c) % 2 == 0:
                    bit ^= 1
                modules[row][c] = bit
        upward = not upward
        col -= 2

    fmt = format_bits(0)
    coords_a = [(8, i) for i in range(6)] + [(8, 7), (8, 8), (7, 8)] + [(i, 8) for i in range(5, -1, -1)]
    coords_b = [(size - 1 - i, 8) for i in range(7)] + [(8, size - 8 + i) for i in range(8)]
    for i, (x, y) in enumerate(coords_a):
        modules[y][x] = (fmt >> i) & 1
    for i, (x, y) in enumerate(coords_b):
        modules[y][x] = (fmt >> i) & 1

    return [[int(cell or 0) for cell in row] for row in modules]


def qr_svg(text: str) -> str:
    qr = QrCode.encode_text(text, QrCode.Ecc.MEDIUM)
    border = 4
    scale = 10
    size_modules = qr.get_size() + border * 2
    size = size_modules * scale
    rects = []
    for y in range(qr.get_size()):
        for x in range(qr.get_size()):
            if qr.get_module(x, y):
                rects.append(f'<rect x="{(x + border) * scale}" y="{(y + border) * scale}" width="{scale}" height="{scale}"/>')
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" width="{size}" height="{size}" role="img">'
        f'<rect width="100%" height="100%" fill="#fff"/>'
        f'<g fill="#111">{"".join(rects)}</g>'
        f'</svg>'
    )


def credential_svg(data: dict) -> str:
    token = str(data["token"])
    qr = QrCode.encode_text(token, QrCode.Ecc.MEDIUM)
    border = 4
    scale = 10
    qr_size = (qr.get_size() + border * 2) * scale
    qr_x = 65
    qr_y = 86
    rects = []
    for y in range(qr.get_size()):
        for x in range(qr.get_size()):
            if qr.get_module(x, y):
                rects.append(
                    f'<rect x="{qr_x + (x + border) * scale}" y="{qr_y + (y + border) * scale}" width="{scale}" height="{scale}"/>'
                )
    full_name = escape(f"{data.get('first_name', '')} {data.get('last_name', '')}".strip() or "Participante")
    company = escape(str(data.get("company") or "Sin empresa"))
    event_name = escape(str(data.get("event_name") or "Evento"))
    acc_type = escape(str(data.get("type") or "General"))
    token_safe = escape(token)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 420 680" width="420" height="680" role="img">
<rect width="420" height="680" rx="28" fill="#f6f7f8"/>
<rect x="26" y="24" width="368" height="632" rx="24" fill="#fff" stroke="#d9e0e6" stroke-width="2"/>
<text x="210" y="62" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="17" font-weight="700" fill="#116a7b" textLength="300" lengthAdjust="spacingAndGlyphs">{event_name}</text>
<rect x="{qr_x - 16}" y="{qr_y - 16}" width="{qr_size + 32}" height="{qr_size + 32}" rx="18" fill="#fff" stroke="#d9e0e6" stroke-width="2"/>
<g fill="#111">{"".join(rects)}</g>
<text x="210" y="438" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="28" font-weight="700" fill="#17212b" textLength="330" lengthAdjust="spacingAndGlyphs">{full_name}</text>
<text x="210" y="478" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="20" fill="#617080" textLength="320" lengthAdjust="spacingAndGlyphs">{company}</text>
<text x="210" y="520" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="17" fill="#17212b">{acc_type}</text>
<rect x="72" y="548" width="276" height="54" rx="12" fill="#edf4f6"/>
<text x="210" y="581" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="18" font-weight="700" fill="#116a7b">{token_safe}</text>
<text x="210" y="628" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="13" fill="#617080">Credencial digital</text>
</svg>"""


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def fit_text(draw: ImageDraw.ImageDraw, text: str, max_width: int, size: int, bold: bool = False):
    text = text or ""
    while size > 12:
        selected = font(size, bold)
        width = draw.textbbox((0, 0), text, font=selected)[2]
        if width <= max_width:
            return selected
        size -= 1
    return font(size, bold)


def draw_centered(draw: ImageDraw.ImageDraw, y: int, text: str, max_width: int, size: int, fill: str, bold: bool = False) -> None:
    selected = fit_text(draw, text, max_width, size, bold)
    bbox = draw.textbbox((0, 0), text, font=selected)
    x = (420 - (bbox[2] - bbox[0])) // 2
    draw.text((x, y), text, fill=fill, font=selected)


def draw_centered_on(draw: ImageDraw.ImageDraw, canvas_width: int, y: int, text: str, max_width: int, size: int, fill: str, bold: bool = False) -> None:
    selected = fit_text(draw, text, max_width, size, bold)
    bbox = draw.textbbox((0, 0), text, font=selected)
    x = (canvas_width - (bbox[2] - bbox[0])) // 2
    draw.text((x, y), text, fill=fill, font=selected)


def credential_image(data: dict) -> Image.Image:
    image = Image.new("RGB", (420, 680), "#f6f7f8")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((26, 24, 394, 656), radius=24, fill="#ffffff", outline="#d9e0e6", width=2)
    draw_centered(draw, 42, str(data.get("event_name") or "Evento"), 300, 17, "#116a7b", True)

    token = str(data["token"])
    qr = QrCode.encode_text(token, QrCode.Ecc.MEDIUM)
    border = 4
    scale = 10
    qr_x = 65
    qr_y = 86
    qr_size = (qr.get_size() + border * 2) * scale
    draw.rounded_rectangle((qr_x - 16, qr_y - 16, qr_x + qr_size + 16, qr_y + qr_size + 16), radius=18, fill="#ffffff", outline="#d9e0e6", width=2)
    for y in range(qr.get_size()):
        for x in range(qr.get_size()):
            if qr.get_module(x, y):
                left = qr_x + (x + border) * scale
                top = qr_y + (y + border) * scale
                draw.rectangle((left, top, left + scale - 1, top + scale - 1), fill="#111111")

    full_name = f"{data.get('first_name', '')} {data.get('last_name', '')}".strip() or "Participante"
    company = str(data.get("company") or "Sin empresa")
    acc_type = str(data.get("type") or "General")
    draw_centered(draw, 430, full_name, 330, 28, "#17212b", True)
    draw_centered(draw, 474, company, 320, 20, "#617080")
    draw_centered(draw, 520, acc_type, 300, 17, "#17212b")
    draw.rounded_rectangle((72, 548, 348, 602), radius=12, fill="#edf4f6")
    draw_centered(draw, 565, token, 250, 18, "#116a7b", True)
    draw_centered(draw, 628, "Credencial digital", 240, 13, "#617080")
    return image


def credential_image_bytes(data: dict, fmt: str) -> bytes:
    output = BytesIO()
    image = credential_image(data)
    if fmt == "PDF":
        image.save(output, format="PDF", resolution=144.0)
    else:
        image.save(output, format="PNG")
    return output.getvalue()


def certificate_image(data: dict) -> Image.Image:
    width, height = 1600, 1130
    image = Image.new("RGB", (width, height), "#fbfbf8")
    draw = ImageDraw.Draw(image)
    draw.rectangle((42, 42, width - 42, height - 42), outline="#116a7b", width=8)
    draw.rectangle((70, 70, width - 70, height - 70), outline="#d4a23a", width=3)
    draw_centered_on(draw, width, 130, str(data.get("event_name") or "Evento"), 1200, 46, "#116a7b", True)
    draw_centered_on(draw, width, 230, "CERTIFICADO DE ASISTENCIA", 1200, 58, "#17212b", True)
    draw_centered_on(draw, width, 330, "Se certifica que", 900, 30, "#617080")
    full_name = f"{data.get('first_name', '')} {data.get('last_name', '')}".strip() or "Participante"
    draw_centered_on(draw, width, 385, full_name, 1200, 62, "#17212b", True)
    company = str(data.get("company") or "").strip()
    if company:
        draw_centered_on(draw, width, 470, company, 1000, 30, "#617080")
    draw_centered_on(draw, width, 545, "asistio efectivamente a la actividad", 1100, 30, "#617080")
    draw_centered_on(draw, width, 600, str(data.get("activity_title") or "Actividad"), 1250, 48, "#17212b", True)
    detail = f"{data.get('space_name') or ''} - {format_certificate_date(data.get('starts_at'))}".strip(" -")
    draw_centered_on(draw, width, 680, detail, 1100, 28, "#617080")
    percentage = int(data.get("porcentaje") or data.get("attendance_percentage") or 0)
    draw.rounded_rectangle((560, 760, 1040, 845), radius=18, fill="#edf4f6", outline="#d9e0e6", width=2)
    draw_centered_on(draw, width, 783, f"Asistencia registrada: {percentage}%", 450, 32, "#116a7b", True)
    footer = f"Folio CE-{data.get('certificate_id')} | Token {data.get('token')}"
    draw_centered_on(draw, width, 940, footer, 1100, 24, "#617080")
    draw_centered_on(draw, width, 990, "Documento generado automaticamente por la plataforma de acreditaciones", 1100, 22, "#617080")
    return image


def format_certificate_date(value: object) -> str:
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return str(value or "")


def certificate_pdf_bytes(data: dict) -> bytes:
    output = BytesIO()
    certificate_image(data).save(output, format="PDF", resolution=144.0)
    return output.getvalue()


def read_json(handler: SimpleHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0"))
    raw = handler.rfile.read(length) if length else b"{}"
    if not raw:
        return {}
    return json.loads(raw.decode("utf-8"))


def send_download(handler: SimpleHTTPRequestHandler, filename: str, content_type: str, body: bytes) -> None:
    handler.send_response(200)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Disposition", f"attachment; filename={filename}")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def create_db_backup() -> Path:
    return backup_service().create_backup()
    BACKUP_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = BACKUP_DIR / f"acreditaciones-{stamp}.sqlite3"
    with DB_LOCK, connect() as db:
        db.execute("PRAGMA wal_checkpoint(FULL)")
    shutil.copy2(DB_PATH, backup_path)
    prune_backups()
    return backup_path


def prune_backups() -> None:
    return backup_service().prune()
    if BACKUP_KEEP_LAST <= 0 or not BACKUP_DIR.exists():
        return
    backups = sorted(BACKUP_DIR.glob("*.sqlite3"), key=lambda p: p.stat().st_mtime, reverse=True)
    for backup in backups[BACKUP_KEEP_LAST:]:
        try:
            backup.unlink()
        except OSError:
            pass


def auto_backup_loop() -> None:
    if AUTO_BACKUP_MINUTES <= 0:
        return
    while not BACKUP_STOP.wait(AUTO_BACKUP_MINUTES * 60):
        try:
            create_db_backup()
        except Exception as exc:
            print(f"Backup automatico fallido: {exc}")


def start_auto_backup() -> threading.Thread | None:
    if AUTO_BACKUP_MINUTES <= 0:
        return None
    thread = threading.Thread(target=auto_backup_loop, name="auto-backup", daemon=True)
    thread.start()
    return thread


def row_to_dict(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row else None


def parse_cookies(header: str | None) -> dict[str, str]:
    cookies: dict[str, str] = {}
    for part in (header or "").split(";"):
        if "=" in part:
            key, value = part.strip().split("=", 1)
            cookies[key] = value
    return cookies


def public_static_path(path: str) -> bool:
    clean = urlparse(path).path
    return clean in {
        "/login.html",
        "/display.html",
        "/scan.html",
        "/e.html",
        "/p.html",
        "/styles.css",
        "/public.js",
        "/app.js",
        "/jsQR.min.js",
        "/html5-qrcode.min.js",
    } or clean.startswith("/p/") or clean.startswith("/api/")


def public_api_get(path: str) -> bool:
    return path in {"/api/app-config", "/api/event", "/api/portal", "/api/qr.svg", "/api/credential.svg", "/api/credential.png", "/api/credential.pdf", "/api/certificate.pdf", "/api/users", "/api/auth/me", "/api/network-info", "/api/public-display", "/api/participant-metrics"}


def public_api_post(path: str) -> bool:
    return path in {
        "/api/register",
        "/api/captation/event",
        "/api/auth/login",
        "/api/auth/logout",
        "/api/portal/reserve",
        "/api/portal/reservations/status",
        "/api/portal/preferences",
        "/api/portal/profile",
    }


def local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def network_info(handler: SimpleHTTPRequestHandler) -> dict:
    host, port = handler.server.server_address[:2]
    ip = local_ip()
    bind_host = str(host)
    base = configured_base_url(handler)
    return {
        "bind_host": bind_host,
        "port": int(port),
        "base_url": base,
        "local_url": f"http://localhost:{port}",
        "network_url": base if BASE_URL else f"http://{ip}:{port}",
        "require_login": bool(getattr(handler.server, "require_login", False)),
        "network_enabled": bind_host in {"0.0.0.0", ""},
        "env": APP_ENV,
        "version": APP_VERSION,
    }


class AppHandler(SimpleHTTPRequestHandler):
    server_version = "AcreditacionesMVP/0.1"

    def login_required(self) -> bool:
        return bool(getattr(self.server, "require_login", False))

    def session_user(self) -> dict | None:
        token = parse_cookies(self.headers.get("Cookie")).get("qr_session", "")
        session = AUTH_SESSIONS.get(token)
        if not session:
            return None
        if time.time() - float(session.get("created_at", 0)) > 12 * 60 * 60:
            AUTH_SESSIONS.pop(token, None)
            return None
        return session

    def is_authenticated(self) -> bool:
        return not self.login_required() or self.session_user() is not None

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        if HTTPS_REQUIRED or self.headers.get("X-Forwarded-Proto") == "https":
            self.send_header("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        super().end_headers()

    def translate_path(self, path: str) -> str:
        parsed = urlparse(path)
        clean = parsed.path
        if clean == "/":
            return str(STATIC_DIR / "index.html")
        if clean.startswith("/p/"):
            return str(STATIC_DIR / "p.html")
        target = STATIC_DIR / clean.lstrip("/")
        if target.exists():
            return str(target)
        return str(LEGACY_STATIC_DIR / clean.lstrip("/"))

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self.send_json({"status": "ok", "env": APP_ENV, "version": APP_VERSION})
            return
        if parsed.path.startswith("/api/"):
            self.handle_api_get(parsed.path, parse_qs(parsed.query))
            return
        if self.login_required() and not public_static_path(parsed.path) and not self.session_user():
            self.send_response(302)
            self.send_header("Location", "/login.html")
            self.end_headers()
            return
        super().do_GET()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self.handle_api_post(parsed.path)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def send_json(self, data: dict | list, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def require_api_auth(self, path: str, is_post: bool = False) -> bool:
        if not self.login_required():
            return True
        public = public_api_post(path) if is_post else public_api_get(path)
        if public:
            return True
        if self.session_user():
            return True
        self.send_json({"error": "Sesion requerida"}, 401)
        return False

    def handle_api_get(self, path: str, query: dict[str, list[str]]) -> None:
        try:
            if not self.require_api_auth(path, is_post=False):
                return
            if path == "/api/auth/me":
                session = self.session_user()
                self.send_json({"authenticated": bool(session), "user": session, "config": runtime_config(self)})
                return

            if path == "/api/app-config":
                self.send_json(runtime_config(self))
                return

            if path == "/api/network-info":
                self.send_json(network_info(self))
                return

            if path == "/api/qr.svg":
                token = query.get("token", [""])[0].strip().upper()
                with connect() as db:
                    svg = qr_service().svg(db, token, qr_svg)
                    acc = db.execute("SELECT id, event_id FROM accreditations WHERE token = ?", (token,)).fetchone()
                    if acc:
                        audit(db, "portal", "portal.qr_viewed", "accreditation", acc["id"], {"event_id": acc["event_id"]})
                if not svg:
                    self.send_error(HTTPStatus.NOT_FOUND, "QR inexistente")
                    return
                body = svg.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "image/svg+xml; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            if path == "/api/credential.svg":
                token = query.get("token", [""])[0].strip().upper()
                with connect() as db:
                    data = portal_payload(db, token)
                    if data:
                        audit(db, "portal", "portal.credential_downloaded", "accreditation", data["id"], {"event_id": data["event_id"]})
                if not data:
                    self.send_error(HTTPStatus.NOT_FOUND, "Credencial inexistente")
                    return
                body = credential_svg(data).encode("utf-8")
                filename = f"{token}-credencial.svg"
                self.send_response(200)
                self.send_header("Content-Type", "image/svg+xml; charset=utf-8")
                self.send_header("Content-Disposition", f"attachment; filename={filename}")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            if path in {"/api/credential.png", "/api/credential.pdf"}:
                token = query.get("token", [""])[0].strip().upper()
                with connect() as db:
                    data = portal_payload(db, token)
                    if data:
                        audit(db, "portal", "portal.credential_downloaded", "accreditation", data["id"], {"event_id": data["event_id"], "format": path.rsplit(".", 1)[-1]})
                if not data:
                    self.send_error(HTTPStatus.NOT_FOUND, "Credencial inexistente")
                    return
                is_pdf = path.endswith(".pdf")
                body = credential_image_bytes(data, "PDF" if is_pdf else "PNG")
                ext = "pdf" if is_pdf else "png"
                content_type = "application/pdf" if is_pdf else "image/png"
                filename = f"{token}-credencial.{ext}"
                disposition = "inline" if query.get("inline", ["0"])[0] == "1" else "attachment"
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Disposition", f"{disposition}; filename={filename}")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            if path == "/api/certificate.pdf":
                token = query.get("token", [""])[0].strip().upper()
                activity_id = int(query.get("activity_id", ["0"])[0] or 0)
                manual = query.get("manual", ["0"])[0] == "1"
                with connect() as db:
                    if manual:
                        session = self.session_user()
                        if not session:
                            self.send_json({"error": "Sesion requerida"}, 401)
                            return
                        actor = session["name"]
                        if not can_actor(db, actor, ADMIN_ROLES | RECEPTION_ROLES):
                            self.send_json(deny_message(actor), 403)
                            return
                    data = certificate_payload(db, token, activity_id or None, manual=manual)
                    if data:
                        audit(
                            db,
                            "portal" if not manual else "Admin",
                            "certificate.downloaded" if not manual else "certificate.manual_printed",
                            "certificate_eligibility",
                            data["certificate_id"],
                            {"token": token, "activity_id": data.get("activity_id"), "manual": manual},
                        )
                if not data:
                    self.send_error(HTTPStatus.NOT_FOUND, "Certificado no disponible")
                    return
                body = certificate_pdf_bytes(data)
                filename = f"{token}-certificado.pdf"
                self.send_response(200)
                self.send_header("Content-Type", "application/pdf")
                self.send_header("Content-Disposition", f"inline; filename={filename}")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            if path == "/api/events":
                with connect() as db:
                    rows = db.execute(
                        """
                        SELECT e.*,
                               SUM(CASE WHEN a.status <> 'cancelled' THEN 1 ELSE 0 END) AS accreditation_count,
                               SUM(CASE WHEN a.checked_in_at IS NOT NULL AND a.status <> 'cancelled' THEN 1 ELSE 0 END) AS checked_in_count
                        FROM events e
                        LEFT JOIN accreditations a ON a.event_id = e.id
                        GROUP BY e.id
                        ORDER BY e.id DESC
                        """
                    ).fetchall()
                self.send_json([dict(r) for r in rows])
                return

            if path == "/api/event":
                event_id = int(query.get("event_id", ["0"])[0])
                with connect() as db:
                    attendance_service().ensure_absences(db, event_id)
                    event = row_to_dict(db.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone())
                    if not event:
                        self.send_json({"error": "Evento inexistente"}, 404)
                        return
                    activities = [
                        dict(r)
                        for r in db.execute(
                            """
                            SELECT a.*, s.name AS space_name
                            FROM activities a
                            JOIN spaces s ON s.id = a.space_id
                            WHERE a.event_id = ? AND a.status = 'published'
                            ORDER BY a.starts_at
                            """,
                            (event_id,),
                        ).fetchall()
                    ]
                    for activity in activities:
                        availability = public_availability(db, activity["id"])
                        activity["public_availability"] = availability["label"]
                        activity["public_availability_color"] = availability["color"]
                        activity["public_remaining"] = availability["remaining"]
                        activity.pop("capacity", None)
                    types = [
                        dict(r)
                        for r in db.execute(
                            "SELECT name FROM accreditation_types WHERE event_id = ? AND access_enabled = 1 ORDER BY name",
                            (event_id,),
                        ).fetchall()
                    ]
                event["activities"] = activities
                event["types"] = types
                self.send_json(event)
                return

            if path == "/api/users":
                with connect() as db:
                    ensure_default_users(db)
                    rows = db.execute(
                        "SELECT * FROM users WHERE active = 1 ORDER BY id"
                    ).fetchall()
                self.send_json([dict(r) for r in rows])
                return

            if path == "/api/audit":
                event_id = int(query.get("event_id", ["0"])[0])
                params: list[object] = []
                where = "1 = 1"
                if event_id:
                    where = """
                    (
                        (entity_type = 'event' AND entity_id = ?)
                        OR payload LIKE ?
                    )
                    """
                    params = [event_id, f'%"event_id": {event_id}%']
                with connect() as db:
                    rows = db.execute(
                        f"""
                        SELECT *
                        FROM audit_logs
                        WHERE {where}
                        ORDER BY id DESC
                        LIMIT 200
                        """,
                        params,
                    ).fetchall()
                result = []
                for row in rows:
                    item = dict(row)
                    try:
                        item["payload"] = json.loads(item["payload"] or "{}")
                    except json.JSONDecodeError:
                        item["payload"] = {}
                    result.append(item)
                self.send_json(result)
                return

            if path == "/api/types":
                event_id = int(query.get("event_id", ["0"])[0])
                with connect() as db:
                    ensure_default_types(db, event_id)
                    rows = db.execute(
                        """
                        SELECT t.*,
                               SUM(CASE WHEN a.status <> 'cancelled' THEN 1 ELSE 0 END) AS used,
                               SUM(CASE WHEN a.checked_in_at IS NOT NULL AND a.status <> 'cancelled' THEN 1 ELSE 0 END) AS checked_in
                        FROM accreditation_types t
                        LEFT JOIN accreditations a ON a.event_id = t.event_id AND a.type = t.name
                        WHERE t.event_id = ?
                        GROUP BY t.id
                        ORDER BY
                            CASE t.name
                                WHEN 'General' THEN 1
                                WHEN 'VIP' THEN 2
                                WHEN 'Prensa' THEN 3
                                WHEN 'Staff' THEN 4
                                WHEN 'Sponsor' THEN 5
                                WHEN 'Disertante' THEN 6
                                ELSE 99
                            END,
                            t.name
                        """,
                        (event_id,),
                    ).fetchall()
                self.send_json([dict(r) for r in rows])
                return

            if path == "/api/spaces":
                event_id = int(query.get("event_id", ["0"])[0])
                with connect() as db:
                    ensure_default_spaces(db, event_id)
                    rows = db.execute(
                        """
                        SELECT s.*,
                               COUNT(a.id) AS activity_count
                        FROM spaces s
                        LEFT JOIN activities a ON a.space_id = s.id AND a.status <> 'cancelled'
                        WHERE s.event_id = ?
                        GROUP BY s.id
                        ORDER BY s.name
                        """,
                        (event_id,),
                    ).fetchall()
                self.send_json([dict(r) for r in rows])
                return

            if path == "/api/activities":
                event_id = int(query.get("event_id", ["0"])[0])
                with connect() as db:
                    ensure_capacity_bags(db, event_id=event_id)
                    rows = db.execute(
                        """
                        SELECT a.*, s.name AS space_name, s.transition_minutes,
                               (SELECT COUNT(*) FROM reservations r WHERE r.activity_id = a.id) AS reservations_count,
                               (SELECT COUNT(*) FROM reservations r WHERE r.activity_id = a.id AND r.status = 'confirmed') AS confirmed_count,
                               (SELECT COUNT(*) FROM reservations r WHERE r.activity_id = a.id AND r.status = 'waitlisted') AS waitlist_count
                        FROM activities a
                        JOIN spaces s ON s.id = a.space_id
                        WHERE a.event_id = ?
                        ORDER BY a.starts_at, s.name
                        """,
                        (event_id,),
                    ).fetchall()
                self.send_json([dict(r) for r in rows])
                return

            if path == "/api/reservations":
                event_id = int(query.get("event_id", ["0"])[0])
                with connect() as db:
                    rows = db.execute(
                        """
                        SELECT r.*, a.title AS activity_title, a.starts_at, a.ends_at, s.name AS space_name,
                               p.first_name, p.last_name, p.email, ac.token, ac.type
                        FROM reservations r
                        JOIN activities a ON a.id = r.activity_id
                        JOIN spaces s ON s.id = a.space_id
                        JOIN accreditations ac ON ac.id = r.accreditation_id
                        JOIN people p ON p.id = ac.person_id
                        WHERE r.event_id = ?
                        ORDER BY r.status DESC, a.starts_at, p.last_name
                        """,
                        (event_id,),
                    ).fetchall()
                self.send_json([dict(r) for r in rows])
                return

            if path == "/api/attendances":
                event_id = int(query.get("event_id", ["0"])[0])
                activity_id = int(query.get("activity_id", ["0"])[0] or 0)
                params: list[object] = [event_id]
                where = "at.event_id = ?"
                if activity_id:
                    where += " AND at.activity_id = ?"
                    params.append(activity_id)
                with DB_LOCK, connect() as db:
                    db.execute("BEGIN IMMEDIATE")
                    attendance_service().ensure_absences(db, event_id)
                    rows = db.execute(
                        f"""
                        SELECT at.*, a.title AS activity_title, a.starts_at, a.ends_at, s.name AS space_name,
                               p.first_name, p.last_name, p.email, p.company, ac.token, ac.type
                        FROM activity_attendance at
                        JOIN activities a ON a.id = at.activity_id
                        JOIN spaces s ON s.id = a.space_id
                        JOIN accreditations ac ON ac.id = at.accreditation_id
                        JOIN people p ON p.id = ac.person_id
                        WHERE {where}
                        ORDER BY a.starts_at, p.last_name, p.first_name
                        """,
                        params,
                    ).fetchall()
                    db.execute("COMMIT")
                self.send_json([dict(r) for r in rows])
                return

            if path == "/api/attendance-dashboard":
                event_id = int(query.get("event_id", ["0"])[0])
                with DB_LOCK, connect() as db:
                    db.execute("BEGIN IMMEDIATE")
                    attendance_service().ensure_absences(db, event_id)
                    activities = [
                        dict(r)
                        for r in db.execute(
                            """
                            SELECT a.id, a.title, s.name AS space_name,
                                   (SELECT COUNT(*) FROM reservations r WHERE r.activity_id = a.id AND r.status = 'confirmed') AS reserved,
                                   (SELECT COUNT(*) FROM activity_attendance at WHERE at.activity_id = a.id AND at.status IN ('Presente', 'Completa')) AS present,
                                   (SELECT COUNT(*) FROM activity_attendance at WHERE at.activity_id = a.id AND at.status = 'Ausente') AS absent,
                                   (SELECT COUNT(*) FROM activity_attendance at WHERE at.activity_id = a.id AND at.status = 'Parcial') AS partial,
                                   (SELECT COUNT(*) FROM activity_attendance at WHERE at.activity_id = a.id AND at.eligibility_status = 'Elegible') AS eligible,
                                   (SELECT COUNT(*) FROM activity_attendance at WHERE at.activity_id = a.id AND at.eligibility_status = 'No elegible') AS not_eligible,
                                   (SELECT ROUND(AVG(at.attendance_percentage), 1) FROM activity_attendance at WHERE at.activity_id = a.id AND at.status <> 'Pendiente') AS average_percentage
                            FROM activities a
                            JOIN spaces s ON s.id = a.space_id
                            WHERE a.event_id = ? AND a.status <> 'cancelled'
                            GROUP BY a.id
                            ORDER BY a.starts_at
                            """,
                            (event_id,),
                        ).fetchall()
                    ]
                    totals = dict(
                        db.execute(
                            """
                            SELECT
                                SUM(CASE WHEN status IN ('Presente', 'Completa') THEN 1 ELSE 0 END) AS present,
                                SUM(CASE WHEN status = 'Ausente' THEN 1 ELSE 0 END) AS absent,
                                SUM(CASE WHEN status = 'Parcial' THEN 1 ELSE 0 END) AS partial,
                                SUM(CASE WHEN eligibility_status = 'Elegible' THEN 1 ELSE 0 END) AS eligible,
                                SUM(CASE WHEN eligibility_status = 'No elegible' THEN 1 ELSE 0 END) AS not_eligible,
                                ROUND(AVG(CASE WHEN status <> 'Pendiente' THEN attendance_percentage END), 1) AS average_percentage
                            FROM activity_attendance
                            WHERE event_id = ?
                            """,
                            (event_id,),
                        ).fetchone()
                    )
                    db.execute("COMMIT")
                self.send_json({"totals": totals, "activities": activities})
                return

            if path == "/api/marketing-dashboard":
                event_id = int(query.get("event_id", ["0"])[0])
                with connect() as db:
                    by_source = [
                        dict(r)
                        for r in db.execute(
                            """
                            SELECT source,
                                   SUM(CASE WHEN action = 'landing_opened' THEN 1 ELSE 0 END) AS visitors,
                                   SUM(CASE WHEN action = 'form_started' THEN 1 ELSE 0 END) AS started,
                                   SUM(CASE WHEN action = 'form_completed' THEN 1 ELSE 0 END) AS registrations,
                                   SUM(CASE WHEN action = 'portal_created' THEN 1 ELSE 0 END) AS portals,
                                   SUM(CASE WHEN action = 'reservation_created' THEN 1 ELSE 0 END) AS reservations
                            FROM captation_events
                            WHERE event_id = ?
                            GROUP BY source
                            ORDER BY registrations DESC, visitors DESC
                            """,
                            (event_id,),
                        ).fetchall()
                    ]
                    for row in by_source:
                        visitors = int(row["visitors"] or 0)
                        registrations = int(row["registrations"] or 0)
                        row["conversion_rate"] = round((registrations / visitors) * 100, 1) if visitors else 0
                        row["abandonment"] = max(int(row["started"] or 0) - registrations, 0)
                    by_device = [
                        dict(r)
                        for r in db.execute(
                            """
                            SELECT device_type,
                                   SUM(CASE WHEN action = 'landing_opened' THEN 1 ELSE 0 END) AS visitors,
                                   SUM(CASE WHEN action = 'form_completed' THEN 1 ELSE 0 END) AS registrations
                            FROM captation_events
                            WHERE event_id = ?
                            GROUP BY device_type
                            ORDER BY registrations DESC
                            """,
                            (event_id,),
                        ).fetchall()
                    ]
                    qr_sources = [
                        dict(r)
                        for r in db.execute(
                            """
                            SELECT source, source_detail,
                                   SUM(CASE WHEN action = 'landing_opened' THEN 1 ELSE 0 END) AS visitors,
                                   SUM(CASE WHEN action = 'form_completed' THEN 1 ELSE 0 END) AS registrations
                            FROM captation_events
                            WHERE event_id = ? AND (source LIKE 'qr_%' OR source = 'qr_fisico')
                            GROUP BY source, source_detail
                            ORDER BY registrations DESC, visitors DESC
                            """,
                            (event_id,),
                        ).fetchall()
                    ]
                    totals = dict(
                        db.execute(
                            """
                            SELECT
                                SUM(CASE WHEN action = 'landing_opened' THEN 1 ELSE 0 END) AS visitors,
                                SUM(CASE WHEN action = 'form_started' THEN 1 ELSE 0 END) AS started,
                                SUM(CASE WHEN action = 'form_completed' THEN 1 ELSE 0 END) AS registrations
                            FROM captation_events
                            WHERE event_id = ?
                            """,
                            (event_id,),
                        ).fetchone()
                    )
                    visitors = int(totals["visitors"] or 0)
                    registrations = int(totals["registrations"] or 0)
                    totals["conversion_rate"] = round((registrations / visitors) * 100, 1) if visitors else 0
                    totals["abandonment"] = max(int(totals["started"] or 0) - registrations, 0)
                self.send_json({"totals": totals, "by_source": by_source, "by_device": by_device, "qr_sources": qr_sources})
                return

            if path == "/api/alerts":
                event_id = int(query.get("event_id", ["0"])[0])
                alerts: list[dict] = []
                with connect() as db:
                    ensure_capacity_bags(db, event_id=event_id)
                    event = db.execute(
                        """
                        SELECT e.*, COUNT(a.id) AS used
                        FROM events e
                        LEFT JOIN accreditations a ON a.event_id = e.id
                        WHERE e.id = ?
                        GROUP BY e.id
                        """,
                        (event_id,),
                    ).fetchone()
                    if event and int(event["capacity"] or 0):
                        usage = int(event["used"] or 0) / int(event["capacity"])
                        if usage >= 0.9:
                            alerts.append({"level": "warn", "message": f"Cupo general al {round(usage * 100)}%"})
                    type_rows = db.execute(
                        """
                        SELECT t.name, t.capacity, COUNT(a.id) AS used
                        FROM accreditation_types t
                        LEFT JOIN accreditations a ON a.event_id = t.event_id AND a.type = t.name
                        WHERE t.event_id = ?
                        GROUP BY t.id
                        """,
                        (event_id,),
                    ).fetchall()
                    for row in type_rows:
                        capacity = int(row["capacity"] or 0)
                        used = int(row["used"] or 0)
                        if capacity and used >= capacity:
                            alerts.append({"level": "danger", "message": f"Tipo {row['name']} lleno"})
                        elif capacity and used / capacity >= 0.9:
                            alerts.append({"level": "warn", "message": f"Tipo {row['name']} supera 90%"})
                    activity_rows = db.execute(
                        """
                        SELECT a.title, a.capacity,
                               SUM(CASE WHEN r.status = 'confirmed' THEN 1 ELSE 0 END) AS confirmed,
                               SUM(CASE WHEN r.status = 'waitlisted' THEN 1 ELSE 0 END) AS waitlisted
                        FROM activities a
                        LEFT JOIN reservations r ON r.activity_id = a.id
                        WHERE a.event_id = ?
                        GROUP BY a.id
                        """,
                        (event_id,),
                    ).fetchall()
                    for row in activity_rows:
                        capacity = int(row["capacity"] or 0)
                        confirmed = int(row["confirmed"] or 0)
                        waitlisted = int(row["waitlisted"] or 0)
                        if waitlisted:
                            alerts.append({"level": "warn", "message": f"{row['title']} tiene {waitlisted} en espera"})
                        if capacity and confirmed >= capacity:
                            alerts.append({"level": "danger", "message": f"Actividad {row['title']} llena"})
                        elif capacity and confirmed / capacity >= 0.9:
                            alerts.append({"level": "warn", "message": f"Actividad {row['title']} supera 90%"})
                    bag_rows = db.execute(
                        """
                        SELECT b.*, a.title AS activity_title,
                               COUNT(r.id) AS used
                        FROM capacity_bags b
                        JOIN activities a ON a.id = b.activity_id
                        LEFT JOIN reservations r ON r.bag_id = b.id AND r.status = 'confirmed'
                        WHERE b.event_id = ?
                        GROUP BY b.id
                        """,
                        (event_id,),
                    ).fetchall()
                    for bag in bag_rows:
                        assigned = int(bag["assigned_capacity"] or 0)
                        used = int(bag["used"] or 0)
                        if assigned and used >= assigned:
                            alerts.append({"level": "danger", "message": f"Bolsa {bag['name']} agotada en {bag['activity_title']}"})
                        elif assigned and used / assigned >= 0.8:
                            alerts.append({"level": "warn", "message": f"Bolsa {bag['name']} con ultimos lugares en {bag['activity_title']}"})
                self.send_json(alerts)
                return

            if path == "/api/activity-detail":
                activity_id = int(query.get("activity_id", ["0"])[0] or 0)
                with connect() as db:
                    row = db.execute(
                        """
                        SELECT a.*, s.name AS space_name, s.transition_minutes
                        FROM activities a
                        JOIN spaces s ON s.id = a.space_id
                        WHERE a.id = ?
                        """,
                        (activity_id,),
                    ).fetchone()
                    if not row:
                        self.send_json({"error": "Actividad inexistente"}, 404)
                        return
                    activity = dict(row)
                    attendance_service().ensure_absences(db, int(activity["event_id"]))
                    availability = public_availability(db, activity_id)
                    stats = dict(
                        db.execute(
                            """
                            SELECT
                                SUM(CASE WHEN status = 'confirmed' THEN 1 ELSE 0 END) AS confirmed,
                                SUM(CASE WHEN status = 'waitlisted' THEN 1 ELSE 0 END) AS waitlisted,
                                SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) AS cancelled
                            FROM reservations
                            WHERE activity_id = ?
                            """,
                            (activity_id,),
                        ).fetchone()
                    )
                    attendance = dict(
                        db.execute(
                            """
                            SELECT
                                SUM(CASE WHEN at.status IN ('Presente', 'Completa') THEN 1 ELSE 0 END) AS present,
                                SUM(CASE WHEN at.status = 'Ausente' THEN 1 ELSE 0 END) AS absent,
                                SUM(CASE WHEN at.status = 'Parcial' THEN 1 ELSE 0 END) AS partial,
                                SUM(CASE WHEN at.eligibility_status = 'Elegible' THEN 1 ELSE 0 END) AS eligible,
                                SUM(CASE WHEN at.eligibility_status = 'No elegible' THEN 1 ELSE 0 END) AS not_eligible,
                                ROUND(AVG(CASE WHEN at.status <> 'Pendiente' THEN at.attendance_percentage END), 1) AS average_percentage
                            FROM activity_attendance at
                            WHERE at.activity_id = ?
                            """,
                            (activity_id,),
                        ).fetchone()
                    )
                    bags = [
                        dict(r)
                        for r in db.execute(
                            """
                            SELECT b.*, COUNT(r.id) AS used
                            FROM capacity_bags b
                            LEFT JOIN reservations r ON r.bag_id = b.id AND r.status = 'confirmed'
                            WHERE b.activity_id = ?
                            GROUP BY b.id
                            ORDER BY b.priority, b.id
                            """,
                            (activity_id,),
                        ).fetchall()
                    ]
                    recent_access = [
                        dict(r)
                        for r in db.execute(
                            """
                            SELECT l.result, l.reason, l.operator, l.created_at, p.first_name, p.last_name
                            FROM access_logs l
                            LEFT JOIN accreditations ac ON ac.id = l.accreditation_id
                            LEFT JOIN people p ON p.id = ac.person_id
                            WHERE l.checkpoint LIKE ? OR l.event_id = ?
                            ORDER BY l.id DESC
                            LIMIT 10
                            """,
                            (f"%{activity['title']}%", activity["event_id"]),
                        ).fetchall()
                    ]
                    attendance_rows = [
                        dict(r)
                        for r in db.execute(
                            """
                            SELECT at.*, p.first_name, p.last_name, p.email, ac.token
                            FROM activity_attendance at
                            JOIN accreditations ac ON ac.id = at.accreditation_id
                            JOIN people p ON p.id = ac.person_id
                            WHERE at.activity_id = ?
                            ORDER BY p.last_name, p.first_name
                            LIMIT 80
                            """,
                            (activity_id,),
                        ).fetchall()
                    ]
                self.send_json({"activity": activity, "availability": availability, "stats": stats, "attendance": attendance, "attendance_rows": attendance_rows, "bags": bags, "recent_access": recent_access})
                return

            if path == "/api/system-status":
                event_id = int(query.get("event_id", ["0"])[0])
                since_expr = "datetime('now', '-15 minutes')"
                with connect() as db:
                    active_rows = db.execute(
                        f"""
                        SELECT operator, checkpoint, MAX(created_at) AS last_seen, COUNT(*) AS scans
                        FROM access_logs
                        WHERE (event_id = ? OR ? = 0)
                          AND datetime(created_at) >= {since_expr}
                        GROUP BY operator, checkpoint
                        ORDER BY last_seen DESC
                        """,
                        (event_id, event_id),
                    ).fetchall()
                    recent = db.execute(
                        f"""
                        SELECT
                            SUM(CASE WHEN result = 'granted' THEN 1 ELSE 0 END) AS granted,
                            SUM(CASE WHEN result = 'rejected' THEN 1 ELSE 0 END) AS rejected,
                            COUNT(*) AS total
                        FROM access_logs
                        WHERE (event_id = ? OR ? = 0)
                          AND datetime(created_at) >= {since_expr}
                        """,
                        (event_id, event_id),
                    ).fetchone()
                    rejected_rows = db.execute(
                        """
                        SELECT l.*, p.first_name, p.last_name
                        FROM access_logs l
                        LEFT JOIN accreditations a ON a.id = l.accreditation_id
                        LEFT JOIN people p ON p.id = a.person_id
                        WHERE (l.event_id = ? OR ? = 0) AND l.result = 'rejected'
                        ORDER BY l.id DESC
                        LIMIT 8
                        """,
                        (event_id, event_id),
                    ).fetchall()
                    db_size = DB_PATH.stat().st_size if DB_PATH.exists() else 0
                    backups = sorted(BACKUP_DIR.glob("*.sqlite3"), key=lambda p: p.stat().st_mtime, reverse=True) if BACKUP_DIR.exists() else []
                    latest_backup = None
                    if backups:
                        backup_age_minutes = round((datetime.now() - datetime.fromtimestamp(backups[0].stat().st_mtime)).total_seconds() / 60, 1)
                        backup_check = verify_backup_file(backups[0])
                        latest_backup = {
                            "name": backups[0].name,
                            "size": backups[0].stat().st_size,
                            "created_at": datetime.fromtimestamp(backups[0].stat().st_mtime).isoformat(timespec="seconds"),
                            "age_minutes": backup_age_minutes,
                            "integrity_ok": backup_check["ok"],
                            "integrity_detail": backup_check["detail"],
                            "warning": "Backup antiguo" if backup_age_minutes > max(AUTO_BACKUP_MINUTES * 3, 30) else "",
                        }
                    status = {
                        "server_time": now_iso(),
                        "started_at": STARTED_AT,
                        "env": APP_ENV,
                        "version": APP_VERSION,
                        "base_url": configured_base_url(self),
                        "database": {
                            "engine": DB_CONFIG.engine,
                            "sqlite_path": str(DB_PATH),
                            "production_ready": DB_CONFIG.production_ready,
                        },
                        "database_size": db_size,
                        "latest_backup": latest_backup,
                        "recent_window_minutes": 15,
                        "recent_access": {
                            "granted": int(recent["granted"] or 0),
                            "rejected": int(recent["rejected"] or 0),
                            "total": int(recent["total"] or 0),
                        },
                        "active_operators": [dict(r) for r in active_rows],
                        "recent_rejections": [dict(r) for r in rejected_rows],
                    }
                self.send_json(status)
                return

            if path == "/api/summary":
                event_id = int(query.get("event_id", ["0"])[0])
                with connect() as db:
                    event = row_to_dict(db.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone())
                    if not event:
                        self.send_json({"error": "Evento inexistente"}, 404)
                        return
                    accreditation = dict(
                        db.execute(
                            """
                            SELECT
                                SUM(CASE WHEN status <> 'cancelled' THEN 1 ELSE 0 END) AS active,
                                SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) AS cancelled,
                                SUM(CASE WHEN checked_in_at IS NOT NULL AND status <> 'cancelled' THEN 1 ELSE 0 END) AS checked,
                                SUM(CASE WHEN checked_in_at IS NULL AND status <> 'cancelled' THEN 1 ELSE 0 END) AS pending,
                                COUNT(*) AS total
                            FROM accreditations
                            WHERE event_id = ?
                            """,
                            (event_id,),
                        ).fetchone()
                    )
                    by_type = db.execute(
                        """
                        SELECT type,
                               SUM(CASE WHEN status <> 'cancelled' THEN 1 ELSE 0 END) AS active,
                               SUM(CASE WHEN checked_in_at IS NOT NULL AND status <> 'cancelled' THEN 1 ELSE 0 END) AS checked,
                               SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) AS cancelled
                        FROM accreditations
                        WHERE event_id = ?
                        GROUP BY type
                        ORDER BY active DESC, type
                        """,
                        (event_id,),
                    ).fetchall()
                    reservations = db.execute(
                        """
                        SELECT status, COUNT(*) AS total
                        FROM reservations
                        WHERE event_id = ?
                        GROUP BY status
                        """,
                        (event_id,),
                    ).fetchall()
                    by_activity = db.execute(
                        """
                        SELECT a.title, s.name AS space_name,
                               SUM(CASE WHEN r.status = 'confirmed' THEN 1 ELSE 0 END) AS confirmed,
                               SUM(CASE WHEN r.status = 'waitlisted' THEN 1 ELSE 0 END) AS waitlisted,
                               SUM(CASE WHEN r.status = 'cancelled' THEN 1 ELSE 0 END) AS cancelled
                        FROM activities a
                        JOIN spaces s ON s.id = a.space_id
                        LEFT JOIN reservations r ON r.activity_id = a.id
                        WHERE a.event_id = ?
                        GROUP BY a.id
                        ORDER BY a.starts_at
                        """,
                        (event_id,),
                    ).fetchall()
                    access = db.execute(
                        """
                        SELECT result, COUNT(*) AS total
                        FROM access_logs
                        WHERE event_id = ?
                        GROUP BY result
                        """,
                        (event_id,),
                    ).fetchall()
                    attendance = dict(
                        db.execute(
                            """
                            SELECT
                                SUM(CASE WHEN status IN ('Presente', 'Completa') THEN 1 ELSE 0 END) AS present,
                                SUM(CASE WHEN status = 'Ausente' THEN 1 ELSE 0 END) AS absent,
                                SUM(CASE WHEN status = 'Parcial' THEN 1 ELSE 0 END) AS partial,
                                SUM(CASE WHEN eligibility_status = 'Elegible' THEN 1 ELSE 0 END) AS eligible,
                                SUM(CASE WHEN eligibility_status = 'No elegible' THEN 1 ELSE 0 END) AS not_eligible,
                                ROUND(AVG(CASE WHEN status <> 'Pendiente' THEN attendance_percentage END), 1) AS average_percentage
                            FROM activity_attendance
                            WHERE event_id = ?
                            """,
                            (event_id,),
                        ).fetchone()
                    )
                self.send_json(
                    {
                        "event": event,
                        "accreditation": accreditation,
                        "by_type": [dict(r) for r in by_type],
                        "reservations": [dict(r) for r in reservations],
                        "by_activity": [dict(r) for r in by_activity],
                        "access": [dict(r) for r in access],
                        "attendance": attendance,
                    }
                )
                return

            if path == "/api/readiness":
                event_id = int(query.get("event_id", ["0"])[0])
                now_ts = datetime.now().timestamp()
                backups = sorted(BACKUP_DIR.glob("*.sqlite3"), key=lambda p: p.stat().st_mtime, reverse=True) if BACKUP_DIR.exists() else []
                latest_backup = backups[0] if backups else None
                backup_age_minutes = None
                if latest_backup:
                    backup_age_minutes = round((now_ts - latest_backup.stat().st_mtime) / 60, 1)
                with connect() as db:
                    event = row_to_dict(db.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()) if event_id else None
                    counts = db.execute(
                        """
                        SELECT
                            SUM(CASE WHEN status <> 'cancelled' THEN 1 ELSE 0 END) AS active,
                            SUM(CASE WHEN checked_in_at IS NOT NULL AND status <> 'cancelled' THEN 1 ELSE 0 END) AS checked,
                            SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) AS cancelled
                        FROM accreditations
                        WHERE event_id = ?
                        """,
                        (event_id,),
                    ).fetchone()
                    activity_count = db.execute("SELECT COUNT(*) AS c FROM activities WHERE event_id = ? AND status <> 'cancelled'", (event_id,)).fetchone()["c"]
                    public_activity_count = db.execute(
                        """
                        SELECT COUNT(*) AS c
                        FROM public_display_items i
                        JOIN activities a ON a.id = i.activity_id
                        WHERE i.event_id = ? AND i.visible = 1 AND a.status <> 'cancelled'
                        """,
                        (event_id,),
                    ).fetchone()["c"]
                    access_user_count = db.execute(
                        """
                        SELECT COUNT(*) AS c
                        FROM users
                        WHERE active = 1
                          AND (
                            lower(name) = 'acceso'
                            OR lower(role) LIKE '%acceso%'
                            OR lower(role) LIKE '%admin%'
                          )
                        """
                    ).fetchone()["c"]
                    waitlist_count = db.execute("SELECT COUNT(*) AS c FROM reservations WHERE event_id = ? AND status = 'waitlisted'", (event_id,)).fetchone()["c"]
                    rejection_count = db.execute(
                        """
                        SELECT COUNT(*) AS c
                        FROM access_logs
                        WHERE event_id = ? AND result = 'rejected'
                          AND datetime(created_at) >= datetime('now', '-15 minutes')
                        """,
                        (event_id,),
                    ).fetchone()["c"]
                    index_count = db.execute(
                        "SELECT COUNT(*) AS c FROM sqlite_master WHERE type = 'index' AND name LIKE 'idx_%'"
                    ).fetchone()["c"]
                    integrity = db.execute("PRAGMA quick_check").fetchone()[0]
                checks = [
                    {"key": "event", "label": "Evento activo", "ok": bool(event), "detail": event["name"] if event else "sin evento"},
                    {"key": "database", "label": "Base local", "ok": integrity == "ok", "detail": integrity},
                    {"key": "indexes", "label": "Indices de rendimiento", "ok": int(index_count or 0) >= 8, "detail": f"{index_count} indices"},
                    {"key": "backup", "label": "Backup reciente", "ok": backup_age_minutes is not None and backup_age_minutes <= 30, "detail": f"{backup_age_minutes} min" if backup_age_minutes is not None else "sin backup"},
                    {"key": "accreditations", "label": "Acreditaciones activas", "ok": int(counts["active"] or 0) > 0, "detail": str(int(counts["active"] or 0))},
                    {"key": "activities", "label": "Agenda cargada", "ok": int(activity_count or 0) > 0, "detail": str(int(activity_count or 0))},
                    {"key": "access_users", "label": "Operador de acceso", "ok": int(access_user_count or 0) > 0, "detail": f"{int(access_user_count or 0)} usuario(s)"},
                    {"key": "public_display", "label": "Pantalla publica", "ok": int(public_activity_count or 0) > 0, "detail": f"{int(public_activity_count or 0)} actividades visibles"},
                    {"key": "mobile_scanner", "label": "Escaner movil", "ok": True, "detail": f"/scan.html?event_id={event_id}"},
                    {"key": "waitlist", "label": "Lista de espera", "ok": True, "detail": str(int(waitlist_count or 0))},
                    {"key": "recent_rejections", "label": "Rechazos recientes", "ok": int(rejection_count or 0) == 0, "detail": str(int(rejection_count or 0))},
                ]
                self.send_json(
                    {
                        "ok": all(item["ok"] for item in checks),
                        "server_time": now_iso(),
                        "auto_backup_minutes": AUTO_BACKUP_MINUTES,
                        "backup_keep_last": BACKUP_KEEP_LAST,
                        "latest_backup": latest_backup.name if latest_backup else None,
                        "checks": checks,
                    }
                )
                return

            if path == "/api/accreditations":
                event_id = int(query.get("event_id", ["0"])[0])
                search = query.get("q", [""])[0].strip()
                limit = min(max(int(query.get("limit", ["300"])[0] or 300), 1), 2000)
                params: list[object] = [event_id]
                where = "a.event_id = ?"
                if search:
                    where += """ AND (
                        p.first_name LIKE ? OR p.last_name LIKE ? OR p.email LIKE ? OR
                        p.dni LIKE ? OR p.company LIKE ? OR a.token LIKE ?
                    )"""
                    term = f"%{search}%"
                    params.extend([term, term, term, term, term, term])
                with connect() as db:
                    rows = db.execute(
                        f"""
                        SELECT a.*, p.first_name, p.last_name, p.email, p.phone, p.dni, p.company, e.name AS event_name
                        FROM accreditations a
                        JOIN people p ON p.id = a.person_id
                        JOIN events e ON e.id = a.event_id
                        WHERE {where}
                        ORDER BY a.id DESC
                        LIMIT ?
                        """,
                        params + [limit],
                    ).fetchall()
                    result = []
                    for row in rows:
                        item = dict(row)
                        availability = public_availability(db, item["id"])
                        item["public_availability"] = availability["label"]
                        item["public_availability_color"] = availability["color"]
                        item["public_remaining"] = availability["remaining"]
                        item["public_capacity"] = availability["capacity"]
                        result.append(item)
                self.send_json(result)
                return

            if path == "/api/capacity-bags":
                event_id = int(query.get("event_id", ["0"])[0])
                activity_id = int(query.get("activity_id", ["0"])[0] or 0)
                with connect() as db:
                    ensure_capacity_bags(db, event_id=event_id, activity_id=activity_id or None)
                    params: list[object] = [event_id]
                    where = "b.event_id = ?"
                    if activity_id:
                        where += " AND b.activity_id = ?"
                        params.append(activity_id)
                    rows = db.execute(
                        f"""
                        SELECT b.*, a.title AS activity_title, a.capacity AS physical_capacity,
                               COUNT(r.id) AS used
                        FROM capacity_bags b
                        JOIN activities a ON a.id = b.activity_id
                        LEFT JOIN reservations r ON r.bag_id = b.id AND r.status = 'confirmed'
                        WHERE {where}
                        GROUP BY b.id
                        ORDER BY a.starts_at, b.priority, b.id
                        """,
                        params,
                    ).fetchall()
                self.send_json([dict(r) for r in rows])
                return

            if path == "/api/public-display":
                event_id = int(query.get("event_id", ["0"])[0])
                with connect() as db:
                    config = ensure_public_display_config(db, event_id)
                    rows = db.execute(
                        """
                        SELECT a.*, s.name AS space_name, i.sort_order, i.visible
                        FROM public_display_items i
                        JOIN activities a ON a.id = i.activity_id
                        JOIN spaces s ON s.id = a.space_id
                        WHERE i.event_id = ? AND i.visible = 1 AND a.status <> 'cancelled'
                        ORDER BY i.sort_order, a.starts_at
                        """,
                        (event_id,),
                    ).fetchall()
                    if not rows:
                        rows = db.execute(
                            """
                            SELECT a.*, s.name AS space_name, 0 AS sort_order, 1 AS visible
                            FROM activities a
                            JOIN spaces s ON s.id = a.space_id
                            WHERE a.event_id = ? AND a.status <> 'cancelled'
                            ORDER BY a.starts_at
                            """,
                            (event_id,),
                        ).fetchall()
                    activities = []
                    for row in rows:
                        item = dict(row)
                        availability = public_availability(db, item["id"])
                        item = {
                            "id": item["id"],
                            "title": item["title"],
                            "space_name": item["space_name"],
                            "activity_type": item["activity_type"],
                            "starts_at": item["starts_at"],
                            "ends_at": item["ends_at"],
                            "status": public_activity_status(item),
                            "availability": availability["label"],
                            "availability_color": availability["color"],
                        }
                        activities.append(item)
                self.send_json({"config": config, "activities": activities})
                return

            if path == "/api/portal":
                token = query.get("token", [""])[0].strip()
                with connect() as db:
                    data = portal_payload(db, token)
                    if data:
                        audit(db, "portal", "portal.accessed", "accreditation", data["id"], {"event_id": data["event_id"]})
                        if data.get("announcements"):
                            audit(db, "portal", "portal.announcements_viewed", "event", data["event_id"], {"accreditation_id": data["id"], "count": len(data["announcements"])})
                if not data:
                    self.send_json({"error": "Acreditacion no encontrada"}, 404)
                    return
                self.send_json(data)
                return

            if path == "/api/participant-metrics":
                event_id = int(query.get("event_id", ["0"])[0])
                with connect() as db:
                    self.send_json(participant_metrics(db, event_id))
                return

            if path == "/api/communications":
                event_id = int(query.get("event_id", ["0"])[0])
                with connect() as db:
                    stats = dict(
                        db.execute(
                            """
                            SELECT
                                COUNT(a.id) AS participants,
                                SUM(CASE WHEN p.email <> '' THEN 1 ELSE 0 END) AS with_email,
                                SUM(CASE WHEN p.phone <> '' THEN 1 ELSE 0 END) AS with_whatsapp,
                                SUM(CASE WHEN p.email <> '' AND p.phone <> '' THEN 1 ELSE 0 END) AS with_both,
                                SUM(CASE WHEN cp.acepta_email = 1 OR cp.acepta_whatsapp = 1 THEN 1 ELSE 0 END) AS with_consent
                            FROM accreditations a
                            JOIN people p ON p.id = a.person_id
                            LEFT JOIN participant_communication_preferences cp ON cp.person_id = p.id
                            WHERE a.event_id = ? AND a.status <> 'cancelled'
                            """,
                            (event_id,),
                        ).fetchone()
                    )
                    logs = [
                        dict(r)
                        for r in db.execute(
                            """
                            SELECT l.*, p.first_name, p.last_name, p.email
                            FROM communication_logs l
                            JOIN people p ON p.id = l.person_id
                            WHERE l.event_id = ?
                            ORDER BY l.id DESC
                            LIMIT 100
                            """,
                            (event_id,),
                        ).fetchall()
                    ]
                    templates = [
                        dict(r)
                        for r in db.execute(
                            """
                            SELECT *
                            FROM communication_templates
                            WHERE active = 1 AND (event_id = 0 OR event_id = ?)
                            ORDER BY event_id, id
                            """,
                            (event_id,),
                        ).fetchall()
                    ]
                self.send_json({"stats": stats, "logs": logs, "templates": templates})
                return

            if path == "/api/demo-real":
                event_id = int(query.get("event_id", ["0"])[0])
                with connect() as db:
                    event = row_to_dict(db.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone())
                    if not event or event["name"] != DemoRealService.EVENT_NAME:
                        self.send_json({"active": False, "examples": [], "guide": []})
                        return
                    examples = demo_real_service().examples(db, event_id)
                self.send_json({"active": True, "event": event, "examples": examples, "guide": demo_real_service().guide()})
                return

            if path == "/api/logs":
                event_id = int(query.get("event_id", ["0"])[0])
                with connect() as db:
                    rows = db.execute(
                        """
                        SELECT l.*, p.first_name, p.last_name
                        FROM access_logs l
                        LEFT JOIN accreditations a ON a.id = l.accreditation_id
                        LEFT JOIN people p ON p.id = a.person_id
                        WHERE l.event_id = ? OR ? = 0
                        ORDER BY l.id DESC
                        LIMIT 100
                        """,
                        (event_id, event_id),
                    ).fetchall()
                self.send_json([dict(r) for r in rows])
                return

            if path == "/api/export.csv":
                event_id = int(query.get("event_id", ["0"])[0])
                with connect() as db:
                    rows = db.execute(
                        """
                        SELECT e.name AS evento, p.first_name AS nombre, p.last_name AS apellido,
                               p.email, p.phone AS telefono, p.dni, p.company AS empresa,
                               a.type AS tipo, a.token, a.status AS estado,
                               a.checked_in_at AS ingreso
                        FROM accreditations a
                        JOIN people p ON p.id = a.person_id
                        JOIN events e ON e.id = a.event_id
                        WHERE a.event_id = ?
                        ORDER BY p.last_name, p.first_name
                        """,
                        (event_id,),
                    ).fetchall()
                self.send_response(200)
                self.send_header("Content-Type", "text/csv; charset=utf-8")
                self.send_header("Content-Disposition", "attachment; filename=acreditados.csv")
                self.end_headers()
                writer = csv.writer(self.wfile.read if False else _TextWriter(self.wfile))
                writer.writerow(["Evento", "Nombre", "Apellido", "Email", "Telefono", "DNI", "Empresa", "Tipo", "Token", "Estado", "Ingreso"])
                for r in rows:
                    writer.writerow([r[k] for k in r.keys()])
                return

            if path == "/api/reservations.csv":
                event_id = int(query.get("event_id", ["0"])[0])
                activity_id = int(query.get("activity_id", ["0"])[0] or 0)
                params: list[object] = [event_id]
                where = "r.event_id = ?"
                if activity_id:
                    where += " AND r.activity_id = ?"
                    params.append(activity_id)
                with connect() as db:
                    rows = db.execute(
                        f"""
                        SELECT e.name AS evento, a.title AS actividad, s.name AS sala,
                               a.starts_at AS inicio, a.ends_at AS fin,
                               p.first_name AS nombre, p.last_name AS apellido,
                               p.email, p.phone AS telefono, p.dni, p.company AS empresa,
                               ac.type AS tipo, ac.token, r.status AS reserva
                        FROM reservations r
                        JOIN activities a ON a.id = r.activity_id
                        JOIN spaces s ON s.id = a.space_id
                        JOIN events e ON e.id = r.event_id
                        JOIN accreditations ac ON ac.id = r.accreditation_id
                        JOIN people p ON p.id = ac.person_id
                        WHERE {where}
                        ORDER BY a.starts_at, r.status, p.last_name, p.first_name
                        """,
                        params,
                    ).fetchall()
                self.send_response(200)
                self.send_header("Content-Type", "text/csv; charset=utf-8")
                self.send_header("Content-Disposition", "attachment; filename=reservas.csv")
                self.end_headers()
                writer = csv.writer(self.wfile.read if False else _TextWriter(self.wfile))
                writer.writerow(["Evento", "Actividad", "Sala", "Inicio", "Fin", "Nombre", "Apellido", "Email", "Telefono", "DNI", "Empresa", "Tipo", "Token", "Reserva"])
                for row in rows:
                    writer.writerow([row[key] for key in row.keys()])
                return

            if path == "/api/attendances.csv":
                event_id = int(query.get("event_id", ["0"])[0])
                activity_id = int(query.get("activity_id", ["0"])[0] or 0)
                params: list[object] = [event_id]
                where = "at.event_id = ?"
                if activity_id:
                    where += " AND at.activity_id = ?"
                    params.append(activity_id)
                with DB_LOCK, connect() as db:
                    db.execute("BEGIN IMMEDIATE")
                    attendance_service().ensure_absences(db, event_id)
                    rows = db.execute(
                        f"""
                        SELECT e.name AS evento, a.title AS actividad, s.name AS sala,
                               p.first_name AS nombre, p.last_name AS apellido, p.email,
                               p.company AS empresa, ac.type AS tipo, ac.token,
                               at.entry_at AS ingreso, at.exit_at AS egreso,
                               at.attended_minutes AS minutos, at.attendance_percentage AS porcentaje,
                               at.status AS estado_asistencia, at.eligibility_status AS certificado
                        FROM activity_attendance at
                        JOIN events e ON e.id = at.event_id
                        JOIN activities a ON a.id = at.activity_id
                        JOIN spaces s ON s.id = a.space_id
                        JOIN accreditations ac ON ac.id = at.accreditation_id
                        JOIN people p ON p.id = ac.person_id
                        WHERE {where}
                        ORDER BY a.starts_at, p.last_name, p.first_name
                        """,
                        params,
                    ).fetchall()
                    db.execute("COMMIT")
                self.send_response(200)
                self.send_header("Content-Type", "text/csv; charset=utf-8")
                self.send_header("Content-Disposition", "attachment; filename=asistencias.csv")
                self.end_headers()
                writer = csv.writer(self.wfile.read if False else _TextWriter(self.wfile))
                writer.writerow(["Evento", "Actividad", "Sala", "Nombre", "Apellido", "Email", "Empresa", "Tipo", "Token", "Ingreso", "Egreso", "Minutos", "Porcentaje", "Asistencia", "Certificado"])
                for row in rows:
                    writer.writerow([row[key] for key in row.keys()])
                return

            if path == "/api/certificate-eligibility.csv":
                event_id = int(query.get("event_id", ["0"])[0])
                status = query.get("status", [""])[0].strip()
                params: list[object] = [event_id]
                where = "ce.event_id = ?"
                if status == "eligible":
                    where += " AND ce.elegible = 1"
                elif status == "not_eligible":
                    where += " AND ce.elegible = 0 AND ce.estado = 'No elegible'"
                with connect() as db:
                    rows = db.execute(
                        f"""
                        SELECT e.name AS evento, a.title AS actividad,
                               p.first_name AS nombre, p.last_name AS apellido, p.email,
                               p.company AS empresa, ac.token, ce.porcentaje, ce.estado, ce.fecha_calculo
                        FROM certificate_eligibility ce
                        JOIN events e ON e.id = ce.event_id
                        JOIN activities a ON a.id = ce.activity_id
                        JOIN accreditations ac ON ac.id = ce.accreditation_id
                        JOIN people p ON p.id = ac.person_id
                        WHERE {where}
                        ORDER BY a.starts_at, p.last_name, p.first_name
                        """,
                        params,
                    ).fetchall()
                self.send_response(200)
                self.send_header("Content-Type", "text/csv; charset=utf-8")
                self.send_header("Content-Disposition", "attachment; filename=elegibilidad-certificados.csv")
                self.end_headers()
                writer = csv.writer(self.wfile.read if False else _TextWriter(self.wfile))
                writer.writerow(["Evento", "Actividad", "Nombre", "Apellido", "Email", "Empresa", "Token", "Porcentaje", "Estado", "Fecha calculo"])
                for row in rows:
                    writer.writerow([row[key] for key in row.keys()])
                return

            if path == "/api/captation.csv":
                event_id = int(query.get("event_id", ["0"])[0])
                with connect() as db:
                    rows = db.execute(
                        """
                        SELECT e.name AS evento, ce.source AS origen, ce.source_detail AS detalle,
                               ce.device_type AS dispositivo, ce.action AS accion,
                               ce.session_id AS sesion, p.email, p.first_name AS nombre,
                               p.last_name AS apellido, ce.created_at AS fecha
                        FROM captation_events ce
                        JOIN events e ON e.id = ce.event_id
                        LEFT JOIN people p ON p.id = ce.person_id
                        WHERE ce.event_id = ?
                        ORDER BY ce.id
                        """,
                        (event_id,),
                    ).fetchall()
                self.send_response(200)
                self.send_header("Content-Type", "text/csv; charset=utf-8")
                self.send_header("Content-Disposition", "attachment; filename=captacion.csv")
                self.end_headers()
                writer = csv.writer(self.wfile.read if False else _TextWriter(self.wfile))
                writer.writerow(["Evento", "Origen", "Detalle", "Dispositivo", "Accion", "Sesion", "Email", "Nombre", "Apellido", "Fecha"])
                for row in rows:
                    writer.writerow([row[key] for key in row.keys()])
                return

            if path == "/api/export.json":
                event_id = int(query.get("event_id", ["0"])[0])
                with connect() as db:
                    event = row_to_dict(db.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone())
                    if not event:
                        self.send_json({"error": "Evento inexistente"}, 404)
                        return
                    export = {
                        "generated_at": now_iso(),
                        "event": event,
                        "types": [dict(r) for r in db.execute("SELECT * FROM accreditation_types WHERE event_id = ? ORDER BY name", (event_id,)).fetchall()],
                        "spaces": [dict(r) for r in db.execute("SELECT * FROM spaces WHERE event_id = ? ORDER BY name", (event_id,)).fetchall()],
                        "activities": [dict(r) for r in db.execute("SELECT * FROM activities WHERE event_id = ? ORDER BY starts_at", (event_id,)).fetchall()],
                        "accreditations": [
                            dict(r)
                            for r in db.execute(
                                """
                                SELECT a.*, p.first_name, p.last_name, p.email, p.phone, p.dni, p.company
                                FROM accreditations a
                                JOIN people p ON p.id = a.person_id
                                WHERE a.event_id = ?
                                ORDER BY a.id
                                """,
                                (event_id,),
                            ).fetchall()
                        ],
                        "reservations": [dict(r) for r in db.execute("SELECT * FROM reservations WHERE event_id = ? ORDER BY id", (event_id,)).fetchall()],
                        "activity_attendance": [dict(r) for r in db.execute("SELECT * FROM activity_attendance WHERE event_id = ? ORDER BY id", (event_id,)).fetchall()],
                        "certificate_eligibility": [dict(r) for r in db.execute("SELECT * FROM certificate_eligibility WHERE event_id = ? ORDER BY id", (event_id,)).fetchall()],
                        "captation_events": [dict(r) for r in db.execute("SELECT * FROM captation_events WHERE event_id = ? ORDER BY id", (event_id,)).fetchall()],
                        "conversation_sources": [dict(r) for r in db.execute("SELECT * FROM conversation_sources WHERE event_id = ? ORDER BY id", (event_id,)).fetchall()],
                        "access_logs": [dict(r) for r in db.execute("SELECT * FROM access_logs WHERE event_id = ? ORDER BY id", (event_id,)).fetchall()],
                        "audit_logs": [
                            dict(r)
                            for r in db.execute(
                                """
                                SELECT *
                                FROM audit_logs
                                WHERE (entity_type = 'event' AND entity_id = ?) OR payload LIKE ?
                                ORDER BY id
                                """,
                                (event_id, f'%"event_id": {event_id}%'),
                            ).fetchall()
                        ],
                    }
                body = json.dumps(export, ensure_ascii=False, indent=2).encode("utf-8")
                send_download(self, f"evento-{event_id}-export.json", "application/json; charset=utf-8", body)
                return

            if path == "/api/backup":
                event_id = int(query.get("event_id", ["0"])[0] or 0)
                backup_path = create_db_backup()
                backup_check = verify_backup_file(backup_path)
                session = self.session_user()
                with connect() as db:
                    audit(
                        db,
                        session["name"] if session else "system",
                        "backup.created",
                        "backup",
                        None,
                        {"event_id": event_id, "file": backup_path.name, "integrity_ok": backup_check["ok"], "integrity_detail": backup_check["detail"]},
                    )
                body = backup_path.read_bytes()
                send_download(self, backup_path.name, "application/octet-stream", body)
                return

            self.send_json({"error": "Ruta no encontrada"}, 404)
        except Exception as exc:
            self.send_json({"error": str(exc)}, 500)

    def handle_api_post(self, path: str) -> None:
        try:
            data = read_json(self)
            if not self.require_api_auth(path, is_post=True):
                return
            session = self.session_user()
            if session and path not in {"/api/auth/login", "/api/auth/logout"}:
                if path == "/api/validate":
                    data["operator"] = session["name"]
                else:
                    data["actor"] = session["name"]

            if path == "/api/auth/login":
                name = data.get("name", "").strip()
                pin = data.get("pin", "").strip()
                with connect() as db:
                    user = db.execute("SELECT * FROM users WHERE name = ? AND active = 1", (name,)).fetchone()
                if not user or not verify_pin(pin, user["pin_hash"]):
                    self.send_json({"error": "Usuario o PIN incorrecto"}, 403)
                    return
                token = secrets.token_urlsafe(32)
                AUTH_SESSIONS[token] = {"name": user["name"], "role": user["role"], "created_at": time.time()}
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Set-Cookie", f"qr_session={token}; Path=/; HttpOnly; SameSite=Lax")
                body = json.dumps({"ok": True, "user": {"name": user["name"], "role": user["role"]}}, ensure_ascii=False).encode("utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            if path == "/api/auth/logout":
                token = parse_cookies(self.headers.get("Cookie")).get("qr_session", "")
                AUTH_SESSIONS.pop(token, None)
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Set-Cookie", "qr_session=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax")
                body = b'{"ok": true}'
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            if path == "/api/captation/event":
                event_id = int(data.get("event_id") or 0)
                action = str(data.get("action") or "").strip()
                if not event_id or action not in {"landing_opened", "form_started", "form_abandoned", "whatsapp_clicked"}:
                    self.send_json({"error": "Evento de captacion invalido"}, 400)
                    return
                with connect() as db:
                    record_captation_event(
                        db,
                        event_id,
                        action,
                        str(data.get("source") or "landing"),
                        str(data.get("device_type") or "desktop"),
                        source_detail=str(data.get("source_detail") or ""),
                        session_id=str(data.get("session_id") or ""),
                    )
                    audit(db, "public", f"captation.{action}", "event", event_id, {"source": data.get("source"), "device_type": data.get("device_type")})
                self.send_json({"ok": True})
                return

            if path == "/api/portal/preferences":
                token = data.get("token", "").strip()
                with DB_LOCK, connect() as db:
                    db.execute("BEGIN IMMEDIATE")
                    portal = portal_payload(db, token)
                    if not portal:
                        db.execute("ROLLBACK")
                        self.send_json({"error": "Portal inexistente"}, 404)
                        return
                    payload = {
                        "email": portal["email"],
                        "phone": portal["phone"],
                        "acepta_email": data.get("acepta_email"),
                        "acepta_whatsapp": data.get("acepta_whatsapp"),
                        "canal_preferido": data.get("canal_preferido", "email"),
                    }
                    upsert_communication_preference(db, portal["person_id"], payload)
                    audit(db, "portal", "portal.preferences_updated", "person", portal["person_id"], {"event_id": portal["event_id"]})
                    db.execute("COMMIT")
                    result = portal_payload(db, token)
                self.send_json({"ok": True, "portal": result})
                return

            if path == "/api/portal/profile":
                token = data.get("token", "").strip()
                with DB_LOCK, connect() as db:
                    db.execute("BEGIN IMMEDIATE")
                    portal = portal_payload(db, token)
                    if not portal:
                        db.execute("ROLLBACK")
                        self.send_json({"error": "Portal inexistente"}, 404)
                        return
                    first_name = str(data.get("first_name") or "").strip()
                    last_name = str(data.get("last_name") or "").strip()
                    email = str(data.get("email") or "").strip().lower()
                    if not first_name or not last_name or not email:
                        db.execute("ROLLBACK")
                        self.send_json({"error": "Nombre, apellido y email son obligatorios"}, 400)
                        return
                    db.execute(
                        """
                        UPDATE people
                        SET first_name = ?, last_name = ?, email = ?, phone = ?, company = ?, position = ?
                        WHERE id = ?
                        """,
                        (
                            first_name,
                            last_name,
                            email,
                            str(data.get("phone") or "").strip(),
                            str(data.get("company") or "").strip(),
                            str(data.get("position") or "").strip(),
                            portal["person_id"],
                        ),
                    )
                    upsert_communication_preference(db, portal["person_id"], {**portal, **data, "email": email, "phone": str(data.get("phone") or "").strip()})
                    audit(db, "portal", "portal.profile_updated", "person", portal["person_id"], {"event_id": portal["event_id"]})
                    db.execute("COMMIT")
                    result = portal_payload(db, token)
                self.send_json({"ok": True, "portal": result})
                return

            if path == "/api/portal/reserve":
                token = data.get("token", "").strip()
                activity_id = int(data.get("activity_id") or 0)
                if not token or not activity_id:
                    self.send_json({"error": "Faltan token o actividad"}, 400)
                    return
                with DB_LOCK, connect() as db:
                    db.execute("BEGIN IMMEDIATE")
                    portal = portal_payload(db, token)
                    if not portal:
                        db.execute("ROLLBACK")
                        self.send_json({"error": "Portal inexistente"}, 404)
                        return
                    event = db.execute("SELECT * FROM events WHERE id = ?", (portal["event_id"],)).fetchone()
                    audit(db, "portal", "portal.reservation_attempted", "activity", activity_id, {"event_id": portal["event_id"], "accreditation_id": portal["id"]})
                    if event and not int(event["permitir_reserva_actividades_desde_portal"] or 0):
                        audit(db, "portal", "portal.reservation_rejected", "activity", activity_id, {"event_id": portal["event_id"], "reason": "portal_disabled"})
                        db.execute("COMMIT")
                        self.send_json({"error": "Las reservas desde portal no estan habilitadas"}, 403)
                        return
                    if event and int(event["reserva_requiere_confirmacion"] or 0) and not truthy(data.get("confirmed")):
                        audit(db, "portal", "portal.reservation_rejected", "activity", activity_id, {"event_id": portal["event_id"], "reason": "confirmation_required"})
                        db.execute("COMMIT")
                        self.send_json({"error": "Debes confirmar manualmente la reserva"}, 400)
                        return
                    if event and int(event["reserva_requiere_verificacion_simple"] or 0) and str(data.get("verification_answer") or "").strip() != "7":
                        audit(db, "portal", "portal.reservation_verification_failed", "activity", activity_id, {"event_id": portal["event_id"], "accreditation_id": portal["id"]})
                        db.execute("COMMIT")
                        self.send_json({"error": "Verificacion incorrecta. Escribi el numero 7 para confirmar."}, 400)
                        return
                    existing = db.execute(
                        "SELECT * FROM reservations WHERE activity_id = ? AND accreditation_id = ? AND status <> 'cancelled'",
                        (activity_id, portal["id"]),
                    ).fetchone()
                    if existing:
                        audit(db, "portal", "portal.reservation_rejected", "reservation", existing["id"], {"event_id": portal["event_id"], "reason": "duplicate"})
                        db.execute("COMMIT")
                        self.send_json({"error": "Ya tenes una reserva activa para esta actividad"}, 409)
                        return
                    cooldown = max(10, int(event["reserva_cooldown_segundos"] or 0)) if event else 10
                    if cooldown > 0:
                        last = db.execute(
                            """
                            SELECT created_at
                            FROM reservations
                            WHERE accreditation_id = ? AND status <> 'cancelled'
                            ORDER BY id DESC
                            LIMIT 1
                            """,
                            (portal["id"],),
                        ).fetchone()
                        if last:
                            try:
                                elapsed = (datetime.now(timezone.utc) - datetime.fromisoformat(last["created_at"])).total_seconds()
                            except ValueError:
                                elapsed = cooldown
                            active_count = db.execute(
                                """
                                SELECT COUNT(*) AS c
                                FROM reservations
                                WHERE accreditation_id = ? AND status <> 'cancelled'
                                """,
                                (portal["id"],),
                            ).fetchone()["c"]
                            if int(active_count or 0) > 0 and int(active_count or 0) % 5 == 0 and elapsed < 300:
                                wait = max(1, int(round(300 - elapsed)))
                                audit(db, "portal", "portal.reservation_cooldown_blocked", "activity", activity_id, {"event_id": portal["event_id"], "wait_seconds": wait, "block": "five_reservations"})
                                db.execute("COMMIT")
                                self.send_json({"error": f"Llegaste a 5 reservas seguidas. Espera {wait} segundos antes de continuar.", "wait_seconds": wait, "block": "five_reservations"}, 429)
                                return
                            if elapsed < cooldown:
                                wait = max(1, int(round(cooldown - elapsed)))
                                audit(db, "portal", "portal.reservation_cooldown_blocked", "activity", activity_id, {"event_id": portal["event_id"], "wait_seconds": wait})
                                db.execute("COMMIT")
                                self.send_json({"error": f"Espera {wait} segundos antes de reservar otra actividad", "wait_seconds": wait, "block": "short_cooldown"}, 429)
                                return
                    reservation = create_reservation(db, portal["event_id"], activity_id, portal["id"], "public")
                    if not reservation["ok"]:
                        audit(db, "portal", "portal.reservation_rejected", "activity", activity_id, {"event_id": portal["event_id"], "reason": reservation["error"]})
                        db.execute("COMMIT")
                        self.send_json({"error": reservation["error"]}, int(reservation.get("status_code", 400)))
                        return
                    if not reservation.get("existing"):
                        audit(
                            db,
                            "portal",
                            "portal.reservation_waitlisted" if reservation["status"] == "waitlisted" else "portal.reservation_created",
                            "reservation",
                            reservation.get("id"),
                            {"event_id": portal["event_id"], "activity_id": activity_id, "accreditation_id": portal["id"], "status": reservation["status"]},
                        )
                        record_captation_event(
                            db,
                            portal["event_id"],
                            "reservation_created",
                            portal.get("source") or "landing",
                            portal.get("device_type") or "desktop",
                            accreditation_id=portal["id"],
                            person_id=portal["person_id"],
                        )
                    db.execute("COMMIT")
                    result = portal_payload(db, token)
                self.send_json({"ok": True, "reservation": reservation, "portal": result}, 201)
                return

            if path == "/api/portal/reservations/status":
                token = data.get("token", "").strip()
                reservation_id = int(data.get("id") or 0)
                status = data.get("status", "").strip()
                if not token or not reservation_id or status != "cancelled":
                    self.send_json({"error": "Solo se permite cancelar reservas desde el portal"}, 400)
                    return
                with DB_LOCK, connect() as db:
                    db.execute("BEGIN IMMEDIATE")
                    portal = portal_payload(db, token)
                    if not portal:
                        db.execute("ROLLBACK")
                        self.send_json({"error": "Portal inexistente"}, 404)
                        return
                    reservation = db.execute(
                        "SELECT * FROM reservations WHERE id = ? AND accreditation_id = ?",
                        (reservation_id, portal["id"]),
                    ).fetchone()
                    if not reservation:
                        db.execute("ROLLBACK")
                        self.send_json({"error": "Reserva inexistente"}, 404)
                        return
                    promoted = None
                    db.execute("UPDATE reservations SET status = 'cancelled' WHERE id = ?", (reservation_id,))
                    if reservation["status"] == "confirmed":
                        promoted = promote_next_waitlisted(db, reservation["event_id"], reservation["activity_id"])
                    audit(
                        db,
                        "portal",
                        "portal.reservation_cancelled",
                        "reservation",
                        reservation_id,
                        {"event_id": portal["event_id"], "activity_id": reservation["activity_id"], "promoted": bool(promoted)},
                    )
                    db.execute("COMMIT")
                    result = portal_payload(db, token)
                self.send_json({"ok": True, "promoted": promoted, "portal": result})
                return

            if path == "/api/events":
                actor = data.get("actor", "Admin")
                with connect() as db:
                    if not can_actor(db, actor, CONFIG_ROLES):
                        self.send_json(deny_message(actor), 403)
                        return
                    cur = db.execute(
                        """
                        INSERT INTO events (
                            name, description, venue, starts_at, ends_at, status, capacity,
                            activity_selection_mode, generar_certificados, controlar_asistencia,
                            attendance_mode, porcentaje_minimo_asistencia, captation_mode,
                            primary_action_label, secondary_action_label, whatsapp_number, created_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            data.get("name", "").strip(),
                            data.get("description", "").strip(),
                            data.get("venue", "").strip(),
                            data.get("starts_at", "").strip(),
                            data.get("ends_at", "").strip(),
                            data.get("status", "draft"),
                            int(data.get("capacity") or 0),
                            data.get("activity_selection_mode", "optional_later").strip() or "optional_later",
                            1 if truthy(data.get("generar_certificados", True)) else 0,
                            1 if truthy(data.get("controlar_asistencia", True)) else 0,
                            data.get("attendance_mode", "entry_only").strip() or "entry_only",
                            int(data.get("porcentaje_minimo_asistencia") or 80),
                            data.get("captation_mode", "MIXTO").strip() or "MIXTO",
                            data.get("primary_action_label", "").strip(),
                            data.get("secondary_action_label", "").strip(),
                            data.get("whatsapp_number", "").strip(),
                            now_iso(),
                        ),
                    )
                    ensure_default_types(db, cur.lastrowid)
                    ensure_default_spaces(db, cur.lastrowid)
                    audit(db, actor, "event.created", "event", cur.lastrowid, data)
                self.send_json({"ok": True, "id": cur.lastrowid}, 201)
                return

            if path == "/api/prepare-event":
                actor = data.get("actor", "Admin")
                name = data.get("name", "").strip() or "Evento real"
                venue = data.get("venue", "").strip()
                starts_at = data.get("starts_at", "").strip()
                ends_at = data.get("ends_at", "").strip()
                capacity = int(data.get("capacity") or 0)
                description = data.get("description", "").strip()
                backup_path = create_db_backup()
                with DB_LOCK, connect() as db:
                    db.execute("BEGIN IMMEDIATE")
                    if not can_actor(db, actor, CONFIG_ROLES):
                        db.execute("ROLLBACK")
                        self.send_json(deny_message(actor), 403)
                        return
                    db.execute("DELETE FROM conversation_sources")
                    db.execute("DELETE FROM captation_events")
                    db.execute("DELETE FROM certificate_eligibility")
                    db.execute("DELETE FROM activity_attendance")
                    db.execute("DELETE FROM reservations")
                    db.execute("DELETE FROM activities")
                    db.execute("DELETE FROM access_logs")
                    db.execute("DELETE FROM accreditations")
                    db.execute("DELETE FROM people")
                    db.execute("DELETE FROM accreditation_types")
                    db.execute("DELETE FROM spaces")
                    db.execute("DELETE FROM events")
                    cur = db.execute(
                        """
                        INSERT INTO events (
                            name, description, venue, starts_at, ends_at, status, capacity,
                            activity_selection_mode, generar_certificados, controlar_asistencia,
                            attendance_mode, porcentaje_minimo_asistencia, captation_mode,
                            primary_action_label, secondary_action_label, whatsapp_number, created_at
                        )
                        VALUES (?, ?, ?, ?, ?, 'published', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            name,
                            description,
                            venue,
                            starts_at,
                            ends_at,
                            capacity,
                            data.get("activity_selection_mode", "optional_later").strip() or "optional_later",
                            1 if truthy(data.get("generar_certificados", True)) else 0,
                            1 if truthy(data.get("controlar_asistencia", True)) else 0,
                            data.get("attendance_mode", "entry_only").strip() or "entry_only",
                            int(data.get("porcentaje_minimo_asistencia") or 80),
                            data.get("captation_mode", "MIXTO").strip() or "MIXTO",
                            data.get("primary_action_label", "").strip(),
                            data.get("secondary_action_label", "").strip(),
                            data.get("whatsapp_number", "").strip(),
                            now_iso(),
                        ),
                    )
                    event_id = cur.lastrowid
                    ensure_default_types(db, event_id)
                    ensure_default_spaces(db, event_id)
                    audit(
                        db,
                        actor,
                        "system.prepared_real_event",
                        "event",
                        event_id,
                        {"event_id": event_id, "backup": str(backup_path.name)},
                    )
                    db.execute("COMMIT")
                self.send_json({"ok": True, "event_id": event_id, "backup": backup_path.name})
                return

            if path == "/api/demo-real":
                actor = data.get("actor", "Admin")
                if data.get("confirm", "").strip() != "DEMO":
                    self.send_json({"error": "Escribi DEMO para confirmar"}, 400)
                    return
                backup_before = create_db_backup()
                backup_before_check = verify_backup_file(backup_before)
                with DB_LOCK, connect() as db:
                    db.execute("BEGIN IMMEDIATE")
                    if not can_actor(db, actor, CONFIG_ROLES):
                        db.execute("ROLLBACK")
                        self.send_json(deny_message(actor), 403)
                        return
                    audit(
                        db,
                        actor,
                        "demo.backup_before",
                        "backup",
                        None,
                        {"file": backup_before.name, "integrity_ok": backup_before_check["ok"], "integrity_detail": backup_before_check["detail"]},
                    )
                    result = demo_real_service().create(db, actor)
                    audit(db, actor, "demo.created", "event", result["event_id"], result)
                    db.execute("COMMIT")
                backup_after = create_db_backup()
                backup_after_check = verify_backup_file(backup_after)
                with connect() as db:
                    audit(
                        db,
                        actor,
                        "demo.backup_after",
                        "event",
                        result["event_id"],
                        {"event_id": result["event_id"], "file": backup_after.name, "integrity_ok": backup_after_check["ok"], "integrity_detail": backup_after_check["detail"]},
                    )
                self.send_json(
                    {
                        "ok": True,
                        **result,
                        "backup_before": backup_before.name,
                        "backup_after": backup_after.name,
                    },
                    201,
                )
                return

            if path == "/api/types":
                actor = data.get("actor", "Admin")
                event_id = int(data.get("event_id") or 0)
                name = data.get("name", "").strip()
                if not event_id or not name:
                    self.send_json({"error": "Falta evento o tipo"}, 400)
                    return
                capacity = int(data.get("capacity") or 0)
                access_enabled = 1 if data.get("access_enabled", True) else 0
                with connect() as db:
                    if not can_actor(db, actor, CONFIG_ROLES):
                        self.send_json(deny_message(actor), 403)
                        return
                    db.execute(
                        """
                        INSERT INTO accreditation_types (event_id, name, capacity, access_enabled, created_at)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(event_id, name)
                        DO UPDATE SET capacity = excluded.capacity, access_enabled = excluded.access_enabled
                        """,
                        (event_id, name, capacity, access_enabled, now_iso()),
                    )
                    audit(db, actor, "accreditation_type.saved", "event", event_id, data)
                self.send_json({"ok": True})
                return

            if path == "/api/users":
                actor = data.get("actor", "Admin")
                name = data.get("name", "").strip()
                role = data.get("role", "").strip()
                if not name or not role:
                    self.send_json({"error": "Falta nombre o rol"}, 400)
                    return
                with connect() as db:
                    if not can_actor(db, actor, ADMIN_ROLES):
                        self.send_json(deny_message(actor), 403)
                        return
                    db.execute(
                        """
                        INSERT INTO users (name, role, active, created_at)
                        VALUES (?, ?, 1, ?)
                        ON CONFLICT(name)
                        DO UPDATE SET role = excluded.role, active = 1
                        """,
                        (name, role, now_iso()),
                    )
                    audit(db, actor, "user.saved", "user", None, {"name": name, "role": role})
                self.send_json({"ok": True})
                return

            if path == "/api/communications/send":
                actor = data.get("actor", "Admin")
                event_id = int(data.get("event_id") or 0)
                channel = data.get("channel", "email").strip() or "email"
                message_type = data.get("type", "aviso operativo").strip() or "aviso operativo"
                subject = data.get("subject", "").strip() or "Aviso operativo"
                content = data.get("content", "").strip()
                accreditation_id = int(data.get("accreditation_id") or 0)
                if not event_id or not content:
                    self.send_json({"error": "Faltan evento o contenido"}, 400)
                    return
                with DB_LOCK, connect() as db:
                    db.execute("BEGIN IMMEDIATE")
                    if not can_actor(db, actor, CONFIG_ROLES):
                        db.execute("ROLLBACK")
                        self.send_json(deny_message(actor), 403)
                        return
                    params: list[object] = [event_id]
                    where = "a.event_id = ? AND a.status <> 'cancelled'"
                    if accreditation_id:
                        where += " AND a.id = ?"
                        params.append(accreditation_id)
                    recipients = db.execute(
                        f"""
                        SELECT a.id AS accreditation_id, a.person_id,
                               cp.acepta_email, cp.acepta_whatsapp
                        FROM accreditations a
                        JOIN people p ON p.id = a.person_id
                        LEFT JOIN participant_communication_preferences cp ON cp.person_id = p.id
                        WHERE {where}
                        """,
                        params,
                    ).fetchall()
                    sent = 0
                    skipped = 0
                    for recipient in recipients:
                        allowed = []
                        if channel in {"email", "both"} and int(recipient["acepta_email"] or 0) == 1:
                            allowed.append("email")
                        if channel in {"whatsapp", "both"} and int(recipient["acepta_whatsapp"] or 0) == 1:
                            allowed.append("whatsapp")
                        if not allowed:
                            skipped += 1
                            continue
                        for item_channel in allowed:
                            communication_log(
                                db,
                                event_id,
                                recipient["person_id"],
                                recipient["accreditation_id"],
                                item_channel,
                                message_type,
                                subject,
                                content,
                                "demo",
                            )
                            sent += 1
                    audit(db, actor, "communications.demo_sent", "event", event_id, {"channel": channel, "sent": sent, "skipped": skipped, "type": message_type})
                    db.execute("COMMIT")
                self.send_json({"ok": True, "sent": sent, "skipped": skipped})
                return

            if path == "/api/accreditations/update":
                actor = data.get("actor", "Recepcion")
                accreditation_id = int(data.get("id") or 0)
                if not accreditation_id:
                    self.send_json({"error": "Falta acreditacion"}, 400)
                    return
                with DB_LOCK, connect() as db:
                    db.execute("BEGIN IMMEDIATE")
                    if not can_actor(db, actor, RECEPTION_ROLES):
                        db.execute("ROLLBACK")
                        self.send_json(deny_message(actor), 403)
                        return
                    row = db.execute(
                        """
                        SELECT a.*, p.id AS person_id
                        FROM accreditations a
                        JOIN people p ON p.id = a.person_id
                        WHERE a.id = ?
                        """,
                        (accreditation_id,),
                    ).fetchone()
                    if not row:
                        db.execute("ROLLBACK")
                        self.send_json({"error": "Acreditacion inexistente"}, 404)
                        return
                    db.execute(
                        """
                        UPDATE people
                        SET first_name = ?, last_name = ?, email = ?, phone = ?, dni = ?, company = ?
                        WHERE id = ?
                        """,
                        (
                            data.get("first_name", "").strip(),
                            data.get("last_name", "").strip(),
                            data.get("email", "").strip().lower(),
                            data.get("phone", "").strip(),
                            data.get("dni", "").strip(),
                            data.get("company", "").strip(),
                            row["person_id"],
                        ),
                    )
                    db.execute(
                        "UPDATE accreditations SET type = ? WHERE id = ?",
                        (data.get("type", row["type"]).strip() or row["type"], accreditation_id),
                    )
                    audit(db, actor, "accreditation.updated", "accreditation", accreditation_id, data)
                    db.execute("COMMIT")
                self.send_json({"ok": True})
                return

            if path == "/api/accreditations/status":
                actor = data.get("actor", "Recepcion")
                accreditation_id = int(data.get("id") or 0)
                status = data.get("status", "").strip()
                if not accreditation_id or status not in ("active", "cancelled"):
                    self.send_json({"error": "Estado invalido"}, 400)
                    return
                with DB_LOCK, connect() as db:
                    db.execute("BEGIN IMMEDIATE")
                    if not can_actor(db, actor, RECEPTION_ROLES):
                        db.execute("ROLLBACK")
                        self.send_json(deny_message(actor), 403)
                        return
                    row = db.execute("SELECT * FROM accreditations WHERE id = ?", (accreditation_id,)).fetchone()
                    if not row:
                        db.execute("ROLLBACK")
                        self.send_json({"error": "Acreditacion inexistente"}, 404)
                        return
                    db.execute("UPDATE accreditations SET status = ? WHERE id = ?", (status, accreditation_id))
                    if status == "cancelled":
                        db.execute(
                            "UPDATE reservations SET status = 'cancelled' WHERE accreditation_id = ?",
                            (accreditation_id,),
                        )
                    audit(
                        db,
                        actor,
                        "accreditation.status_changed",
                        "accreditation",
                        accreditation_id,
                        {"event_id": row["event_id"], "status": status, "reason": data.get("reason", "")},
                    )
                    db.execute("COMMIT")
                self.send_json({"ok": True})
                return

            if path == "/api/spaces":
                actor = data.get("actor", "Admin")
                event_id = int(data.get("event_id") or 0)
                name = data.get("name", "").strip()
                if not event_id or not name:
                    self.send_json({"error": "Falta evento o espacio"}, 400)
                    return
                transition = max(int(data.get("transition_minutes") or 15), 15)
                with connect() as db:
                    if not can_actor(db, actor, CONFIG_ROLES):
                        self.send_json(deny_message(actor), 403)
                        return
                    db.execute(
                        """
                        INSERT INTO spaces (event_id, name, capacity, responsible, transition_minutes, status, created_at)
                        VALUES (?, ?, ?, ?, ?, 'active', ?)
                        ON CONFLICT(event_id, name)
                        DO UPDATE SET
                            capacity = excluded.capacity,
                            responsible = excluded.responsible,
                            transition_minutes = excluded.transition_minutes,
                            status = 'active'
                        """,
                        (
                            event_id,
                            name,
                            int(data.get("capacity") or 0),
                            data.get("responsible", "").strip(),
                            transition,
                            now_iso(),
                        ),
                    )
                    audit(db, actor, "space.saved", "event", event_id, data)
                self.send_json({"ok": True})
                return

            if path == "/api/capacity-bags":
                actor = data.get("actor", "Admin")
                bag_id = int(data.get("id") or 0)
                assigned = int(data.get("assigned_capacity") or 0)
                if not bag_id:
                    self.send_json({"error": "Falta bolsa"}, 400)
                    return
                with DB_LOCK, connect() as db:
                    db.execute("BEGIN IMMEDIATE")
                    if not can_actor(db, actor, CONFIG_ROLES):
                        db.execute("ROLLBACK")
                        self.send_json(deny_message(actor), 403)
                        return
                    bag = db.execute(
                        "SELECT b.*, a.capacity AS physical_capacity FROM capacity_bags b JOIN activities a ON a.id = b.activity_id WHERE b.id = ?",
                        (bag_id,),
                    ).fetchone()
                    if not bag:
                        db.execute("ROLLBACK")
                        self.send_json({"error": "Bolsa inexistente"}, 404)
                        return
                    used = bag_usage(db, bag_id)
                    if assigned < used:
                        db.execute("ROLLBACK")
                        self.send_json({"error": f"La bolsa ya tiene {used} reservas confirmadas"}, 409)
                        return
                    other_total = int(
                        db.execute(
                            "SELECT SUM(assigned_capacity) AS total FROM capacity_bags WHERE activity_id = ? AND id <> ?",
                            (bag["activity_id"], bag_id),
                        ).fetchone()["total"]
                        or 0
                    )
                    physical = int(bag["physical_capacity"] or 0)
                    if physical and other_total + assigned > physical:
                        db.execute("ROLLBACK")
                        self.send_json({"error": "La suma de bolsas supera la capacidad fisica"}, 409)
                        return
                    db.execute(
                        """
                        UPDATE capacity_bags
                        SET name = ?, assigned_capacity = ?, priority = ?, public_visible = ?,
                            public_registration = ?, reception_enabled = ?, release_enabled = ?, status = ?
                        WHERE id = ?
                        """,
                        (
                            data.get("name", bag["name"]).strip() or bag["name"],
                            assigned,
                            int(data.get("priority") or bag["priority"]),
                            1 if data.get("public_visible") else 0,
                            1 if data.get("public_registration") else 0,
                            1 if data.get("reception_enabled") else 0,
                            1 if data.get("release_enabled") else 0,
                            data.get("status", bag["status"]),
                            bag_id,
                        ),
                    )
                    audit(db, actor, "capacity_bag.saved", "capacity_bag", bag_id, data)
                    db.execute("COMMIT")
                self.send_json({"ok": True})
                return

            if path == "/api/capacity-bags/move":
                actor = data.get("actor", "Admin")
                origin_id = int(data.get("origin_id") or 0)
                target_id = int(data.get("target_id") or 0)
                amount = int(data.get("amount") or 0)
                reason = data.get("reason", "").strip()
                if not origin_id or not target_id or amount <= 0 or origin_id == target_id:
                    self.send_json({"error": "Movimiento invalido"}, 400)
                    return
                with DB_LOCK, connect() as db:
                    db.execute("BEGIN IMMEDIATE")
                    if not can_actor(db, actor, CONFIG_ROLES):
                        db.execute("ROLLBACK")
                        self.send_json(deny_message(actor), 403)
                        return
                    origin = db.execute("SELECT * FROM capacity_bags WHERE id = ?", (origin_id,)).fetchone()
                    target = db.execute("SELECT * FROM capacity_bags WHERE id = ?", (target_id,)).fetchone()
                    if not origin or not target or origin["activity_id"] != target["activity_id"]:
                        db.execute("ROLLBACK")
                        self.send_json({"error": "Las bolsas deben pertenecer a la misma actividad"}, 400)
                        return
                    origin_available = int(origin["assigned_capacity"] or 0) - bag_usage(db, origin_id)
                    if origin_available < amount:
                        db.execute("ROLLBACK")
                        self.send_json({"error": "La bolsa origen no tiene cupo libre suficiente"}, 409)
                        return
                    db.execute("UPDATE capacity_bags SET assigned_capacity = assigned_capacity - ? WHERE id = ?", (amount, origin_id))
                    db.execute("UPDATE capacity_bags SET assigned_capacity = assigned_capacity + ? WHERE id = ?", (amount, target_id))
                    audit(
                        db,
                        actor,
                        "capacity_bag.moved",
                        "capacity_bag",
                        target_id,
                        {"origin_id": origin_id, "target_id": target_id, "amount": amount, "reason": reason, "event_id": target["event_id"], "activity_id": target["activity_id"]},
                    )
                    db.execute("COMMIT")
                self.send_json({"ok": True})
                return

            if path == "/api/public-display/config":
                actor = data.get("actor", "Admin")
                event_id = int(data.get("event_id") or 0)
                if not event_id:
                    self.send_json({"error": "Falta evento"}, 400)
                    return
                with connect() as db:
                    if not can_actor(db, actor, CONFIG_ROLES):
                        self.send_json(deny_message(actor), 403)
                        return
                    ensure_public_display_config(db, event_id)
                    db.execute(
                        """
                        UPDATE public_display_config
                        SET mode = ?, refresh_seconds = ?, paused = ?, message = ?, room_filter = ?, status_filter = ?, updated_at = ?
                        WHERE event_id = ?
                        """,
                        (
                            data.get("mode", "airport"),
                            max(int(data.get("refresh_seconds") or 10), 3),
                            1 if data.get("paused") else 0,
                            data.get("message", "").strip(),
                            data.get("room_filter", "").strip(),
                            data.get("status_filter", "").strip(),
                            now_iso(),
                            event_id,
                        ),
                    )
                    audit(db, actor, "public_display.config_saved", "event", event_id, data)
                self.send_json({"ok": True})
                return

            if path == "/api/public-display/item":
                actor = data.get("actor", "Admin")
                event_id = int(data.get("event_id") or 0)
                activity_id = int(data.get("activity_id") or 0)
                visible = 1 if data.get("visible", True) else 0
                if not event_id or not activity_id:
                    self.send_json({"error": "Falta evento o actividad"}, 400)
                    return
                with connect() as db:
                    if not can_actor(db, actor, CONFIG_ROLES):
                        self.send_json(deny_message(actor), 403)
                        return
                    db.execute(
                        """
                        INSERT INTO public_display_items (event_id, activity_id, sort_order, visible, created_at)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(event_id, activity_id)
                        DO UPDATE SET visible = excluded.visible, sort_order = excluded.sort_order
                        """,
                        (event_id, activity_id, int(data.get("sort_order") or 0), visible, now_iso()),
                    )
                    audit(db, actor, "public_display.item_saved", "activity", activity_id, {"event_id": event_id, "visible": visible})
                self.send_json({"ok": True})
                return

            if path == "/api/activities":
                actor = data.get("actor", "Admin")
                event_id = int(data.get("event_id") or 0)
                space_id = int(data.get("space_id") or 0)
                title = data.get("title", "").strip()
                starts_at = data.get("starts_at", "").strip()
                ends_at = data.get("ends_at", "").strip()
                if not event_id or not space_id or not title or not starts_at or not ends_at:
                    self.send_json({"error": "Faltan datos de actividad"}, 400)
                    return
                with DB_LOCK, connect() as db:
                    db.execute("BEGIN IMMEDIATE")
                    if not can_actor(db, actor, CONFIG_ROLES):
                        db.execute("ROLLBACK")
                        self.send_json(deny_message(actor), 403)
                        return
                    conflict = validate_activity_schedule(db, event_id, space_id, starts_at, ends_at)
                    if conflict:
                        db.execute("ROLLBACK")
                        self.send_json({"error": conflict}, 409)
                        return
                    cur = db.execute(
                        """
                        INSERT INTO activities (
                            event_id, space_id, title, description, speaker, activity_type,
                            starts_at, ends_at, capacity, reservation_mode,
                            requiere_asistencia, porcentaje_minimo_asistencia, habilita_certificado, attendance_mode,
                            status, created_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'published', ?)
                        """,
                        (
                            event_id,
                            space_id,
                            title,
                            data.get("description", "").strip(),
                            data.get("speaker", "").strip(),
                            data.get("activity_type", "Charla").strip() or "Charla",
                            starts_at,
                            ends_at,
                            int(data.get("capacity") or 0),
                            data.get("reservation_mode", "free").strip() or "free",
                            1 if truthy(data.get("requiere_asistencia", True)) else 0,
                            int(data.get("porcentaje_minimo_asistencia") or 80),
                            1 if truthy(data.get("habilita_certificado", True)) else 0,
                            data.get("attendance_mode", "").strip(),
                            now_iso(),
                        ),
                    )
                    ensure_capacity_bags(db, event_id=event_id, activity_id=cur.lastrowid)
                    audit(db, actor, "activity.created", "activity", cur.lastrowid, data)
                    db.execute("COMMIT")
                self.send_json({"ok": True, "id": cur.lastrowid}, 201)
                return

            if path == "/api/reservations":
                actor = data.get("actor", "Recepcion")
                event_id = int(data.get("event_id") or 0)
                activity_id = int(data.get("activity_id") or 0)
                accreditation_id = int(data.get("accreditation_id") or 0)
                if not event_id or not activity_id or not accreditation_id:
                    self.send_json({"error": "Faltan datos de reserva"}, 400)
                    return
                with DB_LOCK, connect() as db:
                    db.execute("BEGIN IMMEDIATE")
                    if not can_actor(db, actor, RECEPTION_ROLES):
                        db.execute("ROLLBACK")
                        self.send_json(deny_message(actor), 403)
                        return
                    reservation = create_reservation(db, event_id, activity_id, accreditation_id, "reception")
                    if reservation["ok"] and reservation.get("existing"):
                        db.execute("COMMIT")
                        self.send_json({"ok": True, "status": reservation["status"], "existing": True})
                        return
                    if not reservation["ok"]:
                        db.execute("ROLLBACK")
                        self.send_json({"error": reservation["error"]}, int(reservation.get("status_code", 400)))
                        return
                    audit(
                        db,
                        actor,
                        "reservation.created",
                        "reservation",
                        reservation.get("id"),
                        {"event_id": event_id, "activity_id": activity_id, "accreditation_id": accreditation_id, "status": reservation["status"]},
                    )
                    db.execute("COMMIT")
                self.send_json({"ok": True, "status": reservation["status"]}, 201)
                return

            if path == "/api/reservations/status":
                actor = data.get("actor", "Recepcion")
                reservation_id = int(data.get("id") or 0)
                status = data.get("status", "").strip()
                if not reservation_id or status not in ("cancelled", "confirmed"):
                    self.send_json({"error": "Estado de reserva invalido"}, 400)
                    return
                with DB_LOCK, connect() as db:
                    db.execute("BEGIN IMMEDIATE")
                    if not can_actor(db, actor, RECEPTION_ROLES):
                        db.execute("ROLLBACK")
                        self.send_json(deny_message(actor), 403)
                        return
                    reservation = db.execute("SELECT * FROM reservations WHERE id = ?", (reservation_id,)).fetchone()
                    if not reservation:
                        db.execute("ROLLBACK")
                        self.send_json({"error": "Reserva inexistente"}, 404)
                        return
                    promoted = None
                    if status == "confirmed":
                        if reservation["status"] != "waitlisted":
                            db.execute("ROLLBACK")
                            self.send_json({"error": "Solo se puede promover una reserva en espera"}, 409)
                            return
                        if not activity_has_capacity(db, reservation["activity_id"]):
                            db.execute("ROLLBACK")
                            self.send_json({"error": "La actividad no tiene cupo disponible"}, 409)
                            return
                        db.execute("UPDATE reservations SET status = 'confirmed' WHERE id = ?", (reservation_id,))
                    else:
                        db.execute("UPDATE reservations SET status = 'cancelled' WHERE id = ?", (reservation_id,))
                        if reservation["status"] == "confirmed":
                            promoted = promote_next_waitlisted(db, reservation["event_id"], reservation["activity_id"])
                            if promoted:
                                audit(
                                    db,
                                    actor,
                                    "reservation.promoted",
                                    "reservation",
                                    promoted["id"],
                                    {"event_id": promoted["event_id"], "activity_id": promoted["activity_id"], "auto": True},
                                )
                    audit(
                        db,
                        actor,
                        "reservation.status_changed",
                        "reservation",
                        reservation_id,
                        {"event_id": reservation["event_id"], "activity_id": reservation["activity_id"], "status": status},
                    )
                    db.execute("COMMIT")
                self.send_json({"ok": True, "status": status, "promoted": promoted})
                return

            if path == "/api/register":
                event_id = int(data.get("event_id") or 0)
                if not event_id:
                    self.send_json({"error": "Falta evento"}, 400)
                    return
                raw_activity_ids = data.get("activity_ids") or []
                if isinstance(raw_activity_ids, str):
                    raw_activity_ids = [item for item in raw_activity_ids.split(",") if item.strip()]
                activity_ids = [int(item) for item in raw_activity_ids if str(item).strip().isdigit()]
                if len(activity_ids) > 1:
                    self.send_json({"error": "Solo se permite reservar una actividad por vez. Repeti el paso para sumar otra actividad."}, 400)
                    return
                with DB_LOCK, connect() as db:
                    db.execute("BEGIN IMMEDIATE")
                    event = db.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
                    if not event:
                        db.execute("ROLLBACK")
                        self.send_json({"error": "Evento inexistente"}, 404)
                        return
                    if not int(event["permitir_reserva_actividades_desde_landing"] or 0):
                        activity_ids = []
                    elif event["activity_selection_mode"] == "required_landing" and not activity_ids:
                        db.execute("ROLLBACK")
                        self.send_json({"error": "Debes seleccionar al menos una actividad"}, 400)
                        return
                    registration = register_accreditation(db, event_id, data)
                    if not registration["ok"]:
                        db.execute("ROLLBACK")
                        self.send_json({"error": registration["error"]}, int(registration.get("status_code", 400)))
                        return
                    source = normalize_source(data.get("source"), "recepcion" if data.get("actor") != "public" else "landing")
                    source_detail = str(data.get("source_detail") or data.get("utm_campaign") or data.get("qr_source") or "").strip()
                    device_type = normalize_device(data.get("device_type"))
                    record_captation_event(
                        db,
                        event_id,
                        "form_completed",
                        source,
                        device_type,
                        source_detail=source_detail,
                        session_id=str(data.get("session_id") or ""),
                        accreditation_id=registration["id"],
                        person_id=registration["person_id"],
                    )
                    if not registration.get("existing"):
                        audit(db, data.get("actor", "public"), "accreditation.created", "accreditation", registration["id"], {"event_id": event_id, "person_id": registration["person_id"], "source": source, "device_type": device_type})
                        audit(db, data.get("actor", "public"), "portal.generated", "accreditation", registration["id"], {"event_id": event_id, "portal_url": public_link(f"/p.html?token={registration['token']}", self), "source": source, "device_type": device_type})
                        record_captation_event(
                            db,
                            event_id,
                            "portal_created",
                            source,
                            device_type,
                            source_detail=source_detail,
                            session_id=str(data.get("session_id") or ""),
                            accreditation_id=registration["id"],
                            person_id=registration["person_id"],
                        )
                        if data.get("actor") == "public":
                            portal_url = public_link(f"/p.html?token={registration['token']}", self)
                            communication_log(
                                db,
                                event_id,
                                registration["person_id"],
                                registration["id"],
                                "email",
                                "confirmacion",
                                "Inscripcion confirmada",
                                f"Tu inscripcion fue confirmada. Portal: {portal_url}",
                                "demo",
                            )
                            communication_log(
                                db,
                                event_id,
                                registration["person_id"],
                                registration["id"],
                                "whatsapp",
                                "confirmacion",
                                "Inscripcion confirmada",
                                f"Tu inscripcion fue confirmada. Portal: {portal_url}",
                                "demo",
                            )
                    reservations = []
                    for activity_id in activity_ids:
                        reservation = create_reservation(db, event_id, activity_id, registration["id"], "public" if data.get("actor") == "public" else "reception")
                        reservations.append(reservation)
                        if reservation["ok"] and not reservation.get("existing"):
                            audit(
                                db,
                                data.get("actor", "public"),
                                "reservation.created",
                                "reservation",
                                reservation.get("id"),
                                {"event_id": event_id, "activity_id": activity_id, "accreditation_id": registration["id"], "status": reservation["status"]},
                            )
                    db.execute("COMMIT")
                self.send_json({"ok": True, "token": registration["token"], "existing": registration.get("existing", False), "portal_url": public_link(f"/p.html?token={registration['token']}", self), "reservations": reservations}, 200 if registration.get("existing") else 201)
                return

            if path == "/api/import-accreditations":
                actor = data.get("actor", "Recepcion")
                event_id = int(data.get("event_id") or 0)
                rows = data.get("rows") or []
                if not event_id or not isinstance(rows, list):
                    self.send_json({"error": "Faltan evento o filas"}, 400)
                    return
                summary = {"created": 0, "existing": 0, "errors": 0, "rows": []}
                with DB_LOCK, connect() as db:
                    db.execute("BEGIN IMMEDIATE")
                    if not can_actor(db, actor, RECEPTION_ROLES):
                        db.execute("ROLLBACK")
                        self.send_json(deny_message(actor), 403)
                        return
                    for index, row in enumerate(rows, start=1):
                        item = {
                            "first_name": str(row.get("first_name") or row.get("nombre") or "").strip(),
                            "last_name": str(row.get("last_name") or row.get("apellido") or "").strip(),
                            "email": str(row.get("email") or row.get("mail") or "").strip(),
                            "phone": str(row.get("phone") or row.get("telefono") or "").strip(),
                            "dni": str(row.get("dni") or "").strip(),
                            "company": str(row.get("company") or row.get("empresa") or "").strip(),
                            "type": str(row.get("type") or row.get("tipo") or "General").strip() or "General",
                            "source": str(row.get("source") or row.get("origen") or "recepcion").strip(),
                            "source_detail": str(row.get("source_detail") or row.get("detalle_origen") or "").strip(),
                            "device_type": str(row.get("device_type") or row.get("dispositivo") or "desktop").strip(),
                            "actor": actor,
                        }
                        registration = register_accreditation(db, event_id, item)
                        if registration["ok"]:
                            if registration.get("existing"):
                                summary["existing"] += 1
                            else:
                                summary["created"] += 1
                                audit(db, actor, "accreditation.created", "accreditation", registration["id"], {"event_id": event_id, "person_id": registration["person_id"], "imported": True})
                            summary["rows"].append({"row": index, "ok": True, "email": item["email"], "token": registration["token"], "existing": registration.get("existing", False)})
                        else:
                            summary["errors"] += 1
                            summary["rows"].append({"row": index, "ok": False, "email": item["email"], "error": registration["error"]})
                    audit(db, actor, "accreditation.imported", "event", event_id, {"event_id": event_id, "summary": {k: summary[k] for k in ("created", "existing", "errors")}})
                    db.execute("COMMIT")
                self.send_json({"ok": True, **summary})
                return

            if path == "/api/validate":
                token = data.get("token", "").strip()
                operator = data.get("operator", "operador").strip()
                checkpoint = data.get("checkpoint", "Acceso principal").strip()
                activity_id = int(data.get("activity_id") or 0)
                with DB_LOCK, connect() as db:
                    db.execute("BEGIN IMMEDIATE")
                    if not can_actor(db, operator, ACCESS_ROLES):
                        db.execute("ROLLBACK")
                        self.send_json(deny_message(operator), 403)
                        return
                    validation = access_validation_service().validate(db, token, operator, checkpoint, activity_id)
                    if validation.get("result") == "granted" and activity_id:
                        attendance = attendance_service().register_entry(db, token, activity_id, operator)
                        release_available_certificates(db)
                        validation["attendance"] = attendance
                        if attendance.get("ok") and not attendance.get("ignored"):
                            validation["reason"] = f"{validation['reason']} - asistencia {attendance['status']}"
                    db.execute("COMMIT")
                status_code = int(validation.pop("status_code", 200))
                self.send_json(validation, status_code)
                return

            if path == "/api/attendance/exit":
                token = data.get("token", "").strip()
                actor = data.get("actor", "Acceso").strip()
                activity_id = int(data.get("activity_id") or 0)
                if not token or not activity_id:
                    self.send_json({"error": "Faltan token o actividad"}, 400)
                    return
                with DB_LOCK, connect() as db:
                    db.execute("BEGIN IMMEDIATE")
                    if not can_actor(db, actor, ACCESS_ROLES):
                        db.execute("ROLLBACK")
                        self.send_json(deny_message(actor), 403)
                        return
                    result = attendance_service().register_exit(db, token, activity_id, actor)
                    if not result.get("ok"):
                        db.execute("ROLLBACK")
                        self.send_json({"error": result["error"]}, 409)
                        return
                    release_available_certificates(db)
                    db.execute("COMMIT")
                self.send_json(result)
                return

            if path == "/api/attendance/manual":
                actor = data.get("actor", "Admin").strip()
                attendance_id = int(data.get("id") or 0)
                if not attendance_id:
                    self.send_json({"error": "Falta asistencia"}, 400)
                    return
                with DB_LOCK, connect() as db:
                    db.execute("BEGIN IMMEDIATE")
                    if not can_actor(db, actor, ADMIN_ROLES):
                        db.execute("ROLLBACK")
                        self.send_json(deny_message(actor), 403)
                        return
                    result = attendance_service().manual_update(
                        db,
                        attendance_id,
                        actor,
                        str(data.get("status") or "Pendiente"),
                        int(data["percentage"]) if str(data.get("percentage", "")).strip() else None,
                        str(data.get("reason") or "").strip(),
                    )
                    if not result.get("ok"):
                        db.execute("ROLLBACK")
                        self.send_json({"error": result["error"]}, 404)
                        return
                    release_available_certificates(db)
                    db.execute("COMMIT")
                self.send_json(result)
                return

            self.send_json({"error": "Ruta no encontrada"}, 404)
        except sqlite3.IntegrityError as exc:
            self.send_json({"error": "Dato duplicado o invalido", "detail": str(exc)}, 409)
        except Exception as exc:
            self.send_json({"error": str(exc)}, 500)


class OperationalHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 512


class _TextWriter:
    def __init__(self, raw):
        self.raw = raw

    def write(self, text: str) -> None:
        self.raw.write(text.encode("utf-8"))


def main() -> None:
    init_db()
    seed_if_empty()
    if APP_ENV in {"demo", "production"} and HTTPS_REQUIRED and not BASE_URL:
        print("ADVERTENCIA: HTTPS_REQUIRED esta activo pero BASE_URL no fue definido")
    host = os.environ.get("QR_HOST", "0.0.0.0" if APP_ENV in {"demo", "production"} else "localhost")
    port = int(os.environ.get("PORT") or os.environ.get("QR_PORT") or "8787")
    start_auto_backup()
    httpd = OperationalHTTPServer((host, port), AppHandler)
    httpd.require_login = REQUIRE_LOGIN or host not in {"localhost", "127.0.0.1"}
    print(f"BITORA {APP_VERSION} iniciada")
    print(f"Entorno: {APP_ENV}")
    print(f"Base URL: {configured_base_url()}")
    print(f"Base de datos: {DB_CONFIG.engine} ({DB_PATH})")
    print(f"Plataforma lista en http://{host}:{port}")
    if httpd.require_login:
        print("Consola protegida con PIN. PIN inicial: Admin=1234, Recepcion=2222, Acceso=3333")
    if AUTO_BACKUP_MINUTES > 0:
        print(f"Backup automatico cada {AUTO_BACKUP_MINUTES} min, conserva {BACKUP_KEEP_LAST} copias")
    try:
        httpd.serve_forever()
    finally:
        BACKUP_STOP.set()
        httpd.server_close()


if __name__ == "__main__":
    main()
