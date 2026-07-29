from __future__ import annotations

import hashlib
import hmac
import json
import re
from typing import Any


class CommunicationsAutomationError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class SinkProvider:
    name = "sink"

    def send(self, *, channel: str, recipient: str, subject: str, content: str, metadata: dict | None = None) -> dict:
        payload = json.dumps({"channel": channel, "recipient": recipient, "subject": subject, "content": content, "metadata": metadata or {}}, sort_keys=True)
        return {
            "accepted": True,
            "provider_message_id": "sink_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24],
            "provider_status": "accepted",
            "error_code": "",
            "error_message_sanitized": "",
            "retryable": False,
        }


class CommunicationsAutomationService:
    """V4.9 communications foundation with safe-mode execution only by default."""

    ALLOWED_CHANNELS = {"email", "whatsapp", "internal"}
    TEMPLATE_STATUSES = {"DRAFT", "PENDING_APPROVAL", "APPROVED", "ACTIVE", "ARCHIVED"}
    CAMPAIGN_STATUSES = {"DRAFT", "VALIDATING", "PENDING_APPROVAL", "APPROVED", "SCHEDULED", "RUNNING", "PAUSED", "COMPLETED", "PARTIALLY_FAILED", "FAILED", "CANCELLED", "RESTORED_REVIEW"}
    AUTOMATION_STATUSES = {"DRAFT", "ACTIVE", "PAUSED", "ARCHIVED"}
    SAFE_VARIABLES = {"first_name", "last_name", "full_name", "email", "event_name", "organization_name", "accreditation_type"}

    def __init__(self, audit_service, now=None, provider=None, *, live_mode: bool = False, force_email: str = "", force_phone: str = "") -> None:
        self.audit_service = audit_service
        self.now = now or (lambda: "")
        self.provider = provider or SinkProvider()
        self.live_mode = bool(live_mode)
        self.force_email = force_email.strip()
        self.force_phone = force_phone.strip()

    def summary(self, db, *, organization_id: int, event_id: int) -> dict:
        self._event(db, organization_id, event_id)
        def count(table: str, where: str = "organization_id = ? AND event_id = ?", params=None) -> int:
            return int(db.execute(f"SELECT COUNT(*) AS c FROM {table} WHERE {where}", params or (organization_id, event_id)).fetchone()["c"] or 0)
        return {
            "ok": True,
            "live_mode": self.live_mode,
            "safe_mode": True,
            "templates": count("communication_v4_templates"),
            "segments": count("communication_v4_segments"),
            "campaigns": count("communication_v4_campaigns"),
            "messages": count("communication_v4_messages"),
            "deliveries": count("communication_v4_deliveries"),
            "automations": count("communication_v4_automations"),
            "updated_at": self.now(),
        }

    def create_template(self, db, *, organization_id: int, event_id: int, actor: str, data: dict) -> dict:
        self._event(db, organization_id, event_id)
        channel = self._choice(data.get("channel") or "email", self.ALLOWED_CHANNELS)
        name = self._text(data.get("name"), 180)
        if not name:
            raise CommunicationsAutomationError("TEMPLATE_NAME_REQUIRED", "Nombre obligatorio")
        subject = self._template_text(data.get("subject") or "", 240)
        content = self._template_text(data.get("content") or "", 8000)
        self._validate_variables(subject + "\n" + content)
        now = self.now()
        cursor = db.execute(
            """
            INSERT INTO communication_v4_templates (organization_id,event_id,channel,name,status,current_version_id,created_by,created_at,updated_at)
            VALUES (?,?,?,?, 'DRAFT', NULL, ?, ?, ?)
            """,
            (organization_id, event_id, channel, name, actor, now, now),
        )
        template_id = int(cursor.lastrowid)
        version_id = self._create_template_version(db, organization_id, event_id, template_id, 1, subject, content, actor, "DRAFT")
        db.execute("UPDATE communication_v4_templates SET current_version_id = ? WHERE id = ?", (version_id, template_id))
        self.audit_service.record(db, actor, "communications.v4.template.created", "communication_v4_template", template_id, {"organization_id": organization_id, "event_id": event_id, "channel": channel})
        return {"ok": True, "template": self._template(db, organization_id, event_id, template_id)}

    def update_template(self, db, *, organization_id: int, event_id: int, template_id: int, actor: str, data: dict) -> dict:
        template = self._template(db, organization_id, event_id, template_id)
        subject = self._template_text(data.get("subject") if "subject" in data else template.get("subject", ""), 240)
        content = self._template_text(data.get("content") if "content" in data else template.get("content", ""), 8000)
        self._validate_variables(subject + "\n" + content)
        latest = int(db.execute("SELECT COALESCE(MAX(version_number), 0) AS n FROM communication_v4_template_versions WHERE template_id = ?", (template_id,)).fetchone()["n"] or 0)
        version_id = self._create_template_version(db, organization_id, event_id, template_id, latest + 1, subject, content, actor, "DRAFT")
        status = "DRAFT" if template["status"] in {"APPROVED", "ACTIVE"} else template["status"]
        db.execute("UPDATE communication_v4_templates SET name = ?, status = ?, current_version_id = ?, updated_at = ? WHERE id = ?", (self._text(data.get("name") or template["name"], 180), status, version_id, self.now(), template_id))
        self.audit_service.record(db, actor, "communications.v4.template.updated", "communication_v4_template", template_id, {"organization_id": organization_id, "event_id": event_id, "version_id": version_id})
        return {"ok": True, "template": self._template(db, organization_id, event_id, template_id)}

    def approve_template(self, db, *, organization_id: int, event_id: int, template_id: int, actor: str) -> dict:
        template = self._template(db, organization_id, event_id, template_id)
        version_id = int(template["current_version_id"] or 0)
        if not version_id:
            raise CommunicationsAutomationError("TEMPLATE_VERSION_REQUIRED", "La plantilla no tiene version")
        now = self.now()
        db.execute("UPDATE communication_v4_template_versions SET status = 'APPROVED', approved_by = ?, approved_at = ? WHERE id = ? AND template_id = ?", (actor, now, version_id, template_id))
        db.execute("UPDATE communication_v4_templates SET status = 'APPROVED', updated_at = ? WHERE id = ?", (now, template_id))
        self.audit_service.record(db, actor, "communications.v4.template.approved", "communication_v4_template", template_id, {"organization_id": organization_id, "event_id": event_id, "version_id": version_id})
        return {"ok": True, "template": self._template(db, organization_id, event_id, template_id)}

    def preview_template(self, db, *, organization_id: int, event_id: int, template_id: int, sample: dict | None = None) -> dict:
        template = self._template(db, organization_id, event_id, template_id)
        version = self._template_version(db, organization_id, event_id, int(template["current_version_id"] or 0))
        sample_data = {"first_name": "Ana", "last_name": "Demo", "full_name": "Ana Demo", "email": "ana.demo@example.test", "event_name": self._event(db, organization_id, event_id)["name"], "organization_name": self._organization_name(db, organization_id), "accreditation_type": "General"}
        sample_data.update({key: str(value) for key, value in (sample or {}).items() if key in self.SAFE_VARIABLES})
        return {"ok": True, "subject": self._render(version["subject"], sample_data), "content": self._render(version["content"], sample_data), "variables": sorted(self._variables(version["subject"] + "\n" + version["content"]))}

    def create_segment(self, db, *, organization_id: int, event_id: int, actor: str, data: dict) -> dict:
        self._event(db, organization_id, event_id)
        name = self._text(data.get("name"), 180)
        if not name:
            raise CommunicationsAutomationError("SEGMENT_NAME_REQUIRED", "Nombre obligatorio")
        rules = data.get("rules") if isinstance(data.get("rules"), dict) else {}
        self._validate_segment_rules(rules)
        now = self.now()
        cur = db.execute(
            "INSERT INTO communication_v4_segments (organization_id,event_id,name,description,rules_json,status,created_by,created_at,updated_at) VALUES (?,?,?,?,?,'ACTIVE',?,?,?)",
            (organization_id, event_id, name, self._text(data.get("description"), 1000), json.dumps(rules, ensure_ascii=True, sort_keys=True), actor, now, now),
        )
        segment_id = int(cur.lastrowid)
        self.audit_service.record(db, actor, "communications.v4.segment.created", "communication_v4_segment", segment_id, {"organization_id": organization_id, "event_id": event_id})
        return {"ok": True, "segment": dict(db.execute("SELECT * FROM communication_v4_segments WHERE id = ?", (segment_id,)).fetchone())}

    def preview_segment(self, db, *, organization_id: int, event_id: int, segment_id: int, channel: str = "email") -> dict:
        segment = self._segment(db, organization_id, event_id, segment_id)
        channel = self._choice(channel or "email", self.ALLOWED_CHANNELS)
        recipients, exclusions = self._segment_recipients(db, organization_id, event_id, json.loads(segment["rules_json"] or "{}"), channel)
        return {"ok": True, "count": len(recipients), "recipients": recipients[:50], "exclusions": exclusions}

    def create_campaign(self, db, *, organization_id: int, event_id: int, actor: str, data: dict) -> dict:
        self._event(db, organization_id, event_id)
        name = self._text(data.get("name"), 180)
        if not name:
            raise CommunicationsAutomationError("CAMPAIGN_NAME_REQUIRED", "Nombre obligatorio")
        channel = self._choice(data.get("channel") or "email", self.ALLOWED_CHANNELS)
        template = self._template(db, organization_id, event_id, int(data.get("template_id") or 0))
        if template["channel"] != channel:
            raise CommunicationsAutomationError("CAMPAIGN_CHANNEL_MISMATCH", "Canal incompatible con la plantilla")
        version = self._template_version(db, organization_id, event_id, int(template["current_version_id"] or 0))
        segment = self._segment(db, organization_id, event_id, int(data.get("segment_id") or 0))
        now = self.now()
        cur = db.execute(
            """
            INSERT INTO communication_v4_campaigns (organization_id,event_id,name,channel,template_id,template_version_id,segment_id,status,safe_mode,live_mode,created_by,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,'DRAFT',1,?,?,?,?)
            """,
            (organization_id, event_id, name, channel, int(template["id"]), int(version["id"]), int(segment["id"]), 1 if self.live_mode else 0, actor, now, now),
        )
        campaign_id = int(cur.lastrowid)
        self.audit_service.record(db, actor, "communications.v4.campaign.created", "communication_v4_campaign", campaign_id, {"organization_id": organization_id, "event_id": event_id})
        return {"ok": True, "campaign": self._campaign(db, organization_id, event_id, campaign_id)}

    def validate_campaign(self, db, *, organization_id: int, event_id: int, campaign_id: int, actor: str) -> dict:
        campaign = self._campaign(db, organization_id, event_id, campaign_id)
        segment = self._segment(db, organization_id, event_id, int(campaign["segment_id"]))
        recipients, exclusions = self._segment_recipients(db, organization_id, event_id, json.loads(segment["rules_json"] or "{}"), campaign["channel"])
        db.execute("DELETE FROM communication_v4_campaign_recipients WHERE campaign_id = ?", (campaign_id,))
        snapshot_hash = hashlib.sha256(json.dumps(recipients, sort_keys=True).encode("utf-8")).hexdigest()
        now = self.now()
        for item in recipients:
            recipient = self._forced_recipient(campaign["channel"], item["recipient"])
            db.execute(
                """
                INSERT INTO communication_v4_campaign_recipients (organization_id,event_id,campaign_id,person_id,accreditation_id,channel,recipient,original_recipient,consent_status,status,idempotency_key,snapshot_hash,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,'READY',?,?,?)
                """,
                (organization_id, event_id, campaign_id, item["person_id"], item["accreditation_id"], campaign["channel"], recipient, item["recipient"], "granted", f"campaign:{campaign_id}:person:{item['person_id']}:channel:{campaign['channel']}:version:{campaign['template_version_id']}", snapshot_hash, now),
            )
        db.execute("UPDATE communication_v4_campaigns SET status = 'VALIDATING', recipient_count = ?, excluded_count = ?, snapshot_hash = ?, updated_at = ? WHERE id = ?", (len(recipients), sum(exclusions.values()), snapshot_hash, now, campaign_id))
        self.audit_service.record(db, actor, "communications.v4.campaign.validated", "communication_v4_campaign", campaign_id, {"organization_id": organization_id, "event_id": event_id, "recipients": len(recipients), "exclusions": exclusions})
        return {"ok": True, "recipient_count": len(recipients), "exclusions": exclusions, "snapshot_hash": snapshot_hash}

    def approve_campaign(self, db, *, organization_id: int, event_id: int, campaign_id: int, actor: str) -> dict:
        campaign = self._campaign(db, organization_id, event_id, campaign_id)
        if int(campaign["recipient_count"] or 0) <= 0:
            raise CommunicationsAutomationError("CAMPAIGN_EMPTY", "La campana no tiene destinatarios validados")
        now = self.now()
        db.execute("UPDATE communication_v4_campaigns SET status = 'APPROVED', approved_by = ?, approved_at = ?, updated_at = ? WHERE id = ?", (actor, now, now, campaign_id))
        db.execute("INSERT INTO communication_v4_approvals (organization_id,event_id,campaign_id,approval_type,status,actor,created_at) VALUES (?,?,?,?,?,?,?)", (organization_id, event_id, campaign_id, "CAMPAIGN", "APPROVED", actor, now))
        self.audit_service.record(db, actor, "communications.v4.campaign.approved", "communication_v4_campaign", campaign_id, {"organization_id": organization_id, "event_id": event_id})
        return {"ok": True, "campaign": self._campaign(db, organization_id, event_id, campaign_id)}

    def execute_campaign(self, db, *, organization_id: int, event_id: int, campaign_id: int, actor: str, correlation_id: str = "") -> dict:
        campaign = self._campaign(db, organization_id, event_id, campaign_id)
        if campaign["status"] not in {"APPROVED", "SCHEDULED", "PAUSED", "RUNNING", "COMPLETED"}:
            raise CommunicationsAutomationError("CAMPAIGN_NOT_APPROVED", "La campana requiere aprobacion")
        now = self.now()
        db.execute("UPDATE communication_v4_campaigns SET status = 'RUNNING', started_at = COALESCE(started_at, ?), updated_at = ? WHERE id = ?", (now, now, campaign_id))
        recipients = db.execute("SELECT * FROM communication_v4_campaign_recipients WHERE organization_id = ? AND event_id = ? AND campaign_id = ? AND status IN ('READY','RETRY','SENT') ORDER BY id", (organization_id, event_id, campaign_id)).fetchall()
        sent = skipped = 0
        version = self._template_version(db, organization_id, event_id, int(campaign["template_version_id"]))
        event_name = self._event(db, organization_id, event_id)["name"]
        organization_name = self._organization_name(db, organization_id)
        for recipient in recipients:
            key = recipient["idempotency_key"]
            existing = db.execute("SELECT id FROM communication_v4_messages WHERE idempotency_key = ?", (key,)).fetchone()
            if existing:
                skipped += 1
                continue
            person = db.execute("SELECT * FROM people WHERE id = ?", (recipient["person_id"],)).fetchone()
            data = self._person_variables(person, event_name, organization_name)
            subject = self._render(version["subject"], data)
            content = self._render(version["content"], data)
            result = self.provider.send(channel=campaign["channel"], recipient=recipient["recipient"], subject=subject, content=content, metadata={"campaign_id": campaign_id, "safe_mode": True, "correlation_id": correlation_id})
            message_id = self._insert_message_delivery_attempt(db, organization_id, event_id, campaign, recipient, subject, content, result, actor, key)
            db.execute("UPDATE communication_v4_campaign_recipients SET status = ?, message_id = ? WHERE id = ?", ("SENT" if result["accepted"] else "FAILED", message_id, recipient["id"]))
            sent += 1 if result["accepted"] else 0
        final_status = "COMPLETED" if skipped + sent >= len(recipients) else "PARTIALLY_FAILED"
        db.execute("UPDATE communication_v4_campaigns SET status = ?, completed_at = ?, sent_count = (SELECT COUNT(*) FROM communication_v4_campaign_recipients WHERE campaign_id = ? AND status = 'SENT'), updated_at = ? WHERE id = ?", (final_status, now, campaign_id, now, campaign_id))
        self.audit_service.record(db, actor, "communications.v4.campaign.executed", "communication_v4_campaign", campaign_id, {"organization_id": organization_id, "event_id": event_id, "sent": sent, "skipped": skipped, "live_mode": self.live_mode})
        return {"ok": True, "sent": sent, "skipped": skipped, "status": final_status, "live_mode": self.live_mode}

    def create_automation(self, db, *, organization_id: int, event_id: int, actor: str, data: dict) -> dict:
        self._event(db, organization_id, event_id)
        trigger = self._choice(data.get("trigger") or "REGISTRATION_CONFIRMED", {"REGISTRATION_CONFIRMED", "ACTIVITY_REMINDER", "ATTENDANCE_RECORDED", "ELIGIBILITY_CLOSED", "CERTIFICATE_ISSUED", "SURVEY_OPENED", "SCHEDULE_CHANGED"})
        now = self.now()
        cur = db.execute(
            "INSERT INTO communication_v4_automations (organization_id,event_id,name,trigger_type,channel,template_id,segment_id,status,safe_mode,limits_json,created_by,created_at,updated_at) VALUES (?,?,?,?,?,?,?,'DRAFT',1,?,?,?,?)",
            (organization_id, event_id, self._text(data.get("name") or trigger, 180), trigger, self._choice(data.get("channel") or "email", self.ALLOWED_CHANNELS), int(data.get("template_id") or 0), int(data.get("segment_id") or 0), json.dumps(data.get("limits") or {"max_per_hour": 10}, ensure_ascii=True), actor, now, now),
        )
        automation_id = int(cur.lastrowid)
        self.audit_service.record(db, actor, "communications.v4.automation.created", "communication_v4_automation", automation_id, {"organization_id": organization_id, "event_id": event_id, "trigger": trigger})
        return {"ok": True, "automation": dict(db.execute("SELECT * FROM communication_v4_automations WHERE id = ?", (automation_id,)).fetchone())}

    def set_automation_status(self, db, *, organization_id: int, event_id: int, automation_id: int, actor: str, status: str) -> dict:
        status = self._choice(status, self.AUTOMATION_STATUSES)
        row = db.execute("SELECT * FROM communication_v4_automations WHERE id = ? AND organization_id = ? AND event_id = ?", (automation_id, organization_id, event_id)).fetchone()
        if not row:
            raise CommunicationsAutomationError("AUTOMATION_NOT_FOUND", "Automatizacion inexistente", 404)
        db.execute("UPDATE communication_v4_automations SET status = ?, updated_at = ? WHERE id = ?", (status, self.now(), automation_id))
        self.audit_service.record(db, actor, "communications.v4.automation.status", "communication_v4_automation", automation_id, {"organization_id": organization_id, "event_id": event_id, "status": status})
        return {"ok": True, "automation": dict(db.execute("SELECT * FROM communication_v4_automations WHERE id = ?", (automation_id,)).fetchone())}

    def record_provider_event(self, db, *, organization_id: int, event_id: int, provider: str, raw_body: bytes, signature: str, secret: str, data: dict) -> dict:
        self._event(db, organization_id, event_id)
        if secret:
            expected = "sha256=" + hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected, signature or ""):
                raise CommunicationsAutomationError("WEBHOOK_SIGNATURE_INVALID", "Firma invalida", 401)
        external_id = self._text(data.get("external_event_id") or data.get("id"), 180)
        if not external_id:
            raise CommunicationsAutomationError("WEBHOOK_EVENT_ID_REQUIRED", "Evento sin identificador")
        existing = db.execute("SELECT id FROM communication_v4_provider_events WHERE provider = ? AND external_event_id = ?", (provider, external_id)).fetchone()
        if existing:
            return {"ok": True, "duplicate": True, "event_id": int(existing["id"])}
        message_provider_id = self._text(data.get("provider_message_id") or data.get("message_id"), 180)
        message = db.execute("SELECT * FROM communication_v4_messages WHERE provider_message_id = ? AND organization_id = ? AND event_id = ?", (message_provider_id, organization_id, event_id)).fetchone()
        if not message:
            raise CommunicationsAutomationError("WEBHOOK_MESSAGE_UNRESOLVED", "Mensaje no resuelto", 404)
        status = self._choice(data.get("status") or "delivered", {"accepted", "sent", "delivered", "read", "bounced", "failed", "rejected", "unsubscribed"})
        now = self.now()
        cur = db.execute(
            "INSERT INTO communication_v4_provider_events (organization_id,event_id,provider,external_event_id,message_id,provider_message_id,event_type,payload_minimized,signature_valid,created_at) VALUES (?,?,?,?,?,?,?,?,1,?)",
            (organization_id, event_id, provider, external_id, int(message["id"]), message_provider_id, status, json.dumps({"status": status}, ensure_ascii=True), now),
        )
        db.execute("UPDATE communication_v4_deliveries SET status = ?, updated_at = ? WHERE message_id = ?", (status, now, int(message["id"])))
        self.audit_service.record(db, "webhook", "communications.v4.webhook.processed", "communication_v4_message", int(message["id"]), {"organization_id": organization_id, "event_id": event_id, "status": status})
        return {"ok": True, "duplicate": False, "event_id": int(cur.lastrowid)}

    def _create_template_version(self, db, organization_id, event_id, template_id, number, subject, content, actor, status):
        content_hash = hashlib.sha256((subject + "\n" + content).encode("utf-8")).hexdigest()
        cur = db.execute(
            "INSERT INTO communication_v4_template_versions (organization_id,event_id,template_id,version_number,subject,content,variables_json,status,content_hash,created_by,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (organization_id, event_id, template_id, number, subject, content, json.dumps(sorted(self._variables(subject + "\n" + content)), ensure_ascii=True), status, content_hash, actor, self.now()),
        )
        return int(cur.lastrowid)

    def _insert_message_delivery_attempt(self, db, organization_id, event_id, campaign, recipient, subject, content, result, actor, key):
        now = self.now()
        cur = db.execute(
            """
            INSERT INTO communication_v4_messages (organization_id,event_id,campaign_id,campaign_recipient_id,person_id,accreditation_id,channel,recipient,subject,content,status,provider,provider_message_id,idempotency_key,correlation_id,created_by,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (organization_id, event_id, campaign["id"], recipient["id"], recipient["person_id"], recipient["accreditation_id"], campaign["channel"], recipient["recipient"], subject, content, "accepted" if result["accepted"] else "failed", self.provider.name, result["provider_message_id"], key, f"campaign:{campaign['id']}", actor, now, now),
        )
        message_id = int(cur.lastrowid)
        delivery = db.execute(
            "INSERT INTO communication_v4_deliveries (organization_id,event_id,message_id,channel,provider,provider_message_id,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (organization_id, event_id, message_id, campaign["channel"], self.provider.name, result["provider_message_id"], result["provider_status"], now, now),
        )
        db.execute(
            "INSERT INTO communication_v4_attempts (organization_id,event_id,message_id,delivery_id,attempt_number,status,error_code,error_message_sanitized,retryable,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (organization_id, event_id, message_id, int(delivery.lastrowid), 1, "accepted" if result["accepted"] else "failed", result["error_code"], result["error_message_sanitized"], 1 if result["retryable"] else 0, now),
        )
        return message_id

    def _segment_recipients(self, db, organization_id: int, event_id: int, rules: dict, channel: str) -> tuple[list[dict], dict]:
        where = ["a.event_id = ?", "a.status <> 'cancelled'"]
        params: list[Any] = [event_id]
        if rules.get("accreditation_status"):
            where.append("a.status = ?")
            params.append(str(rules["accreditation_status"]))
        if rules.get("accreditation_type"):
            where.append("a.type = ?")
            params.append(str(rules["accreditation_type"]))
        if rules.get("activity_id"):
            where.append("EXISTS (SELECT 1 FROM reservations r WHERE r.accreditation_id = a.id AND r.event_id = a.event_id AND r.activity_id = ?)")
            params.append(int(rules["activity_id"]))
        rows = db.execute(
            f"""
            SELECT a.id AS accreditation_id, a.type AS accreditation_type, p.*
            FROM accreditations a
            JOIN people p ON p.id = a.person_id
            WHERE {' AND '.join(where)}
            ORDER BY p.email, p.id
            """,
            tuple(params),
        ).fetchall()
        seen = set()
        result = []
        exclusions = {"duplicate": 0, "missing_recipient": 0, "consent": 0, "suppression": 0}
        for row in rows:
            recipient = row["email"] if channel == "email" else (row["phone"] if channel == "whatsapp" else f"user:{row['id']}")
            recipient_key = str(recipient or "").strip().lower()
            if not recipient_key:
                exclusions["missing_recipient"] += 1
                continue
            if recipient_key in seen:
                exclusions["duplicate"] += 1
                continue
            if not self._has_consent(db, int(row["id"]), channel):
                exclusions["consent"] += 1
                continue
            if self._is_suppressed(db, organization_id, event_id, channel, recipient_key):
                exclusions["suppression"] += 1
                continue
            seen.add(recipient_key)
            result.append({"person_id": int(row["id"]), "accreditation_id": int(row["accreditation_id"]), "recipient": recipient_key, "accreditation_type": row["accreditation_type"]})
        return result, exclusions

    def _has_consent(self, db, person_id: int, channel: str) -> bool:
        pref = db.execute("SELECT * FROM participant_communication_preferences WHERE person_id = ?", (person_id,)).fetchone()
        if not pref:
            return channel == "internal"
        if channel == "email":
            return bool(int(pref["acepta_email"] or 0))
        if channel == "whatsapp":
            return bool(int(pref["acepta_whatsapp"] or 0))
        return True

    def _is_suppressed(self, db, organization_id: int, event_id: int, channel: str, recipient: str) -> bool:
        row = db.execute(
            "SELECT id FROM communication_v4_suppressions WHERE organization_id = ? AND channel = ? AND normalized_recipient = ? AND active = 1 AND (event_id = ? OR scope = 'organization')",
            (organization_id, channel, recipient, event_id),
        ).fetchone()
        return bool(row)

    def _forced_recipient(self, channel: str, recipient: str) -> str:
        if channel == "email" and self.force_email:
            return self.force_email.lower()
        if channel == "whatsapp" and self.force_phone:
            return re.sub(r"\D+", "", self.force_phone)
        return recipient

    def _template(self, db, organization_id: int, event_id: int, template_id: int) -> dict:
        row = db.execute(
            """
            SELECT t.*, v.subject, v.content
            FROM communication_v4_templates t
            LEFT JOIN communication_v4_template_versions v ON v.id = t.current_version_id
            WHERE t.id = ? AND t.organization_id = ? AND t.event_id = ?
            """,
            (template_id, organization_id, event_id),
        ).fetchone()
        if not row:
            raise CommunicationsAutomationError("TEMPLATE_NOT_FOUND", "Plantilla inexistente", 404)
        return dict(row)

    def _template_version(self, db, organization_id: int, event_id: int, version_id: int) -> dict:
        row = db.execute("SELECT * FROM communication_v4_template_versions WHERE id = ? AND organization_id = ? AND event_id = ?", (version_id, organization_id, event_id)).fetchone()
        if not row:
            raise CommunicationsAutomationError("TEMPLATE_VERSION_NOT_FOUND", "Version inexistente", 404)
        return dict(row)

    def _segment(self, db, organization_id: int, event_id: int, segment_id: int) -> dict:
        row = db.execute("SELECT * FROM communication_v4_segments WHERE id = ? AND organization_id = ? AND event_id = ?", (segment_id, organization_id, event_id)).fetchone()
        if not row:
            raise CommunicationsAutomationError("SEGMENT_NOT_FOUND", "Segmento inexistente", 404)
        return dict(row)

    def _campaign(self, db, organization_id: int, event_id: int, campaign_id: int) -> dict:
        row = db.execute("SELECT * FROM communication_v4_campaigns WHERE id = ? AND organization_id = ? AND event_id = ?", (campaign_id, organization_id, event_id)).fetchone()
        if not row:
            raise CommunicationsAutomationError("CAMPAIGN_NOT_FOUND", "Campana inexistente", 404)
        return dict(row)

    def _event(self, db, organization_id: int, event_id: int):
        row = db.execute("SELECT * FROM events WHERE id = ? AND organization_id = ?", (event_id, organization_id)).fetchone()
        if not row:
            raise CommunicationsAutomationError("COMMUNICATIONS_SCOPE_MISMATCH", "Evento fuera de alcance", 403)
        return row

    def _organization_name(self, db, organization_id: int) -> str:
        row = db.execute("SELECT name FROM organizations WHERE id = ?", (organization_id,)).fetchone()
        return str(row["name"] if row else "")

    def _person_variables(self, person, event_name: str, organization_name: str) -> dict:
        first = str(person["first_name"] or "")
        last = str(person["last_name"] or "")
        return {"first_name": first, "last_name": last, "full_name": f"{first} {last}".strip(), "email": str(person["email"] or ""), "event_name": event_name, "organization_name": organization_name, "accreditation_type": "General"}

    def _validate_segment_rules(self, rules: dict) -> None:
        allowed = {"accreditation_status", "accreditation_type", "activity_id"}
        if any(key not in allowed for key in rules):
            raise CommunicationsAutomationError("SEGMENT_RULE_INVALID", "Regla de segmento no permitida")

    def _render(self, text: str, data: dict[str, str]) -> str:
        def replace(match):
            key = match.group(1).strip()
            if key not in self.SAFE_VARIABLES:
                raise CommunicationsAutomationError("TEMPLATE_VARIABLE_INVALID", "Variable no permitida")
            return self._escape(data.get(key, ""))
        return re.sub(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}", replace, text or "")

    def _variables(self, text: str) -> set[str]:
        return {match.group(1).strip() for match in re.finditer(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}", text or "")}

    def _validate_variables(self, text: str) -> None:
        unknown = self._variables(text) - self.SAFE_VARIABLES
        if unknown:
            raise CommunicationsAutomationError("TEMPLATE_VARIABLE_INVALID", "Variable no permitida")
        if re.search(r"<\s*script|javascript:|data:text/html|{{\s*__", text or "", re.I):
            raise CommunicationsAutomationError("TEMPLATE_CONTENT_INVALID", "Contenido de plantilla invalido")

    def _template_text(self, value, limit):
        text = str(value or "").replace("\x00", "").strip()
        if len(text) > limit:
            raise CommunicationsAutomationError("TEXT_TOO_LONG", "Texto demasiado largo")
        return text

    def _text(self, value, limit):
        text = re.sub(r"[\x00-\x1f]", "", str(value or "")).strip()
        if len(text) > limit or re.search(r"<\s*script|javascript:|data:text/html", text, re.I):
            raise CommunicationsAutomationError("TEXT_INVALID", "Texto invalido")
        return text

    def _choice(self, value, choices):
        text = str(value or "").strip()
        normalized = text
        if normalized not in choices and text.upper() in choices:
            normalized = text.upper()
        if normalized not in choices and text.lower() in choices:
            normalized = text.lower()
        if normalized not in choices:
            raise CommunicationsAutomationError("CHOICE_INVALID", "Valor invalido")
        return normalized

    def _escape(self, value) -> str:
        return str(value or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
