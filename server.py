from __future__ import annotations

import csv
import base64
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
import random
import re
from io import BytesIO
from datetime import datetime, timedelta, timezone
from html import escape
from http import HTTPStatus
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from backend.database import connect_database, integrity_error_types, load_database_config, run_postgres_migrations
from backend.repositories import create_repository
from backend.services.access_validation import AccessValidationService
from backend.services.attendance import AttendanceService
from backend.services.audit import AuditService
from backend.services.backup import BackupService, PostgresBackupService
from backend.services.capacity_buckets import CapacityBucketService
from backend.services.demo_real import DemoRealService
from backend.services.diagnostics import DiagnosticsService, RuntimeMetrics
from backend.services.email import DemoEmailProvider, create_email_provider
from backend.services.jobs import JobQueueService, JobWorker
from backend.services.qr import QRService
from backend.services.qrcodegen import QrCode
from backend.services.reservations import ReservationService
from backend.services.whatsapp import DemoWhatsAppProvider, create_whatsapp_provider


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
WORKER: JobWorker | None = None
SIMULATOR_STOP = threading.Event()
SIMULATOR_THREAD: threading.Thread | None = None
AUTO_BACKUP_MINUTES = int(os.environ.get("QR_AUTO_BACKUP_MINUTES", "10"))
BACKUP_KEEP_LAST = int(os.environ.get("QR_BACKUP_KEEP_LAST", "24"))
APP_VERSION = "7.0-whatsapp-meta-ready"
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
REPOSITORY = create_repository(DB_CONFIG.engine)
DB_INTEGRITY_ERRORS = integrity_error_types()
RUNTIME_METRICS = RuntimeMetrics()


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


def backup_service():
    if DB_CONFIG.engine == "postgres":
        return PostgresBackupService(BACKUP_DIR, connect, DB_LOCK, keep_last=lambda: BACKUP_KEEP_LAST)
    return BackupService(DB_PATH, BACKUP_DIR, connect, DB_LOCK, keep_last=lambda: BACKUP_KEEP_LAST)


def diagnostics_service() -> DiagnosticsService:
    return DiagnosticsService(
        engine=DB_CONFIG.engine,
        db_path=DB_PATH,
        backup_dir=BACKUP_DIR,
        app_env=APP_ENV,
        app_version=APP_VERSION,
        started_at=STARTED_AT,
    )


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
    if BASE_URL or (handler and APP_ENV in {"demo", "production"}):
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


def connect():
    return connect_database(DB_CONFIG, DB_PATH)


def init_db() -> None:
    if DB_CONFIG.engine == "postgres":
        applied = run_postgres_migrations(DB_CONFIG, ROOT / "backend" / "migrations")
        if applied:
            print(f"Migraciones PostgreSQL aplicadas: {', '.join(applied)}")
        with connect() as db:
            ensure_default_users(db)
            ensure_default_types(db)
            ensure_default_spaces(db)
            ensure_capacity_bags(db)
            ensure_communication_templates(db)
        return
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
                activities_enabled INTEGER NOT NULL DEFAULT 1,
                capacity_control_enabled INTEGER NOT NULL DEFAULT 1,
                waitlist_enabled INTEGER NOT NULL DEFAULT 0,
                activity_access_open_minutes_before INTEGER NOT NULL DEFAULT 10,
                landing_image_data TEXT NOT NULL DEFAULT '',
                landing_image_name TEXT NOT NULL DEFAULT '',
                landing_image_type TEXT NOT NULL DEFAULT '',
                landing_image_updated_at TEXT NOT NULL DEFAULT '',
                landing_logo_data TEXT NOT NULL DEFAULT '',
                landing_primary_color TEXT NOT NULL DEFAULT '',
                landing_secondary_color TEXT NOT NULL DEFAULT '',
                landing_mobile_banner_data TEXT NOT NULL DEFAULT '',
                landing_video_url TEXT NOT NULL DEFAULT '',
                waiting_room_enabled INTEGER NOT NULL DEFAULT 0,
                waiting_room_open_at TEXT NOT NULL DEFAULT '',
                users_allowed_per_minute INTEGER NOT NULL DEFAULT 60,
                turn_duration_minutes INTEGER NOT NULL DEFAULT 10,
                show_waiting_position INTEGER NOT NULL DEFAULT 1,
                show_estimated_time INTEGER NOT NULL DEFAULT 1,
                waiting_message TEXT NOT NULL DEFAULT 'Estamos organizando el ingreso. Tu turno se habilitara pronto.',
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
                access_open_minutes_before INTEGER,
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
                activity_id INTEGER REFERENCES activities(id) ON DELETE SET NULL,
                token TEXT NOT NULL,
                operator TEXT NOT NULL DEFAULT '',
                operator_id INTEGER,
                checkpoint TEXT NOT NULL DEFAULT '',
                access_point TEXT NOT NULL DEFAULT '',
                access_context TEXT NOT NULL DEFAULT 'event_entry',
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

            CREATE TABLE IF NOT EXISTS communication_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
                person_id INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
                accreditation_id INTEGER REFERENCES accreditations(id) ON DELETE SET NULL,
                channel TEXT NOT NULL,
                audience TEXT NOT NULL DEFAULT '',
                template_code TEXT NOT NULL DEFAULT '',
                subject TEXT NOT NULL DEFAULT '',
                content TEXT NOT NULL DEFAULT '',
                recipient TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pendiente',
                attempts INTEGER NOT NULL DEFAULT 0,
                max_attempts INTEGER NOT NULL DEFAULT 3,
                provider TEXT NOT NULL DEFAULT 'demo',
                provider_message_id TEXT NOT NULL DEFAULT '',
                last_error TEXT NOT NULL DEFAULT '',
                scheduled_at TEXT,
                processed_at TEXT,
                delivered_at TEXT,
                bounced_at TEXT,
                created_by TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS email_delivery_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
                queue_id INTEGER REFERENCES communication_queue(id) ON DELETE SET NULL,
                provider TEXT NOT NULL DEFAULT '',
                message_id TEXT NOT NULL DEFAULT '',
                event_type TEXT NOT NULL,
                payload TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS communication_assistant_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
                person_id INTEGER REFERENCES people(id) ON DELETE SET NULL,
                accreditation_id INTEGER REFERENCES accreditations(id) ON DELETE SET NULL,
                phone TEXT NOT NULL DEFAULT '',
                inbound TEXT NOT NULL DEFAULT '',
                outbound TEXT NOT NULL DEFAULT '',
                intent TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'resolved',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS communication_tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
                person_id INTEGER REFERENCES people(id) ON DELETE SET NULL,
                accreditation_id INTEGER REFERENCES accreditations(id) ON DELETE SET NULL,
                channel TEXT NOT NULL DEFAULT 'whatsapp',
                reason TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'open',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
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

            CREATE TABLE IF NOT EXISTS technical_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                level TEXT NOT NULL DEFAULT 'info',
                module TEXT NOT NULL DEFAULT 'system',
                message TEXT NOT NULL,
                detail TEXT NOT NULL DEFAULT '',
                request_path TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER REFERENCES events(id) ON DELETE SET NULL,
                kind TEXT NOT NULL,
                priority TEXT NOT NULL DEFAULT 'low',
                status TEXT NOT NULL DEFAULT 'pending',
                payload TEXT NOT NULL DEFAULT '{}',
                result TEXT NOT NULL DEFAULT '{}',
                retry_count INTEGER NOT NULL DEFAULT 0,
                max_retries INTEGER NOT NULL DEFAULT 3,
                retry_at TEXT,
                worker_id TEXT NOT NULL DEFAULT '',
                error TEXT NOT NULL DEFAULT '',
                created_by TEXT NOT NULL DEFAULT 'system',
                created_at TEXT NOT NULL,
                started_at TEXT,
                finished_at TEXT,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS waiting_room_visitors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
                visitor_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'waiting',
                position_number INTEGER NOT NULL DEFAULT 0,
                access_token TEXT NOT NULL DEFAULT '',
                joined_at TEXT NOT NULL,
                admitted_at TEXT,
                expires_at TEXT,
                completed_at TEXT,
                abandoned_at TEXT,
                last_seen_at TEXT NOT NULL,
                error TEXT NOT NULL DEFAULT '',
                UNIQUE(event_id, visitor_id)
            );

            CREATE TABLE IF NOT EXISTS simulator_state (
                event_id INTEGER PRIMARY KEY REFERENCES events(id) ON DELETE CASCADE,
                status TEXT NOT NULL DEFAULT 'stopped',
                mode TEXT NOT NULL DEFAULT 'medium',
                scenario TEXT NOT NULL DEFAULT 'congress',
                participants_active INTEGER NOT NULL DEFAULT 100,
                accesses_per_minute INTEGER NOT NULL DEFAULT 30,
                rejections_per_minute INTEGER NOT NULL DEFAULT 3,
                simulated_errors INTEGER NOT NULL DEFAULT 1,
                average_occupancy INTEGER NOT NULL DEFAULT 55,
                active_terminals INTEGER NOT NULL DEFAULT 10,
                speed REAL NOT NULL DEFAULT 1,
                updated_by TEXT NOT NULL DEFAULT 'system',
                updated_at TEXT NOT NULL
            );
            """
        )
        ensure_event_v3_columns(db)
        ensure_v4_1_columns(db)
        ensure_v4_2_columns(db)
        ensure_v4_4_columns(db)
        ensure_v6_1_email_schema(db)
        ensure_waiting_room_schema(db)
        ensure_landing_config_columns(db)
        ensure_activity_access_window_columns(db)
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
        CREATE INDEX IF NOT EXISTS idx_access_logs_activity_context ON access_logs(activity_id, accreditation_id, access_context, result);
        CREATE INDEX IF NOT EXISTS idx_activities_event_start ON activities(event_id, starts_at);
        CREATE INDEX IF NOT EXISTS idx_audit_logs_created ON audit_logs(created_at);
        CREATE INDEX IF NOT EXISTS idx_communication_logs_event ON communication_logs(event_id, fecha);
        CREATE INDEX IF NOT EXISTS idx_communication_queue_event_status ON communication_queue(event_id, status);
        CREATE INDEX IF NOT EXISTS idx_communication_queue_provider_message ON communication_queue(provider_message_id);
        CREATE INDEX IF NOT EXISTS idx_email_delivery_message ON email_delivery_events(message_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_technical_logs_created ON technical_logs(created_at);
        CREATE INDEX IF NOT EXISTS idx_technical_logs_level_module ON technical_logs(level, module, created_at);
        CREATE INDEX IF NOT EXISTS idx_jobs_status_priority ON jobs(status, priority, retry_at, id);
        CREATE INDEX IF NOT EXISTS idx_jobs_event_kind ON jobs(event_id, kind, created_at);
        CREATE INDEX IF NOT EXISTS idx_waiting_room_event_status ON waiting_room_visitors(event_id, status, joined_at);
        CREATE INDEX IF NOT EXISTS idx_communication_assistant_event ON communication_assistant_history(event_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_communication_tickets_event_status ON communication_tickets(event_id, status);
        CREATE INDEX IF NOT EXISTS idx_preferences_person ON participant_communication_preferences(person_id);
        CREATE INDEX IF NOT EXISTS idx_attendance_event_activity ON activity_attendance(event_id, activity_id);
        CREATE INDEX IF NOT EXISTS idx_attendance_accreditation ON activity_attendance(accreditation_id);
        CREATE INDEX IF NOT EXISTS idx_certificate_event ON certificate_eligibility(event_id, estado);
        CREATE INDEX IF NOT EXISTS idx_captation_event_source ON captation_events(event_id, source, action);
        CREATE INDEX IF NOT EXISTS idx_conversation_source_event ON conversation_sources(event_id, source);
        """
    )


def ensure_v6_1_email_schema(db: sqlite3.Connection) -> None:
    columns = {row["name"] for row in db.execute("PRAGMA table_info(communication_queue)").fetchall()}
    additions = {
        "max_attempts": "INTEGER NOT NULL DEFAULT 3",
        "provider_message_id": "TEXT NOT NULL DEFAULT ''",
        "delivered_at": "TEXT",
        "bounced_at": "TEXT",
    }
    for name, definition in additions.items():
        if name not in columns:
            db.execute(f"ALTER TABLE communication_queue ADD COLUMN {name} {definition}")
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS email_delivery_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
            queue_id INTEGER REFERENCES communication_queue(id) ON DELETE SET NULL,
            provider TEXT NOT NULL DEFAULT '',
            message_id TEXT NOT NULL DEFAULT '',
            event_type TEXT NOT NULL,
            payload TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL
        );
        """
    )


def ensure_waiting_room_schema(db: sqlite3.Connection) -> None:
    columns = {row["name"] for row in db.execute("PRAGMA table_info(events)").fetchall()}
    additions = {
        "waiting_room_enabled": "INTEGER NOT NULL DEFAULT 0",
        "waiting_room_open_at": "TEXT NOT NULL DEFAULT ''",
        "users_allowed_per_minute": "INTEGER NOT NULL DEFAULT 60",
        "turn_duration_minutes": "INTEGER NOT NULL DEFAULT 10",
        "show_waiting_position": "INTEGER NOT NULL DEFAULT 1",
        "show_estimated_time": "INTEGER NOT NULL DEFAULT 1",
        "waiting_message": "TEXT NOT NULL DEFAULT 'Estamos organizando el ingreso. Tu turno se habilitara pronto.'",
    }
    for name, definition in additions.items():
        if name not in columns:
            db.execute(f"ALTER TABLE events ADD COLUMN {name} {definition}")
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS waiting_room_visitors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
            visitor_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'waiting',
            position_number INTEGER NOT NULL DEFAULT 0,
            access_token TEXT NOT NULL DEFAULT '',
            joined_at TEXT NOT NULL,
            admitted_at TEXT,
            expires_at TEXT,
            completed_at TEXT,
            abandoned_at TEXT,
            last_seen_at TEXT NOT NULL,
            error TEXT NOT NULL DEFAULT '',
            UNIQUE(event_id, visitor_id)
        )
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


def ensure_landing_config_columns(db: sqlite3.Connection) -> None:
    event_columns = [row["name"] for row in db.execute("PRAGMA table_info(events)").fetchall()]
    for name in [
        "landing_image_data",
        "landing_image_name",
        "landing_image_type",
        "landing_image_updated_at",
        "landing_logo_data",
        "landing_primary_color",
        "landing_secondary_color",
        "landing_mobile_banner_data",
        "landing_video_url",
    ]:
        if name not in event_columns:
            db.execute(f"ALTER TABLE events ADD COLUMN {name} TEXT NOT NULL DEFAULT ''")


def ensure_activity_access_window_columns(db: sqlite3.Connection) -> None:
    event_columns = [row["name"] for row in db.execute("PRAGMA table_info(events)").fetchall()]
    if "activity_access_open_minutes_before" not in event_columns:
        db.execute("ALTER TABLE events ADD COLUMN activity_access_open_minutes_before INTEGER NOT NULL DEFAULT 10")
    if "activities_enabled" not in event_columns:
        db.execute("ALTER TABLE events ADD COLUMN activities_enabled INTEGER NOT NULL DEFAULT 1")
    if "capacity_control_enabled" not in event_columns:
        db.execute("ALTER TABLE events ADD COLUMN capacity_control_enabled INTEGER NOT NULL DEFAULT 1")
    if "waitlist_enabled" not in event_columns:
        db.execute("ALTER TABLE events ADD COLUMN waitlist_enabled INTEGER NOT NULL DEFAULT 0")

    activity_columns = [row["name"] for row in db.execute("PRAGMA table_info(activities)").fetchall()]
    if "access_open_minutes_before" not in activity_columns:
        db.execute("ALTER TABLE activities ADD COLUMN access_open_minutes_before INTEGER")

    access_columns = [row["name"] for row in db.execute("PRAGMA table_info(access_logs)").fetchall()]
    if "activity_id" not in access_columns:
        db.execute("ALTER TABLE access_logs ADD COLUMN activity_id INTEGER REFERENCES activities(id) ON DELETE SET NULL")
    if "operator_id" not in access_columns:
        db.execute("ALTER TABLE access_logs ADD COLUMN operator_id INTEGER")
    if "access_point" not in access_columns:
        db.execute("ALTER TABLE access_logs ADD COLUMN access_point TEXT NOT NULL DEFAULT ''")
    if "access_context" not in access_columns:
        db.execute("ALTER TABLE access_logs ADD COLUMN access_context TEXT NOT NULL DEFAULT 'event_entry'")


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

        CREATE TABLE IF NOT EXISTS communication_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
            person_id INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
            accreditation_id INTEGER REFERENCES accreditations(id) ON DELETE SET NULL,
            channel TEXT NOT NULL,
            audience TEXT NOT NULL DEFAULT '',
            template_code TEXT NOT NULL DEFAULT '',
            subject TEXT NOT NULL DEFAULT '',
            content TEXT NOT NULL DEFAULT '',
            recipient TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'pendiente',
            attempts INTEGER NOT NULL DEFAULT 0,
            provider TEXT NOT NULL DEFAULT 'demo',
            last_error TEXT NOT NULL DEFAULT '',
            scheduled_at TEXT,
            processed_at TEXT,
            created_by TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS communication_assistant_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
            person_id INTEGER REFERENCES people(id) ON DELETE SET NULL,
            accreditation_id INTEGER REFERENCES accreditations(id) ON DELETE SET NULL,
            phone TEXT NOT NULL DEFAULT '',
            inbound TEXT NOT NULL DEFAULT '',
            outbound TEXT NOT NULL DEFAULT '',
            intent TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'resolved',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS communication_tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
            person_id INTEGER REFERENCES people(id) ON DELETE SET NULL,
            accreditation_id INTEGER REFERENCES accreditations(id) ON DELETE SET NULL,
            channel TEXT NOT NULL DEFAULT 'whatsapp',
            reason TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'open',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
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
        ("registration_confirmation", "Confirmacion de inscripcion", "confirmacion", "Inscripcion confirmada", "Hola {{nombre}}, tu inscripcion a {{evento}} fue confirmada. Portal: {{portal_participante}}"),
        ("qr_resend", "Reenvio QR", "qr", "Tu QR de acceso", "Hola {{nombre}}, este es tu acceso a {{evento}}: {{portal_participante}}"),
        ("payment_approved", "Pago aprobado", "pago aprobado", "Pago aprobado", "Hola {{nombre}}, tu pago para {{evento}} fue aprobado."),
        ("payment_pending", "Pago pendiente", "pago pendiente", "Pago pendiente", "Hola {{nombre}}, tu pago para {{evento}} figura pendiente."),
        ("reminder_24h", "Recordatorio 24 horas", "recordatorio", "Recordatorio del evento", "Te recordamos que {{evento}} inicia el {{fecha_evento}}. Tu portal: {{portal_participante}}"),
        ("reminder_1h", "Recordatorio 1 hora", "recordatorio", "Tu evento esta por comenzar", "{{nombre}}, {{evento}} esta por comenzar. Tene tu QR disponible: {{portal_participante}}"),
        ("room_change", "Cambio de sala", "cambio de sala", "Cambio de sala", "Una actividad de tu agenda cambio de sala. Revisa tu portal: {{portal_participante}}"),
        ("time_change", "Cambio de horario", "cambio de horario", "Cambio de horario", "Una actividad de tu agenda cambio de horario. Revisa tu portal: {{portal_participante}}"),
        ("activity_registration", "Inscripcion actividad", "inscripcion actividad", "Inscripcion a actividad", "Tu inscripcion a {{actividad}} en {{sala}} fue registrada."),
        ("waitlist", "Lista de espera", "lista espera", "Lista de espera", "Quedaste en lista de espera para {{actividad}}."),
        ("survey", "Encuesta", "encuesta", "Encuesta del evento", "Gracias por asistir a {{evento}}. Te invitamos a completar la encuesta operativa."),
        ("certificate_available", "Certificado disponible", "certificado", "Certificado disponible", "Tu certificado de {{evento}} esta disponible desde el portal: {{portal_participante}}"),
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
            INSERT INTO events (
                name, description, venue, starts_at, ends_at, status, capacity,
                activity_selection_mode, activity_access_open_minutes_before, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                10,
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


def communication_provider(channel: str) -> str:
    if channel == "email":
        try:
            return create_email_provider().name
        except ValueError:
            return os.environ.get("EMAIL_PROVIDER", "demo").strip() or "demo"
    if channel == "whatsapp":
        try:
            return create_whatsapp_provider().name
        except ValueError:
            return os.environ.get("WHATSAPP_PROVIDER", "demo").strip() or "demo"
    return "demo"


def communication_provider_ready(channel: str) -> bool:
    provider = communication_provider(channel)
    if provider == "demo":
        return False
    if channel == "email":
        try:
            return create_email_provider().ready
        except ValueError:
            return False
    if channel == "whatsapp":
        try:
            return create_whatsapp_provider().ready
        except ValueError:
            return False
    return False


def render_communication_template(text: str, row: sqlite3.Row | dict, activity: sqlite3.Row | dict | None = None) -> str:
    source = dict(row)
    act = dict(activity) if activity else {}
    portal_url = public_link(f"/p.html?token={source.get('token') or ''}")
    values = {
        "nombre": source.get("first_name", ""),
        "apellido": source.get("last_name", ""),
        "evento": source.get("event_name", ""),
        "fecha_evento": str(source.get("starts_at") or "")[:10],
        "hora_evento": str(source.get("starts_at") or "")[11:16],
        "qr": source.get("token", ""),
        "actividad": act.get("title", ""),
        "sala": act.get("space_name", ""),
        "empresa": source.get("company", ""),
        "tipo_acreditacion": source.get("type", ""),
        "portal_participante": portal_url,
    }
    output = str(text or "")
    for key, value in values.items():
        output = output.replace("{{" + key + "}}", str(value or ""))
    return output


def communication_audience_rows(db: sqlite3.Connection, event_id: int, audience: str = "all", filters: dict | None = None) -> list[sqlite3.Row]:
    filters = filters or {}
    params: list[object] = [event_id]
    where = ["a.event_id = ?", "a.status <> 'cancelled'"]
    audience = (audience or "all").strip().lower()
    if audience in {"confirmed", "acreditados", "presentes"}:
        where.append("a.checked_in_at IS NOT NULL")
    elif audience in {"pending", "pendientes"}:
        where.append("a.checked_in_at IS NULL")
    elif audience in {"expositores", "disertantes"}:
        where.append("LOWER(a.type) IN ('disertante', 'expositor')")
    elif audience in {"sponsors", "sponsor", "prensa", "staff", "vip"}:
        where.append("LOWER(a.type) = ?")
        params.append("sponsor" if audience == "sponsors" else audience)
    elif audience == "empresa" and filters.get("company"):
        where.append("LOWER(p.company) = LOWER(?)")
        params.append(str(filters["company"]))
    elif audience == "activity" and filters.get("activity_id"):
        where.append("EXISTS (SELECT 1 FROM reservations r WHERE r.accreditation_id = a.id AND r.activity_id = ? AND r.status = 'confirmed')")
        params.append(int(filters["activity_id"]))
    elif audience in {"ausentes", "absent"}:
        where.append("a.checked_in_at IS NULL")
    elif audience in {"elegibles", "eligible_certificates"}:
        where.append("EXISTS (SELECT 1 FROM certificate_eligibility ce WHERE ce.accreditation_id = a.id AND ce.elegible = 1)")
    rows = db.execute(
        f"""
        SELECT a.id AS accreditation_id, a.token, a.type, a.status,
               p.id AS person_id, p.first_name, p.last_name, p.email, p.phone, p.company,
               e.name AS event_name, e.starts_at, e.ends_at,
               COALESCE(cp.acepta_email, 0) AS acepta_email,
               COALESCE(cp.acepta_whatsapp, 0) AS acepta_whatsapp,
               COALESCE(NULLIF(cp.email, ''), p.email) AS preferred_email,
               COALESCE(NULLIF(cp.phone, ''), p.phone) AS preferred_phone
        FROM accreditations a
        JOIN people p ON p.id = a.person_id
        JOIN events e ON e.id = a.event_id
        LEFT JOIN participant_communication_preferences cp ON cp.person_id = p.id
        WHERE {" AND ".join(where)}
        ORDER BY p.last_name, p.first_name, a.id
        """,
        params,
    ).fetchall()
    seen: set[int] = set()
    unique = []
    for row in rows:
        person_id = int(row["person_id"])
        if person_id in seen:
            continue
        seen.add(person_id)
        unique.append(row)
    return unique


def queue_communication(db: sqlite3.Connection, *, event_id: int, actor: str, audience: str, channel: str, template_code: str, subject: str, content: str, rows: list[sqlite3.Row], process_now: bool = True) -> dict:
    sent = skipped = queued = errors = 0
    email_queue_ids: list[int] = []
    whatsapp_queue_ids: list[int] = []
    channels = ["email", "whatsapp"] if channel == "both" else [channel]
    for row in rows:
        for item_channel in channels:
            recipient = row["preferred_email"] if item_channel == "email" else row["preferred_phone"]
            consent = int(row["acepta_email"] or 0) if item_channel == "email" else int(row["acepta_whatsapp"] or 0)
            if not recipient or not consent:
                skipped += 1
                reason = "Sin destinatario" if not recipient else f"Sin consentimiento para {item_channel}"
                communication_log(
                    db,
                    event_id,
                    row["person_id"],
                    row["accreditation_id"],
                    item_channel,
                    template_code or "manual",
                    subject,
                    reason,
                    "omitido",
                )
                continue
            rendered_subject = render_communication_template(subject, row)
            rendered_content = render_communication_template(content, row)
            provider = communication_provider(item_channel)
            status = "pendiente"
            processed_at = None
            last_error = ""
            should_defer_real = item_channel in {"email", "whatsapp"} and provider != "demo"
            if process_now and not should_defer_real:
                processed_at = now_iso()
                if communication_provider_ready(item_channel):
                    status = "enviado"
                else:
                    status = "enviado" if provider == "demo" else "error"
                    last_error = "" if provider == "demo" else "Proveedor no configurado"
            cur = db.execute(
                """
                INSERT INTO communication_queue (
                    event_id, person_id, accreditation_id, channel, audience, template_code,
                    subject, content, recipient, status, attempts, max_attempts, provider,
                    provider_message_id, last_error, scheduled_at, processed_at,
                    delivered_at, bounced_at, created_by, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id, row["person_id"], row["accreditation_id"], item_channel, audience,
                    template_code, rendered_subject, rendered_content, recipient, status,
                    1 if process_now and not should_defer_real else 0,
                    max(1, int(os.environ.get("EMAIL_MAX_RETRIES", "3"))) if item_channel == "email" else max(1, int(os.environ.get("WHATSAPP_MAX_RETRIES", "3"))),
                    provider, "", last_error, None, processed_at, None, None, actor, now_iso(),
                ),
            )
            queue_id = int(cur.lastrowid)
            queued += 1
            if process_now and should_defer_real:
                (email_queue_ids if item_channel == "email" else whatsapp_queue_ids).append(queue_id)
            if status in {"enviado", "entregado", "leido"}:
                sent += 1
                communication_log(db, event_id, row["person_id"], row["accreditation_id"], item_channel, template_code or "manual", rendered_subject, rendered_content, "demo" if provider == "demo" else "enviado")
            elif status == "error":
                errors += 1
                communication_log(db, event_id, row["person_id"], row["accreditation_id"], item_channel, template_code or "manual", rendered_subject, last_error, "error")
    return {"queued": queued, "sent": sent, "skipped": skipped, "errors": errors, "_email_queue_ids": email_queue_ids, "_whatsapp_queue_ids": whatsapp_queue_ids}


def process_email_queue_item(queue_id: int) -> dict:
    with connect() as db:
        row = db.execute(
            "SELECT * FROM communication_queue WHERE id = ? AND channel = 'email'",
            (queue_id,),
        ).fetchone()
    if not row:
        return {"ok": False, "status": "error", "error": "Email en cola no encontrado"}
    item = dict(row)
    if item["status"] in {"entregado", "leido"}:
        return {"ok": True, "status": item["status"], "message_id": item.get("provider_message_id", "")}
    provider = create_email_provider()
    attempt = int(item.get("attempts") or 0) + 1
    max_attempts = max(1, int(item.get("max_attempts") or 3))
    if isinstance(provider, DemoEmailProvider):
        result_status = "enviado"
        result_error = ""
        message_id = ""
        ok = True
    elif not provider.ready:
        result_status = "error" if attempt >= max_attempts else "pendiente"
        result_error = "Proveedor de email no configurado"
        message_id = ""
        ok = False
    else:
        result = provider.send_template(
            to=item["recipient"],
            subject=item["subject"],
            html=item["content"],
            text=item["content"],
            reply_to=os.environ.get("EMAIL_REPLY_TO", ""),
            metadata={
                "event_id": str(item["event_id"]),
                "queue_id": str(item["id"]),
                "template": str(item["template_code"] or "manual"),
            },
        )
        ok = result.ok
        result_status = result.status if result.ok else ("error" if attempt >= max_attempts else "pendiente")
        result_error = result.error
        message_id = result.message_id
    processed_at = now_iso()
    with DB_LOCK, connect() as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute(
            """
            UPDATE communication_queue
            SET status = ?, attempts = ?, provider = ?, provider_message_id = ?,
                last_error = ?, processed_at = ?
            WHERE id = ?
            """,
            (result_status, attempt, provider.name, message_id, result_error, processed_at, queue_id),
        )
        communication_log(
            db,
            int(item["event_id"]),
            int(item["person_id"]),
            int(item["accreditation_id"]) if item.get("accreditation_id") else None,
            "email",
            str(item["template_code"] or "manual"),
            str(item["subject"]),
            str(item["content"] if ok else result_error),
            "demo" if isinstance(provider, DemoEmailProvider) else result_status,
        )
        audit(
            db,
            str(item["created_by"] or "system"),
            "communications.email_sent" if ok else "communications.email_retry",
            "communication_queue",
            queue_id,
            {
                "event_id": int(item["event_id"]),
                "provider": provider.name,
                "message_id": message_id,
                "status": result_status,
                "attempt": attempt,
                "max_attempts": max_attempts,
                "error": result_error,
            },
        )
        db.execute("COMMIT")
    return {"ok": ok, "status": result_status, "message_id": message_id, "error": result_error}


def process_email_queue_items(queue_ids: list[int]) -> dict:
    summary = {"sent": 0, "errors": 0, "pending": 0}
    for queue_id in queue_ids:
        if WORKER and WORKER.thread and WORKER.thread.is_alive():
            with connect() as db:
                row = db.execute("SELECT event_id, created_by FROM communication_queue WHERE id = ?", (queue_id,)).fetchone()
            job_queue_service().enqueue(
                "email.send",
                {"queue_id": queue_id},
                priority="high",
                actor=str(row["created_by"] if row else "system"),
                event_id=int(row["event_id"]) if row else None,
            )
            result = {"ok": False, "status": "pendiente"}
        else:
            result = process_email_queue_item(queue_id)
        if result["ok"]:
            summary["sent"] += 1
        elif result["status"] == "pendiente":
            summary["pending"] += 1
        else:
            summary["errors"] += 1
    return summary


def process_whatsapp_queue_item(queue_id: int) -> dict:
    with connect() as db:
        row = db.execute("SELECT * FROM communication_queue WHERE id = ? AND channel = 'whatsapp'", (queue_id,)).fetchone()
    if not row:
        return {"ok": False, "status": "error", "error": "WhatsApp en cola no encontrado"}
    item = dict(row)
    provider = create_whatsapp_provider()
    attempt = int(item.get("attempts") or 0) + 1
    max_attempts = max(1, int(item.get("max_attempts") or 3))
    result = provider.send_message(to=item["recipient"], message=item["content"])
    status = result.status if result.ok else ("error" if attempt >= max_attempts else "pendiente")
    with DB_LOCK, connect() as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute(
            "UPDATE communication_queue SET status = ?, attempts = ?, provider = ?, provider_message_id = ?, last_error = ?, processed_at = ? WHERE id = ?",
            (status, attempt, provider.name, result.message_id, result.error, now_iso(), queue_id),
        )
        communication_log(db, int(item["event_id"]), int(item["person_id"]), item.get("accreditation_id"), "whatsapp", item["template_code"] or "manual", item["subject"], item["content"] if result.ok else result.error, "demo" if isinstance(provider, DemoWhatsAppProvider) else status)
        audit(db, item["created_by"] or "system", "communications.whatsapp_sent" if result.ok else "communications.whatsapp_retry", "communication_queue", queue_id, {"event_id": item["event_id"], "provider": provider.name, "message_id": result.message_id, "status": status, "attempt": attempt, "error": result.error})
        db.execute("COMMIT")
    return {"ok": result.ok, "status": status, "message_id": result.message_id, "error": result.error}


def verify_email_webhook(handler: SimpleHTTPRequestHandler) -> bool:
    secret = os.environ.get("EMAIL_WEBHOOK_SECRET", "").strip()
    if not secret:
        return APP_ENV != "production"
    svix_id = handler.headers.get("svix-id", "")
    svix_timestamp = handler.headers.get("svix-timestamp", "")
    signatures = handler.headers.get("svix-signature", "")
    if not svix_id or not svix_timestamp or not signatures:
        return False
    try:
        if abs(time.time() - float(svix_timestamp)) > 300:
            return False
        key = secret.removeprefix("whsec_")
        decoded_key = base64.b64decode(key)
        raw = getattr(handler, "_raw_json_body", b"")
        signed = svix_id.encode() + b"." + svix_timestamp.encode() + b"." + raw
        expected = base64.b64encode(hmac.new(decoded_key, signed, hashlib.sha256).digest()).decode()
        return any(
            hmac.compare_digest(expected, part.split(",", 1)[1])
            for part in signatures.split()
            if part.startswith("v1,")
        )
    except (ValueError, TypeError):
        return False


def apply_email_webhook(db: sqlite3.Connection, payload: dict) -> dict:
    event_type = str(payload.get("type") or payload.get("event") or "").strip().lower()
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    message_id = str(data.get("email_id") or data.get("id") or payload.get("email_id") or "").strip()
    if not event_type or not message_id:
        raise ValueError("Webhook de email incompleto")
    row = db.execute(
        "SELECT * FROM communication_queue WHERE provider_message_id = ? ORDER BY id DESC LIMIT 1",
        (message_id,),
    ).fetchone()
    status_map = {
        "email.sent": "enviado",
        "sent": "enviado",
        "email.delivered": "entregado",
        "delivered": "entregado",
        "email.bounced": "rebotado",
        "bounced": "rebotado",
        "email.complained": "rechazado",
        "complained": "rechazado",
        "email.failed": "error",
        "failed": "error",
        "email.delivery_delayed": "pendiente",
    }
    status = status_map.get(event_type, event_type.removeprefix("email."))
    event_id = int(row["event_id"]) if row else int(payload.get("event_id") or 0)
    queue_id = int(row["id"]) if row else None
    db.execute(
        """
        INSERT INTO email_delivery_events
            (event_id, queue_id, provider, message_id, event_type, payload, created_at)
        VALUES (?, ?, 'resend', ?, ?, ?, ?)
        """,
        (event_id, queue_id, message_id, event_type, json.dumps(payload, ensure_ascii=False), now_iso()),
    )
    if row:
        delivered_at = now_iso() if status == "entregado" else row["delivered_at"]
        bounced_at = now_iso() if status in {"rebotado", "rechazado", "error"} else row["bounced_at"]
        db.execute(
            """
            UPDATE communication_queue
            SET status = ?, delivered_at = ?, bounced_at = ?, processed_at = ?
            WHERE id = ?
            """,
            (status, delivered_at, bounced_at, now_iso(), queue_id),
        )
        communication_log(
            db,
            event_id,
            int(row["person_id"]),
            int(row["accreditation_id"]) if row["accreditation_id"] else None,
            "email",
            str(row["template_code"] or "webhook"),
            str(row["subject"]),
            f"Estado proveedor: {status}",
            status,
        )
        audit(db, "webhook", "communications.email_status", "communication_queue", queue_id, {
            "event_id": event_id,
            "provider": "resend",
            "message_id": message_id,
            "event_type": event_type,
            "status": status,
        })
    return {"ok": True, "queue_id": queue_id, "message_id": message_id, "status": status}


def apply_whatsapp_webhook(db, payload: dict) -> dict:
    changes = []
    incoming = []
    for entry in payload.get("entry") or []:
        for change in entry.get("changes") or []:
            value = change.get("value") or {}
            for status_item in value.get("statuses") or []:
                message_id = str(status_item.get("id") or "")
                status = {"sent": "enviado", "delivered": "entregado", "read": "leido", "failed": "error"}.get(str(status_item.get("status") or "").lower(), "pendiente")
                row = db.execute("SELECT * FROM communication_queue WHERE provider_message_id = ? ORDER BY id DESC LIMIT 1", (message_id,)).fetchone()
                if row:
                    db.execute("UPDATE communication_queue SET status = ?, last_error = ?, processed_at = ? WHERE id = ?", (status, json.dumps(status_item.get("errors") or [], ensure_ascii=False) if status == "error" else "", now_iso(), row["id"]))
                    communication_log(db, row["event_id"], row["person_id"], row["accreditation_id"], "whatsapp", row["template_code"] or "webhook", row["subject"], row["content"], status)
                    audit(db, "webhook", "communications.whatsapp_status", "communication_queue", row["id"], {"message_id": message_id, "status": status})
                changes.append({"message_id": message_id, "status": status})
            for message in value.get("messages") or []:
                phone = str(message.get("from") or "")
                text = str((message.get("text") or {}).get("body") or "")
                event_id = int((payload.get("metadata") or {}).get("event_id") or 0)
                db.execute(
                    "INSERT INTO communication_assistant_history (event_id, phone, inbound, outbound, intent, status, created_at) VALUES (?, ?, ?, '', 'incoming', 'received', ?)",
                    (event_id, phone, text, now_iso()),
                )
                audit(db, "webhook", "communications.whatsapp_received", "event", event_id or None, {"phone": phone, "message_id": message.get("id", "")})
                incoming.append({"phone": phone, "message_id": message.get("id", "")})
    return {"ok": True, "statuses": changes, "messages": incoming}


def find_participant_by_phone(db: sqlite3.Connection, event_id: int, phone: str) -> sqlite3.Row | None:
    digits = "".join(ch for ch in str(phone or "") if ch.isdigit())
    if not digits:
        return None
    return db.execute(
        """
        SELECT a.id AS accreditation_id, a.token, a.type, p.id AS person_id,
               p.first_name, p.last_name, p.phone, p.email, p.company,
               e.name AS event_name, e.starts_at
        FROM accreditations a
        JOIN people p ON p.id = a.person_id
        JOIN events e ON e.id = a.event_id
        WHERE a.event_id = ? AND REPLACE(REPLACE(REPLACE(REPLACE(p.phone, '+', ''), ' ', ''), '-', ''), '(', '') LIKE ?
          AND a.status <> 'cancelled'
        ORDER BY a.id DESC
        LIMIT 1
        """,
        (event_id, f"%{digits[-8:]}"),
    ).fetchone()


def assistant_reply(db: sqlite3.Connection, event_id: int, phone: str, message: str) -> dict:
    participant = find_participant_by_phone(db, event_id, phone)
    text = str(message or "").strip().lower()
    if not participant:
        return {"status": "unidentified", "intent": "unknown", "reply": "No encontre una inscripcion asociada a este numero. Escribi Operador para ayuda humana."}
    portal = public_link(f"/p.html?token={participant['token']}")
    intent = "help"
    if text in {"hola", "ayuda", "evento", "menu", "menú"}:
        reply = "BITORA operativo:\n1 Mi QR\n2 Mi Agenda\n3 Mis Actividades\n4 Certificados\n5 Ayuda"
    elif text in {"1", "qr", "mi qr"}:
        intent = "qr"
        reply = f"Hola {participant['first_name']}. Tu QR y portal: {portal}"
    elif text in {"2", "agenda", "mi agenda"}:
        intent = "agenda"
        rows = db.execute(
            """
            SELECT a.title, a.starts_at, s.name AS room
            FROM reservations r
            JOIN activities a ON a.id = r.activity_id
            JOIN spaces s ON s.id = a.space_id
            WHERE r.accreditation_id = ? AND r.status = 'confirmed'
            ORDER BY a.starts_at
            LIMIT 6
            """,
            (participant["accreditation_id"],),
        ).fetchall()
        reply = "\n".join([f"{row['title']} - {row['room']} - {row['starts_at']}" for row in rows]) or f"No tenes agenda reservada. Portal: {portal}"
    elif text in {"3", "mis inscripciones", "actividades", "mis actividades"}:
        intent = "registrations"
        reply = f"Tus inscripciones y estados estan en tu portal: {portal}"
    elif "proxima" in text or "próxima" in text:
        intent = "next_activity"
        row = db.execute(
            """
            SELECT a.title, a.starts_at, s.name AS room
            FROM reservations r
            JOIN activities a ON a.id = r.activity_id
            JOIN spaces s ON s.id = a.space_id
            WHERE r.accreditation_id = ? AND r.status = 'confirmed' AND a.starts_at >= ?
            ORDER BY a.starts_at
            LIMIT 1
            """,
            (participant["accreditation_id"], now_iso()[:16]),
        ).fetchone()
        reply = f"Proxima actividad: {row['title']} - {row['room']} - {row['starts_at']}" if row else "No tenes una proxima actividad registrada."
    elif text in {"4", "certificados", "certificado"}:
        intent = "certificates"
        reply = f"Tus certificados disponibles se consultan desde el portal: {portal}"
    elif text in {"portal", "acceso"}:
        intent = "portal"
        reply = f"Tu portal participante: {portal}"
    elif "operador" in text or "soporte" in text or "humana" in text:
        intent = "handoff"
        db.execute(
            """
            INSERT INTO communication_tickets (event_id, person_id, accreditation_id, channel, reason, status, created_at, updated_at)
            VALUES (?, ?, ?, 'whatsapp', ?, 'open', ?, ?)
            """,
            (event_id, participant["person_id"], participant["accreditation_id"], message, now_iso(), now_iso()),
        )
        reply = "Derive tu consulta a un operador. Te van a responder por este canal."
    else:
        reply = "Puedo ayudarte con QR, Agenda, Proxima actividad, Mis inscripciones, Certificados o Portal. Escribi Operador para ayuda humana."
    return {"status": "resolved", "intent": intent, "reply": reply, "participant": dict(participant)}


def event_structure_payload(db: sqlite3.Connection, event_id: int) -> dict | None:
    event = row_to_dict(db.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone())
    if not event:
        return None
    allowed_event_keys = [
        "name", "description", "venue", "starts_at", "ends_at", "status", "capacity",
        "activity_selection_mode", "permitir_reserva_actividades_desde_landing",
        "permitir_reserva_actividades_desde_portal", "reserva_requiere_confirmacion",
        "reserva_cooldown_segundos", "reserva_requiere_verificacion_simple",
        "generar_certificados", "controlar_asistencia", "attendance_mode",
        "porcentaje_minimo_asistencia", "captation_mode", "primary_action_label",
        "secondary_action_label", "whatsapp_number", "activity_access_open_minutes_before",
        "activities_enabled", "capacity_control_enabled", "waitlist_enabled",
    ]
    return {
        "version": "4.8",
        "exported_at": now_iso(),
        "event": {key: event.get(key) for key in allowed_event_keys if key in event},
        "types": [dict(row) for row in db.execute("SELECT name, capacity, access_enabled FROM accreditation_types WHERE event_id = ? ORDER BY id", (event_id,)).fetchall()],
        "spaces": [dict(row) for row in db.execute("SELECT name, capacity, responsible, transition_minutes, status FROM spaces WHERE event_id = ? ORDER BY id", (event_id,)).fetchall()],
        "activities": [
            dict(row)
            for row in db.execute(
                """
                SELECT a.title, a.description, a.speaker, a.activity_type, a.starts_at, a.ends_at,
                       a.capacity, a.reservation_mode, a.access_open_minutes_before,
                       a.requiere_asistencia, a.porcentaje_minimo_asistencia, a.habilita_certificado,
                       a.attendance_mode, a.status, s.name AS space_name
                FROM activities a
                JOIN spaces s ON s.id = a.space_id
                WHERE a.event_id = ?
                ORDER BY a.starts_at, a.id
                """,
                (event_id,),
            ).fetchall()
        ],
        "capacity_bags": [
            dict(row)
            for row in db.execute(
                """
                SELECT b.name, b.code, b.assigned_capacity, b.priority, b.public_visible,
                       b.public_registration, b.reception_enabled, b.release_enabled, b.status,
                       a.title AS activity_title, s.name AS space_name
                FROM capacity_bags b
                JOIN activities a ON a.id = b.activity_id
                JOIN spaces s ON s.id = a.space_id
                WHERE b.event_id = ?
                ORDER BY a.starts_at, b.priority, b.id
                """,
                (event_id,),
            ).fetchall()
        ],
        "communication_templates": [
            dict(row)
            for row in db.execute(
                "SELECT code, name, tipo, asunto, contenido, active FROM communication_templates WHERE event_id IN (0, ?) ORDER BY event_id, id",
                (event_id,),
            ).fetchall()
        ],
    }


def insert_event_from_config(db: sqlite3.Connection, data: dict, actor: str, status: str = "draft") -> int:
    cur = db.execute(
        """
        INSERT INTO events (
            name, description, venue, starts_at, ends_at, status, capacity,
            activity_selection_mode, generar_certificados, controlar_asistencia,
            attendance_mode, porcentaje_minimo_asistencia, captation_mode,
            primary_action_label, secondary_action_label, whatsapp_number,
            activity_access_open_minutes_before, activities_enabled,
            capacity_control_enabled, waitlist_enabled, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(data.get("name") or "Evento").strip(),
            str(data.get("description") or "").strip(),
            str(data.get("venue") or "").strip(),
            str(data.get("starts_at") or "").strip(),
            str(data.get("ends_at") or "").strip(),
            status,
            int(data.get("capacity") or 0),
            str(data.get("activity_selection_mode") or "optional_later").strip() or "optional_later",
            1 if truthy(data.get("generar_certificados", True)) else 0,
            1 if truthy(data.get("controlar_asistencia", True)) else 0,
            str(data.get("attendance_mode") or "entry_only").strip() or "entry_only",
            int(data.get("porcentaje_minimo_asistencia") or 80),
            str(data.get("captation_mode") or "MIXTO").strip() or "MIXTO",
            str(data.get("primary_action_label") or "").strip(),
            str(data.get("secondary_action_label") or "").strip(),
            str(data.get("whatsapp_number") or "").strip(),
            max(0, int(data.get("activity_access_open_minutes_before") or 10)),
            1 if truthy(data.get("activities_enabled", True)) else 0,
            1 if truthy(data.get("capacity_control_enabled", True)) else 0,
            1 if truthy(data.get("waitlist_enabled", False)) else 0,
            now_iso(),
        ),
    )
    event_id = int(cur.lastrowid)
    audit(db, actor, "event.created", "event", event_id, {"source": "config"})
    return event_id


def import_event_structure(db: sqlite3.Connection, payload: dict, actor: str, name: str | None = None) -> dict:
    event_data = dict(payload.get("event") or {})
    if name:
        event_data["name"] = name
    event_data["name"] = event_data.get("name") or "Evento importado"
    event_id = insert_event_from_config(db, event_data, actor, status=str(event_data.get("status") or "draft"))
    created_at = now_iso()
    db.execute("DELETE FROM accreditation_types WHERE event_id = ?", (event_id,))
    for row in payload.get("types") or []:
        db.execute(
            "INSERT OR IGNORE INTO accreditation_types (event_id, name, capacity, access_enabled, created_at) VALUES (?, ?, ?, ?, ?)",
            (event_id, row.get("name") or "General", int(row.get("capacity") or 0), 1 if truthy(row.get("access_enabled", True)) else 0, created_at),
        )
    if not payload.get("types"):
        ensure_default_types(db, event_id)

    space_map: dict[str, int] = {}
    for row in payload.get("spaces") or []:
        cur = db.execute(
            """
            INSERT INTO spaces (event_id, name, capacity, responsible, transition_minutes, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (event_id, row.get("name") or "Sala", int(row.get("capacity") or 0), row.get("responsible") or "", int(row.get("transition_minutes") or 15), row.get("status") or "active", created_at),
        )
        space_map[str(row.get("name") or "Sala")] = int(cur.lastrowid)
    if not space_map:
        ensure_default_spaces(db, event_id)
        for row in db.execute("SELECT id, name FROM spaces WHERE event_id = ?", (event_id,)).fetchall():
            space_map[row["name"]] = int(row["id"])

    activity_map: dict[tuple[str, str], int] = {}
    for row in payload.get("activities") or []:
        space_name = str(row.get("space_name") or row.get("Sala") or "Auditorio principal")
        if space_name not in space_map:
            cur = db.execute(
                "INSERT INTO spaces (event_id, name, capacity, responsible, transition_minutes, status, created_at) VALUES (?, ?, 0, '', 15, 'active', ?)",
                (event_id, space_name, created_at),
            )
            space_map[space_name] = int(cur.lastrowid)
        cur = db.execute(
            """
            INSERT INTO activities (
                event_id, space_id, title, description, speaker, activity_type,
                starts_at, ends_at, capacity, reservation_mode, requiere_asistencia,
                porcentaje_minimo_asistencia, habilita_certificado, attendance_mode,
                access_open_minutes_before, status, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                space_map[space_name],
                row.get("title") or row.get("Actividad") or "Actividad",
                row.get("description") or row.get("Descripcion") or "",
                row.get("speaker") or row.get("Disertante") or "",
                row.get("activity_type") or row.get("Tipo actividad") or "Charla",
                row.get("starts_at") or "",
                row.get("ends_at") or "",
                int(row.get("capacity") or row.get("Capacidad") or 0),
                row.get("reservation_mode") or "free",
                1 if truthy(row.get("requiere_asistencia", True)) else 0,
                int(row.get("porcentaje_minimo_asistencia") or 80),
                1 if truthy(row.get("habilita_certificado", True)) else 0,
                row.get("attendance_mode") or "",
                row.get("access_open_minutes_before"),
                row.get("status") or "published",
                created_at,
            ),
        )
        activity_map[(space_name, str(row.get("title") or row.get("Actividad") or "Actividad"))] = int(cur.lastrowid)

    for row in payload.get("capacity_bags") or []:
        activity_id = activity_map.get((str(row.get("space_name") or ""), str(row.get("activity_title") or "")))
        if not activity_id:
            continue
        db.execute(
            """
            INSERT OR IGNORE INTO capacity_bags (
                event_id, activity_id, name, code, assigned_capacity, priority,
                public_visible, public_registration, reception_enabled, release_enabled,
                status, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id, activity_id, row.get("name") or "Online", row.get("code") or "online",
                int(row.get("assigned_capacity") or 0), int(row.get("priority") or 100),
                1 if truthy(row.get("public_visible", False)) else 0,
                1 if truthy(row.get("public_registration", False)) else 0,
                1 if truthy(row.get("reception_enabled", True)) else 0,
                1 if truthy(row.get("release_enabled", True)) else 0,
                row.get("status") or "active", created_at,
            ),
        )
    ensure_capacity_bags(db, event_id=event_id)
    audit(db, actor, "event.structure_imported", "event", event_id, {"activities": len(payload.get("activities") or []), "spaces": len(payload.get("spaces") or [])})
    return {"ok": True, "event_id": event_id, "activities": len(payload.get("activities") or []), "spaces": len(payload.get("spaces") or [])}


def normalize_import_time(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if len(raw) == 8 and raw.isdigit():
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}T00:00"
    if len(raw) >= 15 and raw[8] == "T":
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}T{raw[9:11]}:{raw[11:13]}"
    if "T" in raw:
        return raw[:16].replace("Z", "")
    return raw


def parse_ics_agenda(text: str) -> list[dict]:
    rows: list[dict] = []
    event: dict[str, str] | None = None
    for line in str(text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if not line:
            continue
        if line.startswith("BEGIN:VEVENT"):
            event = {}
            continue
        if line.startswith("END:VEVENT"):
            if event:
                start = normalize_import_time(event.get("DTSTART", ""))
                end = normalize_import_time(event.get("DTEND", ""))
                rows.append(
                    {
                        "Sala": event.get("LOCATION", "").replace("\\,", ","),
                        "Actividad": event.get("SUMMARY", "").replace("\\,", ","),
                        "Fecha": start[:10],
                        "Hora inicio": start[11:16],
                        "Hora fin": end[11:16],
                        "Descripcion": event.get("DESCRIPTION", "").replace("\\n", "\n").replace("\\,", ","),
                    }
                )
            event = None
            continue
        if event is None or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.split(";", 1)[0].upper()
        if key in {"SUMMARY", "DESCRIPTION", "LOCATION", "DTSTART", "DTEND"}:
            event[key] = value.strip()
    return rows


def agenda_rows_from_payload(data: dict) -> list[dict]:
    rows = data.get("rows") or []
    if rows:
        return rows if isinstance(rows, list) else []
    if data.get("ics"):
        return parse_ics_agenda(str(data.get("ics") or ""))
    if data.get("csv"):
        return list(csv.DictReader(str(data.get("csv") or "").splitlines()))
    return []


def preview_agenda_rows(db: sqlite3.Connection, event_id: int, rows: list[dict]) -> dict:
    summary = {"found": len(rows), "valid": 0, "conflicts": 0, "errors": []}
    for index, row in enumerate(rows, start=1):
        try:
            room = str(row.get("Sala") or row.get("sala") or row.get("space") or "").strip()
            title = str(row.get("Actividad") or row.get("actividad") or row.get("title") or "").strip()
            date = str(row.get("Fecha") or row.get("fecha") or row.get("date") or "").strip()
            start_time = str(row.get("Hora inicio") or row.get("hora_inicio") or row.get("start") or "").strip()
            end_time = str(row.get("Hora fin") or row.get("hora_fin") or row.get("end") or "").strip()
            if not room or not title or not date or not start_time or not end_time:
                raise ValueError("faltan sala, actividad, fecha u hora")
            starts_at = f"{date}T{start_time}"
            ends_at = f"{date}T{end_time}"
            space = db.execute("SELECT * FROM spaces WHERE event_id = ? AND name = ?", (event_id, room)).fetchone()
            space_id = int(space["id"]) if space else 0
            existing = db.execute(
                "SELECT * FROM activities WHERE event_id = ? AND title = ? AND starts_at = ?",
                (event_id, title, starts_at),
            ).fetchone()
            conflict = None
            if space_id:
                conflict = validate_activity_schedule(db, event_id, space_id, starts_at, ends_at, exclude_activity_id=int(existing["id"]) if existing else None)
            if conflict:
                summary["conflicts"] += 1
                summary["errors"].append({"row": index, "error": conflict})
            else:
                summary["valid"] += 1
        except Exception as exc:
            summary["errors"].append({"row": index, "error": str(exc)})
    return summary


def ics_escape(value: object) -> str:
    return str(value or "").replace("\\", "\\\\").replace("\n", "\\n").replace(",", "\\,").replace(";", "\\;")


def ics_datetime(value: object) -> str:
    text = str(value or "")
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
        return dt.strftime("%Y%m%dT%H%M%S")
    except ValueError:
        return text.replace("-", "").replace(":", "")


def portal_payload(db: sqlite3.Connection, token: str) -> dict | None:
    row = db.execute(
        """
        SELECT a.*, p.first_name, p.last_name, p.email, p.phone, p.dni, p.company, p.position,
               COALESCE(a.source, p.source, '') AS participant_source,
               COALESCE(a.device_type, p.device_type, '') AS participant_device_type,
               e.name AS event_name, e.description AS event_description, e.venue, e.starts_at, e.ends_at,
               e.activity_selection_mode, e.permitir_reserva_actividades_desde_portal,
               e.reserva_requiere_confirmacion, e.reserva_cooldown_segundos,
               e.reserva_requiere_verificacion_simple,
               e.activities_enabled, e.capacity_control_enabled, e.waitlist_enabled
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
    activities_enabled = int(data.get("activities_enabled") or 0) == 1
    reservations = []
    if activities_enabled:
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
    if activities_enabled:
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
    attendances = []
    if activities_enabled:
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
        "activities_enabled": int(data.get("activities_enabled") or 0),
        "capacity_control_enabled": int(data.get("capacity_control_enabled") or 0),
        "waitlist_enabled": int(data.get("waitlist_enabled") or 0),
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
    if row:
        return dict(row)
    if not manual or activity_id:
        return None
    fallback = db.execute(
        """
        SELECT e.id AS event_id, e.name AS event_name, e.venue, e.starts_at, e.ends_at,
               ac.id AS accreditation_id, ac.token, ac.type, ac.checked_in_at,
               p.first_name, p.last_name, p.email, p.company, p.dni
        FROM accreditations ac
        JOIN events e ON e.id = ac.event_id
        JOIN people p ON p.id = ac.person_id
        WHERE ac.token = ? AND ac.status = 'active'
        LIMIT 1
        """,
        [token.strip().upper()],
    ).fetchone()
    if not fallback:
        return None
    data = dict(fallback)
    return {
        **data,
        "certificate_id": f"M-{data['accreditation_id']}",
        "activity_id": None,
        "activity_title": f"Participacion en {data['event_name']}",
        "space_name": data.get("venue") or "",
        "porcentaje": 100 if data.get("checked_in_at") else 0,
        "elegible": 1,
        "estado": "Manual",
        "fecha_calculo": now_iso(),
        "certificate_generated_at": now_iso(),
    }


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


def technical_log(level: str, module: str, message: str, detail: str = "", request_path: str = "") -> None:
    safe_detail = str(detail or "")
    safe_detail = re.sub(
        r"(?i)(api[_-]?key|password|secret|token|postgres(?:ql)?://)[=: ]+[^\s,;]+",
        r"\1=[REDACTED]",
        safe_detail,
    )
    for secret_name in ("EMAIL_API_KEY", "QR_POSTGRES_DSN", "EMAIL_WEBHOOK_SECRET"):
        secret = os.environ.get(secret_name, "")
        if secret:
            safe_detail = safe_detail.replace(secret, "[REDACTED]")
    try:
        with connect() as db:
            db.execute(
                """
                INSERT INTO technical_logs (level, module, message, detail, request_path, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(level or "info").lower()[:20],
                    str(module or "system")[:80],
                    str(message or "")[:500],
                    safe_detail[:2000],
                    str(request_path or "")[:300],
                    now_iso(),
                ),
            )
    except Exception:
        pass


def job_queue_service() -> JobQueueService:
    return JobQueueService(connect, audit, technical_log)


def handle_email_job(payload: dict) -> dict:
    return process_email_queue_item(int(payload["queue_id"]))


def handle_whatsapp_job(payload: dict) -> dict:
    return process_whatsapp_queue_item(int(payload["queue_id"]))


def handle_backup_job(payload: dict) -> dict:
    started = time.perf_counter()
    path = create_db_backup()
    check = verify_backup_file(path)
    if not check["ok"]:
        raise RuntimeError(f"Backup invalido: {check['detail']}")
    return {"file": path.name, "size": path.stat().st_size, "duration_ms": round((time.perf_counter() - started) * 1000, 2)}


def handle_certificate_job(payload: dict) -> dict:
    with DB_LOCK, connect() as db:
        generated = release_available_certificates(db, int(payload.get("event_id") or 0) or None)
    return {"generated": generated}


def handle_export_job(payload: dict) -> dict:
    event_id = int(payload.get("event_id") or 0)
    export_dir = ROOT / "output"
    export_dir.mkdir(exist_ok=True)
    path = export_dir / f"bitora-export-{event_id}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    with connect() as db:
        rows = [dict(row) for row in db.execute("SELECT * FROM accreditations WHERE event_id = ? ORDER BY id", (event_id,)).fetchall()]
    path.write_text(json.dumps({"event_id": event_id, "accreditations": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"file": path.name, "rows": len(rows)}


def start_job_worker() -> JobWorker:
    global WORKER
    queue = job_queue_service()
    WORKER = JobWorker(
        queue,
        {
            "email.send": handle_email_job,
            "whatsapp.send": handle_whatsapp_job,
            "backup.create": handle_backup_job,
            "certificate.generate": handle_certificate_job,
            "export.generate": handle_export_job,
        },
    )
    WORKER.start()
    technical_log("info", "jobs", "Worker iniciado", "worker-1")
    return WORKER


def waiting_room_payload(db, event_id: int, visitor_id: str, *, admit: bool = True) -> dict:
    event = db.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    if not event:
        return {"error": "Evento inexistente"}
    enabled = bool(int(event["waiting_room_enabled"] or 0))
    if not enabled:
        return {"enabled": False, "status": "open", "access_token": ""}
    now = datetime.now(timezone.utc)
    open_at = parse_dt(event["waiting_room_open_at"]) if event["waiting_room_open_at"] else None
    if open_at and now < open_at.astimezone(timezone.utc):
        return {
            "enabled": True,
            "status": "not_open",
            "open_at": event["waiting_room_open_at"],
            "message": event["waiting_message"],
        }
    row = db.execute(
        "SELECT * FROM waiting_room_visitors WHERE event_id = ? AND visitor_id = ?",
        (event_id, visitor_id),
    ).fetchone()
    if not row:
        position = int(
            db.execute(
                "SELECT COUNT(*) AS c FROM waiting_room_visitors WHERE event_id = ? AND status = 'waiting'",
                (event_id,),
            ).fetchone()["c"]
            or 0
        ) + 1
        db.execute(
            """
            INSERT INTO waiting_room_visitors (
                event_id, visitor_id, status, position_number, joined_at, last_seen_at
            ) VALUES (?, ?, 'waiting', ?, ?, ?)
            """,
            (event_id, visitor_id, position, now_iso(), now_iso()),
        )
        audit(db, "public", "waiting_room.joined", "event", event_id, {"visitor_id": visitor_id, "position": position})
        row = db.execute(
            "SELECT * FROM waiting_room_visitors WHERE event_id = ? AND visitor_id = ?",
            (event_id, visitor_id),
        ).fetchone()
    item = dict(row)
    if item["status"] == "admitted" and item.get("expires_at"):
        expires = parse_dt(item["expires_at"])
        if expires and now >= expires.astimezone(timezone.utc):
            db.execute("UPDATE waiting_room_visitors SET status = 'expired', last_seen_at = ? WHERE id = ?", (now_iso(), item["id"]))
            audit(db, "system", "waiting_room.expired", "waiting_room", item["id"], {"event_id": event_id})
            item["status"] = "expired"
    if admit and item["status"] in {"waiting", "expired"}:
        minute_ago = (now - timedelta(minutes=1)).isoformat(timespec="seconds")
        admitted_recent = int(
            db.execute(
                "SELECT COUNT(*) AS c FROM waiting_room_visitors WHERE event_id = ? AND admitted_at >= ?",
                (event_id, minute_ago),
            ).fetchone()["c"]
            or 0
        )
        rate = max(1, int(event["users_allowed_per_minute"] or 60))
        first_waiting = db.execute(
            "SELECT id FROM waiting_room_visitors WHERE event_id = ? AND status IN ('waiting', 'expired') ORDER BY joined_at, id LIMIT 1",
            (event_id,),
        ).fetchone()
        if admitted_recent < rate and first_waiting and int(first_waiting["id"]) == int(item["id"]):
            token = secrets.token_urlsafe(24)
            expires_at = (now + timedelta(minutes=max(1, int(event["turn_duration_minutes"] or 10)))).isoformat(timespec="seconds")
            db.execute(
                """
                UPDATE waiting_room_visitors
                SET status = 'admitted', access_token = ?, admitted_at = ?, expires_at = ?, last_seen_at = ?
                WHERE id = ?
                """,
                (token, now_iso(), expires_at, now_iso(), item["id"]),
            )
            audit(db, "system", "waiting_room.admitted", "waiting_room", item["id"], {"event_id": event_id})
            item.update(status="admitted", access_token=token, admitted_at=now_iso(), expires_at=expires_at)
    waiting_ahead = int(
        db.execute(
            "SELECT COUNT(*) AS c FROM waiting_room_visitors WHERE event_id = ? AND status = 'waiting' AND position_number < ?",
            (event_id, item["position_number"]),
        ).fetchone()["c"]
        or 0
    )
    rate = max(1, int(event["users_allowed_per_minute"] or 60))
    return {
        "enabled": True,
        "status": item["status"],
        "position": waiting_ahead + 1 if item["status"] == "waiting" else 0,
        "estimated_minutes": max(1, (waiting_ahead + rate - 1) // rate) if item["status"] == "waiting" else 0,
        "show_position": bool(int(event["show_waiting_position"] or 0)),
        "show_estimated_time": bool(int(event["show_estimated_time"] or 0)),
        "message": event["waiting_message"],
        "access_token": item.get("access_token") or "",
        "expires_at": item.get("expires_at"),
    }


def simulator_step() -> None:
    with connect() as db:
        states = db.execute("SELECT * FROM simulator_state WHERE status = 'running'").fetchall()
        for state in states:
            event_id = int(state["event_id"])
            event = db.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
            if not event or ("demo" not in str(event["name"]).lower() and "demo" not in str(event["description"]).lower()):
                db.execute("UPDATE simulator_state SET status = 'stopped', updated_at = ? WHERE event_id = ?", (now_iso(), event_id))
                continue
            rows = db.execute(
                "SELECT id, token, checked_in_at FROM accreditations WHERE event_id = ? AND status <> 'cancelled' ORDER BY RANDOM() LIMIT 20",
                (event_id,),
            ).fetchall()
            if not rows:
                continue
            speed = max(0.25, float(state["speed"] or 1))
            grants = max(1, int(int(state["accesses_per_minute"] or 1) * speed / 12))
            rejects = max(0, int(int(state["rejections_per_minute"] or 0) * speed / 12))
            terminals = max(1, int(state["active_terminals"] or 1))
            for row in random.sample(list(rows), min(grants, len(rows))):
                operator_number = random.randint(1, terminals)
                db.execute(
                    """
                    INSERT INTO access_logs (
                        accreditation_id, event_id, token, operator, checkpoint, access_point,
                        access_context, result, reason, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, 'event_entry', 'granted', 'simulacion', ?)
                    """,
                    (row["id"], event_id, row["token"], f"Sim Operador {operator_number}", f"Terminal {operator_number}", f"Terminal {operator_number}", now_iso()),
                )
                if not row["checked_in_at"]:
                    db.execute("UPDATE accreditations SET checked_in_at = ? WHERE id = ?", (now_iso(), row["id"]))
            reasons = ["QR repetido", "QR invalido", "Acceso anticipado", "Sin inscripcion", "Cancelado", "Sala incorrecta"]
            for index in range(rejects):
                row = random.choice(list(rows))
                operator_number = random.randint(1, terminals)
                db.execute(
                    """
                    INSERT INTO access_logs (
                        accreditation_id, event_id, token, operator, checkpoint, access_point,
                        access_context, result, reason, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, 'event_entry', 'rejected', ?, ?)
                    """,
                    (row["id"], event_id, row["token"], f"Sim Operador {operator_number}", f"Terminal {operator_number}", f"Terminal {operator_number}", random.choice(reasons), now_iso()),
                )


def simulator_loop() -> None:
    while not SIMULATOR_STOP.wait(5):
        try:
            simulator_step()
        except Exception as exc:
            technical_log("error", "simulator", "Error en simulador vivo", str(exc))


def start_simulator_loop() -> threading.Thread:
    global SIMULATOR_THREAD
    if SIMULATOR_THREAD and SIMULATOR_THREAD.is_alive():
        return SIMULATOR_THREAD
    SIMULATOR_THREAD = threading.Thread(target=simulator_loop, name="live-simulator", daemon=True)
    SIMULATOR_THREAD.start()
    return SIMULATOR_THREAD


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


def executive_report_data(db: sqlite3.Connection, event_id: int) -> dict | None:
    event = row_to_dict(db.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone())
    if not event:
        return None

    totals = dict(db.execute(
        """
        SELECT COUNT(*) AS registered,
               SUM(CASE WHEN checked_in_at IS NOT NULL AND status <> 'cancelled' THEN 1 ELSE 0 END) AS checked,
               SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) AS cancelled
        FROM accreditations
        WHERE event_id = ?
        """,
        (event_id,),
    ).fetchone())
    reservations = dict(db.execute(
        """
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN status = 'confirmed' THEN 1 ELSE 0 END) AS confirmed,
               SUM(CASE WHEN status = 'waitlisted' THEN 1 ELSE 0 END) AS waitlisted,
               SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) AS cancelled
        FROM reservations
        WHERE event_id = ?
        """,
        (event_id,),
    ).fetchone())
    attendance = dict(db.execute(
        """
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN status IN ('Presente', 'Completa') THEN 1 ELSE 0 END) AS present,
               SUM(CASE WHEN status = 'Parcial' THEN 1 ELSE 0 END) AS partial,
               SUM(CASE WHEN status = 'Ausente' THEN 1 ELSE 0 END) AS absent,
               ROUND(AVG(COALESCE(attendance_percentage, 0)), 1) AS average_percentage
        FROM activity_attendance
        WHERE event_id = ?
        """,
        (event_id,),
    ).fetchone())
    eligibility = dict(db.execute(
        """
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN elegible = 1 THEN 1 ELSE 0 END) AS eligible,
               SUM(CASE WHEN elegible = 0 THEN 1 ELSE 0 END) AS not_eligible
        FROM certificate_eligibility
        WHERE event_id = ?
        """,
        (event_id,),
    ).fetchone())
    access = dict(db.execute(
        """
        SELECT SUM(CASE WHEN result = 'granted' THEN 1 ELSE 0 END) AS granted,
               SUM(CASE WHEN result = 'rejected' THEN 1 ELSE 0 END) AS rejected,
               COUNT(DISTINCT CASE WHEN datetime(created_at) >= datetime('now', '-15 minutes') THEN operator END) AS active_operators,
               SUM(CASE WHEN result = 'granted' AND datetime(created_at) >= datetime('now', '-15 minutes') THEN 1 ELSE 0 END) AS granted_15
        FROM access_logs
        WHERE event_id = ?
        """,
        (event_id,),
    ).fetchone())
    rooms = [dict(row) for row in db.execute(
        """
        SELECT s.name AS room,
               COALESCE(NULLIF(s.capacity, 0), MAX(COALESCE(a.capacity, 0)), 0) AS capacity,
               COUNT(DISTINCT CASE WHEN at.status IN ('Presente', 'Completa', 'Parcial') THEN at.id END) AS present
        FROM spaces s
        LEFT JOIN activities a ON a.space_id = s.id AND a.status <> 'cancelled'
        LEFT JOIN activity_attendance at ON at.activity_id = a.id
        WHERE s.event_id = ? AND s.status <> 'cancelled'
        GROUP BY s.id
        ORDER BY present DESC, s.name
        """,
        (event_id,),
    ).fetchall()]
    for room in rooms:
        capacity = int(room.get("capacity") or 0)
        room["percentage"] = min(100, int(round(int(room.get("present") or 0) * 100 / capacity))) if capacity else 0

    activities = [dict(row) for row in db.execute(
        """
        SELECT a.title, s.name AS room, a.capacity,
               COUNT(DISTINCT CASE WHEN r.status = 'confirmed' THEN r.id END) AS reserved,
               COUNT(DISTINCT CASE WHEN at.status IN ('Presente', 'Completa', 'Parcial') THEN at.id END) AS present
        FROM activities a
        LEFT JOIN spaces s ON s.id = a.space_id
        LEFT JOIN reservations r ON r.activity_id = a.id
        LEFT JOIN activity_attendance at ON at.activity_id = a.id
        WHERE a.event_id = ? AND a.status <> 'cancelled'
        GROUP BY a.id
        ORDER BY present DESC, reserved DESC, a.starts_at
        LIMIT 10
        """,
        (event_id,),
    ).fetchall()]
    rejections = [dict(row) for row in db.execute(
        "SELECT COALESCE(NULLIF(reason, ''), 'Sin motivo') AS label, COUNT(*) AS value FROM access_logs WHERE event_id = ? AND result = 'rejected' GROUP BY label ORDER BY value DESC LIMIT 8",
        (event_id,),
    ).fetchall()]
    sources = [dict(row) for row in db.execute(
        "SELECT COALESCE(NULLIF(source, ''), 'Sin origen') AS label, COUNT(*) AS value FROM accreditations WHERE event_id = ? GROUP BY label ORDER BY value DESC LIMIT 8",
        (event_id,),
    ).fetchall()]

    registered = int(totals.get("registered") or 0)
    checked = int(totals.get("checked") or 0)
    rejected = int(access.get("rejected") or 0)
    room_average = round(sum(int(room["percentage"]) for room in rooms) / len(rooms)) if rooms else 100
    attendance_score = round(checked * 100 / registered) if registered else 100
    health = max(0, min(100, round((room_average + attendance_score) / 2 - min(30, rejected * 3))))
    alerts = []
    if int(access.get("granted_15") or 0) >= 100:
        alerts.append("Alto flujo de ingreso en los ultimos 15 minutos.")
    if rejected >= 5:
        alerts.append(f"Se registraron {rejected} rechazos de acceso.")
    for room in rooms:
        if int(room["capacity"] or 0) and int(room["percentage"]) < 30:
            alerts.append(f"Ocupacion baja en {room['room']}: {room['percentage']}%.")
    if int(reservations.get("waitlisted") or 0):
        alerts.append(f"{int(reservations.get('waitlisted') or 0)} personas permanecen en lista de espera.")

    return {
        "event": event,
        "totals": totals,
        "reservations": reservations,
        "attendance": attendance,
        "eligibility": eligibility,
        "access": access,
        "rooms": rooms,
        "activities": activities,
        "rejections": rejections,
        "sources": sources,
        "health": health,
        "alerts": alerts,
        "generated_at": now_iso(),
    }


def executive_report_pdf_bytes(data: dict) -> bytes:
    output = BytesIO()
    page_size = landscape(A4)
    doc = SimpleDocTemplate(
        output,
        pagesize=page_size,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=15 * mm,
        bottomMargin=14 * mm,
        title=f"Resumen ejecutivo - {data['event'].get('name') or 'Evento'}",
        author="BITORA",
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="BitoraTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=24, leading=28, textColor=colors.HexColor("#17212b"), alignment=TA_LEFT, spaceAfter=5))
    styles.add(ParagraphStyle(name="BitoraSubtitle", parent=styles["Normal"], fontSize=10, leading=14, textColor=colors.HexColor("#617080"), spaceAfter=12))
    styles.add(ParagraphStyle(name="BitoraSection", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=15, leading=18, textColor=colors.HexColor("#0b6f76"), spaceBefore=7, spaceAfter=8))
    styles.add(ParagraphStyle(name="BitoraBody", parent=styles["BodyText"], fontSize=9, leading=12, textColor=colors.HexColor("#33434d")))
    styles.add(ParagraphStyle(name="BitoraSmall", parent=styles["BodyText"], fontSize=8, leading=10, textColor=colors.HexColor("#617080")))
    styles.add(ParagraphStyle(name="KpiValue", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=22, leading=24, textColor=colors.HexColor("#17212b"), alignment=TA_CENTER))
    styles.add(ParagraphStyle(name="KpiLabel", parent=styles["Normal"], fontSize=8, leading=10, textColor=colors.HexColor("#617080"), alignment=TA_CENTER))

    event = data["event"]
    generated = format_certificate_date(data["generated_at"])
    story = [
        Paragraph("BITORA - RESUMEN EJECUTIVO", styles["BitoraSmall"]),
        Paragraph(escape(str(event.get("name") or "Evento")), styles["BitoraTitle"]),
        Paragraph(
            escape(f"{event.get('venue') or 'Sin ubicacion'} | Generado: {generated} | Informe operativo"),
            styles["BitoraSubtitle"],
        ),
    ]

    totals = data["totals"]
    access = data["access"]
    attendance = data["attendance"]
    eligibility = data["eligibility"]
    kpis = [
        ("Salud operativa", f"{data['health']}%"),
        ("Inscriptos", int(totals.get("registered") or 0)),
        ("Acreditados", int(totals.get("checked") or 0)),
        ("Accesos OK", int(access.get("granted") or 0)),
        ("Rechazos", int(access.get("rejected") or 0)),
        ("Asistencia prom.", f"{float(attendance.get('average_percentage') or 0):.1f}%"),
        ("Elegibles", int(eligibility.get("eligible") or 0)),
    ]
    kpi_cells = []
    for label, value in kpis:
        kpi_cells.append([Paragraph(str(value), styles["KpiValue"]), Paragraph(label, styles["KpiLabel"])])
    kpi_table = Table([kpi_cells], colWidths=[36 * mm] * len(kpi_cells), rowHeights=[27 * mm])
    kpi_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f2f7f7")),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#d7e2e3")),
        ("INNERGRID", (0, 0), (-1, -1), 0.6, colors.HexColor("#d7e2e3")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.extend([kpi_table, Spacer(1, 5 * mm)])

    story.append(Paragraph("Lectura ejecutiva", styles["BitoraSection"]))
    checked = int(totals.get("checked") or 0)
    registered = int(totals.get("registered") or 0)
    accreditation_rate = round(checked * 100 / registered, 1) if registered else 0
    reservations = data["reservations"]
    summary_rows = [
        ["Indicador", "Resultado", "Interpretacion"],
        ["Tasa de acreditacion", f"{accreditation_rate}%", f"{checked} de {registered} participantes ingresaron."],
        ["Reservas confirmadas", str(int(reservations.get("confirmed") or 0)), f"Lista de espera: {int(reservations.get('waitlisted') or 0)}."],
        ["Asistencia registrada", str(int(attendance.get("total") or 0)), f"Presentes/completas: {int(attendance.get('present') or 0)}; parciales: {int(attendance.get('partial') or 0)}."],
        ["Operacion QR reciente", str(int(access.get("granted_15") or 0)), f"Operadores activos ultimos 15 min: {int(access.get('active_operators') or 0)}."],
    ]
    summary_table = Table(summary_rows, colWidths=[55 * mm, 38 * mm, 160 * mm], repeatRows=1)
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0b6f76")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d7e2e3")),
        ("BACKGROUND", (0, 1), (-1, -1), colors.white),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.extend([summary_table, Spacer(1, 4 * mm)])

    alert_text = data["alerts"][:6] or ["Sin alertas operativas relevantes al momento de generar el informe."]
    story.append(Paragraph("Alertas e incidencias", styles["BitoraSection"]))
    for item in alert_text:
        story.append(Paragraph(f"- {escape(str(item))}", styles["BitoraBody"]))

    story.append(PageBreak())
    story.append(Paragraph("Ocupacion y actividades", styles["BitoraTitle"]))
    room_rows = [["Sala", "Presentes", "Capacidad", "Ocupacion", "Visual"]]
    for row in data["rooms"][:12]:
        pct = int(row.get("percentage") or 0)
        filled = max(0, min(10, round(pct / 10)))
        room_rows.append([
            str(row.get("room") or "Sin sala"),
            str(int(row.get("present") or 0)),
            str(int(row.get("capacity") or 0)),
            f"{pct}%",
            ("#" * filled) + ("-" * (10 - filled)),
        ])
    if len(room_rows) == 1:
        room_rows.append(["Sin salas", "0", "0", "0%", "----------"])
    room_table = Table(room_rows, colWidths=[75 * mm, 30 * mm, 30 * mm, 30 * mm, 75 * mm], repeatRows=1)
    room_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#17212b")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (4, 1), (4, -1), "Courier-Bold"),
        ("TEXTCOLOR", (4, 1), (4, -1), colors.HexColor("#0b7f86")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d7e2e3")),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.extend([room_table, Spacer(1, 5 * mm), Paragraph("Actividades con mayor participacion", styles["BitoraSection"])])
    activity_rows = [["Actividad", "Sala", "Reservados", "Presentes", "Cupo"]]
    for row in data["activities"]:
        activity_rows.append([
            Paragraph(escape(str(row.get("title") or "Actividad")), styles["BitoraSmall"]),
            str(row.get("room") or "Sin sala"),
            str(int(row.get("reserved") or 0)),
            str(int(row.get("present") or 0)),
            str(int(row.get("capacity") or 0)),
        ])
    if len(activity_rows) == 1:
        activity_rows.append(["Sin actividades", "-", "0", "0", "0"])
    activity_table = Table(activity_rows, colWidths=[105 * mm, 55 * mm, 30 * mm, 30 * mm, 25 * mm], repeatRows=1)
    activity_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0b6f76")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d7e2e3")),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(activity_table)

    story.append(PageBreak())
    story.append(Paragraph("Accesos, rechazos y captacion", styles["BitoraTitle"]))
    left_rows = [["Motivo de rechazo", "Cantidad"]] + [[str(row["label"]), str(row["value"])] for row in data["rejections"]]
    right_rows = [["Origen de inscripcion", "Cantidad"]] + [[str(row["label"]), str(row["value"])] for row in data["sources"]]
    if len(left_rows) == 1:
        left_rows.append(["Sin rechazos", "0"])
    if len(right_rows) == 1:
        right_rows.append(["Sin origen registrado", "0"])

    def compact_table(rows, header_color):
        table = Table(rows, colWidths=[90 * mm, 28 * mm], repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(header_color)),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ALIGN", (1, 1), (1, -1), "RIGHT"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d7e2e3")),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        return table

    comparison = Table(
        [[compact_table(left_rows, "#b42318"), compact_table(right_rows, "#0b6f76")]],
        colWidths=[126 * mm, 126 * mm],
    )
    comparison.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 8)]))
    story.extend([comparison, Spacer(1, 8 * mm)])
    story.append(Paragraph("Notas del informe", styles["BitoraSection"]))
    story.append(Paragraph(
        "Este resumen se genera con los datos registrados en BITORA al momento de la descarga. "
        "Una reserva no implica asistencia y una acreditacion general no implica presencia en una actividad. "
        "Los valores de asistencia dependen de los ingresos y egresos QR efectivamente registrados.",
        styles["BitoraBody"],
    ))

    def footer(canvas, document):
        canvas.saveState()
        width, _ = page_size
        canvas.setStrokeColor(colors.HexColor("#d7e2e3"))
        canvas.line(16 * mm, 10 * mm, width - 16 * mm, 10 * mm)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#617080"))
        canvas.drawString(16 * mm, 6 * mm, "BITORA - Bitacora digital de eventos")
        canvas.drawRightString(width - 16 * mm, 6 * mm, f"Pagina {document.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()


def read_json(handler: SimpleHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0"))
    raw = handler.rfile.read(length) if length else b"{}"
    handler._raw_json_body = raw
    if not raw:
        return {}
    return json.loads(raw.decode("utf-8"))


LANDING_ALLOWED_IMAGE_TYPES = {
    "image/jpeg": "JPEG",
    "image/jpg": "JPEG",
    "image/png": "PNG",
    "image/webp": "WEBP",
}
LANDING_IMAGE_MAX_BYTES = int(os.environ.get("LANDING_IMAGE_MAX_BYTES", str(3 * 1024 * 1024)))
LANDING_IMAGE_MIN_WIDTH = int(os.environ.get("LANDING_IMAGE_MIN_WIDTH", "800"))
LANDING_IMAGE_MIN_HEIGHT = int(os.environ.get("LANDING_IMAGE_MIN_HEIGHT", "450"))


def validate_landing_image(data_url: str, filename: str = "") -> dict:
    if not data_url or "," not in data_url or not data_url.startswith("data:"):
        raise ValueError("Imagen invalida")
    header, encoded = data_url.split(",", 1)
    content_type = header[5:].split(";", 1)[0].lower().strip()
    if content_type not in LANDING_ALLOWED_IMAGE_TYPES:
        raise ValueError("Formato no permitido. Usa JPG, JPEG, PNG o WEBP")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise ValueError("No se pudo leer la imagen") from exc
    if len(raw) > LANDING_IMAGE_MAX_BYTES:
        raise ValueError(f"Imagen demasiado pesada. Maximo {LANDING_IMAGE_MAX_BYTES // (1024 * 1024)} MB")
    try:
        with Image.open(BytesIO(raw)) as image:
            width, height = image.size
            image.verify()
    except Exception as exc:
        raise ValueError("Archivo de imagen invalido") from exc
    if width < LANDING_IMAGE_MIN_WIDTH or height < LANDING_IMAGE_MIN_HEIGHT:
        raise ValueError(f"Resolucion minima {LANDING_IMAGE_MIN_WIDTH} x {LANDING_IMAGE_MIN_HEIGHT}")
    return {
        "data_url": data_url,
        "filename": str(filename or "landing").strip()[:120],
        "content_type": content_type,
        "width": width,
        "height": height,
        "bytes": len(raw),
    }


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
            if WORKER and WORKER.thread and WORKER.thread.is_alive():
                job_queue_service().enqueue("backup.create", {}, priority="low", actor="auto-backup")
            else:
                create_db_backup()
        except Exception as exc:
            technical_log("error", "backup", "Backup automatico fallido", str(exc))


def start_auto_backup() -> threading.Thread | None:
    if AUTO_BACKUP_MINUTES <= 0 or DB_CONFIG.engine == "postgres":
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
        "/web.html",
        "/web",
        "/e.html",
        "/p.html",
        "/styles.css",
        "/public.js",
        "/app.js",
        "/jsQR.min.js",
        "/html5-qrcode.min.js",
    } or clean.startswith("/assets/") or clean.startswith("/p/") or clean.startswith("/api/")


def public_api_get(path: str) -> bool:
    return path in {"/api/app-config", "/api/event", "/api/portal", "/api/qr.svg", "/api/credential.svg", "/api/credential.png", "/api/credential.pdf", "/api/certificate.pdf", "/api/users", "/api/auth/me", "/api/network-info", "/api/public-display", "/api/participant-metrics", "/api/waiting-room/status"}


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
        "/api/communications/whatsapp/webhook",
        "/api/communications/email/webhook",
        "/api/waiting-room/join",
        "/api/waiting-room/abandon",
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

    def send_response(self, code: int, message: str | None = None) -> None:
        self._response_status = int(code)
        super().send_response(code, message)

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

    def effective_user(self) -> dict | None:
        return self.session_user() or ({"name": "Admin", "role": "Super Admin", "local": True} if not self.login_required() else None)

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
        if clean == "/web":
            return str(STATIC_DIR / "web.html")
        if clean == "/reports-display":
            return str(STATIC_DIR / "reports-display.html")
        if clean.startswith("/p/"):
            return str(STATIC_DIR / "p.html")
        target = STATIC_DIR / clean.lstrip("/")
        if target.exists():
            return str(target)
        return str(LEGACY_STATIC_DIR / clean.lstrip("/"))

    def do_GET(self) -> None:
        started = RUNTIME_METRICS.begin()
        self._response_status = 200
        parsed = urlparse(self.path)
        try:
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
        finally:
            RUNTIME_METRICS.finish(started, "GET", parsed.path, getattr(self, "_response_status", 200))

    def do_POST(self) -> None:
        started = RUNTIME_METRICS.begin()
        self._response_status = 200
        parsed = urlparse(self.path)
        try:
            if parsed.path.startswith("/api/"):
                self.handle_api_post(parsed.path)
                return
            self.send_error(HTTPStatus.NOT_FOUND)
        finally:
            RUNTIME_METRICS.finish(started, "POST", parsed.path, getattr(self, "_response_status", 200))

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
                session = self.effective_user()
                if not session and not self.login_required():
                    session = {"name": "Admin", "role": "Super Admin", "local": True}
                self.send_json({"authenticated": bool(session), "user": session, "config": runtime_config(self)})
                return

            if path == "/api/app-config":
                self.send_json(runtime_config(self))
                return

            if path == "/api/network-info":
                self.send_json(network_info(self))
                return

            if path == "/api/waiting-room/status":
                event_id = int(query.get("event_id", ["0"])[0])
                visitor_id = query.get("visitor_id", [""])[0].strip()
                if not event_id or not visitor_id:
                    self.send_json({"error": "Falta evento o visitante"}, 400)
                    return
                with DB_LOCK, connect() as db:
                    db.execute("BEGIN IMMEDIATE")
                    result = waiting_room_payload(db, event_id, visitor_id)
                    db.execute("COMMIT")
                self.send_json(result, 404 if result.get("error") else 200)
                return

            if path == "/api/communications/whatsapp/webhook":
                verify_token = query.get("hub.verify_token", [""])[0]
                challenge = query.get("hub.challenge", [""])[0]
                mode = query.get("hub.mode", [""])[0]
                if mode == "subscribe" and verify_token and hmac.compare_digest(verify_token, os.environ.get("WHATSAPP_VERIFY_TOKEN", "")):
                    body = challenge.encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/plain; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                else:
                    self.send_json({"error": "Verificacion WhatsApp invalida"}, 403)
                return

            if path == "/api/diagnostics/status":
                session = self.effective_user()
                if not session or session.get("role") not in ADMIN_ROLES:
                    self.send_json({"error": "Diagnostico disponible solo para Super Admin"}, 403)
                    return
                with connect() as db:
                    result = diagnostics_service().collect(
                        db,
                        runtime={
                            **RUNTIME_METRICS.snapshot(),
                            "worker_alive": bool(WORKER and WORKER.thread and WORKER.thread.is_alive()),
                            "worker_heartbeat_age": round(time.time() - WORKER.last_heartbeat, 2) if WORKER and WORKER.last_heartbeat else None,
                        },
                        sessions=list(AUTH_SESSIONS.values()),
                        auto_backup_minutes=AUTO_BACKUP_MINUTES,
                    )
                    whatsapp_provider = create_whatsapp_provider()
                    result["services"]["whatsapp"] = {
                        "status": "online" if whatsapp_provider.ready else "inactive",
                        "label": "Conectado" if whatsapp_provider.ready else "No configurado",
                    }
                    audit(db, session["name"], "diagnostics.opened", "system", None, {"app_status": result["app_status"]})
                self.send_json(result)
                return

            if path == "/api/jobs":
                session = self.effective_user()
                if not session or session.get("role") not in ADMIN_ROLES:
                    self.send_json({"error": "Jobs disponibles solo para Super Admin"}, 403)
                    return
                kind = query.get("kind", [""])[0].strip()
                where = "1 = 1"
                params: list[object] = []
                if kind:
                    where = "kind LIKE ?"
                    params.append(f"{kind}%")
                with connect() as db:
                    rows = db.execute(
                        f"""
                        SELECT id, event_id, kind, priority, status, retry_count, max_retries,
                               retry_at, worker_id, error, created_by, created_at, started_at,
                               finished_at, updated_at
                        FROM jobs WHERE {where}
                        ORDER BY id DESC LIMIT 200
                        """,
                        params,
                    ).fetchall()
                self.send_json([dict(row) for row in rows])
                return

            if path == "/api/simulator/status":
                session = self.effective_user()
                if not session or session.get("role") not in ADMIN_ROLES:
                    self.send_json({"error": "Simulador disponible solo para Super Admin"}, 403)
                    return
                event_id = int(query.get("event_id", ["0"])[0])
                with connect() as db:
                    row = db.execute("SELECT * FROM simulator_state WHERE event_id = ?", (event_id,)).fetchone()
                self.send_json(dict(row) if row else {"event_id": event_id, "status": "stopped", "mode": "medium", "scenario": "congress"})
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

            if path == "/api/event-structure.json":
                event_id = int(query.get("event_id", ["0"])[0] or 0)
                with connect() as db:
                    payload = event_structure_payload(db, event_id)
                    if not payload:
                        self.send_json({"error": "Evento inexistente"}, 404)
                        return
                    session = self.session_user()
                    audit(db, session["name"] if session else "system", "event.structure_exported", "event", event_id, {"event_id": event_id})
                body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
                send_download(self, f"evento-{event_id}-estructura.json", "application/json; charset=utf-8", body)
                return

            if path == "/api/agenda.csv":
                event_id = int(query.get("event_id", ["0"])[0] or 0)
                with connect() as db:
                    rows = db.execute(
                        """
                        SELECT s.name AS sala, a.title AS actividad, substr(a.starts_at, 1, 10) AS fecha,
                               substr(a.starts_at, 12, 5) AS hora_inicio, substr(a.ends_at, 12, 5) AS hora_fin,
                               a.speaker AS disertante, a.description AS descripcion, a.capacity AS capacidad,
                               a.activity_type AS tipo_actividad
                        FROM activities a
                        JOIN spaces s ON s.id = a.space_id
                        WHERE a.event_id = ?
                        ORDER BY a.starts_at, s.name
                        """,
                        (event_id,),
                    ).fetchall()
                    audit(db, (self.session_user() or {}).get("name", "system"), "agenda.exported", "event", event_id, {"count": len(rows)})
                out = BytesIO()
                writer = csv.writer(_TextWriter(out))
                writer.writerow(["Sala", "Actividad", "Fecha", "Hora inicio", "Hora fin", "Disertante", "Descripcion", "Capacidad", "Tipo actividad"])
                for row in rows:
                    writer.writerow([row[key] for key in row.keys()])
                send_download(self, f"evento-{event_id}-agenda.csv", "text/csv; charset=utf-8", out.getvalue())
                return

            if path == "/api/agenda.ics":
                event_id = int(query.get("event_id", ["0"])[0] or 0)
                with connect() as db:
                    rows = db.execute(
                        """
                        SELECT e.name AS event_name, s.name AS sala, a.title, a.description, a.starts_at, a.ends_at
                        FROM activities a
                        JOIN events e ON e.id = a.event_id
                        JOIN spaces s ON s.id = a.space_id
                        WHERE a.event_id = ? AND a.status <> 'cancelled'
                        ORDER BY a.starts_at, s.name
                        """,
                        (event_id,),
                    ).fetchall()
                    audit(db, (self.session_user() or {}).get("name", "system"), "agenda.ics_exported", "event", event_id, {"count": len(rows)})
                lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//BITORA//Agenda//ES", "CALSCALE:GREGORIAN"]
                for row in rows:
                    lines.extend(
                        [
                            "BEGIN:VEVENT",
                            f"UID:bitora-{event_id}-{ics_escape(row['title'])}-{ics_datetime(row['starts_at'])}",
                            f"SUMMARY:{ics_escape(row['title'])}",
                            f"DESCRIPTION:{ics_escape(row['description'])}",
                            f"LOCATION:{ics_escape(row['sala'])}",
                            f"DTSTART:{ics_datetime(row['starts_at'])}",
                            f"DTEND:{ics_datetime(row['ends_at'])}",
                            "END:VEVENT",
                        ]
                    )
                lines.append("END:VCALENDAR")
                send_download(self, f"evento-{event_id}-agenda.ics", "text/calendar; charset=utf-8", ("\r\n".join(lines) + "\r\n").encode("utf-8"))
                return

            if path == "/api/reports/executive.pdf":
                event_id = int(query.get("event_id", ["0"])[0] or 0)
                with connect() as db:
                    report_data = executive_report_data(db, event_id)
                    if not report_data:
                        self.send_json({"error": "Evento inexistente"}, 404)
                        return
                    audit(
                        db,
                        (self.session_user() or {}).get("name", "system"),
                        "reports.executive_exported",
                        "event",
                        event_id,
                        {"event_id": event_id},
                    )
                body = executive_report_pdf_bytes(report_data)
                safe_name = "".join(char if char.isalnum() else "-" for char in str(report_data["event"].get("name") or "evento")).strip("-").lower()
                send_download(
                    self,
                    f"{safe_name or 'evento'}-resumen-ejecutivo.pdf",
                    "application/pdf",
                    body,
                )
                return

            if path == "/api/reports/visual-summary":
                event_id = int(query.get("event_id", ["0"])[0] or 0)
                with connect() as db:
                    event = row_to_dict(db.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone())
                    if not event:
                        self.send_json({"error": "Evento inexistente"}, 404)
                        return
                    accreditation_status_counts = [dict(r) for r in db.execute(
                        """
                        SELECT
                          CASE
                            WHEN status = 'cancelled' THEN 'Canceladas'
                            WHEN checked_in_at IS NOT NULL THEN 'Acreditadas'
                            ELSE 'Pendientes'
                          END AS label,
                          COUNT(*) AS value
                        FROM accreditations
                        WHERE event_id = ?
                        GROUP BY label
                        """,
                        (event_id,),
                    ).fetchall()]
                    by_type = [dict(r) for r in db.execute("SELECT type AS label, COUNT(*) AS value FROM accreditations WHERE event_id = ? AND status <> 'cancelled' GROUP BY type ORDER BY value DESC", (event_id,)).fetchall()]
                    access_by_time = [dict(r) for r in db.execute(
                        """
                        SELECT substr(created_at, 1, 13) || ':00' AS label, COUNT(*) AS value
                        FROM access_logs
                        WHERE event_id = ? AND result = 'granted'
                        GROUP BY label
                        ORDER BY label
                        LIMIT 24
                        """,
                        (event_id,),
                    ).fetchall()]
                    rejection_reasons = [dict(r) for r in db.execute("SELECT reason AS label, COUNT(*) AS value FROM access_logs WHERE event_id = ? AND result = 'rejected' GROUP BY reason ORDER BY value DESC LIMIT 8", (event_id,)).fetchall()]
                    activity_occupancy = [dict(r) for r in db.execute(
                        """
                        SELECT a.title AS label,
                               SUM(CASE WHEN r.status = 'confirmed' THEN 1 ELSE 0 END) AS value,
                               a.capacity
                        FROM activities a
                        LEFT JOIN reservations r ON r.activity_id = a.id
                        WHERE a.event_id = ? AND a.status <> 'cancelled'
                        GROUP BY a.id
                        ORDER BY value DESC, a.starts_at
                        LIMIT 8
                        """,
                        (event_id,),
                    ).fetchall()]
                    source_counts = [dict(r) for r in db.execute("SELECT COALESCE(NULLIF(source, ''), 'sin origen') AS label, COUNT(*) AS value FROM accreditations WHERE event_id = ? GROUP BY label ORDER BY value DESC LIMIT 8", (event_id,)).fetchall()]
                    device_counts = [dict(r) for r in db.execute("SELECT COALESCE(NULLIF(device_type, ''), 'sin dispositivo') AS label, COUNT(*) AS value FROM accreditations WHERE event_id = ? GROUP BY label ORDER BY value DESC", (event_id,)).fetchall()]
                    communication_status_counts = [dict(r) for r in db.execute("SELECT estado AS label, COUNT(*) AS value FROM communication_logs WHERE event_id = ? GROUP BY estado", (event_id,)).fetchall()]
                    operator_activity = [dict(r) for r in db.execute(
                        """
                        SELECT operator AS label, COUNT(*) AS value
                        FROM access_logs
                        WHERE event_id = ? AND datetime(created_at) >= datetime('now', '-15 minutes')
                        GROUP BY operator
                        ORDER BY value DESC
                        LIMIT 8
                        """,
                        (event_id,),
                    ).fetchall()]
                    occupancy_rows = [
                        dict(r)
                        for r in db.execute(
                            """
                            SELECT s.id, s.name AS room,
                                   COALESCE(NULLIF(s.capacity, 0), SUM(COALESCE(NULLIF(a.capacity, 0), 0)), 0) AS capacity,
                                   COUNT(DISTINCT CASE WHEN r.status = 'confirmed' THEN r.id END) AS registered,
                                   COUNT(DISTINCT CASE WHEN at.status IN ('Presente', 'Completa', 'Parcial') THEN at.id END) AS present
                            FROM spaces s
                            LEFT JOIN activities a ON a.space_id = s.id AND a.status <> 'cancelled'
                            LEFT JOIN reservations r ON r.activity_id = a.id
                            LEFT JOIN activity_attendance at ON at.activity_id = a.id
                            WHERE s.event_id = ? AND s.status <> 'cancelled'
                            GROUP BY s.id
                            ORDER BY s.name
                            """,
                            (event_id,),
                        ).fetchall()
                    ]
                    occupancy_by_room = []
                    low_threshold = int(query.get("occupancy_low_threshold", ["30"])[0] or 30)
                    for row in occupancy_rows:
                        capacity = int(row.get("capacity") or 0)
                        present = int(row.get("present") or 0)
                        registered = int(row.get("registered") or 0)
                        percentage = min(100, int(round((present / capacity * 100), 0))) if capacity else 0
                        if percentage > 60:
                            color = "green"
                        elif percentage >= low_threshold:
                            color = "yellow"
                        else:
                            color = "red"
                        occupancy_by_room.append(
                            {
                                "room": row["room"],
                                "capacity": capacity,
                                "registered": registered,
                                "present": present,
                                "percentage": percentage,
                                "color": color,
                                "low": capacity > 0 and percentage < low_threshold,
                            }
                        )
                    room_ranking = sorted(occupancy_by_room, key=lambda item: item["percentage"], reverse=True)
                    room_heatmap = [{"room": item["room"], "color": item["color"], "percentage": item["percentage"]} for item in room_ranking]
                    attendance_vs_capacity = [
                        {
                            "room": item["room"],
                            "capacity": item["capacity"],
                            "registered": item["registered"],
                            "present": item["present"],
                            "attendance_percentage": item["percentage"],
                        }
                        for item in room_ranking
                    ]
                    critical_activities = [
                        dict(r)
                        for r in db.execute(
                            """
                            SELECT a.title, s.name AS room, a.capacity,
                                   COUNT(DISTINCT CASE WHEN r.status = 'confirmed' THEN r.id END) AS registered,
                                   COUNT(DISTINCT CASE WHEN at.status IN ('Presente', 'Completa', 'Parcial') THEN at.id END) AS present
                            FROM activities a
                            JOIN spaces s ON s.id = a.space_id
                            LEFT JOIN reservations r ON r.activity_id = a.id
                            LEFT JOIN activity_attendance at ON at.activity_id = a.id
                            WHERE a.event_id = ? AND a.status <> 'cancelled'
                            GROUP BY a.id
                            HAVING COALESCE(a.capacity, 0) > 0
                               AND ROUND(COUNT(DISTINCT CASE WHEN at.status IN ('Presente', 'Completa', 'Parcial') THEN at.id END) * 100.0 / a.capacity, 0) < ?
                            ORDER BY present ASC, a.starts_at
                            LIMIT 8
                            """,
                            (event_id, low_threshold),
                        ).fetchall()
                    ]
                    totals = dict(db.execute(
                        """
                        SELECT COUNT(*) AS registered,
                               SUM(CASE WHEN checked_in_at IS NOT NULL AND status <> 'cancelled' THEN 1 ELSE 0 END) AS checked,
                               SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) AS cancelled
                        FROM accreditations
                        WHERE event_id = ?
                        """,
                        (event_id,),
                    ).fetchone())
                    recent_granted_15 = int(db.execute(
                        """
                        SELECT COUNT(*) AS c
                        FROM access_logs
                        WHERE event_id = ? AND result = 'granted'
                          AND datetime(created_at) >= datetime('now', '-15 minutes')
                        """,
                        (event_id,),
                    ).fetchone()["c"])
                    active_operator_count = int(db.execute(
                        """
                        SELECT COUNT(DISTINCT operator) AS c
                        FROM access_logs
                        WHERE event_id = ?
                          AND datetime(created_at) >= datetime('now', '-15 minutes')
                          AND COALESCE(operator, '') <> ''
                        """,
                        (event_id,),
                    ).fetchone()["c"])
                    operational_alerts = []
                    if recent_granted_15 >= 100:
                        operational_alerts.append({"type": "high_flow", "level": "yellow", "title": "Alto flujo de ingreso", "message": f"{recent_granted_15} accesos concedidos en los ultimos 15 minutos"})
                    if active_operator_count >= 30:
                        operational_alerts.append({"type": "terminal_inactive", "level": "yellow", "title": "Terminal a revisar", "message": f"{active_operator_count} terminales activas y 1 terminal marcada para supervision"})
                    for item in occupancy_by_room:
                        if item["low"]:
                            operational_alerts.append({"type": "occupancy_low", "level": "red", "title": "Ocupacion baja", "message": f"{item['room']}: {item['percentage']}% - {item['present']} presentes / {item['capacity']} capacidad"})
                    for item in critical_activities:
                        present = int(item.get("present") or 0)
                        capacity = int(item.get("capacity") or 0)
                        percentage = int(round(present / capacity * 100, 0)) if capacity else 0
                        title = "Actividad sin asistentes" if present == 0 else "Actividad critica"
                        operational_alerts.append({"type": "critical_activity", "level": "yellow" if present else "red", "title": title, "message": f"{item['title']} - {item['room']} - {percentage}%"})
                    rejected_recent = int(sum(int(row.get("value") or 0) for row in rejection_reasons))
                    if rejected_recent >= 5:
                        operational_alerts.append({"type": "qr_rejections", "level": "yellow", "title": "Rechazos QR elevados", "message": f"{rejected_recent} rechazos registrados"})
                    if int(event.get("waitlist_enabled") or 0):
                        waitlisted_total = int(db.execute("SELECT COUNT(*) AS c FROM reservations WHERE event_id = ? AND status = 'waitlisted'", (event_id,)).fetchone()["c"])
                        if waitlisted_total >= 10:
                            operational_alerts.append({"type": "waitlist_high", "level": "yellow", "title": "Lista de espera alta", "message": f"{waitlisted_total} personas en espera"})
                    communication_errors = int(db.execute("SELECT COUNT(*) AS c FROM communication_logs WHERE event_id = ? AND estado IN ('error', 'fallido')", (event_id,)).fetchone()["c"])
                    if communication_errors:
                        operational_alerts.append({"type": "communication_error", "level": "yellow", "title": "Errores de comunicacion", "message": f"{communication_errors} envios con error"})
                    avg_occupancy = int(round(sum(item["percentage"] for item in occupancy_by_room) / len(occupancy_by_room), 0)) if occupancy_by_room else 100
                    registered_total = int(totals.get("registered") or 0)
                    checked_total = int(totals.get("checked") or 0)
                    attendance_score = int(round(checked_total / registered_total * 100, 0)) if registered_total else 100
                    rejection_penalty = min(30, rejected_recent * 3)
                    alert_penalty = min(40, len(operational_alerts) * 8)
                    event_health = max(0, min(100, int(round((avg_occupancy + attendance_score) / 2 - rejection_penalty - alert_penalty, 0))))
                    audit(db, (self.session_user() or {}).get("name", "system"), "reports.visual_opened", "event", event_id, {"event_id": event_id})
                self.send_json({
                    "event": {key: event.get(key) for key in ("id", "name", "venue", "activities_enabled", "capacity_control_enabled", "waitlist_enabled")},
                    "generated_at": now_iso(),
                    "totals": totals,
                    "event_health": event_health,
                    "operational_alerts": operational_alerts,
                    "accreditation_status_counts": accreditation_status_counts,
                    "by_type": by_type,
                    "access_by_time": access_by_time,
                    "rejection_reasons": rejection_reasons,
                    "activity_occupancy": activity_occupancy,
                    "occupancy_by_room": occupancy_by_room,
                    "room_heatmap": room_heatmap,
                    "room_ranking": room_ranking,
                    "critical_activities": critical_activities,
                    "attendance_vs_capacity": attendance_vs_capacity,
                    "source_counts": source_counts,
                    "device_counts": device_counts,
                    "communication_status_counts": communication_status_counts,
                    "operator_activity": operator_activity,
                })
                return

            if path == "/api/event":
                event_id = int(query.get("event_id", ["0"])[0])
                with connect() as db:
                    attendance_service().ensure_absences(db, event_id)
                    event = row_to_dict(db.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone())
                    if not event:
                        self.send_json({"error": "Evento inexistente"}, 404)
                        return
                    activities = []
                    if int(event.get("activities_enabled") or 0) == 1:
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
                    access_open_minutes = activity.get("access_open_minutes_before")
                    if access_open_minutes in (None, ""):
                        event_config = db.execute(
                            "SELECT activity_access_open_minutes_before FROM events WHERE id = ?",
                            (activity["event_id"],),
                        ).fetchone()
                        access_open_minutes = int(event_config["activity_access_open_minutes_before"] or 10) if event_config else 10
                    access_open_minutes = max(0, int(access_open_minutes or 0))
                    access_open_at = (parse_local_datetime(activity["starts_at"]) - timedelta(minutes=access_open_minutes)).isoformat(timespec="minutes")
                    access_attempts = dict(
                        db.execute(
                            """
                            SELECT
                                SUM(CASE WHEN result = 'rejected' AND reason LIKE 'Acceso aun no habilitado%' THEN 1 ELSE 0 END) AS early_attempts,
                                SUM(CASE WHEN result = 'rejected' THEN 1 ELSE 0 END) AS rejected,
                                SUM(CASE WHEN result = 'granted' THEN 1 ELSE 0 END) AS granted
                            FROM access_logs
                            WHERE activity_id = ?
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
                            WHERE l.activity_id = ?
                            ORDER BY l.id DESC
                            LIMIT 10
                            """,
                            (activity_id,),
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
                self.send_json({
                    "activity": activity,
                    "availability": availability,
                    "stats": stats,
                    "attendance": attendance,
                    "access_window": {
                        "minutes_before": access_open_minutes,
                        "opens_at": access_open_at,
                        "early_attempts": int(access_attempts.get("early_attempts") or 0),
                        "rejected": int(access_attempts.get("rejected") or 0),
                        "granted": int(access_attempts.get("granted") or 0),
                    },
                    "attendance_rows": attendance_rows,
                    "bags": bags,
                    "recent_access": recent_access,
                })
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
                order_clause = "a.id DESC"
                if search:
                    terms = [part for part in search.replace(",", " ").split() if part]
                    if not terms:
                        terms = [search]
                    for _ in terms:
                        where += """ AND (
                            p.first_name LIKE ? OR p.last_name LIKE ? OR
                            (p.first_name || ' ' || p.last_name) LIKE ? OR
                            (p.last_name || ' ' || p.first_name) LIKE ? OR
                            p.email LIKE ? OR p.dni LIKE ? OR p.company LIKE ? OR
                            p.phone LIKE ? OR a.token LIKE ? OR a.type LIKE ?
                        )"""
                    for term_raw in terms:
                        term = f"%{term_raw}%"
                        params.extend([term, term, term, term, term, term, term, term, term, term])
                    search_like = f"%{search}%"
                    order_clause = """
                        CASE
                          WHEN lower(p.first_name || ' ' || p.last_name) = lower(?) THEN 0
                          WHEN lower(p.last_name || ' ' || p.first_name) = lower(?) THEN 1
                          WHEN (p.first_name || ' ' || p.last_name) LIKE ? THEN 2
                          WHEN (p.last_name || ' ' || p.first_name) LIKE ? THEN 3
                          WHEN p.dni = ? THEN 4
                          WHEN p.company LIKE ? THEN 5
                          ELSE 9
                        END,
                        a.id DESC
                    """
                    params.extend([search, search, search_like, search_like, search, search_like])
                with connect() as db:
                    rows = db.execute(
                        f"""
                        SELECT a.*, p.first_name, p.last_name, p.email, p.phone, p.dni, p.company, e.name AS event_name
                        FROM accreditations a
                        JOIN people p ON p.id = a.person_id
                        JOIN events e ON e.id = a.event_id
                        WHERE {where}
                        ORDER BY {order_clause}
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
                    selected_rows = db.execute(
                        """
                        SELECT activity_id
                        FROM public_display_items
                        WHERE event_id = ? AND visible = 1
                        ORDER BY sort_order, activity_id
                        """,
                        (event_id,),
                    ).fetchall()
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
                self.send_json({
                    "config": config,
                    "activities": activities,
                    "selected_activity_ids": [int(row["activity_id"]) for row in selected_rows],
                    "has_selection": bool(selected_rows),
                })
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
                    queue = [
                        dict(r)
                        for r in db.execute(
                            """
                            SELECT q.*, p.first_name, p.last_name
                            FROM communication_queue q
                            JOIN people p ON p.id = q.person_id
                            WHERE q.event_id = ?
                            ORDER BY q.id DESC
                            LIMIT 100
                            """,
                            (event_id,),
                        ).fetchall()
                    ]
                    queue_metrics = dict(
                        db.execute(
                            """
                            SELECT
                                SUM(CASE WHEN channel = 'email' AND status IN ('enviado', 'entregado', 'leido') THEN 1 ELSE 0 END) AS emails_sent,
                                SUM(CASE WHEN channel = 'email' AND status IN ('entregado', 'leido') THEN 1 ELSE 0 END) AS emails_delivered,
                                SUM(CASE WHEN channel = 'email' AND status IN ('rebotado', 'rechazado') THEN 1 ELSE 0 END) AS emails_bounced,
                                SUM(CASE WHEN channel = 'email' AND status = 'error' THEN 1 ELSE 0 END) AS emails_failed,
                                SUM(CASE WHEN channel = 'whatsapp' AND status IN ('enviado', 'entregado', 'leido') THEN 1 ELSE 0 END) AS whatsapp_sent,
                                SUM(CASE WHEN channel = 'whatsapp' AND status IN ('entregado', 'leido') THEN 1 ELSE 0 END) AS whatsapp_delivered,
                                SUM(CASE WHEN channel = 'whatsapp' AND status = 'leido' THEN 1 ELSE 0 END) AS whatsapp_read,
                                SUM(CASE WHEN status = 'pendiente' THEN 1 ELSE 0 END) AS pending,
                                SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) AS errors
                            FROM communication_queue
                            WHERE event_id = ?
                            """,
                            (event_id,),
                        ).fetchone()
                    )
                    assistant_metrics = dict(
                        db.execute(
                            """
                            SELECT
                                COUNT(*) AS received,
                                SUM(CASE WHEN status = 'resolved' THEN 1 ELSE 0 END) AS resolved,
                                SUM(CASE WHEN intent = 'handoff' THEN 1 ELSE 0 END) AS handoffs,
                                SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) AS errors
                            FROM communication_assistant_history
                            WHERE event_id = ?
                            """,
                            (event_id,),
                        ).fetchone()
                    )
                    tickets = [dict(r) for r in db.execute("SELECT * FROM communication_tickets WHERE event_id = ? ORDER BY id DESC LIMIT 50", (event_id,)).fetchall()]
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
                    email_last_success = db.execute(
                        """
                        SELECT processed_at
                        FROM communication_queue
                        WHERE event_id = ? AND channel = 'email'
                          AND status IN ('enviado', 'entregado', 'leido')
                        ORDER BY id DESC LIMIT 1
                        """,
                        (event_id,),
                    ).fetchone()
                    email_last_error = db.execute(
                        """
                        SELECT last_error, processed_at
                        FROM communication_queue
                        WHERE event_id = ? AND channel = 'email' AND last_error <> ''
                        ORDER BY id DESC LIMIT 1
                        """,
                        (event_id,),
                    ).fetchone()
                self.send_json({
                    "mode": "demo" if communication_provider("email") == "demo" and communication_provider("whatsapp") == "demo" else "provider",
                    "providers": {
                        "email": {
                            "provider": communication_provider("email"),
                            "ready": communication_provider_ready("email"),
                            "enabled": os.environ.get("EMAIL_ENABLED", "true").lower() in {"1", "true", "yes", "si"},
                            "from": os.environ.get("EMAIL_FROM", ""),
                            "reply_to": os.environ.get("EMAIL_REPLY_TO", ""),
                            "last_success": email_last_success["processed_at"] if email_last_success else "",
                            "last_error": email_last_error["last_error"] if email_last_error else "",
                            "last_error_at": email_last_error["processed_at"] if email_last_error else "",
                        },
                        "whatsapp": {
                            "provider": communication_provider("whatsapp"),
                            "ready": communication_provider_ready("whatsapp"),
                            "phone_id": os.environ.get("WHATSAPP_PHONE_NUMBER_ID", os.environ.get("WHATSAPP_PHONE_ID", "")),
                            "enabled": os.environ.get("WHATSAPP_ENABLED", "false").lower() in {"1", "true", "yes", "si"},
                        },
                    },
                    "stats": stats,
                    "queue_metrics": queue_metrics,
                    "assistant_metrics": assistant_metrics,
                    "queue": queue,
                    "tickets": tickets,
                    "logs": logs,
                    "templates": templates,
                })
                return

            if path == "/api/communications/history":
                event_id = int(query.get("event_id", ["0"])[0])
                person_id = int(query.get("person_id", ["0"])[0] or 0)
                params: list[object] = [event_id]
                where = "l.event_id = ?"
                if person_id:
                    where += " AND l.person_id = ?"
                    params.append(person_id)
                with connect() as db:
                    rows = db.execute(
                        f"""
                        SELECT l.*, p.first_name, p.last_name
                        FROM communication_logs l
                        JOIN people p ON p.id = l.person_id
                        WHERE {where}
                        ORDER BY l.id DESC
                        LIMIT 200
                        """,
                        params,
                    ).fetchall()
                self.send_json([dict(r) for r in rows])
                return

            if path == "/api/communications/assistant/history":
                event_id = int(query.get("event_id", ["0"])[0])
                with connect() as db:
                    rows = db.execute(
                        """
                        SELECT h.*, p.first_name, p.last_name
                        FROM communication_assistant_history h
                        LEFT JOIN people p ON p.id = h.person_id
                        WHERE h.event_id = ?
                        ORDER BY h.id DESC
                        LIMIT 100
                        """,
                        (event_id,),
                    ).fetchall()
                self.send_json([dict(r) for r in rows])
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
                self.send_header("Content-Disposition", "attachment; filename=inscripciones.csv")
                self.end_headers()
                writer = csv.writer(self.wfile.read if False else _TextWriter(self.wfile))
                writer.writerow(["Evento", "Actividad", "Sala", "Inicio", "Fin", "Nombre", "Apellido", "Email", "Telefono", "DNI", "Empresa", "Tipo", "Token", "Inscripcion"])
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
                session = self.effective_user()
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
            technical_log("error", "api.get", "Error procesando solicitud", str(exc), path)
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

            if path == "/api/waiting-room/join":
                event_id = int(data.get("event_id") or 0)
                visitor_id = str(data.get("visitor_id") or "").strip()
                if not event_id or not visitor_id:
                    self.send_json({"error": "Falta evento o visitante"}, 400)
                    return
                with DB_LOCK, connect() as db:
                    db.execute("BEGIN IMMEDIATE")
                    result = waiting_room_payload(db, event_id, visitor_id)
                    db.execute("COMMIT")
                self.send_json(result, 404 if result.get("error") else 200)
                return

            if path == "/api/waiting-room/abandon":
                event_id = int(data.get("event_id") or 0)
                visitor_id = str(data.get("visitor_id") or "").strip()
                with DB_LOCK, connect() as db:
                    db.execute("BEGIN IMMEDIATE")
                    row = db.execute(
                        "SELECT id FROM waiting_room_visitors WHERE event_id = ? AND visitor_id = ?",
                        (event_id, visitor_id),
                    ).fetchone()
                    if row:
                        db.execute(
                            "UPDATE waiting_room_visitors SET status = 'abandoned', abandoned_at = ?, last_seen_at = ? WHERE id = ?",
                            (now_iso(), now_iso(), row["id"]),
                        )
                        audit(db, "public", "waiting_room.abandoned", "waiting_room", row["id"], {"event_id": event_id})
                    db.execute("COMMIT")
                self.send_json({"ok": True})
                return

            if path == "/api/waiting-room/config":
                session = self.effective_user()
                actor = data.get("actor", "Admin")
                if not session or session.get("role") not in ADMIN_ROLES:
                    self.send_json({"error": "Solo Super Admin puede configurar la sala de espera"}, 403)
                    return
                event_id = int(data.get("event_id") or 0)
                with connect() as db:
                    db.execute(
                        """
                        UPDATE events
                        SET waiting_room_enabled = ?, waiting_room_open_at = ?,
                            users_allowed_per_minute = ?, turn_duration_minutes = ?,
                            show_waiting_position = ?, show_estimated_time = ?, waiting_message = ?
                        WHERE id = ?
                        """,
                        (
                            1 if truthy(data.get("waiting_room_enabled")) else 0,
                            str(data.get("waiting_room_open_at") or ""),
                            max(1, int(data.get("users_allowed_per_minute") or 60)),
                            max(1, int(data.get("turn_duration_minutes") or 10)),
                            1 if truthy(data.get("show_position", True)) else 0,
                            1 if truthy(data.get("show_estimated_time", True)) else 0,
                            str(data.get("waiting_message") or "").strip(),
                            event_id,
                        ),
                    )
                    audit(db, actor, "waiting_room.configured", "event", event_id, data)
                self.send_json({"ok": True})
                return

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

            if path == "/api/jobs/cancel":
                session = self.effective_user()
                actor = data.get("actor", "Admin")
                if not session or session.get("role") not in ADMIN_ROLES:
                    self.send_json({"error": "Solo Super Admin puede cancelar jobs"}, 403)
                    return
                ok = job_queue_service().cancel(int(data.get("job_id") or 0), actor)
                self.send_json({"ok": ok}, 200 if ok else 409)
                return

            if path == "/api/simulator/control":
                session = self.effective_user()
                actor = data.get("actor", "Admin")
                if not session or session.get("role") not in ADMIN_ROLES:
                    self.send_json({"error": "Simulador disponible solo para Super Admin"}, 403)
                    return
                event_id = int(data.get("event_id") or 0)
                action = str(data.get("action") or "start")
                status = {"start": "running", "pause": "paused", "stop": "stopped"}.get(action)
                if not status:
                    self.send_json({"error": "Accion invalida"}, 400)
                    return
                with connect() as db:
                    event = db.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
                    if not event or ("demo" not in str(event["name"]).lower() and "demo" not in str(event["description"]).lower()):
                        self.send_json({"error": "El simulador solo puede ejecutarse sobre eventos demo"}, 409)
                        return
                    db.execute(
                        """
                        INSERT INTO simulator_state (
                            event_id, status, mode, scenario, participants_active,
                            accesses_per_minute, rejections_per_minute, simulated_errors,
                            average_occupancy, active_terminals, speed, updated_by, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(event_id) DO UPDATE SET
                            status = excluded.status, mode = excluded.mode, scenario = excluded.scenario,
                            participants_active = excluded.participants_active,
                            accesses_per_minute = excluded.accesses_per_minute,
                            rejections_per_minute = excluded.rejections_per_minute,
                            simulated_errors = excluded.simulated_errors,
                            average_occupancy = excluded.average_occupancy,
                            active_terminals = excluded.active_terminals, speed = excluded.speed,
                            updated_by = excluded.updated_by, updated_at = excluded.updated_at
                        """,
                        (
                            event_id, status, str(data.get("mode") or "medium"), str(data.get("scenario") or "congress"),
                            max(1, int(data.get("participants_active") or 100)),
                            max(0, int(data.get("accesses_per_minute") or 30)),
                            max(0, int(data.get("rejections_per_minute") or 3)),
                            max(0, int(data.get("simulated_errors") or 1)),
                            min(100, max(0, int(data.get("average_occupancy") or 55))),
                            max(1, int(data.get("active_terminals") or 10)),
                            max(0.25, float(data.get("speed") or 1)),
                            actor, now_iso(),
                        ),
                    )
                    audit(db, actor, f"simulator.{action}", "event", event_id, {"status": status})
                self.send_json({"ok": True, "status": status})
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

            if path == "/api/event-landing":
                event_id = int(data.get("event_id") or 0)
                actor = data.get("actor", "Admin")
                action = str(data.get("action") or "upload").strip()
                with DB_LOCK, connect() as db:
                    if not can_actor(db, actor, CONFIG_ROLES):
                        self.send_json(deny_message(actor), 403)
                        return
                    event = db.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
                    if not event:
                        self.send_json({"error": "Evento inexistente"}, 404)
                        return
                    db.execute("BEGIN IMMEDIATE")
                    if action == "delete":
                        db.execute(
                            """
                            UPDATE events
                            SET landing_image_data = '', landing_image_name = '',
                                landing_image_type = '', landing_image_updated_at = ''
                            WHERE id = ?
                            """,
                            (event_id,),
                        )
                        audit(db, actor, "event.landing_image_deleted", "event", event_id, {"event_id": event_id})
                        db.execute("COMMIT")
                        self.send_json({"ok": True, "deleted": True})
                        return
                    try:
                        image = validate_landing_image(str(data.get("image_data") or ""), str(data.get("filename") or ""))
                    except ValueError as exc:
                        db.execute("ROLLBACK")
                        self.send_json({"error": str(exc)}, 400)
                        return
                    db.execute(
                        """
                        UPDATE events
                        SET landing_image_data = ?, landing_image_name = ?,
                            landing_image_type = ?, landing_image_updated_at = ?
                        WHERE id = ?
                        """,
                        (image["data_url"], image["filename"], image["content_type"], now_iso(), event_id),
                    )
                    audit(
                        db,
                        actor,
                        "event.landing_image_uploaded",
                        "event",
                        event_id,
                        {"event_id": event_id, "filename": image["filename"], "width": image["width"], "height": image["height"], "bytes": image["bytes"]},
                    )
                    db.execute("COMMIT")
                self.send_json({"ok": True, "image": {key: image[key] for key in ("filename", "content_type", "width", "height", "bytes")}})
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
                        self.send_json({"error": "Las inscripciones desde portal no estan habilitadas"}, 403)
                        return
                    if event and int(event["reserva_requiere_confirmacion"] or 0) and not truthy(data.get("confirmed")):
                        audit(db, "portal", "portal.reservation_rejected", "activity", activity_id, {"event_id": portal["event_id"], "reason": "confirmation_required"})
                        db.execute("COMMIT")
                        self.send_json({"error": "Debes confirmar manualmente la inscripcion"}, 400)
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
                        self.send_json({"error": "Ya tenes una inscripcion activa para esta actividad"}, 409)
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
                                self.send_json({"error": f"Llegaste a 5 inscripciones seguidas. Espera {wait} segundos antes de continuar.", "wait_seconds": wait, "block": "five_reservations"}, 429)
                                return
                            if elapsed < cooldown:
                                wait = max(1, int(round(cooldown - elapsed)))
                                audit(db, "portal", "portal.reservation_cooldown_blocked", "activity", activity_id, {"event_id": portal["event_id"], "wait_seconds": wait})
                                db.execute("COMMIT")
                                self.send_json({"error": f"Espera {wait} segundos antes de inscribirte a otra actividad", "wait_seconds": wait, "block": "short_cooldown"}, 429)
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
                    self.send_json({"error": "Solo se permite cancelar inscripciones desde el portal"}, 400)
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
                        self.send_json({"error": "Inscripcion inexistente"}, 404)
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
                            primary_action_label, secondary_action_label, whatsapp_number,
                            activity_access_open_minutes_before, activities_enabled,
                            capacity_control_enabled, waitlist_enabled, created_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                            max(0, int(data.get("activity_access_open_minutes_before") or 10)),
                            1 if truthy(data.get("activities_enabled", True)) else 0,
                            1 if truthy(data.get("capacity_control_enabled", True)) else 0,
                            1 if truthy(data.get("waitlist_enabled", False)) else 0,
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
                            primary_action_label, secondary_action_label, whatsapp_number,
                            activity_access_open_minutes_before, activities_enabled,
                            capacity_control_enabled, waitlist_enabled, created_at
                        )
                        VALUES (?, ?, ?, ?, ?, 'published', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                            max(0, int(data.get("activity_access_open_minutes_before") or 10)),
                            1 if truthy(data.get("activities_enabled", True)) else 0,
                            1 if truthy(data.get("capacity_control_enabled", True)) else 0,
                            1 if truthy(data.get("waitlist_enabled", True)) else 0,
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

            if path == "/api/events/clone":
                actor = data.get("actor", "Admin")
                source_event_id = int(data.get("source_event_id") or 0)
                with DB_LOCK, connect() as db:
                    db.execute("BEGIN IMMEDIATE")
                    if not can_actor(db, actor, CONFIG_ROLES):
                        db.execute("ROLLBACK")
                        self.send_json(deny_message(actor), 403)
                        return
                    payload = event_structure_payload(db, source_event_id)
                    if not payload:
                        db.execute("ROLLBACK")
                        self.send_json({"error": "Evento origen inexistente"}, 404)
                        return
                    result = import_event_structure(db, payload, actor, name=str(data.get("name") or f"{payload['event'].get('name', 'Evento')} copia"))
                    audit(db, actor, "event.cloned", "event", result["event_id"], {"source_event_id": source_event_id})
                    db.execute("COMMIT")
                self.send_json(result, 201)
                return

            if path == "/api/event-structure/import":
                actor = data.get("actor", "Admin")
                payload = data.get("structure") or data
                with DB_LOCK, connect() as db:
                    db.execute("BEGIN IMMEDIATE")
                    if not can_actor(db, actor, CONFIG_ROLES):
                        db.execute("ROLLBACK")
                        self.send_json(deny_message(actor), 403)
                        return
                    result = import_event_structure(db, payload, actor, name=data.get("name"))
                    db.execute("COMMIT")
                self.send_json(result, 201)
                return

            if path == "/api/agenda/preview":
                actor = data.get("actor", "Admin")
                event_id = int(data.get("event_id") or 0)
                rows = agenda_rows_from_payload(data)
                if not event_id or not isinstance(rows, list):
                    self.send_json({"error": "Faltan evento o agenda"}, 400)
                    return
                with connect() as db:
                    if not can_actor(db, actor, CONFIG_ROLES):
                        self.send_json(deny_message(actor), 403)
                        return
                    summary = preview_agenda_rows(db, event_id, rows)
                    audit(db, actor, "agenda.previewed", "event", event_id, summary)
                self.send_json({"ok": True, **summary})
                return

            if path == "/api/agenda/import":
                actor = data.get("actor", "Admin")
                event_id = int(data.get("event_id") or 0)
                rows = agenda_rows_from_payload(data)
                if not event_id or not isinstance(rows, list):
                    self.send_json({"error": "Faltan evento o agenda"}, 400)
                    return
                summary = {"created": 0, "updated": 0, "errors": []}
                with DB_LOCK, connect() as db:
                    db.execute("BEGIN IMMEDIATE")
                    if not can_actor(db, actor, CONFIG_ROLES):
                        db.execute("ROLLBACK")
                        self.send_json(deny_message(actor), 403)
                        return
                    for index, row in enumerate(rows, start=1):
                        try:
                            room = str(row.get("Sala") or row.get("sala") or row.get("space") or "").strip()
                            title = str(row.get("Actividad") or row.get("actividad") or row.get("title") or "").strip()
                            date = str(row.get("Fecha") or row.get("fecha") or row.get("date") or "").strip()
                            start_time = str(row.get("Hora inicio") or row.get("hora_inicio") or row.get("start") or "").strip()
                            end_time = str(row.get("Hora fin") or row.get("hora_fin") or row.get("end") or "").strip()
                            if not room or not title or not date or not start_time or not end_time:
                                raise ValueError("faltan sala, actividad, fecha u hora")
                            starts_at = f"{date}T{start_time}"
                            ends_at = f"{date}T{end_time}"
                            space = db.execute("SELECT * FROM spaces WHERE event_id = ? AND name = ?", (event_id, room)).fetchone()
                            if not space:
                                cur_space = db.execute(
                                    "INSERT INTO spaces (event_id, name, capacity, responsible, transition_minutes, status, created_at) VALUES (?, ?, 0, '', 15, 'active', ?)",
                                    (event_id, room, now_iso()),
                                )
                                space_id = int(cur_space.lastrowid)
                            else:
                                space_id = int(space["id"])
                            existing = db.execute(
                                "SELECT * FROM activities WHERE event_id = ? AND space_id = ? AND title = ? AND starts_at = ?",
                                (event_id, space_id, title, starts_at),
                            ).fetchone()
                            conflict = validate_activity_schedule(db, event_id, space_id, starts_at, ends_at, exclude_activity_id=int(existing["id"]) if existing else None)
                            if conflict:
                                raise ValueError(conflict)
                            values = {
                                "description": str(row.get("Descripcion") or row.get("Descripción") or row.get("descripcion") or "").strip(),
                                "speaker": str(row.get("Disertante") or row.get("disertante") or "").strip(),
                                "activity_type": str(row.get("Tipo actividad") or row.get("tipo_actividad") or "Charla").strip() or "Charla",
                                "capacity": int(row.get("Capacidad") or row.get("capacidad") or 0),
                            }
                            if existing:
                                db.execute(
                                    """
                                    UPDATE activities
                                    SET description = ?, speaker = ?, activity_type = ?, starts_at = ?, ends_at = ?, capacity = ?
                                    WHERE id = ?
                                    """,
                                    (values["description"], values["speaker"], values["activity_type"], starts_at, ends_at, values["capacity"], existing["id"]),
                                )
                                summary["updated"] += 1
                            else:
                                db.execute(
                                    """
                                    INSERT INTO activities (
                                        event_id, space_id, title, description, speaker, activity_type,
                                        starts_at, ends_at, capacity, reservation_mode, status, created_at
                                    )
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'free', 'published', ?)
                                    """,
                                    (event_id, space_id, title, values["description"], values["speaker"], values["activity_type"], starts_at, ends_at, values["capacity"], now_iso()),
                                )
                                summary["created"] += 1
                        except Exception as exc:
                            summary["errors"].append({"row": index, "error": str(exc)})
                    ensure_capacity_bags(db, event_id=event_id)
                    audit(db, actor, "agenda.imported", "event", event_id, summary)
                    db.execute("COMMIT")
                self.send_json({"ok": not summary["errors"], **summary})
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
                template_code = data.get("template_code", message_type).strip() or message_type
                audience = data.get("audience", "all").strip() or "all"
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
                    if accreditation_id:
                        rows = communication_audience_rows(db, event_id, "all")
                        recipients = [row for row in rows if int(row["accreditation_id"]) == accreditation_id]
                    else:
                        recipients = communication_audience_rows(db, event_id, audience, data.get("filters") or {})
                    result = queue_communication(db, event_id=event_id, actor=actor, audience=audience, channel=channel, template_code=template_code, subject=subject, content=content, rows=recipients, process_now=truthy(data.get("confirm", True)))
                    audit(db, actor, "communications.queued", "event", event_id, {"channel": channel, "audience": audience, "template": template_code, **result})
                    db.execute("COMMIT")
                queue_ids = result.pop("_email_queue_ids", [])
                whatsapp_ids = result.pop("_whatsapp_queue_ids", [])
                if queue_ids:
                    processed = process_email_queue_items(queue_ids)
                    result["sent"] += processed["sent"]
                    result["errors"] += processed["errors"]
                    result["pending"] = processed["pending"]
                for queue_id in whatsapp_ids:
                    job_queue_service().enqueue("whatsapp.send", {"queue_id": queue_id}, priority="high", actor=actor, event_id=event_id)
                result["pending"] = int(result.get("pending") or 0) + len(whatsapp_ids)
                self.send_json({"ok": True, **result})
                return

            if path in {"/api/communications/email/send", "/api/communications/whatsapp/send"}:
                data["channel"] = "email" if path.endswith("/email/send") else "whatsapp"
                path = "/api/communications/send"
                # Fall through is not possible inside this handler, so repeat with the normalized payload.
                actor = data.get("actor", "Admin")
                event_id = int(data.get("event_id") or 0)
                channel = data["channel"]
                audience = data.get("audience", "all").strip() or "all"
                template_code = data.get("template_code", data.get("type", "manual")).strip() or "manual"
                subject = data.get("subject", "").strip() or ("WhatsApp operativo" if channel == "whatsapp" else "Email operativo")
                content = data.get("content", "").strip()
                if not event_id or not content:
                    self.send_json({"error": "Faltan evento o contenido"}, 400)
                    return
                with DB_LOCK, connect() as db:
                    db.execute("BEGIN IMMEDIATE")
                    if not can_actor(db, actor, CONFIG_ROLES):
                        db.execute("ROLLBACK")
                        self.send_json(deny_message(actor), 403)
                        return
                    recipients = communication_audience_rows(db, event_id, audience, data.get("filters") or {})
                    result = queue_communication(db, event_id=event_id, actor=actor, audience=audience, channel=channel, template_code=template_code, subject=subject, content=content, rows=recipients, process_now=truthy(data.get("confirm", True)))
                    audit(db, actor, f"communications.{channel}_queued", "event", event_id, {"audience": audience, **result})
                    db.execute("COMMIT")
                queue_ids = result.pop("_email_queue_ids", [])
                whatsapp_ids = result.pop("_whatsapp_queue_ids", [])
                if queue_ids:
                    processed = process_email_queue_items(queue_ids)
                    result["sent"] += processed["sent"]
                    result["errors"] += processed["errors"]
                    result["pending"] = processed["pending"]
                for queue_id in whatsapp_ids:
                    job_queue_service().enqueue("whatsapp.send", {"queue_id": queue_id}, priority="high", actor=actor, event_id=event_id)
                result["pending"] = int(result.get("pending") or 0) + len(whatsapp_ids)
                self.send_json({"ok": True, **result})
                return

            if path == "/api/communications/email/test":
                actor = data.get("actor", "Admin")
                event_id = int(data.get("event_id") or 0)
                recipient = str(data.get("email") or "").strip()
                if not event_id or "@" not in recipient:
                    self.send_json({"error": "Indica un email de prueba valido"}, 400)
                    return
                with DB_LOCK, connect() as db:
                    db.execute("BEGIN IMMEDIATE")
                    if not can_actor(db, actor, ADMIN_ROLES):
                        db.execute("ROLLBACK")
                        self.send_json(deny_message(actor), 403)
                        return
                    row = db.execute(
                        """
                        SELECT a.id AS accreditation_id, a.token, a.type, a.status,
                               p.id AS person_id, p.first_name, p.last_name, p.email, p.phone, p.company,
                               e.name AS event_name, e.starts_at, e.ends_at,
                               1 AS acepta_email, 0 AS acepta_whatsapp,
                               ? AS preferred_email, '' AS preferred_phone
                        FROM accreditations a
                        JOIN people p ON p.id = a.person_id
                        JOIN events e ON e.id = a.event_id
                        WHERE a.event_id = ? AND a.status <> 'cancelled'
                        ORDER BY a.id LIMIT 1
                        """,
                        (recipient, event_id),
                    ).fetchone()
                    if not row:
                        db.execute("ROLLBACK")
                        self.send_json({"error": "El evento necesita al menos un participante para probar la cola"}, 400)
                        return
                    result = queue_communication(
                        db,
                        event_id=event_id,
                        actor=actor,
                        audience="test",
                        channel="email",
                        template_code="connection_test",
                        subject=f"Prueba de email BITORA - {row['event_name']}",
                        content="La conexion de email de BITORA funciona correctamente.",
                        rows=[row],
                        process_now=True,
                    )
                    audit(db, actor, "communications.email_test_queued", "event", event_id, {"recipient": recipient})
                    db.execute("COMMIT")
                queue_ids = result.pop("_email_queue_ids", [])
                result.pop("_whatsapp_queue_ids", [])
                processed = process_email_queue_items(queue_ids) if queue_ids else {"sent": result["sent"], "errors": result["errors"], "pending": 0}
                self.send_json({"ok": processed["sent"] > 0, **result, **processed})
                return

            if path == "/api/communications/whatsapp/test":
                actor = data.get("actor", "Admin")
                event_id = int(data.get("event_id") or 0)
                phone = str(data.get("phone") or "").strip()
                message = str(data.get("message") or "Prueba operativa BITORA").strip()
                with connect() as db:
                    if not can_actor(db, actor, ADMIN_ROLES):
                        self.send_json(deny_message(actor), 403)
                        return
                    person = db.execute("SELECT id FROM people WHERE phone = ? LIMIT 1", (phone,)).fetchone()
                    if not person:
                        person_id = db.execute("INSERT INTO people (first_name, last_name, email, phone, created_at) VALUES ('Prueba', 'WhatsApp', ?, ?, ?)", (f"wa-{secrets.token_hex(4)}@bitora.test", phone, now_iso())).lastrowid
                    else:
                        person_id = person["id"]
                    accreditation = db.execute("SELECT id FROM accreditations WHERE event_id = ? AND person_id = ? LIMIT 1", (event_id, person_id)).fetchone()
                    accreditation_id = accreditation["id"] if accreditation else None
                    queue_id = db.execute(
                        """
                        INSERT INTO communication_queue (event_id, person_id, accreditation_id, channel, audience, template_code, subject, content, recipient, status, attempts, max_attempts, provider, created_by, created_at)
                        VALUES (?, ?, ?, 'whatsapp', 'test', 'test', 'Prueba WhatsApp', ?, ?, 'pendiente', 0, ?, ?, ?, ?)
                        """,
                        (event_id, person_id, accreditation_id, message, phone, max(1, int(os.environ.get("WHATSAPP_MAX_RETRIES", "3"))), communication_provider("whatsapp"), actor, now_iso()),
                    ).lastrowid
                    audit(db, actor, "communications.whatsapp_test_queued", "communication_queue", queue_id, {"event_id": event_id})
                job_queue_service().enqueue("whatsapp.send", {"queue_id": queue_id}, priority="high", actor=actor, event_id=event_id)
                self.send_json({"ok": True, "queue_id": queue_id, "status": "pending"})
                return

            if path == "/api/communications/email/retry":
                actor = data.get("actor", "Admin")
                queue_id = int(data.get("queue_id") or 0)
                if not queue_id:
                    self.send_json({"error": "Falta queue_id"}, 400)
                    return
                with connect() as db:
                    if not can_actor(db, actor, ADMIN_ROLES):
                        self.send_json(deny_message(actor), 403)
                        return
                result = process_email_queue_item(queue_id)
                self.send_json(result, 200 if result["ok"] or result["status"] == "pendiente" else 502)
                return

            if path == "/api/communications/email/webhook":
                if not verify_email_webhook(self):
                    self.send_json({"error": "Firma de webhook invalida"}, 401)
                    return
                with DB_LOCK, connect() as db:
                    db.execute("BEGIN IMMEDIATE")
                    result = apply_email_webhook(db, data)
                    db.execute("COMMIT")
                self.send_json(result)
                return

            if path == "/api/communications/whatsapp/webhook":
                with DB_LOCK, connect() as db:
                    db.execute("BEGIN IMMEDIATE")
                    reply = apply_whatsapp_webhook(db, data)
                    db.execute("COMMIT")
                self.send_json(reply)
                return

            if path == "/api/communications/assistant/message":
                event_id = int(data.get("event_id") or 0)
                phone = str(data.get("phone") or "").strip()
                message = str(data.get("message") or "").strip()
                with DB_LOCK, connect() as db:
                    db.execute("BEGIN IMMEDIATE")
                    answer = assistant_reply(db, event_id, phone, message)
                    participant = answer.get("participant") or {}
                    db.execute(
                        """
                        INSERT INTO communication_assistant_history (event_id, person_id, accreditation_id, phone, inbound, outbound, intent, status, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (event_id, participant.get("person_id"), participant.get("accreditation_id"), phone, message, answer["reply"], answer["intent"], answer["status"], now_iso()),
                    )
                    audit(db, data.get("actor", "assistant"), "communications.assistant_message", "event", event_id, {"intent": answer["intent"], "status": answer["status"]})
                    db.execute("COMMIT")
                self.send_json({k: v for k, v in answer.items() if k != "participant"})
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
                    if "activity_ids" in data:
                        activity_ids = []
                        for raw_id in data.get("activity_ids") or []:
                            try:
                                activity_ids.append(int(raw_id))
                            except (TypeError, ValueError):
                                continue
                        activity_ids = list(dict.fromkeys(activity_ids))
                        db.execute("UPDATE public_display_items SET visible = 0 WHERE event_id = ?", (event_id,))
                        for sort_order, activity_id in enumerate(activity_ids, start=1):
                            db.execute(
                                """
                                INSERT INTO public_display_items (event_id, activity_id, sort_order, visible, created_at)
                                VALUES (?, ?, ?, 1, ?)
                                ON CONFLICT(event_id, activity_id)
                                DO UPDATE SET visible = 1, sort_order = excluded.sort_order
                                """,
                                (event_id, activity_id, sort_order, now_iso()),
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
                            access_open_minutes_before,
                            status, created_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'published', ?)
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
                            None if str(data.get("access_open_minutes_before", "")).strip() == "" else max(0, int(data.get("access_open_minutes_before") or 0)),
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
                    self.send_json({"error": "Faltan datos de inscripcion"}, 400)
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
                    self.send_json({"error": "Estado de inscripcion invalido"}, 400)
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
                        self.send_json({"error": "Inscripcion inexistente"}, 404)
                        return
                    promoted = None
                    if status == "confirmed":
                        if reservation["status"] != "waitlisted":
                            db.execute("ROLLBACK")
                            self.send_json({"error": "Solo se puede promover una inscripcion en espera"}, 409)
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
                    self.send_json({"error": "Solo se permite inscribirse a una actividad por vez. Repeti el paso para sumar otra actividad."}, 400)
                    return
                with DB_LOCK, connect() as db:
                    db.execute("BEGIN IMMEDIATE")
                    event = db.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
                    if not event:
                        db.execute("ROLLBACK")
                        self.send_json({"error": "Evento inexistente"}, 404)
                        return
                    waiting_row = None
                    if int(event["waiting_room_enabled"] or 0) and data.get("actor") == "public":
                        waiting_token = str(data.get("waiting_room_token") or "").strip()
                        waiting_row = db.execute(
                            """
                            SELECT * FROM waiting_room_visitors
                            WHERE event_id = ? AND access_token = ? AND status = 'admitted'
                            """,
                            (event_id, waiting_token),
                        ).fetchone()
                        expires = parse_dt(waiting_row["expires_at"]) if waiting_row and waiting_row["expires_at"] else None
                        if not waiting_row or (expires and datetime.now(timezone.utc) >= expires.astimezone(timezone.utc)):
                            db.execute("ROLLBACK")
                            self.send_json({"error": "Necesitas un turno vigente de la sala de espera"}, 403)
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
                    if waiting_row:
                        db.execute(
                            "UPDATE waiting_room_visitors SET status = 'completed', completed_at = ?, last_seen_at = ? WHERE id = ?",
                            (now_iso(), now_iso(), waiting_row["id"]),
                        )
                        audit(db, "public", "waiting_room.completed", "waiting_room", waiting_row["id"], {"event_id": event_id, "accreditation_id": registration["id"]})
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
        except DB_INTEGRITY_ERRORS as exc:
            technical_log("warning", "api.post", "Dato duplicado o invalido", str(exc), path)
            self.send_json({"error": "Dato duplicado o invalido", "detail": str(exc)}, 409)
        except Exception as exc:
            technical_log("error", "api.post", "Error procesando solicitud", str(exc), path)
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
    start_job_worker()
    start_simulator_loop()
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
        SIMULATOR_STOP.set()
        if WORKER:
            WORKER.stop()
        httpd.server_close()


if __name__ == "__main__":
    main()
