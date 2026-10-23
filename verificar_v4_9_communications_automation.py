import hashlib
import hmac
import json
import os
import tempfile
from pathlib import Path

tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
root = Path(tmp.name)
os.environ["QR_SQLITE_PATH"] = str(root / "v4_9_communications.sqlite3")
os.environ["BITORA_STORAGE_PATH"] = str(root / "storage")
os.environ["BITORA_COMMUNICATIONS_V4_ENABLED"] = "true"
os.environ["BITORA_COMMUNICATIONS_AUTOMATION_V4_ENABLED"] = "true"
os.environ["BITORA_COMMUNICATIONS_LIVE_MODE_ENABLED"] = "false"
os.environ["COMMUNICATIONS_FORCE_EMAIL_RECIPIENT"] = "qa@example.test"
os.environ["COMMUNICATIONS_FORCE_WHATSAPP_RECIPIENT"] = "5491100000000"
os.environ["QR_REQUIRE_LOGIN"] = ""

import server  # noqa: E402
from backend.services.backup import EventBackupService, EventRestoreService  # noqa: E402


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def seed():
    now = server.now_iso()
    with server.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        org = db.execute("INSERT INTO organizations (public_id,name,legal_name,trade_name,status,plan,created_at,updated_at) VALUES ('comm-v49','Comms Alfa','Comms Alfa','Comms Alfa','active','standard',?,?)", (now, now))
        org_id = int(org.lastrowid)
        other_org = db.execute("INSERT INTO organizations (public_id,name,legal_name,trade_name,status,plan,created_at,updated_at) VALUES ('comm-v49-beta','Comms Beta','Comms Beta','Comms Beta','active','standard',?,?)", (now, now))
        event = db.execute("INSERT INTO events (organization_id,name,starts_at,ends_at,status,created_at) VALUES (?,?,?,?,'draft',?)", (org_id, "Evento Comunicaciones", "2027-02-01T09:00:00+00:00", "2027-02-01T18:00:00+00:00", now))
        event_id = int(event.lastrowid)
        other_event = db.execute("INSERT INTO events (organization_id,name,starts_at,ends_at,status,created_at) VALUES (?,?,?,?,'draft',?)", (int(other_org.lastrowid), "Evento Beta", "2027-02-02T09:00:00+00:00", "2027-02-02T18:00:00+00:00", now))
        people = []
        for index in range(4):
            person = db.execute("INSERT INTO people (first_name,last_name,email,phone,created_at) VALUES (?,?,?,?,?)", (f"Ana{index}", "Demo", f"ana{index}@example.test", f"54911000000{index}", now))
            person_id = int(person.lastrowid)
            acc = db.execute("INSERT INTO accreditations (event_id,person_id,type,token,status,created_at) VALUES (?,?,?,?,?,?)", (event_id, person_id, "General", f"V49TOKEN{index}", "active", now))
            db.execute("INSERT INTO participant_communication_preferences (person_id,email,phone,acepta_email,acepta_whatsapp,canal_preferido,fecha_consentimiento,updated_at) VALUES (?,?,?,?,?,?,?,?)", (person_id, f"ana{index}@example.test", f"54911000000{index}", 1 if index != 2 else 0, 1, "email", now, now))
            people.append((person_id, int(acc.lastrowid)))
        db.execute("COMMIT")
    return org_id, event_id, int(other_org.lastrowid), int(other_event.lastrowid), people


def main():
    server.init_db()
    org_id, event_id, other_org_id, _other_event_id, _people = seed()
    service = server.communications_automation_service()
    check(not service.live_mode, "Live Mode debe permanecer OFF")
    with server.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        template = service.create_template(db, organization_id=org_id, event_id=event_id, actor="tester", data={"name": "Recordatorio", "channel": "email", "subject": "BITORA STAGING {{event_name}}", "content": "Hola {{first_name}}, prueba controlada"})["template"]
        try:
            service.update_template(db, organization_id=org_id, event_id=event_id, template_id=template["id"], actor="tester", data={"content": "{{__import__}}"})
            raise AssertionError("plantilla maliciosa aceptada")
        except server.CommunicationsAutomationError:
            pass
        approved = service.approve_template(db, organization_id=org_id, event_id=event_id, template_id=template["id"], actor="approver")["template"]
        preview = service.preview_template(db, organization_id=org_id, event_id=event_id, template_id=template["id"], sample={"first_name": "<Ana>"})
        check("&lt;Ana&gt;" in preview["content"], "preview sin escape")
        segment = service.create_segment(db, organization_id=org_id, event_id=event_id, actor="tester", data={"name": "Todos", "rules": {"accreditation_status": "active"}})["segment"]
        db.execute("INSERT INTO communication_v4_suppressions (organization_id,event_id,channel,recipient,normalized_recipient,reason,scope,active,created_by,created_at,updated_at) VALUES (?,?,?,?,?,'qa','event',1,'tester',?,?)", (org_id, event_id, "email", "ana1@example.test", "ana1@example.test", server.now_iso(), server.now_iso()))
        segment_preview = service.preview_segment(db, organization_id=org_id, event_id=event_id, segment_id=segment["id"], channel="email")
        check(segment_preview["count"] == 2, "segmento no aplico consentimiento/supresion")
        campaign = service.create_campaign(db, organization_id=org_id, event_id=event_id, actor="tester", data={"name": "Campana segura", "channel": "email", "template_id": approved["id"], "segment_id": segment["id"]})["campaign"]
        validation = service.validate_campaign(db, organization_id=org_id, event_id=event_id, campaign_id=campaign["id"], actor="tester")
        check(validation["recipient_count"] == 2, "snapshot de destinatarios incorrecto")
        service.approve_campaign(db, organization_id=org_id, event_id=event_id, campaign_id=campaign["id"], actor="approver")
        result = service.execute_campaign(db, organization_id=org_id, event_id=event_id, campaign_id=campaign["id"], actor="tester", correlation_id="v49-test")
        check(result["sent"] == 2 and not result["live_mode"], "ejecucion segura incorrecta")
        second = service.execute_campaign(db, organization_id=org_id, event_id=event_id, campaign_id=campaign["id"], actor="tester", correlation_id="v49-test")
        check(second["sent"] == 0 and second["skipped"] == 2, "idempotencia de campana fallida")
        forced = db.execute("SELECT DISTINCT recipient FROM communication_v4_messages WHERE campaign_id = ?", (campaign["id"],)).fetchall()
        check({row["recipient"] for row in forced} == {"qa@example.test"}, "Safe Mode no forzo destinatario")
        message = db.execute("SELECT * FROM communication_v4_messages WHERE campaign_id = ? LIMIT 1", (campaign["id"],)).fetchone()
        raw = json.dumps({"external_event_id": "evt-v49-1", "provider_message_id": message["provider_message_id"], "status": "delivered"}, ensure_ascii=True, sort_keys=True).encode("utf-8")
        signature = "sha256=" + hmac.new(b"secret", raw, hashlib.sha256).hexdigest()
        webhook = service.record_provider_event(db, organization_id=org_id, event_id=event_id, provider="sink", raw_body=raw, signature=signature, secret="secret", data=json.loads(raw.decode("utf-8")))
        duplicate = service.record_provider_event(db, organization_id=org_id, event_id=event_id, provider="sink", raw_body=raw, signature=signature, secret="secret", data=json.loads(raw.decode("utf-8")))
        check(webhook["ok"] and duplicate["duplicate"], "webhook/idempotencia invalida")
        try:
            service.record_provider_event(db, organization_id=org_id, event_id=event_id, provider="sink", raw_body=raw, signature="sha256=bad", secret="secret", data=json.loads(raw.decode("utf-8")))
            raise AssertionError("firma invalida aceptada")
        except server.CommunicationsAutomationError:
            pass
        automation = service.create_automation(db, organization_id=org_id, event_id=event_id, actor="tester", data={"name": "Recordatorio automatico", "template_id": approved["id"], "segment_id": segment["id"]})["automation"]
        service.set_automation_status(db, organization_id=org_id, event_id=event_id, automation_id=automation["id"], actor="tester", status="ACTIVE")
        try:
            service.preview_segment(db, organization_id=other_org_id, event_id=event_id, segment_id=segment["id"], channel="email")
            raise AssertionError("cross-tenant permitido")
        except server.CommunicationsAutomationError:
            pass
        db.execute("COMMIT")

    backup_dir = root / "backups"
    backup = EventBackupService(backup_dir, server.connect, server.DB_LOCK, app_version=server.APP_VERSION, storage=server.STORAGE).create_event_bundle(event_id, actor="tester")
    restore = EventRestoreService(server.connect, server.DB_LOCK, server.make_token, server.now_iso, app_version=server.APP_VERSION, backup_service=None, storage=server.STORAGE)
    restored = restore.restore_bytes(backup.read_bytes(), actor="tester", mode="new_event", new_event_name="Evento Comunicaciones Restaurado")
    check(restored["ok"], "restore V4.9 fallo")
    with server.connect() as db:
        new_event_id = int(restored["event_id"])
        restored_campaign = db.execute("SELECT status, live_mode FROM communication_v4_campaigns WHERE event_id = ? LIMIT 1", (new_event_id,)).fetchone()
        restored_automation = db.execute("SELECT status, safe_mode FROM communication_v4_automations WHERE event_id = ? LIMIT 1", (new_event_id,)).fetchone()
        check(restored_campaign and restored_campaign["status"] == "RESTORED_REVIEW" and int(restored_campaign["live_mode"]) == 0, "campana restaurada insegura")
        check(restored_automation and restored_automation["status"] == "PAUSED" and int(restored_automation["safe_mode"]) == 1, "automatizacion restaurada insegura")
    print("V4.9 communications automation foundation: OK")


if __name__ == "__main__":
    try:
        main()
    finally:
        tmp.cleanup()
