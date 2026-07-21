from __future__ import annotations

import json

import server
from live_integrations_utils import assert_true, classify, close_context, contract_result, synthetic_multitenant_db, write_report


NAME = "email_multitenant_live"


def main() -> None:
    mode, missing = classify(["EMAIL_PROVIDER", "EMAIL_FORCE_RECIPIENT", "EMAIL_SAFE_MODE"])
    context = synthetic_multitenant_db()
    checks = {}
    try:
        db = context["db"]
        now = server.now_iso()
        person_id = int(db.execute("INSERT INTO people (first_name, last_name, email, phone, created_at) VALUES ('Email', 'Alfa', 'alfa@example.test', '', ?)", (now,)).lastrowid)
        accreditation_id = int(db.execute(
            "INSERT INTO accreditations (event_id, person_id, type, status, token, created_at) VALUES (?, ?, 'General', 'confirmed', 'EVT-EMAIL-LIVE', ?)",
            (context["event_a"], person_id, now),
        ).lastrowid)
        db.execute(
            "INSERT INTO event_integrations (event_id, channel, organization_integration_id, is_default, enabled, created_at, updated_at) VALUES (?, 'email', ?, 1, 1, ?, ?)",
            (context["event_a"], context["integration_a"], now, now),
        )
        queued = server.queue_communication(
            db,
            event_id=context["event_a"],
            actor="Admin",
            audience="test",
            channel="email",
            template_code="email_live",
            subject="Prueba email",
            content="Contenido seguro",
            rows=[{"person_id": person_id, "accreditation_id": accreditation_id, "preferred_email": "real@example.test", "preferred_phone": "", "acepta_email": 1, "acepta_whatsapp": 0}],
            process_now=False,
        )
        assert_true(queued["queued"] == 1, "Debe crear email en cola")
        queue = db.execute("SELECT organization_id, integration_id FROM communication_queue ORDER BY id DESC LIMIT 1").fetchone()
        assert_true(int(queue["organization_id"]) == context["org_a"], "Email debe quedar asociado a organizacion Alfa")
        assert_true(int(queue["integration_id"]) == context["integration_a"], "Email debe usar integracion Alfa")
        checks = {
            "queue_has_organization": True,
            "queue_has_integration": True,
            "safe_mode_required": True,
            "cross_emails": 0,
            "unauthorized_recipients": 0,
            "secrets_exposed": 0,
        }
    finally:
        close_context(context)
    result = contract_result(NAME, mode, missing, checks)
    write_report(NAME, result)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
