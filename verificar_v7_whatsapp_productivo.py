from __future__ import annotations

import hashlib
import hmac
import os
import tempfile

os.environ.setdefault("QR_REQUIRE_LOGIN", "0")
os.environ["QR_DB_ENGINE"] = "sqlite"
os.environ["DATABASE_ENGINE"] = "sqlite"
os.environ.setdefault("WHATSAPP_PROVIDER", "meta")
os.environ.setdefault("WHATSAPP_ENABLED", "false")

import server
from backend.services.whatsapp import MetaCloudWhatsAppProvider, normalize_phone, verify_meta_signature


def seed_event(db):
    event_id = int(
        db.execute(
            """
            INSERT INTO events (name, description, venue, starts_at, ends_at, status, project_type, capacity, created_at)
            VALUES ('Evento WhatsApp', '', 'Demo', '2026-07-20T10:00:00', '2026-07-20T18:00:00', 'published', 'conference', 100, ?)
            """,
            (server.now_iso(),),
        ).lastrowid
    )
    server.ensure_default_types(db, event_id)
    person_id = int(
        db.execute(
            "INSERT INTO people (first_name, last_name, email, phone, company, created_at) VALUES ('Ana', 'WhatsApp', 'ana.wa@example.com', '54 9 299 4522126', 'BITORA', ?)",
            (server.now_iso(),),
        ).lastrowid
    )
    accreditation_id = int(
        db.execute(
            """
            INSERT INTO accreditations (event_id, person_id, type, token, status, checked_in_at, created_at)
            VALUES (?, ?, 'General', 'EVT-WA-TEST', 'active', NULL, ?)
            """,
            (event_id, person_id, server.now_iso()),
        ).lastrowid
    )
    server.upsert_communication_preference(
        db,
        person_id,
        {"email": "ana.wa@example.com", "phone": "54 9 299 4522126", "acepta_email": 0, "acepta_whatsapp": 1},
    )
    return event_id, person_id, accreditation_id


def main() -> None:
    fd, path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    original_path = server.DB_PATH
    previous_env = {key: os.environ.get(key) for key in [
        "APP_ENV",
        "WHATSAPP_ENABLED",
        "WHATSAPP_PROVIDER",
        "WHATSAPP_ACCESS_TOKEN",
        "WHATSAPP_PHONE_NUMBER_ID",
        "WHATSAPP_BUSINESS_ACCOUNT_ID",
        "WHATSAPP_VERIFY_TOKEN",
        "WHATSAPP_APP_SECRET",
        "WHATSAPP_SAFE_MODE",
    ]}
    server.DB_PATH = server.Path(path)
    try:
        server.init_db()
        with server.connect() as db:
            event_id, person_id, accreditation_id = seed_event(db)
            rows = server.communication_audience_rows(db, event_id, "all")
            assert len(rows) == 1

            valid = server.queue_communication(
                db,
                event_id=event_id,
                actor="QA",
                audience="all",
                channel="whatsapp",
                template_code="manual",
                subject="Prueba",
                content="Hola {{nombre}}",
                rows=rows,
                process_now=True,
            )
            assert valid["queued"] == 1
            assert db.execute("SELECT recipient FROM communication_queue WHERE channel = 'whatsapp'").fetchone()["recipient"] == "5492994522126"

            duplicate = server.queue_communication(db, event_id=event_id, actor="QA", audience="all", channel="whatsapp", template_code="manual", subject="Prueba", content="Hola {{nombre}}", rows=rows, process_now=True)
            assert duplicate["skipped"] == 1

            bad_row = dict(rows[0])
            bad_row["preferred_phone"] = "sin-numero"
            invalid = server.queue_communication(db, event_id=event_id, actor="QA", audience="all", channel="whatsapp", template_code="manual", subject="Malo", content="Contenido", rows=[bad_row], process_now=True)
            assert invalid["skipped"] == 1

            server.suppress_whatsapp(db, event_id, "5492994522126", "opt_out", "test", "event")
            assert server.whatsapp_is_suppressed(db, event_id, "54 9 299 4522126")[0]
            suppressed = server.queue_communication(db, event_id=event_id, actor="QA", audience="all", channel="whatsapp", template_code="otra", subject="Otra", content="Contenido", rows=rows, process_now=True)
            assert suppressed["skipped"] == 1

            queue_id = int(db.execute("SELECT id FROM communication_queue WHERE channel = 'whatsapp' ORDER BY id LIMIT 1").fetchone()["id"])
            db.execute("UPDATE communication_queue SET provider_message_id = 'wamid.demo.1', provider = 'meta' WHERE id = ?", (queue_id,))
            os.environ["WHATSAPP_ENABLED"] = "true"
            os.environ["WHATSAPP_PROVIDER"] = "meta"
            os.environ["WHATSAPP_ACCESS_TOKEN"] = "token"
            os.environ["WHATSAPP_PHONE_NUMBER_ID"] = "123"
            os.environ["WHATSAPP_BUSINESS_ACCOUNT_ID"] = "456"
            os.environ["WHATSAPP_VERIFY_TOKEN"] = "verify"
            os.environ["WHATSAPP_APP_SECRET"] = "secret"
            delivered = server.apply_whatsapp_webhook(
                db,
                {
                    "entry": [
                        {
                            "changes": [
                                {
                                    "value": {
                                        "metadata": {"phone_number_id": "123"},
                                        "statuses": [{"id": "wamid.demo.1", "status": "delivered", "timestamp": "1", "recipient_id": "5492994522126"}],
                                    }
                                }
                            ]
                        }
                    ]
                },
            )
            assert delivered["statuses"][0]["status"] == "entregado"
            duplicate_status = server.apply_whatsapp_webhook(
                db,
                {
                    "entry": [
                        {
                            "changes": [
                                {
                                    "value": {
                                        "metadata": {"phone_number_id": "123"},
                                        "statuses": [{"id": "wamid.demo.1", "status": "delivered", "timestamp": "1", "recipient_id": "5492994522126"}],
                                    }
                                }
                            ]
                        }
                    ]
                },
            )
            assert duplicate_status["statuses"][0]["status"] == "duplicate"
            assert db.execute("SELECT COUNT(*) AS c FROM whatsapp_delivery_events").fetchone()["c"] == 1

            incoming = server.apply_whatsapp_webhook(
                db,
                {
                    "entry": [
                        {
                            "changes": [
                                {
                                    "value": {
                                        "metadata": {"phone_number_id": "123"},
                                        "messages": [{"id": "wamid.in.1", "from": "5492994522126", "timestamp": "2", "type": "text", "text": {"body": "Necesito mi QR"}}],
                                    }
                                }
                            ]
                        }
                    ]
                },
            )
            assert incoming["messages"][0]["event_id"] == event_id
            assert db.execute("SELECT COUNT(*) AS c FROM communication_assistant_history WHERE event_id = ?", (event_id,)).fetchone()["c"] == 1

        os.environ["APP_ENV"] = "production"
        os.environ["WHATSAPP_ENABLED"] = "true"
        os.environ["WHATSAPP_PROVIDER"] = "meta"
        os.environ["WHATSAPP_ACCESS_TOKEN"] = ""
        os.environ["WHATSAPP_SAFE_MODE"] = "true"
        readiness = server.validate_production_configuration(
            {
                "APP_ENV": "production",
                "BASE_URL": "https://bitora.test",
                "HTTPS_REQUIRED": "true",
                "QR_DB_ENGINE": "postgres",
                "QR_POSTGRES_DSN": "postgresql://redacted",
                "QR_REQUIRE_LOGIN": "1",
                "WHATSAPP_ENABLED": "true",
                "WHATSAPP_PROVIDER": "meta",
                "WHATSAPP_SAFE_MODE": "true",
            }
        )
        assert not readiness["ok"]
        assert any("WHATSAPP_ACCESS_TOKEN" in item for item in readiness["errors"])
        assert any("WHATSAPP_SAFE_MODE" in item for item in readiness["errors"])

        provider = MetaCloudWhatsAppProvider(access_token="token", phone_number_id="123", business_account_id="456", verify_token="verify", app_secret="secret")
        assert provider.validate_configuration()["ok"]
        os.environ["WHATSAPP_SAFE_MODE"] = "false"
        assert provider.validate_configuration()["ok"]

        raw = b'{"ok":true}'
        signature = "sha256=" + hmac.new(b"secret", raw, hashlib.sha256).hexdigest()
        assert verify_meta_signature(raw, signature, "secret")
        assert not verify_meta_signature(raw, "sha256=bad", "secret")
        assert normalize_phone("+54 9 299 452-2126") == "5492994522126"

        print("OK: WhatsApp productivo validado en configuracion, cola, webhooks, firma e idempotencia")
    finally:
        server.DB_PATH = original_path
        for key, value in previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        try:
            os.remove(path)
        except OSError:
            pass


if __name__ == "__main__":
    main()
