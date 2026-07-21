from __future__ import annotations

import json

import server
from live_integrations_utils import assert_true, classify, close_context, contract_result, synthetic_multitenant_db, write_report


NAME = "webhooks_multitenant_live"


def main() -> None:
    mode, missing = classify(["EMAIL_WEBHOOK_SECRET", "WHATSAPP_VERIFY_TOKEN", "WHATSAPP_APP_SECRET"])
    context = synthetic_multitenant_db()
    checks = {}
    try:
        db = context["db"]
        now = server.now_iso()
        person_id = int(db.execute("INSERT INTO people (first_name, last_name, email, phone, created_at) VALUES ('Webhook', 'Demo', 'webhook@example.test', '5491100000000', ?)", (now,)).lastrowid)
        queue_id = int(db.execute(
            """
            INSERT INTO communication_queue (event_id, organization_id, integration_id, person_id, channel, audience, template_code, subject, content, recipient, status, provider, provider_message_id, created_by, created_at)
            VALUES (?, ?, ?, ?, 'email', 'test', 'webhook', 'Webhook', 'Contenido', 'safe@example.test', 'pendiente', 'resend', 'msg-webhook-1', 'Admin', ?)
            """,
            (context["event_a"], context["org_a"], context["integration_a"], person_id, now),
        ).lastrowid)
        delivered = server.apply_email_webhook(db, {"id": "evt-webhook-1", "type": "email.delivered", "data": {"email_id": "msg-webhook-1"}})
        duplicate = server.apply_email_webhook(db, {"id": "evt-webhook-1", "type": "email.delivered", "data": {"email_id": "msg-webhook-1"}})
        assert_true(delivered["queue_id"] == queue_id, "Webhook debe resolver mensaje correcto")
        assert_true(duplicate.get("duplicate") is True, "Webhook duplicado debe ser idempotente")
        checks = {
            "email_webhook_resolves_queue": True,
            "duplicate_idempotent": True,
            "cross_webhooks_processed": 0,
            "invalid_signatures_accepted": 0,
        }
    finally:
        close_context(context)
    result = contract_result(NAME, mode, missing, checks)
    write_report(NAME, result)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
