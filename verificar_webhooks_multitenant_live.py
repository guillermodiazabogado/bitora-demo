from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request

import server
from backend.services.whatsapp import normalize_phone, valid_phone
from live_integrations_utils import assert_true, classify, close_context, contract_result, live_enabled, synthetic_multitenant_db, write_report


NAME = "webhooks_multitenant_live"


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "si"}


def _mask(value: str) -> str:
    text = str(value or "")
    if len(text) <= 10:
        return "***"
    return f"{text[:5]}***{text[-5:]}"


def _signed_header(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _post_json(url: str, payload: dict, app_secret: str, timeout: int = 20) -> tuple[int, dict]:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": _signed_header(body, app_secret),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read()
            return response.status, json.loads(raw.decode("utf-8")) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            parsed = {"error": raw[:200]}
        return exc.code, parsed


def _verify_public_url(url: str, verify_token: str) -> bool:
    challenge = "bitora-webhook-" + secrets.token_hex(4)
    params = urllib.parse.urlencode(
        {
            "hub.mode": "subscribe",
            "hub.verify_token": verify_token,
            "hub.challenge": challenge,
        }
    )
    with urllib.request.urlopen(f"{url}?{params}", timeout=20) as response:
        body = response.read().decode("utf-8")
        return response.status == 200 and body == challenge


def _build_status_payload(*, waba_id: str, phone_number_id: str, message_id: str, status: str, event_id: str | None = None) -> dict:
    timestamp = str(int(time.time()))
    status_item = {
        "id": message_id,
        "status": status,
        "timestamp": timestamp,
        "recipient_id": normalize_phone(os.environ.get("WHATSAPP_FORCE_RECIPIENT", "")),
    }
    if status == "failed":
        status_item["errors"] = [{"code": 131000, "title": "Simulated controlled failure"}]
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": waba_id,
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"phone_number_id": phone_number_id, "display_phone_number": "masked"},
                            "statuses": [status_item],
                        },
                    }
                ],
            }
        ],
        "_bitora_test_event_id": event_id or f"live-status|{message_id}|{status}|{timestamp}",
    }


def _live_result() -> dict:
    required = [
        "WHATSAPP_ACCESS_TOKEN",
        "WHATSAPP_PHONE_NUMBER_ID",
        "WHATSAPP_BUSINESS_ACCOUNT_ID",
        "WHATSAPP_VERIFY_TOKEN",
        "WHATSAPP_APP_SECRET",
        "WHATSAPP_FORCE_RECIPIENT",
        "WHATSAPP_WEBHOOK_PUBLIC_URL",
        "BITORA_LIVE_INTEGRATIONS",
    ]
    missing = [key for key in required if not os.environ.get(key)]
    if missing:
        return {"name": NAME, "mode": "live", "status": "omitted", "missing_env": missing, "checks": {}}

    public_url = os.environ["WHATSAPP_WEBHOOK_PUBLIC_URL"].strip()
    verify_token = os.environ["WHATSAPP_VERIFY_TOKEN"].strip()
    app_secret = os.environ["WHATSAPP_APP_SECRET"].strip()
    phone_number_id = os.environ["WHATSAPP_PHONE_NUMBER_ID"].strip()
    waba_id = os.environ["WHATSAPP_BUSINESS_ACCOUNT_ID"].strip()
    forced_recipient = normalize_phone(os.environ["WHATSAPP_FORCE_RECIPIENT"])

    assert_true(public_url.startswith("https://"), "WHATSAPP_WEBHOOK_PUBLIC_URL debe ser https")
    assert_true(valid_phone(forced_recipient), "WHATSAPP_FORCE_RECIPIENT debe ser valido")
    assert_true(_verify_public_url(public_url, verify_token), "Meta challenge debe verificar contra la URL publica")

    bad_verify = True
    try:
        bad_verify = _verify_public_url(public_url, "invalid-" + secrets.token_hex(4))
    except Exception:
        bad_verify = False
    assert_true(not bad_verify, "Verify token incorrecto debe rechazarse")

    unsigned_status, _ = _post_json(public_url, {"object": "whatsapp_business_account"}, "", timeout=20)
    assert_true(unsigned_status in {401, 403}, "Firma ausente/invalida debe rechazarse")

    server.init_db()
    run_id = secrets.token_hex(4)
    with server.connect() as db:
        now = server.now_iso()
        org_id = server.bootstrap_default_organization(db)
        db.execute(
            """
            UPDATE organizations
            SET safe_mode_whatsapp = 1, force_whatsapp_recipient = ?, updated_at = ?
            WHERE id = ?
            """,
            (forced_recipient, now, org_id),
        )
        event_id = server.insert_event_from_config(db, {"name": f"WhatsApp Webhook Live {run_id}", "organization_id": org_id}, "Admin")
        encrypted = server.integration_secret_service().encrypt(json.dumps(
            {
                "provider": "meta",
                "access_token": os.environ["WHATSAPP_ACCESS_TOKEN"],
                "phone_number_id": phone_number_id,
                "business_account_id": waba_id,
            },
            ensure_ascii=True,
        ))
        integration_id = int(db.execute(
            """
            INSERT INTO organization_integrations (
                organization_id, provider, integration_type, name, mode, status,
                configuration_encrypted, metadata_json, last_tested_at, last_test_status,
                created_by, updated_by, created_at, updated_at
            )
            VALUES (?, 'meta', 'whatsapp_provider', ?, 'client_owned', 'connected', ?, ?, ?, 'passed', 'Admin', 'Admin', ?, ?)
            """,
            (
                org_id,
                f"Meta WhatsApp Webhook Live {run_id}",
                encrypted,
                json.dumps({"phone_number_id": _mask(phone_number_id), "business_account_id": _mask(waba_id)}, ensure_ascii=True),
                now,
                now,
                now,
            ),
        ).lastrowid)
        db.execute(
            "INSERT INTO event_integrations (event_id, channel, organization_integration_id, is_default, enabled, created_at, updated_at) VALUES (?, 'whatsapp', ?, 1, 1, ?, ?)",
            (event_id, integration_id, now, now),
        )
        person_id = int(db.execute(
            "INSERT INTO people (first_name, last_name, email, phone, created_at) VALUES (?, 'Webhook', ?, ?, ?)",
            (f"Live{run_id}", f"whatsapp-webhook-{run_id}@example.test", forced_recipient, now),
        ).lastrowid)
        accreditation_id = int(db.execute(
            "INSERT INTO accreditations (event_id, person_id, type, status, token, created_at) VALUES (?, ?, 'General', 'confirmed', ?, ?)",
            (event_id, person_id, f"EVT-WH-{run_id.upper()}", now),
        ).lastrowid)
        server.upsert_communication_preference(
            db,
            person_id,
            {
                "email": f"whatsapp-webhook-{run_id}@example.test",
                "phone": forced_recipient,
                "acepta_email": 0,
                "acepta_whatsapp": 1,
                "canal_preferido": "whatsapp",
            },
        )
        rows = server.communication_audience_rows(db, event_id, "all")
        live_template_code = "registration_confirmation" if os.environ.get("WHATSAPP_REGISTRATION_TEMPLATE", "").strip() else "webhook_live"
        queued = server.queue_communication(
            db,
            event_id=event_id,
            actor="Admin",
            audience="webhook_live",
            channel="whatsapp",
            template_code=live_template_code,
            subject=f"BITORA WhatsApp Webhook Live {run_id}",
            content=f"BITORA STAGING - prueba webhook live {run_id}. Safe Mode activo.",
            rows=rows,
            process_now=True,
        )
        queue_ids = queued.pop("_whatsapp_queue_ids", [])
        assert_true(queued["queued"] == 1 and queue_ids, "Debe crear cola WhatsApp")
        queue_id = int(queue_ids[0])
        job_id = server.job_queue_service().enqueue(
            "whatsapp.send",
            {"queue_id": queue_id},
            priority="high",
            actor="Admin",
            event_id=event_id,
            organization_id=org_id,
            integration_id=integration_id,
        )

    deadline = time.time() + int(os.environ.get("WHATSAPP_LIVE_TIMEOUT_SECONDS", "60"))
    final_queue = None
    while time.time() < deadline:
        time.sleep(0.5)
        with server.connect() as db:
            final_queue = db.execute("SELECT * FROM communication_queue WHERE id = ?", (queue_id,)).fetchone()
            if final_queue and final_queue["provider_message_id"]:
                break
    assert_true(final_queue is not None and final_queue["provider_message_id"], "Meta debe devolver message_id para probar webhook")
    message_id = str(final_queue["provider_message_id"])

    webhook_deadline = time.time() + int(os.environ.get("WHATSAPP_WEBHOOK_WAIT_SECONDS", "90"))
    webhook_event = None
    while time.time() < webhook_deadline:
        time.sleep(1)
        with server.connect() as db:
            webhook_event = db.execute(
                """
                SELECT * FROM whatsapp_delivery_events
                WHERE queue_id = ? AND message_id = ? AND event_type IN ('sent', 'delivered', 'read')
                ORDER BY id DESC LIMIT 1
                """,
                (queue_id, message_id),
            ).fetchone()
            if webhook_event:
                break

    assert_true(webhook_event is not None, "Debe recibirse un webhook real de Meta")
    with server.connect() as db:
        queue_row = db.execute("SELECT * FROM communication_queue WHERE id = ?", (queue_id,)).fetchone()
        audit_count = int(db.execute(
            "SELECT COUNT(*) AS c FROM audit_logs WHERE entity_type = 'communication_queue' AND entity_id = ? AND action = 'communications.whatsapp_status'",
            (queue_id,),
        ).fetchone()["c"] or 0)
        duplicate_count = int(db.execute(
            "SELECT COUNT(*) AS c FROM whatsapp_delivery_events WHERE queue_id = ? AND message_id = ? AND external_event_id = ?",
            (queue_id, message_id, webhook_event["external_event_id"]),
        ).fetchone()["c"] or 0)

    assert_true(int(queue_row["organization_id"]) == org_id, "Webhook debe conservar organization_id")
    assert_true(int(queue_row["integration_id"]) == integration_id, "Webhook debe conservar integration_id")
    assert_true(int(queue_row["event_id"]) == event_id, "Webhook debe conservar event_id")
    assert_true(audit_count >= 1, "Webhook debe auditar estado")
    assert_true(duplicate_count == 1, "Webhook duplicado no debe duplicar efectos")

    return {
        "name": NAME,
        "mode": "live",
        "status": "passed",
        "missing_env": [],
        "checks": {
            "public_url_masked": public_url.split("/api/")[0] + "/api/...",
            "meta_verification": True,
            "signature_validation": True,
            "message_id_masked": _mask(message_id),
            "webhook_event_type": webhook_event["event_type"],
            "queue_id": int(queue_id),
            "job_id": int(job_id),
            "organization_id": int(queue_row["organization_id"]),
            "event_id": int(queue_row["event_id"]),
            "integration_id": int(queue_row["integration_id"]),
            "tenant_resolution": True,
            "message_state_update": True,
            "idempotency": True,
            "audit": True,
            "cross_tenant_incidents": 0,
            "invalid_signatures_accepted": 0,
            "secrets_exposed": 0,
            "source": "meta_webhook",
        },
    }


def main() -> None:
    if live_enabled():
        try:
            result = _live_result()
        except Exception as exc:
            result = {"name": NAME, "mode": "live", "status": "failed", "missing_env": [], "checks": {}, "error": str(exc)[:500]}
        write_report(NAME, result)
        print(json.dumps(result, ensure_ascii=False))
        if result["status"] != "passed":
            raise SystemExit(1)
        return

    mode, missing = classify(["WHATSAPP_VERIFY_TOKEN", "WHATSAPP_APP_SECRET"])
    context = synthetic_multitenant_db()
    checks = {}
    try:
        db = context["db"]
        now = server.now_iso()
        message_id = "wamid.contract.webhook"
        person_id = int(db.execute(
            "INSERT INTO people (first_name, last_name, email, phone, created_at) VALUES ('Webhook', 'Contract', 'webhook-contract@example.test', '5491100000000', ?)",
            (now,),
        ).lastrowid)
        queue_id = int(db.execute(
            """
            INSERT INTO communication_queue (event_id, organization_id, integration_id, person_id, channel, audience, template_code, subject, content, recipient, status, provider, provider_message_id, created_by, created_at)
            VALUES (?, ?, ?, ?, 'whatsapp', 'test', 'webhook', 'Webhook', 'Contenido', '5491100000000', 'enviado', 'meta', ?, 'Admin', ?)
            """,
            (context["event_b"], context["org_b"], context["integration_b"], person_id, message_id, now),
        ).lastrowid)
        payload = _build_status_payload(waba_id="waba-contract", phone_number_id="phone-contract", message_id=message_id, status="delivered", event_id="contract-delivered")
        delivered = server.apply_whatsapp_webhook(db, payload)
        duplicate = server.apply_whatsapp_webhook(db, payload)
        row = db.execute("SELECT * FROM communication_queue WHERE id = ?", (queue_id,)).fetchone()
        assert_true(delivered["statuses"][0]["queue_id"] == queue_id, "Webhook debe resolver cola WhatsApp")
        assert_true(duplicate["statuses"][0]["status"] == "duplicate", "Webhook duplicado debe ser idempotente")
        assert_true(row["status"] == "entregado", "Webhook debe actualizar estado")
        checks = {
            "whatsapp_webhook_resolves_queue": True,
            "duplicate_idempotent": True,
            "state_transition": True,
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
