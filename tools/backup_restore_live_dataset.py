from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import server


def main() -> int:
    parser = argparse.ArgumentParser(description="BITORA backup/restore live dataset helper")
    parser.add_argument("command", choices=["seed", "manifest", "validate"])
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--manifest")
    parser.add_argument("--output")
    args = parser.parse_args()
    if args.command == "seed":
        payload = seed_dataset(args.run_id)
    elif args.command == "manifest":
        payload = build_manifest(args.run_id)
    else:
        if not args.manifest:
            raise SystemExit("--manifest es obligatorio para validate")
        expected = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
        payload = validate_restore(args.run_id, expected)
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


def seed_dataset(run_id: str) -> dict[str, Any]:
    server.init_db()
    with server.connect() as db:
        existing = db.execute("SELECT COUNT(*) AS c FROM organizations WHERE name LIKE ?", (f"BRL {run_id}%",)).fetchone()["c"]
        if int(existing or 0):
            return {"run_id": run_id, "status": "already_seeded", "organizations": int(existing)}
        now = server.now_iso()
        org_ids: list[int] = []
        user_ids: list[int] = []
        integration_ids: list[int] = []
        event_ids: list[int] = []
        for org_index in range(4):
            org_id = int(db.execute(
                """
                INSERT INTO organizations (
                    public_id, name, legal_name, status, plan,
                    safe_mode_email, safe_mode_whatsapp,
                    force_email_recipient, force_whatsapp_recipient,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, 'active', 'standard', 1, 1, ?, ?, ?, ?)
                """,
                (
                    server.make_public_id("org"),
                    f"BRL {run_id} Org {org_index}",
                    f"BRL {run_id} Org {org_index}",
                    f"safe-{run_id.lower()}-{org_index}@example.test",
                    "5491100000000",
                    now,
                    now,
                ),
            ).lastrowid)
            org_ids.append(org_id)
            encrypted = server.integration_secret_service().encrypt(
                json.dumps({"provider": "backup_restore_live", "run_id": run_id, "secret_ref": f"encrypted-{org_index}"})
            )
            integration_id = int(db.execute(
                """
                INSERT INTO organization_integrations (
                    organization_id, provider, integration_type, name, mode, status,
                    configuration_encrypted, metadata_json, created_by, updated_by,
                    created_at, updated_at
                )
                VALUES (?, 'backup_restore', 'email_provider', ?, 'platform_managed', 'connected', ?, ?, 'BSTF', 'BSTF', ?, ?)
                """,
                (
                    org_id,
                    f"BRL {run_id} Integration {org_index}",
                    encrypted,
                    json.dumps({"run_id": run_id, "org_index": org_index}),
                    now,
                    now,
                ),
            ).lastrowid)
            integration_ids.append(integration_id)
            for user_index in range(2):
                user_id = int(db.execute(
                    "INSERT INTO users (name, role, pin_hash, active, created_at) VALUES (?, ?, ?, 1, ?)",
                    (
                        f"BRL {run_id} User {org_index}-{user_index}",
                        "Productor" if user_index == 0 else "Visualizador",
                        server.hash_pin(f"{org_index}{user_index}77"),
                        now,
                    ),
                ).lastrowid)
                user_ids.append(user_id)
                db.execute(
                    """
                    INSERT INTO organization_users (organization_id, user_id, role, status, accepted_at, created_at, updated_at)
                    VALUES (?, ?, ?, 'active', ?, ?, ?)
                    """,
                    (org_id, user_id, "organization_admin" if user_index == 0 else "viewer", now, now, now),
                )
        for event_index in range(20):
            org_index = event_index // 5
            org_id = org_ids[org_index]
            integration_id = integration_ids[org_index]
            event_id = int(server.insert_event_from_config(
                db,
                {
                    "name": f"BRL {run_id} Event {event_index:02d}",
                    "venue": "BITORA Restore Validation",
                    "capacity": 200,
                    "status": "published",
                    "organization_id": org_id,
                },
                "BSTF",
                status="published",
            ))
            event_ids.append(event_id)
            for user_id in user_ids[org_index * 2:(org_index * 2) + 2]:
                server.assign_user_to_event(db, user_id, event_id, "Productor" if user_id == user_ids[org_index * 2] else "Visualizador")
            db.execute(
                """
                INSERT INTO event_integrations (event_id, channel, organization_integration_id, is_default, enabled, created_at, updated_at)
                VALUES (?, 'email', ?, 1, 1, ?, ?)
                """,
                (event_id, integration_id, now, now),
            )
            space_ids = []
            activity_ids = []
            for activity_index in range(2):
                space_id = int(db.execute(
                    "INSERT INTO spaces (event_id, name, capacity, created_at) VALUES (?, ?, ?, ?)",
                    (event_id, f"BRL Sala {activity_index}", 100, now),
                ).lastrowid)
                activity_id = int(db.execute(
                    """
                    INSERT INTO activities (event_id, space_id, title, starts_at, ends_at, capacity, reservation_mode, created_at)
                    VALUES (?, ?, ?, ?, ?, 100, 'required', ?)
                    """,
                    (
                        event_id,
                        space_id,
                        f"BRL {run_id} Charla {event_index:02d}-{activity_index}",
                        "2027-01-01 09:00",
                        "2027-01-01 10:00",
                        now,
                    ),
                ).lastrowid)
                space_ids.append(space_id)
                activity_ids.append(activity_id)
            for person_index in range(50):
                global_index = (event_index * 50) + person_index
                person_id = int(db.execute(
                    "INSERT INTO people (first_name, last_name, email, phone, company, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        f"BRLNombre{global_index}",
                        f"BRLApellido{global_index}",
                        f"brl-{run_id.lower()}-{global_index:04d}@example.test",
                        f"5491100{global_index:06d}",
                        f"BRL Empresa {org_index}",
                        now,
                    ),
                ).lastrowid)
                acc_id = int(db.execute(
                    """
                    INSERT INTO accreditations (event_id, person_id, type, token, status, created_at)
                    VALUES (?, ?, 'General', ?, 'active', ?)
                    """,
                    (event_id, person_id, f"BRL-{run_id}-{event_index:02d}-{person_index:03d}", now),
                ).lastrowid)
                db.execute(
                    """
                    INSERT INTO participant_communication_preferences (
                        person_id, email, phone, acepta_email, acepta_whatsapp, canal_preferido, fecha_consentimiento, updated_at
                    )
                    VALUES (?, ?, ?, 1, 1, 'email', ?, ?)
                    """,
                    (person_id, f"brl-{run_id.lower()}-{global_index:04d}@example.test", f"5491100{global_index:06d}", now, now),
                )
                if person_index < 5:
                    db.execute(
                        """
                        INSERT INTO reservations (event_id, activity_id, accreditation_id, status, created_at)
                        VALUES (?, ?, ?, 'confirmed', ?)
                        """,
                        (event_id, activity_ids[person_index % 2], acc_id, now),
                    )
                    db.execute(
                        """
                        INSERT INTO activity_attendance (
                            event_id, activity_id, accreditation_id, entry_at, entry_operator,
                            attended_minutes, attendance_percentage, status, eligibility_status, created_at, updated_at
                        )
                        VALUES (?, ?, ?, ?, 'BSTF', 45, 90, 'Presente', 'Elegible', ?, ?)
                        """,
                        (event_id, activity_ids[person_index % 2], acc_id, now, now, now),
                    )
                if person_index == 0:
                    queue_id = int(db.execute(
                        """
                        INSERT INTO communication_queue (
                            event_id, organization_id, integration_id, person_id, accreditation_id,
                            channel, audience, template_code, subject, content, recipient, status,
                            provider, provider_message_id, idempotency_key, created_by, created_at
                        )
                        VALUES (?, ?, ?, ?, ?, 'email', 'backup_restore_live', 'brl', ?, ?, ?, 'pendiente',
                                'backup_restore', ?, ?, 'BSTF', ?)
                        """,
                        (
                            event_id,
                            org_id,
                            integration_id,
                            person_id,
                            acc_id,
                            f"BRL {run_id} subject",
                            f"BITORA STAGING {run_id}",
                            f"brl-{run_id.lower()}-{global_index:04d}@example.test",
                            f"brl-provider-{run_id}-{event_index:02d}",
                            f"brl-idem-{run_id}-{event_index:02d}",
                            now,
                        ),
                    ).lastrowid)
                    db.execute(
                        """
                        INSERT INTO jobs (
                            event_id, organization_id, integration_id, kind, priority, status,
                            payload, result, retry_count, max_retries, created_by, created_at, updated_at
                        )
                        VALUES (?, ?, ?, 'email.send', 'low', ?, ?, '{}', 0, 3, 'BSTF', ?, ?)
                        """,
                        (
                            event_id,
                            org_id,
                            integration_id,
                            "pending" if event_index % 2 == 0 else "completed",
                            json.dumps({"queue_id": queue_id, "run_id": run_id}),
                            now,
                            now,
                        ),
                    )
                    server.audit(
                        db,
                        "BSTF",
                        "backup_restore_live.event_seeded",
                        "event",
                        event_id,
                        {"run_id": run_id, "organization_id": org_id, "integration_id": integration_id, "queue_id": queue_id},
                    )
            server.STORAGE.save_event(event_id, "uploads", f"brl-{run_id}-evidence.txt", f"evento {event_id} run {run_id}".encode("utf-8"))
            server.STORAGE.save_event(event_id, "certificates", f"brl-{run_id}-certificate.txt", f"certificado {event_id} run {run_id}".encode("utf-8"))
        return {"run_id": run_id, "status": "seeded", "organizations": 4, "events": 20, "participants": 1000, "storage_files": 40}


def build_manifest(run_id: str) -> dict[str, Any]:
    server.init_db()
    with server.connect() as db:
        event_rows = db.execute("SELECT id, organization_id FROM events WHERE name LIKE ? ORDER BY id", (f"BRL {run_id} Event%",)).fetchall()
        event_ids = [int(row["id"]) for row in event_rows]
        org_ids = sorted({int(row["organization_id"]) for row in event_rows})
        storage_items = []
        for event_id in event_ids:
            storage_items.extend(server.STORAGE.event_inventory(event_id))
        manifest = {
            "run_id": run_id,
            "commit": git_commit(),
            "environment": os.environ.get("APP_ENV", ""),
            "db_engine": server.DB_CONFIG.engine,
            "postgres_version": query_scalar(db, "SELECT version() AS value"),
            "counts": {
                "organizations": count(db, "organizations", "name LIKE ?", (f"BRL {run_id} Org%",)),
                "events": len(event_ids),
                "users": count(db, "users", "name LIKE ?", (f"BRL {run_id} User%",)),
                "organization_users": count_in(db, "organization_users", "organization_id", org_ids),
                "participants": count(db, "people", "email LIKE ?", (f"brl-{run_id.lower()}-%@example.test",)),
                "accreditations": count_in(db, "accreditations", "event_id", event_ids),
                "activities": count_in(db, "activities", "event_id", event_ids),
                "spaces": count_in(db, "spaces", "event_id", event_ids),
                "reservations": count_in(db, "reservations", "event_id", event_ids),
                "attendance": count_in(db, "activity_attendance", "event_id", event_ids),
                "integrations": count_in(db, "organization_integrations", "organization_id", org_ids),
                "event_integrations": count_in(db, "event_integrations", "event_id", event_ids),
                "communication_queue": count_in(db, "communication_queue", "event_id", event_ids),
                "jobs": count_in(db, "jobs", "event_id", event_ids),
                "audit_logs": count(db, "audit_logs", "action = ? AND payload LIKE ?", ("backup_restore_live.event_seeded", f"%{run_id}%")),
                "storage_files": len(storage_items),
            },
            "job_status_counts": grouped_counts(db, "jobs", "status", event_ids),
            "checksums": {
                "organizations": checksum_rows(db, "organizations", "name LIKE ?", (f"BRL {run_id} Org%",)),
                "events": checksum_rows(db, "events", "name LIKE ?", (f"BRL {run_id} Event%",)),
                "users": checksum_rows(db, "users", "name LIKE ?", (f"BRL {run_id} User%",)),
                "participants": checksum_rows(db, "people", "email LIKE ?", (f"brl-{run_id.lower()}-%@example.test",)),
                "accreditations": checksum_rows_in(db, "accreditations", "event_id", event_ids),
                "activities": checksum_rows_in(db, "activities", "event_id", event_ids),
                "reservations": checksum_rows_in(db, "reservations", "event_id", event_ids),
                "integrations": checksum_rows_in(db, "organization_integrations", "organization_id", org_ids),
                "jobs": checksum_rows_in(db, "jobs", "event_id", event_ids),
                "audit_logs": checksum_rows(db, "audit_logs", "action = ? AND payload LIKE ?", ("backup_restore_live.event_seeded", f"%{run_id}%")),
                "storage": checksum_payload(storage_items),
            },
            "integrity": {
                "orphan_accreditations": orphan_count(db, "accreditations", "event_id", "events"),
                "orphan_reservations": orphan_count(db, "reservations", "event_id", "events"),
                "orphan_jobs": orphan_count(db, "jobs", "event_id", "events"),
                "qr_duplicates": duplicate_count(db, "accreditations", "token", "token LIKE ?", (f"BRL-{run_id}-%",)),
                "provider_message_duplicates": duplicate_count(db, "communication_queue", "provider_message_id", "provider_message_id LIKE ?", (f"brl-provider-{run_id}-%",)),
                "cross_event_integrations": cross_event_integrations(db, event_ids),
                "cross_jobs": cross_jobs(db, event_ids),
            },
            "storage": {
                "file_count": len(storage_items),
                "total_bytes": sum(int(item["size"]) for item in storage_items),
                "sample": storage_items[:8],
            },
            "event_ids_sample": event_ids[:5],
            "organization_ids_sample": org_ids[:4],
        }
        return manifest


def validate_restore(run_id: str, expected: dict[str, Any]) -> dict[str, Any]:
    current = build_manifest(run_id)
    mismatches = []
    for section in ["counts", "job_status_counts", "checksums", "integrity"]:
        if current.get(section) != expected.get(section):
            mismatches.append(section)
    required_counts = {"organizations": 4, "events": 20, "participants": 1000, "storage_files": 40}
    count_errors = {key: current["counts"].get(key) for key, expected_value in required_counts.items() if current["counts"].get(key) != expected_value}
    integrity_errors = {key: value for key, value in current["integrity"].items() if int(value or 0) != 0}
    return {
        "run_id": run_id,
        "status": "passed" if not mismatches and not count_errors and not integrity_errors else "failed",
        "mismatches": mismatches,
        "count_errors": count_errors,
        "integrity_errors": integrity_errors,
        "current": current,
    }


def count(db, table: str, where: str, params: tuple[Any, ...]) -> int:
    return int(db.execute(f"SELECT COUNT(*) AS c FROM {table} WHERE {where}", params).fetchone()["c"] or 0)


def count_in(db, table: str, column: str, ids: list[int]) -> int:
    if not ids:
        return 0
    placeholders = ",".join("?" for _ in ids)
    return int(db.execute(f"SELECT COUNT(*) AS c FROM {table} WHERE {column} IN ({placeholders})", tuple(ids)).fetchone()["c"] or 0)


def checksum_rows(db, table: str, where: str, params: tuple[Any, ...]) -> str:
    rows = db.execute(f"SELECT * FROM {table} WHERE {where} ORDER BY id", params).fetchall()
    return checksum_payload([dict(row) for row in rows])


def checksum_rows_in(db, table: str, column: str, ids: list[int]) -> str:
    if not ids:
        return checksum_payload([])
    placeholders = ",".join("?" for _ in ids)
    rows = db.execute(f"SELECT * FROM {table} WHERE {column} IN ({placeholders}) ORDER BY id", tuple(ids)).fetchall()
    return checksum_payload([dict(row) for row in rows])


def checksum_payload(payload: Any) -> str:
    normalized = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()


def query_scalar(db, sql: str) -> str:
    try:
        row = db.execute(sql).fetchone()
        return str(row["value"] if row and "value" in row else "")
    except Exception:
        return ""


def grouped_counts(db, table: str, group_col: str, event_ids: list[int]) -> dict[str, int]:
    if not event_ids:
        return {}
    placeholders = ",".join("?" for _ in event_ids)
    rows = db.execute(
        f"SELECT {group_col} AS label, COUNT(*) AS c FROM {table} WHERE event_id IN ({placeholders}) GROUP BY {group_col} ORDER BY {group_col}",
        tuple(event_ids),
    ).fetchall()
    return {str(row["label"]): int(row["c"]) for row in rows}


def orphan_count(db, table: str, column: str, parent_table: str) -> int:
    try:
        row = db.execute(
            f"SELECT COUNT(*) AS c FROM {table} child LEFT JOIN {parent_table} parent ON parent.id = child.{column} WHERE child.{column} IS NOT NULL AND parent.id IS NULL"
        ).fetchone()
        return int(row["c"] or 0)
    except Exception:
        return 0


def duplicate_count(db, table: str, column: str, where: str, params: tuple[Any, ...]) -> int:
    rows = db.execute(
        f"SELECT {column}, COUNT(*) AS c FROM {table} WHERE {where} AND {column} <> '' GROUP BY {column} HAVING COUNT(*) > 1",
        params,
    ).fetchall()
    return len(rows)


def cross_event_integrations(db, event_ids: list[int]) -> int:
    if not event_ids:
        return 0
    placeholders = ",".join("?" for _ in event_ids)
    row = db.execute(
        f"""
        SELECT COUNT(*) AS c
        FROM event_integrations ei
        JOIN events e ON e.id = ei.event_id
        JOIN organization_integrations oi ON oi.id = ei.organization_integration_id
        WHERE ei.event_id IN ({placeholders}) AND oi.organization_id <> e.organization_id
        """,
        tuple(event_ids),
    ).fetchone()
    return int(row["c"] or 0)


def cross_jobs(db, event_ids: list[int]) -> int:
    if not event_ids:
        return 0
    placeholders = ",".join("?" for _ in event_ids)
    row = db.execute(
        f"""
        SELECT COUNT(*) AS c
        FROM jobs j
        JOIN events e ON e.id = j.event_id
        WHERE j.event_id IN ({placeholders}) AND j.organization_id IS NOT NULL AND j.organization_id <> e.organization_id
        """,
        tuple(event_ids),
    ).fetchone()
    return int(row["c"] or 0)


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""


if __name__ == "__main__":
    raise SystemExit(main())
