from __future__ import annotations

import os
import re
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DatabaseConfig:
    engine: str
    sqlite_path: str
    postgres_dsn: str
    postgres_pool_min: int = 1
    postgres_pool_max: int = 10
    connection_timeout: int = 10
    statement_timeout_ms: int = 30000

    @property
    def production_ready(self) -> bool:
        return self.engine == "postgres" and bool(self.postgres_dsn)


def load_database_config() -> DatabaseConfig:
    engine = os.environ.get("QR_DB_ENGINE") or os.environ.get("DATABASE_ENGINE") or "sqlite"
    engine = engine.strip().lower()
    if engine in {"postgresql", "pg"}:
        engine = "postgres"
    if engine not in {"sqlite", "postgres"}:
        raise ValueError("QR_DB_ENGINE/DATABASE_ENGINE debe ser sqlite o postgres")
    postgres_dsn = os.environ.get("QR_POSTGRES_DSN") or os.environ.get("DATABASE_URL") or ""
    return DatabaseConfig(
        engine=engine,
        sqlite_path=os.environ.get("QR_SQLITE_PATH", "acreditaciones.sqlite3"),
        postgres_dsn=postgres_dsn.strip(),
        postgres_pool_min=max(1, int(os.environ.get("QR_POSTGRES_POOL_MIN") or os.environ.get("DB_POOL_MIN") or "1")),
        postgres_pool_max=max(1, int(os.environ.get("QR_POSTGRES_POOL_MAX") or os.environ.get("DB_POOL_MAX") or "10")),
        connection_timeout=max(1, int(os.environ.get("DB_CONNECTION_TIMEOUT", "10"))),
        statement_timeout_ms=max(1000, int(os.environ.get("DB_STATEMENT_TIMEOUT_MS", "30000"))),
    )


def connect_database(config: DatabaseConfig, sqlite_path: Path | None = None):
    if config.engine == "postgres":
        return _postgres_connection(config)
    path = sqlite_path or Path(config.sqlite_path)
    conn = sqlite3.connect(path, timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 30000")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def connect_database_probe(config: DatabaseConfig, sqlite_path: Path | None = None, *, timeout_seconds: int = 1):
    """Open a short-lived, fail-fast connection for health/readiness probes."""
    if config.engine != "postgres":
        return connect_database(config, sqlite_path)
    if not config.postgres_dsn:
        raise RuntimeError("QR_POSTGRES_DSN es obligatorio cuando QR_DB_ENGINE=postgres")
    psycopg, dict_row = _load_psycopg()
    return psycopg.connect(
        config.postgres_dsn,
        row_factory=dict_row,
        autocommit=True,
        connect_timeout=max(1, int(timeout_seconds)),
    )


def run_postgres_migrations(config: DatabaseConfig, migrations_dir: Path) -> list[str]:
    if config.engine != "postgres":
        return []
    if not config.postgres_dsn:
        raise RuntimeError("QR_POSTGRES_DSN es obligatorio cuando QR_DB_ENGINE=postgres")
    psycopg, dict_row = _load_psycopg()
    applied: list[str] = []
    with psycopg.connect(config.postgres_dsn, row_factory=dict_row, autocommit=True) as conn:
        conn.execute("SELECT pg_advisory_lock(74867201)")
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version TEXT PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            known = {row["version"] for row in conn.execute("SELECT version FROM schema_migrations").fetchall()}
            for path in sorted(migrations_dir.glob("*.sql")):
                if path.name in known:
                    continue
                sql = path.read_text(encoding="utf-8")
                with conn.transaction():
                    conn.execute(sql)
                    conn.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (path.name,))
                applied.append(path.name)
        finally:
            conn.execute("SELECT pg_advisory_unlock(74867201)")
    return applied


def migration_status(connection: Any, migrations_dir: Path) -> dict[str, Any]:
    """Compare the exact migration file set with the database ledger."""
    expected = sorted(path.name for path in migrations_dir.glob("*.sql"))
    rows = connection.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()
    applied = sorted(str(row["version"]) for row in rows)
    expected_set = set(expected)
    applied_set = set(applied)
    missing = sorted(expected_set - applied_set)
    unexpected = sorted(applied_set - expected_set)
    duplicates = sorted(version for version in applied_set if applied.count(version) > 1)
    return {
        "ok": not missing and not unexpected and not duplicates and len(applied) == len(expected),
        "expected_count": len(expected),
        "applied_count": len(applied),
        "missing": missing,
        "unexpected": unexpected,
        "duplicates": duplicates,
    }


def postgres_driver_available() -> bool:
    try:
        _load_psycopg()
        return True
    except RuntimeError:
        return False


def integrity_error_types():
    errors: list[type[BaseException]] = [sqlite3.IntegrityError]
    try:
        psycopg, _dict_row = _load_psycopg()
        errors.append(psycopg.IntegrityError)
    except RuntimeError:
        pass
    return tuple(errors)


def is_postgres_connection(connection: Any) -> bool:
    return getattr(connection, "engine", "") == "postgres"


_POSTGRES_POOL = None
_ID_TABLES = {
    "access_logs",
    "accreditation_types",
    "accreditations",
    "activities",
    "analytics_v4_data_quality_issues",
    "analytics_v4_export_jobs",
    "analytics_v4_reports",
    "analytics_v4_saved_views",
    "analytics_v4_snapshots",
    "activity_attendance",
    "attendance_corrections",
    "attendance_closures",
    "attendance_eligibility_decisions",
    "attendance_evaluation_items",
    "attendance_evaluations",
    "attendance_events",
    "attendance_overrides",
    "attendance_records",
    "attendance_reopenings",
    "attendance_rule_set_versions",
    "attendance_rule_sets",
    "audit_logs",
    "auth_login_rate_limits",
    "capacity_bags",
    "captation_events",
    "certificate_eligibility",
    "certificate_batches",
    "certificate_documents",
    "certificate_issuances",
    "certificate_number_sequences",
    "certificate_reissuances",
    "certificate_revocations",
    "certificate_template_versions",
    "certificate_templates",
    "certificate_types",
    "certificate_verification_tokens",
    "communication_assistant_history",
    "communication_logs",
    "communication_queue",
    "communication_templates",
    "communication_tickets",
    "communication_v4_approvals",
    "communication_v4_attempts",
    "communication_v4_automation_runs",
    "communication_v4_automations",
    "communication_v4_campaign_recipients",
    "communication_v4_campaigns",
    "communication_v4_consents",
    "communication_v4_deliveries",
    "communication_v4_messages",
    "communication_v4_provider_events",
    "communication_v4_segments",
    "communication_v4_suppressions",
    "communication_v4_template_versions",
    "communication_v4_templates",
    "communication_v4_unsubscribes",
    "conversation_sources",
    "duplicate_resolution_decisions",
    "email_delivery_events",
    "email_suppressions",
    "enterprise_credentials",
    "enterprise_access_comparisons",
    "enterprise_access_events",
    "enterprise_access_state_snapshots",
    "enterprise_credential_revocations",
    "enterprise_device_heartbeats",
    "enterprise_devices",
    "enterprise_event_edges",
    "enterprise_device_profiles",
    "enterprise_device_pairing_codes",
    "enterprise_pairing_rate_limits",
    "enterprise_capability_execution_classes",
    "enterprise_edge_checkpoints",
    "enterprise_edge_queue",
    "enterprise_edge_reconciliations",
    "enterprise_entitlement_adjustments",
    "enterprise_entitlement_consumptions",
    "enterprise_entitlement_grant_batches",
    "enterprise_entitlement_types",
    "enterprise_event_datasets",
    "enterprise_approval_requests",
    "enterprise_companies",
    "enterprise_company_event_participation",
    "enterprise_company_quotas",
    "enterprise_company_users",
    "enterprise_delegation_members",
    "enterprise_delegations",
    "enterprise_domain_events",
    "enterprise_doors",
    "enterprise_entities",
    "enterprise_entitlements",
    "enterprise_import_jobs",
    "enterprise_invitations",
    "enterprise_lead_consents",
    "enterprise_lead_exports",
    "enterprise_lead_interactions",
    "enterprise_lead_licenses",
    "enterprise_leads",
    "enterprise_identities",
    "enterprise_rules",
    "enterprise_service_points",
    "enterprise_stands",
    "enterprise_logistics_destinations",
    "enterprise_vehicle_access_events",
    "enterprise_vehicle_access_slots",
    "enterprise_vehicle_event_participation",
    "enterprise_vehicle_import_jobs",
    "enterprise_vehicle_state_snapshots",
    "enterprise_vehicles",
    "enterprise_alert_rules",
    "enterprise_operational_alerts",
    "enterprise_venues",
    "enterprise_venue_maps",
    "enterprise_venue_map_elements",
    "enterprise_event_map_configurations",
    "event_zones",
    "events",
    "event_integrations",
    "feature_flags",
    "functional_closure_actions",
    "functional_closure_findings",
    "functional_closure_gate_results",
    "functional_closure_reviews",
    "google_oauth_states",
    "jobs",
    "networking_classifications",
    "networking_contact_channels",
    "networking_contacts",
    "networking_event_participations",
    "networking_interaction_events",
    "networking_intents",
    "networking_organizations",
    "networking_taxonomy_concepts",
    "organization_integrations",
    "organization_users",
    "organizations",
    "operations_center_alerts",
    "operations_center_incidents",
    "operations_center_tasks",
    "participant_announcements",
    "participant_communication_preferences",
    "people",
    "public_display_items",
    "reservations",
    "spaces",
    "survey_access_tokens",
    "survey_answer_options",
    "survey_answers",
    "survey_assignments",
    "survey_question_options",
    "survey_questions",
    "survey_response_sessions",
    "survey_types",
    "survey_versions",
    "surveys",
    "speaker_access_tokens",
    "speaker_activity_assignments",
    "speaker_documents",
    "speaker_event_assignments",
    "speaker_private_details",
    "speaker_profile_versions",
    "speaker_profiles",
    "technical_logs",
    "users",
    "visualization_layouts",
    "zone_access_assignments",
    "zone_access_overrides",
    "zone_access_validations",
    "whatsapp_delivery_events",
    "whatsapp_suppressions",
}


def _load_psycopg():
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as exc:
        raise RuntimeError(
            "PostgreSQL requiere psycopg. Instalar dependencias con: pip install -r requirements.txt"
        ) from exc
    return psycopg, dict_row


def _postgres_connection(config: DatabaseConfig):
    global _POSTGRES_POOL
    if not config.postgres_dsn:
        raise RuntimeError("QR_POSTGRES_DSN es obligatorio cuando QR_DB_ENGINE=postgres")
    psycopg, dict_row = _load_psycopg()
    try:
        from psycopg_pool import ConnectionPool
    except ImportError as exc:
        raise RuntimeError("PostgreSQL requiere psycopg_pool") from exc
    last_error = None
    for attempt in range(2):
        try:
            if _POSTGRES_POOL is None:
                _POSTGRES_POOL = ConnectionPool(
                    conninfo=config.postgres_dsn,
                    min_size=config.postgres_pool_min,
                    max_size=max(config.postgres_pool_min, config.postgres_pool_max),
                    timeout=config.connection_timeout,
                    reconnect_timeout=config.connection_timeout,
                    kwargs={"autocommit": True, "row_factory": dict_row},
                    open=True,
                    check=ConnectionPool.check_connection,
                )
            raw = _POSTGRES_POOL.getconn(timeout=config.connection_timeout)
            raw.execute("SELECT 1")
            raw.execute("SELECT set_config('statement_timeout', %s, false)", (str(config.statement_timeout_ms),))
            return PostgresConnection(raw, _POSTGRES_POOL)
        except Exception as exc:
            last_error = exc
            if _POSTGRES_POOL is not None:
                try:
                    _POSTGRES_POOL.close(timeout=config.connection_timeout)
                except Exception:
                    pass
                _POSTGRES_POOL = None
            if attempt == 0:
                time.sleep(0.25)
    raise RuntimeError("No se pudo conectar temporalmente con PostgreSQL") from last_error


class PostgresCursor:
    def __init__(self, cursor, lastrowid: int | None = None) -> None:
        self._cursor = cursor
        self.lastrowid = lastrowid

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def __iter__(self):
        return iter(self._cursor)

    @property
    def rowcount(self) -> int:
        return self._cursor.rowcount


class PostgresConnection:
    engine = "postgres"

    def __init__(self, raw, pool) -> None:
        self.raw = raw
        self.pool = pool
        self._closed = False

    def execute(self, sql: str, params: Any = ()) -> PostgresCursor:
        translated = _translate_sql(sql)
        if translated == "__PRAGMA_OK__":
            cursor = self.raw.execute("SELECT 'ok' AS quick_check")
            return PostgresCursor(cursor)
        if translated == "__PRAGMA_NOOP__":
            cursor = self.raw.execute("SELECT 1 AS ok")
            return PostgresCursor(cursor)
        wants_id = _insert_target(translated) in _ID_TABLES and " returning " not in translated.lower()
        if wants_id:
            translated = translated.rstrip().rstrip(";") + " RETURNING id"
        cursor = self.raw.execute(translated, tuple(params or ()))
        lastrowid = None
        if wants_id:
            row = cursor.fetchone()
            if row:
                lastrowid = int(row["id"])
        return PostgresCursor(cursor, lastrowid)

    def executescript(self, sql: str) -> None:
        self.raw.execute(sql)

    def commit(self) -> None:
        self.raw.commit()

    def rollback(self) -> None:
        self.raw.rollback()

    def close(self) -> None:
        if not self._closed:
            self.pool.putconn(self.raw)
            self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        try:
            if exc_type:
                self.rollback()
            elif self.raw.info.transaction_status:
                self.commit()
        finally:
            self.close()
        return False


def _insert_target(sql: str) -> str:
    match = re.match(r"\s*INSERT\s+INTO\s+([a-zA-Z_][a-zA-Z0-9_]*)", sql, re.I)
    return match.group(1).lower() if match else ""


def _translate_sql(sql: str) -> str:
    stripped = sql.strip()
    upper = stripped.upper()
    if upper.startswith("PRAGMA QUICK_CHECK"):
        return "__PRAGMA_OK__"
    table_info = re.match(r"PRAGMA\s+table_info\(\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\)", stripped, re.I)
    if table_info:
        table = table_info.group(1).lower()
        return (
            "SELECT column_name AS name "
            "FROM information_schema.columns "
            f"WHERE table_schema = 'public' AND table_name = '{table}' "
            "ORDER BY ordinal_position"
        )
    if upper.startswith("PRAGMA"):
        return "__PRAGMA_NOOP__"
    if upper == "BEGIN IMMEDIATE":
        return "BEGIN"

    translated = re.sub(r"\bINSERT\s+OR\s+IGNORE\s+INTO\b", "INSERT INTO", sql, flags=re.I)
    insert_ignore = bool(re.search(r"\bINSERT\s+OR\s+IGNORE\s+INTO\b", sql, flags=re.I))
    translated = re.sub(r"\s+COLLATE\s+NOCASE\b", "", translated, flags=re.I)
    translated = re.sub(
        r"datetime\(\s*'now'\s*,\s*'-(\d+)\s+minutes?'\s*\)",
        r"(CURRENT_TIMESTAMP - INTERVAL '\1 minutes')",
        translated,
        flags=re.I,
    )
    translated = re.sub(r"datetime\(\s*([a-zA-Z_][a-zA-Z0-9_.]*)\s*\)", r"(\1)::timestamptz", translated, flags=re.I)
    translated = _qmark_to_percent(translated)
    if insert_ignore and " ON CONFLICT " not in translated.upper():
        translated = translated.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"
    return translated


def _qmark_to_percent(sql: str) -> str:
    result: list[str] = []
    quote = ""
    index = 0
    while index < len(sql):
        char = sql[index]
        if quote:
            result.append(char)
            if char == quote:
                if index + 1 < len(sql) and sql[index + 1] == quote:
                    result.append(sql[index + 1])
                    index += 1
                else:
                    quote = ""
        elif char in {"'", '"'}:
            quote = char
            result.append(char)
        elif char == "?":
            result.append("%s")
        else:
            result.append(char)
        index += 1
    return "".join(result)
