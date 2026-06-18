from __future__ import annotations

import os
from pathlib import Path

from backend.database import (
    DatabaseConfig,
    connect_database,
    postgres_driver_available,
    run_postgres_migrations,
)
from backend.repositories import PostgresRepository


ROOT = Path(__file__).resolve().parent


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def static_checks():
    migrations = sorted((ROOT / "backend" / "migrations").glob("*.sql"))
    require(len(migrations) >= 2, "Faltan migraciones PostgreSQL versionadas")
    schema = "\n".join(path.read_text(encoding="utf-8") for path in migrations)
    for table in (
        "events",
        "people",
        "accreditations",
        "activities",
        "reservations",
        "access_logs",
        "audit_logs",
        "communication_queue",
        "email_delivery_events",
        "activity_attendance",
    ):
        require(f"CREATE TABLE IF NOT EXISTS {table}" in schema, f"Falta tabla {table}")
    require("uq_activity_granted_access" in schema, "Falta proteccion contra doble acceso a actividad")
    require("FOR UPDATE" in (ROOT / "backend" / "repositories" / "postgres.py").read_text(encoding="utf-8"), "Faltan bloqueos de fila")
    require("psycopg" in (ROOT / "requirements.txt").read_text(encoding="utf-8"), "Falta driver PostgreSQL")


def live_checks(dsn: str):
    config = DatabaseConfig(engine="postgres", sqlite_path="", postgres_dsn=dsn)
    applied = run_postgres_migrations(config, ROOT / "backend" / "migrations")
    repository = PostgresRepository()
    with connect_database(config) as db:
        db.execute("BEGIN")
        try:
            stamp = "2099-01-01T00:00:00+00:00"
            event = db.execute(
                "INSERT INTO events (name, created_at) VALUES (?, ?)",
                ("BITORA verificar_postgres", stamp),
            )
            event_id = event.lastrowid
            person = db.execute(
                "INSERT INTO people (first_name, last_name, email, created_at) VALUES (?, ?, ?, ?)",
                ("Postgres", "Test", f"postgres-{event_id}@bitora.test", stamp),
            )
            accreditation = db.execute(
                "INSERT INTO accreditations (event_id, person_id, token, created_at) VALUES (?, ?, ?, ?)",
                (event_id, person.lastrowid, f"EVT-PG{event_id}", stamp),
            )
            row = repository.accreditation_for_access(db, f"EVT-PG{event_id}")
            require(row and row["id"] == accreditation.lastrowid, "No se recupero acreditacion/QR")
            repository.add_access_log(
                db,
                accreditation_id=accreditation.lastrowid,
                event_id=event_id,
                token=f"EVT-PG{event_id}",
                operator="verificar_postgres",
                checkpoint="General",
                result="granted",
                reason="OK",
                created_at=stamp,
            )
            repository.insert_audit(
                db,
                actor="verificar_postgres",
                action="postgres.checked",
                entity_type="event",
                entity_id=event_id,
                payload_json="{}",
                created_at=stamp,
            )
            require(db.execute("SELECT COUNT(*) AS c FROM access_logs WHERE event_id = ?", (event_id,)).fetchone()["c"] == 1, "Fallo acceso")
            require(db.execute("SELECT COUNT(*) AS c FROM audit_logs WHERE entity_id = ?", (event_id,)).fetchone()["c"] == 1, "Fallo auditoria")
        finally:
            db.execute("ROLLBACK")
    print(f"OK postgres live migrations={applied}")


def main():
    static_checks()
    require(postgres_driver_available(), "Driver psycopg no instalado")
    dsn = os.environ.get("QR_POSTGRES_DSN", "").strip()
    if not dsn:
        print("OK postgres static; live=SKIP (QR_POSTGRES_DSN no configurado)")
        return
    live_checks(dsn)


if __name__ == "__main__":
    main()
