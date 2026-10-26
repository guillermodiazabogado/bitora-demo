from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import uuid
from urllib.parse import urlparse

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "backend" / "migrations"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.database import DatabaseConfig, migration_status, run_postgres_migrations


def migration_inventory() -> dict:
    names = sorted(path.name for path in MIGRATIONS.glob("*.sql"))
    prefixes: dict[str, list[str]] = {}
    for name in names:
        prefixes.setdefault(name.split("_", 1)[0], []).append(name)
    return {
        "names": names,
        "duplicate_sequence_prefixes": {key: value for key, value in prefixes.items() if len(value) > 1},
    }


def require_safe_admin_dsn() -> str:
    dsn = os.environ.get("BITORA_CERT_POSTGRES_DSN", "").strip()
    if not dsn:
        raise RuntimeError("BITORA_CERT_POSTGRES_DSN_REQUIRED")
    parsed = urlparse(dsn)
    if parsed.hostname not in {"127.0.0.1", "localhost", "::1"} and os.environ.get("BITORA_CERT_ALLOW_REMOTE") != "1":
        raise RuntimeError("REMOTE_POSTGRES_REQUIRES_BITORA_CERT_ALLOW_REMOTE=1")
    if os.environ.get("BITORA_CERT_CONFIRM") != "TEMPORARY_DATABASES":
        raise RuntimeError("BITORA_CERT_CONFIRM=TEMPORARY_DATABASES_REQUIRED")
    return dsn


def database_dsn(admin_dsn: str, database: str) -> str:
    parsed = urlparse(admin_dsn)
    return parsed._replace(path=f"/{database}").geturl()


def config(dsn: str) -> DatabaseConfig:
    return DatabaseConfig(engine="postgres", sqlite_path="", postgres_dsn=dsn)


def schema_fingerprint(dsn: str) -> dict[str, list[dict]]:
    columns_query = """
        SELECT c.table_name, c.column_name, c.ordinal_position, c.data_type,
               c.is_nullable, COALESCE(c.column_default, '') AS column_default
        FROM information_schema.columns c
        WHERE c.table_schema = 'public' AND c.table_name <> 'schema_migrations'
        ORDER BY c.table_name, c.ordinal_position
    """
    constraints_query = """
        SELECT tc.table_name, tc.constraint_name, tc.constraint_type,
               COALESCE(kcu.column_name, '') AS column_name,
               COALESCE(kcu.ordinal_position, 0) AS ordinal_position
        FROM information_schema.table_constraints tc
        LEFT JOIN information_schema.key_column_usage kcu
          ON kcu.constraint_schema = tc.constraint_schema
         AND kcu.constraint_name = tc.constraint_name
         AND kcu.table_name = tc.table_name
        WHERE tc.table_schema = 'public' AND tc.table_name <> 'schema_migrations'
          -- PostgreSQL exposes internal NOT NULL constraints with names that
          -- embed relation OIDs (for example 2200_16399_10_not_null). Their
          -- semantics are already captured by columns.is_nullable; their
          -- generated names necessarily differ between temporary databases.
          AND NOT (
              tc.constraint_type = 'CHECK'
              AND tc.constraint_name ~ '^[0-9]+_[0-9]+_[0-9]+_not_null$'
          )
        ORDER BY tc.table_name, tc.constraint_name, ordinal_position
    """
    indexes_query = """
        SELECT tablename AS table_name, indexname AS index_name, indexdef AS definition
        FROM pg_indexes
        WHERE schemaname = 'public' AND tablename <> 'schema_migrations'
        ORDER BY tablename, indexname
    """
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        fingerprint = {
            "columns": [dict(row) for row in conn.execute(columns_query).fetchall()],
            "constraints": [dict(row) for row in conn.execute(constraints_query).fetchall()],
            "indexes": [dict(row) for row in conn.execute(indexes_query).fetchall()],
        }
    # PostgreSQL catalog queries may return tied rows in a different physical
    # order across two otherwise identical databases. Compare a canonical
    # representation so the gate measures schema semantics, not heap order.
    return {
        key: sorted(rows, key=lambda row: json.dumps(row, sort_keys=True, default=str))
        for key, rows in fingerprint.items()
    }


def fingerprint_diff(clean: dict[str, list[dict]], upgrade: dict[str, list[dict]]) -> dict:
    differences = {}
    for key in clean:
        clean_rows = {json.dumps(row, sort_keys=True, default=str) for row in clean[key]}
        upgrade_rows = {json.dumps(row, sort_keys=True, default=str) for row in upgrade[key]}
        if clean_rows != upgrade_rows:
            differences[key] = {
                "only_clean": [json.loads(row) for row in sorted(clean_rows - upgrade_rows)[:20]],
                "only_upgrade": [json.loads(row) for row in sorted(upgrade_rows - clean_rows)[:20]],
            }
    return differences


def certify() -> dict:
    admin_dsn = require_safe_admin_dsn()
    run_id = uuid.uuid4().hex[:10]
    clean_name = f"bitora_cert_{run_id}_clean"
    upgrade_name = f"bitora_cert_{run_id}_upgrade"
    databases = [clean_name, upgrade_name]
    inventory = migration_inventory()
    result = {
        "ok": False,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "migration_count": len(list(MIGRATIONS.glob("*.sql"))),
        "migration_inventory": inventory,
        "checks": {},
        "temporary_databases": databases,
    }
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        try:
            for name in databases:
                admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))

            clean_dsn = database_dsn(admin_dsn, clean_name)
            upgrade_dsn = database_dsn(admin_dsn, upgrade_name)
            first = run_postgres_migrations(config(clean_dsn), MIGRATIONS)
            second = run_postgres_migrations(config(clean_dsn), MIGRATIONS)
            with psycopg.connect(clean_dsn, row_factory=dict_row) as conn:
                clean_status = migration_status(conn, MIGRATIONS)
                try:
                    conn.execute("INSERT INTO schema_migrations(version) VALUES (%s)", (first[0],))
                except psycopg.errors.UniqueViolation:
                    duplicate_rejected = True
                    conn.rollback()
                else:
                    duplicate_rejected = False
                    conn.rollback()
                conn.execute("INSERT INTO schema_migrations(version) VALUES ('999_drift_probe.sql')")
                drift_detected = not migration_status(conn, MIGRATIONS)["ok"]
                conn.rollback()

            migration_files = sorted(MIGRATIONS.glob("*.sql"))
            with tempfile.TemporaryDirectory(prefix="bitora-cert-upgrade-") as temp_dir:
                partial = Path(temp_dir)
                for path in migration_files[:-1]:
                    shutil.copy2(path, partial / path.name)
                partial_applied = run_postgres_migrations(config(upgrade_dsn), partial)
                upgrade_applied = run_postgres_migrations(config(upgrade_dsn), MIGRATIONS)
            with psycopg.connect(upgrade_dsn, row_factory=dict_row) as conn:
                upgrade_status = migration_status(conn, MIGRATIONS)

            clean_fingerprint = schema_fingerprint(clean_dsn)
            upgrade_fingerprint = schema_fingerprint(upgrade_dsn)
            schema_diff = fingerprint_diff(clean_fingerprint, upgrade_fingerprint)
            result["checks"] = {
                "clean_install": bool(first) and clean_status["ok"],
                "idempotent_rerun": second == [],
                "duplicate_ledger_rejected": duplicate_rejected,
                "unexpected_drift_detected": drift_detected,
                "upgrade_applied_prefix": len(partial_applied) == max(0, len(migration_files) - 1),
                "upgrade_applied_tail": upgrade_applied == ([migration_files[-1].name] if migration_files else []),
                "upgrade_ledger_exact": upgrade_status["ok"],
                "clean_upgrade_schema_equal": not schema_diff,
            }
            result["clean_status"] = clean_status
            result["upgrade_status"] = upgrade_status
            result["applied_clean"] = first
            result["applied_upgrade_tail"] = upgrade_applied
            result["schema_objects"] = {key: len(value) for key, value in clean_fingerprint.items()}
            result["schema_diff"] = schema_diff
            result["ok"] = all(result["checks"].values())
        finally:
            for name in databases:
                admin.execute(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s AND pid <> pg_backend_pid()",
                    (name,),
                )
                admin.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(name)))
    result["finished_at"] = datetime.now(timezone.utc).isoformat()
    result["temporary_databases_removed"] = True
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Certifica migraciones PostgreSQL de BITORA sobre bases temporales.")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    try:
        result = certify()
    except Exception as exc:
        result = {"ok": False, "error": str(exc), "finished_at": datetime.now(timezone.utc).isoformat()}
    encoded = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    print(encoded)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(encoded + "\n", encoding="utf-8")
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
