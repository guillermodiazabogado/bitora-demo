from __future__ import annotations

import os
import sqlite3
import tempfile
from pathlib import Path

from backend.services.email import ResendEmailProvider
from server import (
    apply_email_webhook,
    email_is_suppressed,
    queue_communication,
    suppress_email,
    validate_production_configuration,
)


def connect(path: Path):
    db = sqlite3.connect(path, isolation_level=None)
    db.row_factory = sqlite3.Row
    return db


def build_schema(db):
    db.executescript(
        """
        CREATE TABLE participant_communication_preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id INTEGER UNIQUE,
            email TEXT NOT NULL DEFAULT '',
            phone TEXT NOT NULL DEFAULT '',
            acepta_email INTEGER NOT NULL DEFAULT 0,
            acepta_whatsapp INTEGER NOT NULL DEFAULT 0,
            canal_preferido TEXT NOT NULL DEFAULT 'email',
            fecha_consentimiento TEXT,
            ultimo_contacto TEXT,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE communication_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            person_id INTEGER NOT NULL,
            accreditation_id INTEGER,
            canal TEXT NOT NULL,
            fecha TEXT NOT NULL,
            tipo TEXT NOT NULL,
            asunto TEXT NOT NULL DEFAULT '',
            contenido TEXT NOT NULL DEFAULT '',
            estado TEXT NOT NULL DEFAULT 'demo'
        );
        CREATE TABLE communication_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            person_id INTEGER NOT NULL,
            accreditation_id INTEGER,
            channel TEXT NOT NULL,
            audience TEXT NOT NULL DEFAULT '',
            template_code TEXT NOT NULL DEFAULT '',
            subject TEXT NOT NULL DEFAULT '',
            content TEXT NOT NULL DEFAULT '',
            recipient TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'pendiente',
            attempts INTEGER NOT NULL DEFAULT 0,
            max_attempts INTEGER NOT NULL DEFAULT 3,
            provider TEXT NOT NULL DEFAULT 'demo',
            provider_message_id TEXT NOT NULL DEFAULT '',
            last_error TEXT NOT NULL DEFAULT '',
            scheduled_at TEXT,
            processed_at TEXT,
            delivered_at TEXT,
            bounced_at TEXT,
            complained_at TEXT,
            opened_at TEXT,
            clicked_at TEXT,
            idempotency_key TEXT NOT NULL DEFAULT '',
            created_by TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        );
        CREATE UNIQUE INDEX idx_communication_queue_idempotency
            ON communication_queue(idempotency_key)
            WHERE idempotency_key <> '';
        CREATE TABLE email_delivery_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            queue_id INTEGER,
            provider TEXT NOT NULL DEFAULT '',
            message_id TEXT NOT NULL DEFAULT '',
            external_event_id TEXT NOT NULL DEFAULT '',
            event_type TEXT NOT NULL,
            payload TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL
        );
        CREATE UNIQUE INDEX idx_email_delivery_unique_event
            ON email_delivery_events(provider, external_event_id)
            WHERE external_event_id <> '';
        CREATE TABLE email_suppressions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER,
            email TEXT NOT NULL,
            normalized_email TEXT NOT NULL,
            reason TEXT NOT NULL,
            scope TEXT NOT NULL DEFAULT 'global',
            source TEXT NOT NULL DEFAULT '',
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(normalized_email, scope, event_id)
        );
        CREATE TABLE audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER,
            actor TEXT,
            action TEXT,
            entity_type TEXT,
            entity_id INTEGER,
            payload TEXT,
            created_at TEXT
        );
        """
    )


def row(email: str, person_id: int = 1):
    return {
        "person_id": person_id,
        "accreditation_id": person_id,
        "preferred_email": email,
        "preferred_phone": "",
        "acepta_email": 1,
        "acepta_whatsapp": 0,
        "first_name": "Ana",
        "last_name": "Demo",
        "event_name": "Evento",
        "starts_at": "2026-07-20T10:00:00",
        "token": "EVT-TEST",
        "type": "General",
        "company": "Demo",
    }


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="bitora-email-prod-"))
    db_path = tmp / "email.sqlite3"
    try:
        with connect(db_path) as db:
            build_schema(db)
            invalid = queue_communication(
                db,
                event_id=1,
                actor="QA",
                audience="manual",
                channel="email",
                template_code="test",
                subject="Hola",
                content="Contenido",
                rows=[row("mal-email")],
                process_now=True,
            )
            assert invalid["skipped"] == 1

            suppress_email(db, 1, "rebote@demo.com", "hard_bounce", "test", "event")
            assert email_is_suppressed(db, 1, "rebote@demo.com")[0]
            suppressed = queue_communication(db, event_id=1, actor="QA", audience="manual", channel="email", template_code="test", subject="Hola", content="Contenido", rows=[row("rebote@demo.com")], process_now=True)
            assert suppressed["skipped"] == 1

            queued = queue_communication(db, event_id=1, actor="QA", audience="manual", channel="email", template_code="test", subject="Hola", content="Contenido", rows=[row("ok@demo.com")], process_now=True)
            assert queued["queued"] == 1
            duplicated = queue_communication(db, event_id=1, actor="QA", audience="manual", channel="email", template_code="test", subject="Hola", content="Contenido", rows=[row("ok@demo.com")], process_now=True)
            assert duplicated["skipped"] == 1

            queue_id = db.execute("SELECT id FROM communication_queue WHERE recipient = 'ok@demo.com'").fetchone()["id"]
            db.execute("UPDATE communication_queue SET provider_message_id = 'email-msg-1', provider = 'resend' WHERE id = ?", (queue_id,))
            delivered = apply_email_webhook(db, {"id": "evt-1", "type": "email.delivered", "data": {"email_id": "email-msg-1"}})
            assert delivered["status"] == "entregado"
            duplicate = apply_email_webhook(db, {"id": "evt-1", "type": "email.delivered", "data": {"email_id": "email-msg-1"}})
            assert duplicate["duplicate"]
            assert db.execute("SELECT COUNT(*) AS c FROM email_delivery_events").fetchone()["c"] == 1

            db.execute("UPDATE communication_queue SET provider_message_id = 'email-msg-2', recipient = 'bounce@demo.com' WHERE id = ?", (queue_id,))
            bounced = apply_email_webhook(db, {"id": "evt-2", "type": "email.bounced", "data": {"email_id": "email-msg-2"}})
            assert bounced["status"] == "rebotado"
            assert email_is_suppressed(db, 1, "bounce@demo.com")[0]

        bad_env = {
            "APP_ENV": "production",
            "BASE_URL": "https://bitora.test",
            "HTTPS_REQUIRED": "true",
            "QR_DB_ENGINE": "postgres",
            "QR_POSTGRES_DSN": "postgresql://redacted",
            "QR_REQUIRE_LOGIN": "1",
            "EMAIL_ENABLED": "true",
            "EMAIL_PROVIDER": "resend",
            "EMAIL_FROM_ADDRESS": "eventos@otro.com",
            "EMAIL_API_KEY": "",
            "EMAIL_SAFE_MODE": "true",
        }
        readiness = validate_production_configuration(bad_env)
        assert not readiness["ok"]
        assert any("EMAIL_API_KEY" in item for item in readiness["errors"])
        assert any("EMAIL_SAFE_MODE" in item for item in readiness["errors"])

        previous_env = {key: os.environ.get(key) for key in ["APP_ENV", "EMAIL_WEBHOOK_SECRET", "EMAIL_VERIFIED_DOMAIN"]}
        try:
            os.environ["APP_ENV"] = "production"
            os.environ["EMAIL_WEBHOOK_SECRET"] = "whsec_test"
            os.environ["EMAIL_VERIFIED_DOMAIN"] = "bitora.test"
            provider = ResendEmailProvider(api_key="key", from_email="BITORA <eventos@otro.test>")
            assert not provider.validate_configuration()["ok"]
            provider_ok = ResendEmailProvider(api_key="key", from_email="BITORA <eventos@bitora.test>")
            assert provider_ok.validate_configuration()["ok"]
        finally:
            for key, value in previous_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

        print("OK: email productivo validado en configuracion, cola, supresion e idempotencia")
    finally:
        import shutil

        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
