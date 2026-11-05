#!/usr/bin/env python3
"""Deterministic PostgreSQL 16 backup/restore validation for isolated Phase 7.

The target database must end in ``_phase7``.  The script never accepts a DSN
or password and talks only to the explicitly named local Docker container.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
import uuid


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "backend" / "migrations"
SAFE_NAME = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]{0,62}$")
SAFE_CONTAINER = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}$")
CRITICAL_TABLES = (
    "events", "people", "accreditations", "enterprise_credentials",
    "enterprise_access_events", "auth_sessions", "registration_operations",
)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def run(*command: str, timeout: int = 300, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=timeout)
    if check and result.returncode:
        detail = (result.stderr or result.stdout)[-1500:].replace("\n", " ")
        raise RuntimeError(f"COMMAND_FAILED:{command[0]}:{result.returncode}:{detail}")
    return result


def docker_exec(container: str, *command: str, timeout: int = 300) -> str:
    return run("docker", "exec", container, *command, timeout=timeout).stdout.strip()


def psql(container: str, user: str, database: str, sql: str) -> str:
    return docker_exec(
        container, "psql", "-X", "-v", "ON_ERROR_STOP=1", "-At",
        "-U", user, "-d", database, "-c", sql,
    )


def safe_name(value: str, label: str) -> str:
    if not SAFE_NAME.fullmatch(value):
        raise ValueError(f"{label} invalido")
    return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def schema_fingerprint(container: str, user: str, database: str) -> dict[str, int]:
    queries = {
        "tables": "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'",
        "columns": "SELECT count(*) FROM information_schema.columns WHERE table_schema='public'",
        "constraints": "SELECT count(*) FROM information_schema.table_constraints WHERE table_schema='public'",
        "indexes": "SELECT count(*) FROM pg_indexes WHERE schemaname='public'",
        "migrations": "SELECT count(*) FROM schema_migrations",
    }
    return {key: int(psql(container, user, database, query)) for key, query in queries.items()}


def table_counts(container: str, user: str, database: str) -> dict[str, int | None]:
    result: dict[str, int | None] = {}
    for table in CRITICAL_TABLES:
        exists = psql(container, user, database, f"SELECT to_regclass('public.{table}') IS NOT NULL") == "t"
        result[table] = int(psql(container, user, database, f'SELECT count(*) FROM "{table}"')) if exists else None
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--container", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--admin-user", required=True)
    parser.add_argument("--app-user", required=True)
    parser.add_argument("--backup-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    if not SAFE_CONTAINER.fullmatch(args.container):
        raise SystemExit("INVALID_CONTAINER")
    container = args.container
    database = safe_name(args.database, "database")
    admin = safe_name(args.admin_user, "admin user")
    app_user = safe_name(args.app_user, "app user")
    if not database.endswith("_phase7"):
        raise SystemExit("REFUSED_NON_PHASE7_DATABASE")
    restore_database = f"{database}_restore"
    dump_inside = f"/tmp/{database}-{uuid.uuid4().hex}.dump"
    args.backup_dir.mkdir(parents=True, exist_ok=True)
    dump_local = args.backup_dir / Path(dump_inside).name
    marker = uuid.uuid4().hex
    started = time.monotonic()
    report = {
        "schema": "bitora.phase7.postgres-continuity.v1",
        "started_at": utc_now(), "ok": False, "status": "RUNNING",
        "container": container, "source_database": database,
        "restore_database": restore_database, "postgres_version": None,
        "checks": {}, "metrics": {}, "limitations": [
            "Logical restore of an isolated laboratory database is not a production disaster-recovery rehearsal."
        ],
    }
    atomic_json(args.report, report)
    try:
        version = psql(container, admin, database, "SHOW server_version")
        report["postgres_version"] = version
        report["checks"]["postgres_16"] = version.startswith("16.")
        role = psql(
            container, admin, database,
            f"SELECT rolsuper,rolcreatedb,rolcreaterole,rolcanlogin FROM pg_roles WHERE rolname='{app_user}'",
        ).split("|")
        report["checks"]["app_role_present"] = len(role) == 4
        report["checks"]["app_role_least_privilege"] = role == ["f", "f", "f", "t"]
        report["checks"]["app_can_connect"] = psql(
            container, admin, database,
            f"SELECT has_database_privilege('{app_user}','{database}','CONNECT')",
        ) == "t"

        expected = sorted(path.name for path in MIGRATIONS.glob("*.sql"))
        applied = psql(container, admin, database, "SELECT version FROM schema_migrations ORDER BY version").splitlines()
        report["checks"]["migrations_exact"] = applied == expected
        report["migration_count"] = len(applied)

        psql(
            container, admin, database,
            "CREATE TABLE IF NOT EXISTS phase7_continuity_probe (marker text PRIMARY KEY, created_at timestamptz NOT NULL DEFAULT now())",
        )
        psql(container, admin, database, f"INSERT INTO phase7_continuity_probe(marker) VALUES ('{marker}')")
        source_schema = schema_fingerprint(container, admin, database)
        source_counts = table_counts(container, admin, database)

        backup_started = time.monotonic()
        docker_exec(
            container, "pg_dump", "--format=custom", "--no-owner", "--no-acl",
            "-U", admin, "-d", database, "-f", dump_inside, timeout=900,
        )
        run("docker", "cp", f"{container}:{dump_inside}", str(dump_local), timeout=120)
        report["metrics"]["backup_seconds"] = round(time.monotonic() - backup_started, 3)
        report["metrics"]["backup_bytes"] = dump_local.stat().st_size
        report["backup_sha256"] = sha256(dump_local)
        report["checks"]["backup_nonempty"] = dump_local.stat().st_size > 0

        psql(container, admin, "postgres", f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='{restore_database}' AND pid<>pg_backend_pid()")
        psql(container, admin, "postgres", f'DROP DATABASE IF EXISTS "{restore_database}"')
        psql(container, admin, "postgres", f'CREATE DATABASE "{restore_database}"')
        restore_started = time.monotonic()
        docker_exec(
            container, "pg_restore", "--exit-on-error", "--no-owner", "--no-acl",
            "-U", admin, "-d", restore_database, dump_inside, timeout=900,
        )
        report["metrics"]["restore_seconds"] = round(time.monotonic() - restore_started, 3)
        restored_schema = schema_fingerprint(container, admin, restore_database)
        restored_counts = table_counts(container, admin, restore_database)
        restored_marker = psql(
            container, admin, restore_database,
            f"SELECT count(*) FROM phase7_continuity_probe WHERE marker='{marker}'",
        )
        report["checks"]["probe_restored"] = restored_marker == "1"
        report["checks"]["schema_reconciled"] = restored_schema == source_schema
        report["checks"]["critical_counts_reconciled"] = restored_counts == source_counts
        report["source_schema"] = source_schema
        report["restored_schema"] = restored_schema
        report["critical_table_counts"] = source_counts
        report["metrics"]["rto_observed_seconds"] = report["metrics"]["restore_seconds"]
        report["rpo_observed"] = "dump completion point; not zero"
        report["checks"]["checksum_recorded"] = len(report["backup_sha256"]) == 64
        report["ok"] = all(report["checks"].values())
        report["status"] = "PASS" if report["ok"] else "FAIL"
        return 0 if report["ok"] else 1
    except Exception as exc:
        report["status"] = "FAIL"
        report["error"] = f"{type(exc).__name__}:{exc}"
        return 1
    finally:
        cleanup_errors = []
        try:
            run("docker", "exec", container, "rm", "-f", dump_inside, check=False)
        except Exception as exc:
            cleanup_errors.append(type(exc).__name__)
        try:
            psql(container, admin, database, "DROP TABLE IF EXISTS phase7_continuity_probe")
        except Exception as exc:
            cleanup_errors.append(type(exc).__name__)
        if cleanup_errors:
            report["cleanup_errors"] = cleanup_errors
        report["finished_at"] = utc_now()
        report["metrics"]["total_seconds"] = round(time.monotonic() - started, 3)
        atomic_json(args.report, report)


if __name__ == "__main__":
    raise SystemExit(main())
