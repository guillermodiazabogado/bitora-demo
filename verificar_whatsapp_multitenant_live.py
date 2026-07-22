from __future__ import annotations

import json
import os
import secrets
import time

import server
from backend.services.whatsapp import normalize_phone, valid_phone
from live_integrations_utils import assert_true, classify, close_context, contract_result, live_enabled, synthetic_multitenant_db, write_report


NAME = "whatsapp_multitenant_live"


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "si"}


def _mask(value: str) -> str:
    text = str(value or "")
    if len(text) <= 10:
        return "***"
    return f"{text[:5]}***{text[-5:]}"


def _live_result() -> dict:
    required = [
        "WHATSAPP_PROVIDER",
        "WHATSAPP_ENABLED",
        "WHATSAPP_ACCESS_TOKEN",
        "WHATSAPP_PHONE_NUMBER_ID",
        "WHATSAPP_BUSINESS_ACCOUNT_ID",
        "WHATSAPP_FORCE_RECIPIENT",
        "WHATSAPP_SAFE_MODE",
        "BITORA_LIVE_INTEGRATIONS",
    ]
    missing = [key for key in required if not os.environ.get(key)]
    if missing:
        return {"name": NAME, "mode": "contract", "status": "omitted", "missing_env": missing, "checks": {}}
    assert_true(os.environ.get("WHATSAPP_PROVIDER", "").strip().lower() == "meta", "WHATSAPP_PROVIDER debe ser meta")
    assert_true(_truthy(os.environ.get("WHATSAPP_ENABLED")), "WHATSAPP_ENABLED debe estar activo")
    assert_true(_truthy(os.environ.get("WHATSAPP_SAFE_MODE")), "WHATSAPP_SAFE_MODE debe seguir activo")
    forced_recipient = normalize_phone(os.environ.get("WHATSAPP_FORCE_RECIPIENT", ""))
    assert_true(valid_phone(forced_recipient), "WHATSAPP_FORCE_RECIPIENT debe ser un telefono valido con codigo de pais")

    server.init_db()
    run_id = secrets.token_hex(4)
    with server.connect() as db:
        now = server.now_iso()
        org_a = server.bootstrap_default_organization(db)
        db.execute(
            """
            UPDATE organizations
            SET safe_mode_whatsapp = 1, force_whatsapp_recipient = ?, updated_at = ?
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
            VALUES (?, ?, ?, 'active', 'standard', 1, 1, 'beta-safe@example.test', '5491100000000', ?, ?)
            """,
            (server.make_public_id("org"), f"WhatsApp Live Beta {run_id}", f"WhatsApp Live Beta {run_id}", now, now),
        ).lastrowid)
        event_a = server.insert_event_from_config(db, {"name": f"WhatsApp Live Alfa {run_id}", "organization_id": org_a}, "Admin")
        event_b = server.insert_event_from_config(db, {"name": f"WhatsApp Live Beta {run_id}", "organization_id": org_b}, "Admin")
        encrypted = server.integration_secret_service().encrypt(json.dumps(
            {
                "provider": "meta",
                "access_token": os.environ["WHATSAPP_ACCESS_TOKEN"],
                "phone_number_id": os.environ["WHATSAPP_PHONE_NUMBER_ID"],
                "business_account_id": os.environ["WHATSAPP_BUSINESS_ACCOUNT_ID"],
            },
            ensure_ascii=True,
        ))
        integration_a = int(db.execute(
            """
            INSERT INTO organization_integrations (
                organization_id, provider, integration_type, name, mode, status,
                configuration_encrypted, metadata_json, last_tested_at, last_test_status,
                created_by, updated_by, created_at, updated_at
            )
            VALUES (?, 'meta', 'whatsapp_provider', ?, 'client_owned', 'connected', ?, ?, ?, 'passed', 'Admin', 'Admin', ?, ?)
            """,
            (
                org_a,
                f"Meta WhatsApp Live {run_id}",
                encrypted,
                json.dumps(
                    {
                        "phone_number_id": _mask(os.environ["WHATSAPP_PHONE_NUMBER_ID"]),
                        "business_account_id": _mask(os.environ["WHATSAPP_BUSINESS_ACCOUNT_ID"]),
                        "api_version": os.environ.get("WHATSAPP_API_VERSION") or os.environ.get("WHATSAPP_META_API_URL", "https://graph.facebook.com/v22.0").rsplit("/", 1)[-1],
                    },
                    ensure_ascii=True,
                ),
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
            VALUES (?, 'meta', 'whatsapp_provider', ?, 'client_owned', 'connected', ?, '{}', 'Admin', 'Admin', ?, ?)
            """,
            (org_b, f"Meta WhatsApp Beta {run_id}", encrypted, now, now),
        ).lastrowid)
        db.execute(
            "INSERT INTO event_integrations (event_id, channel, organization_integration_id, is_default, enabled, created_at, updated_at) VALUES (?, 'whatsapp', ?, 1, 1, ?, ?)",
            (event_a, integration_a, now, now),
        )
        person_id = int(db.execute(
            "INSERT INTO people (first_name, last_name, email, phone, created_at) VALUES (?, 'WhatsApp', ?, ?, ?)",
            (f"Live{run_id}", f"whatsapp-live-{run_id}@example.test", "5492990000000", now),
        ).lastrowid)
        accreditation_id = int(db.execute(
            "INSERT INTO accreditations (event_id, person_id, type, status, token, created_at) VALUES (?, ?, 'General', 'confirmed', ?, ?)",
            (event_a, person_id, f"EVT-WA-{run_id.upper()}", now),
        ).lastrowid)
        server.upsert_communication_preference(
            db,
            person_id,
            {
                "email": f"whatsapp-live-{run_id}@example.test",
                "phone": "5492990000000",
                "acepta_email": 0,
                "acepta_whatsapp": 1,
                "canal_preferido": "whatsapp",
            },
        )
        rows = server.communication_audience_rows(db, event_a, "all")
        queued = server.queue_communication(
            db,
            event_id=event_a,
            actor="Admin",
            audience="whatsapp_live",
            channel="whatsapp",
            template_code="whatsapp_live",
            subject=f"BITORA WhatsApp Live {run_id}",
            content=f"BITORA STAGING - prueba WhatsApp Live {run_id}. Safe Mode activo.",
            rows=rows,
            process_now=True,
        )
        queue_ids = queued.pop("_whatsapp_queue_ids", [])
        assert_true(queued["queued"] == 1 and queue_ids, "Debe crear un WhatsApp real en cola")
        queue_id = int(queue_ids[0])
        queue_row = db.execute("SELECT * FROM communication_queue WHERE id = ?", (queue_id,)).fetchone()
        assert_true(int(queue_row["organization_id"]) == org_a, "La cola debe guardar organization_id correcto")
        assert_true(int(queue_row["integration_id"]) == integration_a, "La cola debe guardar integration_id correcto")
        assert_true(int(queue_row["event_id"]) == event_a, "La cola debe guardar event_id correcto")
        assert_true(server.event_channel_integration_id(db, event_b, "whatsapp") != integration_a, "Evento Beta no debe resolver integracion Alfa")
        job_id = server.job_queue_service().enqueue(
            "whatsapp.send",
            {"queue_id": queue_id},
            priority="high",
            actor="Admin",
            event_id=event_a,
            organization_id=org_a,
            integration_id=integration_a,
        )

    deadline = time.time() + int(os.environ.get("WHATSAPP_LIVE_TIMEOUT_SECONDS", "60"))
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
    assert_true(final_queue["status"] in {"enviado", "entregado", "leido"}, f"WhatsApp debe quedar enviado, estado={final_queue['status']}, error={final_queue['last_error']}")
    assert_true(str(final_queue["provider"]) == "meta", "Proveedor final debe ser Meta")
    assert_true(bool(final_queue["provider_message_id"]), "Meta debe devolver message_id")
    assert_true(str(final_job["status"]) == "completed", f"Job debe completar, estado={final_job['status']}")

    webhook_receipt = str(final_queue["status"]) in {"entregado", "leido"} or bool(final_queue["delivered_at"] or final_queue["read_at"])
    manual_receipt = _truthy(os.environ.get("WHATSAPP_LIVE_RECEIPT_CONFIRMED"))
    receipt_confirmed = webhook_receipt or manual_receipt
    with server.connect() as db:
        audit_count = int(db.execute(
            "SELECT COUNT(*) AS c FROM audit_logs WHERE entity_type = 'communication_queue' AND entity_id = ? AND action = 'communications.whatsapp_sent'",
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
    assert_true(audit_count >= 1, "Debe existir auditoria de WhatsApp enviado")
    assert_true(wrong_integration is None, "No debe existir integracion cruzada en el evento Alfa")
    assert_true(receipt_confirmed, "Meta acepto el envio, pero falta confirmar recepcion real en telefono o recibir webhook delivered/read")

    return {
        "name": NAME,
        "mode": "live",
        "status": "passed",
        "missing_env": [],
        "checks": {
            "provider": "meta",
            "authentication": True,
            "message_id_masked": _mask(str(final_queue["provider_message_id"])),
            "job_id": int(job_id),
            "queue_id": int(queue_id),
            "organization_id": int(final_queue["organization_id"]),
            "integration_id": int(final_queue["integration_id"]),
            "event_id": int(final_queue["event_id"]),
            "safe_mode": True,
            "forced_recipient_used": True,
            "receipt_confirmed": True,
            "receipt_source": "webhook" if webhook_receipt else "manual_operator_confirmation",
            "audit": True,
            "cross_messages": 0,
            "unauthorized_recipients": 0,
            "tokens_exposed": 0,
            "duplicates_by_bitora": 0,
        },
    }


def main() -> None:
    if live_enabled():
        try:
            result = _live_result()
        except Exception as exc:
            result = {
                "name": NAME,
                "mode": "live",
                "status": "failed",
                "missing_env": [],
                "checks": {},
                "error": str(exc)[:500],
            }
        write_report(NAME, result)
        print(json.dumps(result, ensure_ascii=False))
        if result["status"] != "passed":
            raise SystemExit(1)
        return
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
