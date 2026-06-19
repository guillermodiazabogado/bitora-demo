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

    @property
    def production_ready(self) -> bool:
        return self.engine == "postgres" and bool(self.postgres_dsn)


def load_database_config() -> DatabaseConfig:
    engine = os.environ.get("QR_DB_ENGINE", "sqlite").strip().lower()
    if engine not in {"sqlite", "postgres"}:
        raise ValueError("QR_DB_ENGINE debe ser sqlite o postgres")
    return DatabaseConfig(
        engine=engine,
        sqlite_path=os.environ.get("QR_SQLITE_PATH", "acreditaciones.sqlite3"),
        postgres_dsn=os.environ.get("QR_POSTGRES_DSN", "").strip(),
        postgres_pool_min=max(1, int(os.environ.get("QR_POSTGRES_POOL_MIN", "1"))),
        postgres_pool_max=max(1, int(os.environ.get("QR_POSTGRES_POOL_MAX", "10"))),
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


def run_postgres_migrations(config: DatabaseConfig, migrations_dir: Path) -> list[str]:
    if config.engine != "postgres":
        return []
    if not config.postgres_dsn:
        raise RuntimeError("QR_POSTGRES_DSN es obligatorio cuando QR_DB_ENGINE=postgres")
    psycopg, dict_row = _load_psycopg()
    applied: list[str] = []
    with psycopg.connect(config.postgres_dsn, row_factory=dict_row) as conn:
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
    return applied


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
    "activity_attendance",
    "audit_logs",
    "capacity_bags",
    "captation_events",
    "certificate_eligibility",
    "communication_assistant_history",
    "communication_logs",
    "communication_queue",
    "communication_templates",
    "communication_tickets",
    "conversation_sources",
    "email_delivery_events",
    "events",
    "jobs",
    "participant_announcements",
    "participant_communication_preferences",
    "people",
    "public_display_items",
    "reservations",
    "spaces",
    "technical_logs",
    "users",
    "visualization_layouts",
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
                    kwargs={"autocommit": True, "row_factory": dict_row},
                    open=True,
                    check=ConnectionPool.check_connection,
                )
            raw = _POSTGRES_POOL.getconn(timeout=10)
            raw.execute("SELECT 1")
            return PostgresConnection(raw, _POSTGRES_POOL)
        except Exception as exc:
            last_error = exc
            if _POSTGRES_POOL is not None:
                try:
                    _POSTGRES_POOL.close()
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
