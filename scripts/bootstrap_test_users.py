import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import server  # noqa: E402


BASE_USERS = [
    ("superadmin-demo", "Super Admin"),
    ("admin-demo", "Super Admin"),
    ("coordinador-demo", "Coordinador"),
    ("productor-demo", "Productor"),
    ("recepcion-demo", "Operador de recepcion"),
    ("acceso-demo", "Operador de acceso"),
    ("visualizador-demo", "Visualizador"),
    ("comunicaciones-demo", "Comunicaciones"),
    ("soporte-demo", "Soporte tecnico"),
]


def environment_name() -> str:
    return str(os.environ.get("APP_ENV") or os.environ.get("BITORA_ENV") or "local").lower()


def main() -> int:
    parser = argparse.ArgumentParser(description="Crea usuarios base de prueba para BITORA local/staging.")
    parser.add_argument("--reset", action="store_true", help="Restablece contraseñas aunque el usuario exista.")
    parser.add_argument("--event-id", type=int, default=0, help="Evento al que se asignan los usuarios. Si se omite, usa el primero.")
    parser.add_argument("--organization-id", type=int, default=0, help="Organizacion a la que se asignan los usuarios. Si se omite, usa la primera.")
    args = parser.parse_args()

    env = environment_name()
    if env == "production":
        print("ABORTED: bootstrap de usuarios de prueba no opera en production.")
        return 2

    credentials = []
    with server.DB_LOCK, server.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        server.ensure_default_users(db)
        org_id = args.organization_id or server.bootstrap_default_organization(db)
        event_row = db.execute("SELECT id, name FROM events ORDER BY id LIMIT 1").fetchone()
        if not event_row:
            db.execute("ROLLBACK")
            print("ABORTED: no existe un evento para asignar usuarios de prueba.")
            return 3
        else:
            event_id = args.event_id or int(event_row["id"])
            event_name = str(event_row["name"])
        now = server.now_iso()
        for username, role in BASE_USERS:
            existing = db.execute("SELECT id FROM users WHERE name = ?", (username,)).fetchone()
            password = server.generate_temporary_password()
            if existing:
                user_id = int(existing["id"])
                if args.reset:
                    db.execute(
                        "UPDATE users SET role = ?, pin_hash = ?, active = 1, must_change_password = 1, updated_at = ?, disabled_at = NULL WHERE id = ?",
                        (role, server.hash_pin(password), now, user_id),
                    )
                    credentials.append((username, password))
            else:
                user_id = int(db.execute(
                    """
                    INSERT INTO users (name, role, pin_hash, active, must_change_password, created_at, updated_at)
                    VALUES (?, ?, ?, 1, 1, ?, ?)
                    """,
                    (username, role, server.hash_pin(password), now, now),
                ).lastrowid)
                credentials.append((username, password))
            server.assign_user_to_event(db, user_id, event_id, role)
            db.execute(
                """
                INSERT OR IGNORE INTO organization_users (organization_id, user_id, role, status, accepted_at, created_at, updated_at)
                VALUES (?, ?, ?, 'active', ?, ?, ?)
                """,
                (org_id, user_id, server.organization_role_from_system_role(role), now, now, now),
            )
            server.audit(db, "bootstrap", "user.bootstrap_test", "user", user_id, {"name": username, "role": role, "event_id": event_id})
        db.execute("COMMIT")

    print("BITORA TEST USERS READY")
    print(f"Environment: {env}")
    print(f"Organization ID: {org_id}")
    print(f"Event: {event_name} ({event_id})")
    if credentials:
        print("Temporary passwords, shown once:")
        for username, password in credentials:
            print(f"{username}: {password}")
    else:
        print("No passwords generated. Use --reset to create new temporary passwords.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
