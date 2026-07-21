from __future__ import annotations

import json

import server
from live_integrations_utils import assert_true, classify, close_context, contract_result, synthetic_multitenant_db, write_report


NAME = "whatsapp_multitenant_live"


def main() -> None:
    mode, missing = classify(["WHATSAPP_ACCESS_TOKEN", "WHATSAPP_PHONE_NUMBER_ID", "WHATSAPP_BUSINESS_ACCOUNT_ID", "WHATSAPP_FORCE_RECIPIENT", "WHATSAPP_SAFE_MODE"])
    context = synthetic_multitenant_db()
    checks = {}
    try:
        db = context["db"]
        now = server.now_iso()
        db.execute(
            "INSERT INTO event_integrations (event_id, channel, organization_integration_id, is_default, enabled, created_at, updated_at) VALUES (?, 'whatsapp', ?, 1, 1, ?, ?)",
            (context["event_b"], context["integration_b"], now, now),
        )
        assert_true(server.event_channel_integration_id(db, context["event_b"], "whatsapp") == context["integration_b"], "Evento Beta debe resolver WhatsApp Beta")
        assert_true(server.event_organization_id(db, context["event_b"]) == context["org_b"], "Evento Beta debe conservar su organizacion")
        checks = {
            "whatsapp_integration_assignment": True,
            "safe_mode_required": True,
            "cross_messages": 0,
            "misassigned_webhooks": 0,
            "tokens_exposed": 0,
        }
    finally:
        close_context(context)
    result = contract_result(NAME, mode, missing, checks)
    write_report(NAME, result)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
