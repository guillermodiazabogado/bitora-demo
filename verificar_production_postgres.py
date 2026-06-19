from __future__ import annotations

import os
from pathlib import Path

from backend.database import DatabaseConfig, connect_database, run_postgres_migrations


def main() -> None:
    database_source = Path("backend/database.py").read_text(encoding="utf-8")
    migrations = sorted(Path("backend/migrations").glob("*.sql"))
    migration_text = "\n".join(path.read_text(encoding="utf-8") for path in migrations)
    assert "ConnectionPool" in database_source
    assert "check_connection" in database_source
    assert "range(2)" in database_source
    assert "idx_accreditations_token" in migration_text
    assert "idx_access_logs_event_created" in migration_text
    assert "idx_reservations_activity_status" in migration_text
    assert "008_multivertical.sql" in {path.name for path in migrations}

    dsn = os.environ.get("QR_POSTGRES_DSN", "").strip()
    if dsn:
        config = DatabaseConfig("postgres", "acreditaciones.sqlite3", dsn, 1, 4)
        run_postgres_migrations(config, Path("backend/migrations"))
        with connect_database(config) as db:
            assert db.execute("SELECT 1 AS ok").fetchone()["ok"] == 1
            applied = {row["version"] for row in db.execute("SELECT version FROM schema_migrations").fetchall()}
            assert "008_multivertical.sql" in applied
            indexes = {
                row["indexname"]
                for row in db.execute("SELECT indexname FROM pg_indexes WHERE schemaname = 'public'").fetchall()
            }
            assert "idx_accreditations_token" in indexes
        print("OK: PostgreSQL real conectado, migrado e indexado")
    else:
        print("OK: preparacion PostgreSQL validada; prueba real pendiente de QR_POSTGRES_DSN")


if __name__ == "__main__":
    main()
