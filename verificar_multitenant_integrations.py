from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from cryptography.fernet import Fernet

import server
from backend.database import DatabaseConfig


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    os.environ["BITORA_INTEGRATION_ENCRYPTION_KEY"] = Fernet.generate_key().decode("ascii")
    with tempfile.TemporaryDirectory(prefix="bitora-multitenant-", ignore_cleanup_errors=True) as tmp:
        db_path = Path(tmp) / "bitora.sqlite3"
        server.DB_CONFIG = DatabaseConfig(engine="sqlite", sqlite_path=str(db_path), postgres_dsn="")
        server.DB_PATH = db_path
        server.init_db()

        db = server.connect()
        try:
            default_org = server.bootstrap_default_organization(db)
            admin = db.execute("SELECT * FROM users WHERE name = 'Admin'").fetchone()
            assert_true(admin is not None, "Debe existir usuario Admin")
            admin_session = {"id": int(admin["id"]), "name": admin["name"], "role": admin["role"]}
            assert_true(server.session_can_access_organization(db, admin_session, default_org), "Super Admin debe acceder a la organizacion principal")

            now = server.now_iso()
            org_b = int(db.execute(
                """
                INSERT INTO organizations (public_id, name, legal_name, status, plan, created_at, updated_at)
                VALUES (?, 'Productora B', 'Productora B', 'active', 'standard', ?, ?)
                """,
                (server.make_public_id("org"), now, now),
            ).lastrowid)
            db.execute(
                "INSERT OR IGNORE INTO organization_users (organization_id, user_id, role, status, accepted_at, created_at, updated_at) VALUES (?, ?, 'organization_owner', 'active', ?, ?, ?)",
                (org_b, int(admin["id"]), now, now, now),
            )

            event_a = server.insert_event_from_config(db, {"name": "Evento A", "organization_id": default_org}, "Admin")
            event_b = server.insert_event_from_config(db, {"name": "Evento B", "organization_id": org_b}, "Admin")
            assert_true(server.event_organization_id(db, event_a) == default_org, "Evento A debe pertenecer a organizacion A")
            assert_true(server.event_organization_id(db, event_b) == org_b, "Evento B debe pertenecer a organizacion B")

            service = server.integration_secret_service()
            encrypted = service.encrypt(json.dumps({"api_key": "clave-super-secreta", "refresh_token": "refresh-secreto"}))
            assert_true("clave-super-secreta" not in encrypted, "El secreto no debe quedar en texto plano")
            decrypted = json.loads(service.decrypt(encrypted))
            assert_true(decrypted["api_key"] == "clave-super-secreta", "El secreto debe poder recuperarse con la clave correcta")

            integration_a = int(db.execute(
                """
                INSERT INTO organization_integrations (
                    organization_id, provider, integration_type, name, mode, status,
                    configuration_encrypted, metadata_json, created_by, updated_by, created_at, updated_at
                )
                VALUES (?, 'resend', 'email_provider', 'Email A', 'client_owned', 'connected', ?, ?, 'Admin', 'Admin', ?, ?)
                """,
                (default_org, encrypted, json.dumps({"api_key": "debe-enmascararse"}), now, now),
            ).lastrowid)
            integration_b = int(db.execute(
                """
                INSERT INTO organization_integrations (
                    organization_id, provider, integration_type, name, mode, status,
                    configuration_encrypted, metadata_json, created_by, updated_by, created_at, updated_at
                )
                VALUES (?, 'meta', 'whatsapp_provider', 'WhatsApp B', 'client_owned', 'connected', ?, '{}', 'Admin', 'Admin', ?, ?)
                """,
                (org_b, encrypted, now, now),
            ).lastrowid)

            sanitized = server.sanitize_integration(db.execute("SELECT * FROM organization_integrations WHERE id = ?", (integration_a,)).fetchone())
            assert_true("configuration_encrypted" not in sanitized, "La API no debe exponer configuration_encrypted")
            assert_true("clave-super-secreta" not in json.dumps(sanitized), "La API no debe exponer secretos")
            assert_true(str(sanitized["metadata"]["api_key"]).endswith("arse"), "La metadata sensible debe quedar enmascarada")

            db.execute(
                """
                INSERT INTO event_integrations (event_id, channel, organization_integration_id, is_default, enabled, created_at, updated_at)
                VALUES (?, 'email', ?, 1, 1, ?, ?)
                """,
                (event_a, integration_a, now, now),
            )
            assert_true(server.event_channel_integration_id(db, event_a, "email") == integration_a, "El evento A debe resolver su integracion email")

            foreign_integration = db.execute("SELECT organization_id FROM organization_integrations WHERE id = ?", (integration_b,)).fetchone()
            assert_true(int(foreign_integration["organization_id"]) != server.event_organization_id(db, event_a), "Integracion B no pertenece al evento A")

            db.execute("UPDATE organizations SET safe_mode_email = 1, force_email_recipient = 'safe@example.test' WHERE id = ?", (default_org,))
            safe = server.effective_safe_mode(db, event_a, "email")
            assert_true(safe["enabled"], "Safe mode debe quedar activo por organizacion")
            assert_true(safe["forced_recipient"] == "safe@example.test", "Safe mode debe usar destinatario forzado de la organizacion")

            person_id = int(db.execute(
                "INSERT INTO people (first_name, last_name, email, phone, created_at) VALUES ('Ana', 'Demo', 'ana@example.test', '5491100000000', ?)",
                (now,),
            ).lastrowid)
            accreditation_id = int(db.execute(
                "INSERT INTO accreditations (event_id, person_id, type, status, token, created_at) VALUES (?, ?, 'General', 'confirmed', ?, ?)",
                (event_a, person_id, "EVT-MTENANT-TEST", now),
            ).lastrowid)
            row = {
                "person_id": person_id,
                "accreditation_id": accreditation_id,
                "preferred_email": "ana@example.test",
                "preferred_phone": "5491100000000",
                "acepta_email": 1,
                "acepta_whatsapp": 0,
                "first_name": "Ana",
                "last_name": "Demo",
                "event_name": "Evento A",
                "token": "EVT-MTENANT-TEST",
            }
            queued = server.queue_communication(
                db,
                event_id=event_a,
                actor="Admin",
                audience="test",
                channel="email",
                template_code="test",
                subject="Hola {{nombre}}",
                content="Evento {{evento}}",
                rows=[row],
                process_now=False,
            )
            assert_true(queued["queued"] == 1, "Debe crear un envio en cola")
            queue_row = db.execute("SELECT organization_id, integration_id FROM communication_queue ORDER BY id DESC LIMIT 1").fetchone()
            assert_true(int(queue_row["organization_id"]) == default_org, "La cola debe guardar organization_id")
            assert_true(int(queue_row["integration_id"]) == integration_a, "La cola debe guardar integration_id")
        finally:
            db.close()

        print("OK verificar_multitenant_integrations")


if __name__ == "__main__":
    main()
