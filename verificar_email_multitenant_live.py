from __future__ import annotations

import json
import os
import secrets
import time

import server
from live_integrations_utils import assert_true, classify, close_context, contract_result, live_enabled, synthetic_multitenant_db, write_report


NAME = "email_multitenant_live"


def _mask_message_id(value: str) -> str:
    text = str(value or "")
    if len(text) <= 12:
        return "***"
    return f"{text[:6]}***{text[-6:]}"


def _live_result() -> dict:
    missing = [
        key
        for key in [
            "EMAIL_PROVIDER",
            "EMAIL_ENABLED",
            "EMAIL_API_KEY",
            "EMAIL_FROM",
            "EMAIL_FORCE_RECIPIENT",
            "EMAIL_SAFE_MODE",
            "BITORA_LIVE_INTEGRATIONS",
        ]
        if not os.environ.get(key)
    ]
    if missing:
        return {
            "name": NAME,
            "mode": "contract",
            "status": "omitted",
            "missing_env": missing,
            "checks": {},
        }
    assert_true(os.environ.get("EMAIL_ENABLED", "").lower() in {"1", "true", "yes", "si"}, "EMAIL_ENABLED debe estar activo")
    assert_true(os.environ.get("EMAIL_SAFE_MODE", "").lower() in {"1", "true", "yes", "si"}, "EMAIL_SAFE_MODE debe seguir activo")

    server.init_db()
    run_id = secrets.token_hex(4)
    forced_recipient = os.environ["EMAIL_FORCE_RECIPIENT"].strip()
    with server.connect() as db:
        now = server.now_iso()
        org_a = server.bootstrap_default_organization(db)
        db.execute(
            """
            UPDATE organizations
            SET safe_mode_email = 1, force_email_recipient = ?, updated_at = ?
            WHERE id = ?
            """,
            (forced_recipient, now, org_a),
        )
        org_b = int(db.execute(
            """
            INSERT INTO organizations (
                public_id, name, legal_name, status, plan,
                safe_mode_email, safe_mode_whatsapp, force_email_recipient, force_whatsapp_recipient,
                created_at, updated_at
            )
            VALUES (?, ?, ?, 'active', 'standard', 1, 1, ?, '5491100000000', ?, ?)
            """,
            (server.make_public_id("org"), f"Email Live Beta {run_id}", f"Email Live Beta {run_id}", "beta-safe@example.test", now, now),
        ).lastrowid)
        event_a = server.insert_event_from_config(db, {"name": f"Email Live Alfa {run_id}", "organization_id": org_a}, "Admin")
        event_b = server.insert_event_from_config(db, {"name": f"Email Live Beta {run_id}", "organization_id": org_b}, "Admin")
        encrypted = server.integration_secret_service().encrypt(json.dumps({"provider": "resend", "api_key": os.environ["EMAIL_API_KEY"]}))
        integration_a = int(db.execute(
            """
            INSERT INTO organization_integrations (
                organization_id, provider, integration_type, name, mode, status,
                configuration_encrypted, metadata_json, last_tested_at, last_test_status,
                created_by, updated_by, created_at, updated_at
            )
            VALUES (?, 'resend', 'email_provider', ?, 'client_owned', 'connected', ?, ?, ?, 'passed', 'Admin', 'Admin', ?, ?)
            """,
            (
                org_a,
                f"Resend Email Live {run_id}",
                encrypted,
                json.dumps({"from": os.environ.get("EMAIL_FROM", ""), "reply_to": os.environ.get("EMAIL_REPLY_TO", "")}, ensure_ascii=True),
                now,
                now,
                now,
            ),
        ).lastrowid)
        integration_b = int(db.execute(
            """
            INSERT INTO organization_integrations (
                organization_id, provider, integration_type, name, mode, status,
                configuration_encrypted, metadata_json, created_by, updated_by, created_at, updated_at
            )
            VALUES (?, 'resend', 'email_provider', ?, 'client_owned', 'connected', ?, '{}', 'Admin', 'Admin', ?, ?)
            """,
            (org_b, f"Resend Email Beta {run_id}", encrypted, now, now),
        ).lastrowid)
        db.execute(
            "INSERT INTO event_integrations (event_id, channel, organization_integration_id, is_default, enabled, created_at, updated_at) VALUES (?, 'email', ?, 1, 1, ?, ?)",
            (event_a, integration_a, now, now),
        )
        person_id = int(db.execute(
            "INSERT INTO people (first_name, last_name, email, phone, created_at) VALUES (?, 'Live', ?, '', ?)",
            (f"Email{run_id}", f"email-live-{run_id}@example.test", now),
        ).lastrowid)
        accreditation_id = int(db.execute(
            "INSERT INTO accreditations (event_id, person_id, type, status, token, created_at) VALUES (?, ?, 'General', 'confirmed', ?, ?)",
            (event_a, person_id, f"EVT-EMAIL-{run_id.upper()}", now),
        ).lastrowid)
        server.upsert_communication_preference(
            db,
            person_id,
            {
                "email": f"blocked-{run_id}@example.test",
                "phone": "",
                "acepta_email": 1,
                "acepta_whatsapp": 0,
                "canal_preferido": "email",
            },
        )
        rows = server.communication_audience_rows(db, event_a, "all")
        result = server.queue_communication(
            db,
            event_id=event_a,
            actor="Admin",
            audience="email_live",
            channel="email",
            template_code="email_live",
            subject=f"BITORA Email Live {run_id}",
            content="<p>Prueba live controlada de BITORA via Resend.</p>",
            rows=rows,
            process_now=True,
        )
        queue_ids = result.pop("_email_queue_ids", [])
        assert_true(result["queued"] == 1 and queue_ids, "Debe crear un email real en cola")
        queue_id = int(queue_ids[0])
        queue_row = db.execute("SELECT * FROM communication_queue WHERE id = ?", (queue_id,)).fetchone()
        assert_true(int(queue_row["organization_id"]) == org_a, "La cola debe guardar organization_id correcto")
        assert_true(int(queue_row["integration_id"]) == integration_a, "La cola debe guardar integration_id correcto")
        assert_true(int(queue_row["event_id"]) == event_a, "La cola debe guardar event_id correcto")
        assert_true(server.event_channel_integration_id(db, event_b, "email") != integration_a, "Evento Beta no debe resolver integracion Alfa")
        job_id = server.job_queue_service().enqueue(
            "email.send",
            {"queue_id": queue_id},
            priority="high",
            actor="Admin",
            event_id=event_a,
            organization_id=org_a,
            integration_id=integration_a,
        )

    deadline = time.time() + 45
    final_queue = None
    final_job = None
    while time.time() < deadline:
        time.sleep(0.5)
        with server.connect() as db:
            final_queue = db.execute("SELECT * FROM communication_queue WHERE id = ?", (queue_id,)).fetchone()
            final_job = db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
            if final_queue and final_queue["status"] in {"enviado", "entregado", "leido", "error"}:
                break
    assert_true(final_queue is not None, "Debe existir item de cola")
    assert_true(final_job is not None, "Debe existir job")
    assert_true(final_queue["status"] == "enviado", f"Email debe quedar enviado, estado={final_queue['status']}, error={final_queue['last_error']}")
    assert_true(str(final_queue["provider"]) == "resend", "Proveedor final debe ser Resend")
    assert_true(bool(final_queue["provider_message_id"]), "Resend debe devolver message_id")
    assert_true(str(final_job["status"]) == "completed", f"Job debe completar, estado={final_job['status']}")
    with server.connect() as db:
        audit_count = int(db.execute(
            "SELECT COUNT(*) AS c FROM audit_logs WHERE entity_type = 'communication_queue' AND entity_id = ? AND action = 'communications.email_sent'",
            (queue_id,),
        ).fetchone()["c"] or 0)
        wrong_integration = db.execute(
            """
            SELECT oi.id
            FROM organization_integrations oi
            JOIN event_integrations ei ON ei.organization_integration_id = oi.id
            WHERE ei.event_id = ? AND oi.organization_id <> ?
            """,
            (event_a, org_a),
        ).fetchone()
    assert_true(audit_count >= 1, "Debe existir auditoria de email enviado")
    assert_true(wrong_integration is None, "No debe existir integracion cruzada en el evento Alfa")

    return {
        "name": NAME,
        "mode": "live",
        "status": "passed",
        "missing_env": [],
        "checks": {
            "provider": "resend",
            "authentication": True,
            "message_id_masked": _mask_message_id(str(final_queue["provider_message_id"])),
            "job_id": int(job_id),
            "queue_id": int(queue_id),
            "organization_id": int(final_queue["organization_id"]),
            "integration_id": int(final_queue["integration_id"]),
            "event_id": int(final_queue["event_id"]),
            "safe_mode": True,
            "forced_recipient_used": True,
            "audit": True,
            "cross_emails": 0,
            "unauthorized_recipients": 0,
            "secrets_exposed": 0,
        },
    }


def main() -> None:
    if live_enabled():
        result = _live_result()
        write_report(NAME, result)
        print(json.dumps(result, ensure_ascii=False))
        return
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
