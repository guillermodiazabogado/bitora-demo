"""Fixture helpers used inside the BITORA operational multi-instance image.

The module deliberately operates only against the database selected through the
normal BITORA environment variables.  It never accepts an arbitrary DSN on the
command line, which keeps credentials out of process listings and reports.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

# Direct execution sets sys.path to /app/scripts; add the immutable image root
# so the fixture exercises the same server module as the application containers.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server


ADMIN_PASSWORD = "Operational-Admin-582!"
OPERATOR_PASSWORD = "Operational-Access-582!"


def emit(payload: dict) -> None:
    print("BITORA_OPERATIONAL_RESULT=" + json.dumps(payload, sort_keys=True))


def setup() -> None:
    server.init_db()
    server.seed_if_empty()
    with server.DB_LOCK, server.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        organization_id = server.bootstrap_default_organization(db)
        first = db.execute("SELECT id FROM events ORDER BY id LIMIT 1").fetchone()
        if not first:
            raise RuntimeError("DEFAULT_EVENT_MISSING")
        event_id = int(first["id"])
        now = server.now_iso()

        admin = db.execute("SELECT id FROM users WHERE name = 'Admin'").fetchone()
        if not admin:
            raise RuntimeError("ADMIN_USER_MISSING")
        admin_id = int(admin["id"])
        db.execute(
            "UPDATE users SET role = 'Super Admin', pin_hash = ?, active = 1, "
            "must_change_password = 0, disabled_at = NULL, updated_at = ? WHERE id = ?",
            (server.hash_pin(ADMIN_PASSWORD), now, admin_id),
        )
        server.assign_user_to_event(db, admin_id, event_id, "Super Admin")

        operator = db.execute("SELECT id FROM users WHERE name = 'multi-access'").fetchone()
        if operator:
            operator_id = int(operator["id"])
            db.execute(
                "UPDATE users SET role = 'Operador de acceso', pin_hash = ?, active = 1, "
                "must_change_password = 0, disabled_at = NULL, updated_at = ? WHERE id = ?",
                (server.hash_pin(OPERATOR_PASSWORD), now, operator_id),
            )
        else:
            operator_id = int(
                db.execute(
                    "INSERT INTO users (name, role, pin_hash, active, must_change_password, created_at, updated_at) "
                    "VALUES ('multi-access', 'Operador de acceso', ?, 1, 0, ?, ?)",
                    (server.hash_pin(OPERATOR_PASSWORD), now, now),
                ).lastrowid
            )
        server.assign_user_to_event(db, operator_id, event_id, "Operador de acceso")
        db.execute(
            "INSERT OR IGNORE INTO organization_users "
            "(organization_id, user_id, role, status, accepted_at, created_at, updated_at) "
            "VALUES (?, ?, 'event_operator', 'active', ?, ?, ?)",
            (organization_id, operator_id, now, now, now),
        )

        second = db.execute("SELECT id FROM events WHERE name = 'Operational Isolated Event'").fetchone()
        if second:
            isolated_event_id = int(second["id"])
        else:
            isolated_event_id = server.insert_event_from_config(
                db,
                {
                    "organization_id": organization_id,
                    "name": "Operational Isolated Event",
                    "description": "multi-instance isolation",
                    "venue": "Isolated",
                    "starts_at": now,
                    "ends_at": now,
                },
                "Admin",
                status="draft",
            )
            server.ensure_default_types(db, isolated_event_id)
            server.ensure_default_spaces(db, isolated_event_id)
        server.assign_user_to_event(db, admin_id, isolated_event_id, "Super Admin")
        db.execute(
            "UPDATE user_event_roles SET active = 0 WHERE user_id = ? AND event_id = ?",
            (operator_id, isolated_event_id),
        )

        registration = server.register_accreditation(
            db,
            event_id,
            {
                "first_name": "Multi",
                "last_name": "Instance",
                "email": "multi-instance@bitora.test",
                "type": "General",
                "actor": "operational-harness",
            },
        )
        if not registration.get("ok"):
            raise RuntimeError(f"REGISTRATION_FAILED:{registration}")
        activation = server.set_access_state_enforcement(db, event_id, enabled=True, actor="operational-harness")
        if not activation.get("ok"):
            raise RuntimeError(f"ACCESS_ENFORCEMENT_FAILED:{activation}")
        db.execute("COMMIT")
    emit(
        {
            "organization_id": organization_id,
            "event_id": event_id,
            "isolated_event_id": isolated_event_id,
            "access_token": registration["token"],
        }
    )


def set_admin_role(role: str) -> None:
    allowed = {"Super Admin", "Visualizador"}
    if role not in allowed:
        raise RuntimeError("ROLE_NOT_ALLOWED_BY_OPERATIONAL_FIXTURE")
    with server.DB_LOCK, server.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("UPDATE users SET role = ?, updated_at = ? WHERE name = 'Admin'", (role, server.now_iso()))
        db.execute("COMMIT")
    emit({"ok": True, "role": role})


def inspect(event_id: int) -> None:
    with server.connect() as db:
        events = db.execute(
            "SELECT decision, reason_code, COUNT(*) AS count FROM enterprise_access_events "
            "WHERE event_id = ? GROUP BY decision, reason_code ORDER BY decision, reason_code",
            (event_id,),
        ).fetchall()
        snapshots = db.execute(
            "SELECT current_state, COUNT(*) AS count FROM enterprise_access_state_snapshots "
            "WHERE event_id = ? GROUP BY current_state ORDER BY current_state",
            (event_id,),
        ).fetchall()
        sessions = db.execute(
            "SELECT revoked_at, expires_at FROM auth_sessions ORDER BY id"
        ).fetchall()
    emit(
        {
            "access_events": [dict(row) for row in events],
            "snapshots": [dict(row) for row in snapshots],
            "session_rows": len(sessions),
            "revoked_sessions": sum(1 for row in sessions if str(row["revoked_at"] or "")),
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("setup")
    role_parser = subparsers.add_parser("set-admin-role")
    role_parser.add_argument("role")
    inspect_parser = subparsers.add_parser("inspect")
    inspect_parser.add_argument("event_id", type=int)
    args = parser.parse_args()
    if args.command == "setup":
        setup()
    elif args.command == "set-admin-role":
        set_admin_role(args.role)
    else:
        inspect(args.event_id)


if __name__ == "__main__":
    main()
