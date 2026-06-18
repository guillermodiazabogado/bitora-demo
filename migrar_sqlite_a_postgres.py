from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from backend.database import DatabaseConfig, run_postgres_migrations


ROOT = Path(__file__).resolve().parent
MIGRATIONS = ROOT / "backend" / "migrations"
BACKUPS = ROOT / "backups"
REPORTS = ROOT / "output" / "migration"

TABLE_ORDER = [
    "events",
    "people",
    "users",
    "accreditations",
    "accreditation_types",
    "spaces",
    "activities",
    "capacity_bags",
    "reservations",
    "public_display_config",
    "public_display_items",
    "access_logs",
    "audit_logs",
    "participant_communication_preferences",
    "communication_logs",
    "communication_queue",
    "email_delivery_events",
    "communication_assistant_history",
    "communication_tickets",
    "communication_templates",
    "participant_announcements",
    "captation_events",
    "conversation_sources",
    "activity_attendance",
    "certificate_eligibility",
]


def parse_args():
    parser = argparse.ArgumentParser(description="Migra BITORA desde SQLite a PostgreSQL")
    parser.add_argument("--sqlite", default=os.environ.get("QR_SQLITE_PATH", "acreditaciones.sqlite3"))
    parser.add_argument("--dsn", default=os.environ.get("QR_POSTGRES_DSN", ""))
    parser.add_argument("--replace", action="store_true", help="Vaciar tablas PostgreSQL antes de copiar")
    return parser.parse_args()


def main():
    args = parse_args()
    sqlite_path = Path(args.sqlite).resolve()
    if not sqlite_path.exists():
        raise SystemExit(f"SQLite inexistente: {sqlite_path}")
    if not args.dsn:
        raise SystemExit("Falta QR_POSTGRES_DSN o --dsn")

    try:
        import psycopg
        from psycopg import sql
        from psycopg.rows import dict_row
    except ImportError as exc:
        raise SystemExit("Instalar psycopg con: pip install -r requirements.txt") from exc

    BACKUPS.mkdir(exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = BACKUPS / f"pre-postgres-{stamp}.sqlite3"
    shutil.copy2(sqlite_path, backup_path)

    config = DatabaseConfig(engine="postgres", sqlite_path=str(sqlite_path), postgres_dsn=args.dsn)
    migrations = run_postgres_migrations(config, MIGRATIONS)
    source = sqlite3.connect(sqlite_path)
    source.row_factory = sqlite3.Row
    counts: dict[str, dict[str, int | bool]] = {}

    with psycopg.connect(args.dsn, row_factory=dict_row) as target:
        with target.transaction():
            if args.replace:
                target.execute(
                    sql.SQL("TRUNCATE {} RESTART IDENTITY CASCADE").format(
                        sql.SQL(", ").join(sql.Identifier(table) for table in reversed(TABLE_ORDER))
                    )
                )
            else:
                occupied = {
                    table: target.execute(sql.SQL("SELECT COUNT(*) AS c FROM {}").format(sql.Identifier(table))).fetchone()["c"]
                    for table in TABLE_ORDER
                }
                non_empty = {table: count for table, count in occupied.items() if count}
                if non_empty:
                    raise RuntimeError(f"PostgreSQL no esta vacio: {non_empty}. Usar --replace si corresponde.")

            target.execute("SET CONSTRAINTS ALL DEFERRED")
            for table in TABLE_ORDER:
                exists = source.execute(
                    "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                    (table,),
                ).fetchone()
                rows = [dict(row) for row in source.execute(f'SELECT * FROM "{table}" ORDER BY 1').fetchall()] if exists else []
                if rows:
                    columns = list(rows[0])
                    statement = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
                        sql.Identifier(table),
                        sql.SQL(", ").join(sql.Identifier(column) for column in columns),
                        sql.SQL(", ").join(sql.Placeholder() for _ in columns),
                    )
                    target.executemany(statement, [[row[column] for column in columns] for row in rows])
                counts[table] = {"sqlite": len(rows), "postgres": 0, "ok": False}

            for table in TABLE_ORDER:
                if table == "public_display_config":
                    continue
                target.execute(
                    sql.SQL(
                        "SELECT setval(pg_get_serial_sequence(%s, 'id'), COALESCE((SELECT MAX(id) FROM {}), 1), "
                        "COALESCE((SELECT MAX(id) FROM {}), 0) > 0)"
                    ).format(sql.Identifier(table), sql.Identifier(table)),
                    (table,),
                )

        for table in TABLE_ORDER:
            target_count = int(target.execute(sql.SQL("SELECT COUNT(*) AS c FROM {}").format(sql.Identifier(table))).fetchone()["c"])
            counts[table]["postgres"] = target_count
            counts[table]["ok"] = counts[table]["sqlite"] == target_count

    source.close()
    ok = all(bool(item["ok"]) for item in counts.values())
    report = {
        "ok": ok,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "sqlite": str(sqlite_path),
        "backup": str(backup_path),
        "migrations_applied": migrations,
        "counts": counts,
    }
    report_path = REPORTS / f"sqlite-a-postgres-{stamp}.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not ok:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
