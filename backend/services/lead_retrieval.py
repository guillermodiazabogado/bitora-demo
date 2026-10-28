from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import uuid
from typing import Any


LICENSE_STATUSES = {"PENDING", "ACTIVE", "SUSPENDED", "EXPIRED", "REVOKED"}
QUALIFICATIONS = {"UNQUALIFIED", "COLD", "WARM", "HOT"}
FOLLOW_UP = {"NEW", "CONTACT", "FOLLOW_UP", "QUALIFIED", "CLOSED"}
DEFAULT_FIELDS = ["first_name", "last_name", "company", "email"]
SAFE_FIELDS = {"first_name", "last_name", "company", "position", "email", "phone"}


class LeadRetrievalError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class LeadRetrievalService:
    def __init__(self, enterprise_core=None, audit_service=None, edge_sync=None, now=None) -> None:
        self.enterprise_core = enterprise_core
        self.audit_service = audit_service
        self.edge_sync = edge_sync
        self.now = now or (lambda: "")

    def create_stand(self, db, *, organization_id: int, event_id: int, company_id: int, code: str, name: str, zone_id: int | None = None) -> dict:
        self._participation(db, organization_id, event_id, company_id)
        code = self._clean_key(code, 80)
        now = self.now()
        row = db.execute("SELECT * FROM enterprise_stands WHERE organization_id = ? AND event_id = ? AND company_id = ? AND code = ?", (organization_id, event_id, company_id, code)).fetchone()
        if row:
            db.execute("UPDATE enterprise_stands SET name = ?, zone_id = ?, updated_at = ? WHERE id = ?", (self._clean_text(name, 160), zone_id, now, row["id"]))
            stand_id = int(row["id"])
        else:
            cur = db.execute("INSERT INTO enterprise_stands (organization_id, event_id, company_id, zone_id, code, name, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (organization_id, event_id, company_id, zone_id, code, self._clean_text(name, 160), now, now))
            stand_id = int(cur.lastrowid)
        return self._row(db, "enterprise_stands", stand_id)

    def create_license(self, db, *, organization_id: int, event_id: int, company_id: int, stand_id: int | None = None, max_users: int = 0, max_devices: int = 0, status: str = "PENDING") -> dict:
        self._participation(db, organization_id, event_id, company_id)
        status = self._choice(status, LICENSE_STATUSES, "LICENSE_STATUS_INVALID")
        now = self.now()
        row = db.execute("SELECT * FROM enterprise_lead_licenses WHERE organization_id = ? AND event_id = ? AND company_id = ? AND COALESCE(stand_id, 0) = COALESCE(?, 0)", (organization_id, event_id, company_id, stand_id)).fetchone()
        if row:
            db.execute("UPDATE enterprise_lead_licenses SET max_users = ?, max_devices = ?, status = ?, updated_at = ? WHERE id = ?", (max_users, max_devices, status, now, row["id"]))
            license_id = int(row["id"])
        else:
            cur = db.execute("INSERT INTO enterprise_lead_licenses (organization_id, event_id, company_id, stand_id, max_users, max_devices, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (organization_id, event_id, company_id, stand_id, max_users, max_devices, status, now, now))
            license_id = int(cur.lastrowid)
        return self._row(db, "enterprise_lead_licenses", license_id)

    def grant_consent(self, db, *, organization_id: int, event_id: int, participant_entity_id: int, company_id: int | None = None, fields: list[str] | None = None, source: str = "EXPLICIT_PER_SCAN", policy_version: str = "v1") -> dict:
        self._entity(db, organization_id, event_id, participant_entity_id)
        now = self.now()
        fields = self._fields(fields or DEFAULT_FIELDS)
        cur = db.execute("INSERT INTO enterprise_lead_consents (organization_id, event_id, participant_entity_id, company_id, purpose, policy_version, status, granted_at, source, fields_json, created_at, updated_at) VALUES (?, ?, ?, ?, 'LEAD_RETRIEVAL', ?, 'GRANTED', ?, ?, ?, ?, ?)", (organization_id, event_id, participant_entity_id, company_id, policy_version, now, self._clean_key(source, 80), self._json(fields), now, now))
        return self._row(db, "enterprise_lead_consents", int(cur.lastrowid))

    def revoke_consent(self, db, *, organization_id: int, event_id: int, consent_id: int) -> dict:
        row = self._row(db, "enterprise_lead_consents", consent_id)
        if int(row["organization_id"]) != organization_id or int(row["event_id"]) != event_id:
            raise LeadRetrievalError("CONSENT_SCOPE_ERROR", "Consentimiento fuera de alcance", 403)
        db.execute("UPDATE enterprise_lead_consents SET status = 'REVOKED', revoked_at = ?, updated_at = ? WHERE id = ?", (self.now(), self.now(), consent_id))
        return self._row(db, "enterprise_lead_consents", consent_id)

    def capture(self, db, *, organization_id: int, event_id: int, company_id: int, token: str, consent_id: int | None = None, stand_id: int | None = None, user_email: str = "", device_id: int | None = None, idempotency_key: str = "", source: str = "QR_SCAN", local_payload: dict | None = None) -> dict:
        if not self._license_active(db, organization_id, event_id, company_id, stand_id):
            return {"ok": False, "reason_code": "LICENSE_INACTIVE"}
        if user_email and not self._company_user_allowed(db, organization_id, event_id, company_id, user_email):
            return {"ok": False, "reason_code": "USER_NOT_AUTHORIZED"}
        if device_id and not self._device_allowed(db, organization_id, event_id, device_id):
            return {"ok": False, "reason_code": "DEVICE_NOT_ALLOWED"}
        cred = self._credential_by_token(db, organization_id, event_id, token)
        if not cred:
            return {"ok": False, "reason_code": "UNKNOWN_CREDENTIAL"}
        consent = self._consent(db, organization_id, event_id, int(cred["entity_id"]), company_id, consent_id)
        if not consent:
            return {"ok": False, "reason_code": "CONSENT_REQUIRED"}
        if idempotency_key:
            existing = db.execute("SELECT l.* FROM enterprise_lead_interactions i JOIN enterprise_leads l ON l.id = i.lead_id WHERE i.organization_id = ? AND i.idempotency_key = ?", (organization_id, idempotency_key)).fetchone()
            if existing:
                return {"ok": True, "duplicate": True, "lead": dict(existing)}
        now = self.now()
        fields = self._fields(json.loads(consent["fields_json"] or "[]"))
        snapshot = self._participant_snapshot(db, int(cred["entity_id"]), fields)
        row = db.execute("SELECT * FROM enterprise_leads WHERE organization_id = ? AND event_id = ? AND company_id = ? AND participant_entity_id = ?", (organization_id, event_id, company_id, cred["entity_id"])).fetchone()
        if row:
            lead_id = int(row["id"])
            db.execute("UPDATE enterprise_leads SET captured_at = ?, captured_by_device_id = COALESCE(?, captured_by_device_id), data_snapshot_json = ?, updated_at = ? WHERE id = ?", (now, device_id, self._json(snapshot), now, lead_id))
        else:
            cur = db.execute("INSERT INTO enterprise_leads (organization_id, event_id, company_id, stand_id, participant_entity_id, captured_by_device_id, captured_at, source, consent_id, data_snapshot_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (organization_id, event_id, company_id, stand_id, cred["entity_id"], device_id, now, self._clean_key(source, 80), consent["id"], self._json(snapshot), now, now))
            lead_id = int(cur.lastrowid)
        self._interaction(db, organization_id, event_id, company_id, lead_id, "SCAN", device_id=device_id, idempotency_key=idempotency_key, metadata={"local_payload": local_payload or {}})
        self._domain(db, organization_id, event_id, "LEAD_CAPTURED", entity_id=int(cred["entity_id"]), device_id=device_id, metadata={"company_id": company_id, "lead_id": lead_id})
        return {"ok": True, "lead": self._row(db, "enterprise_leads", lead_id)}

    def qualify(self, db, *, organization_id: int, event_id: int, company_id: int, lead_id: int, qualification: str) -> dict:
        lead = self._lead(db, organization_id, event_id, company_id, lead_id)
        qualification = self._choice(qualification, QUALIFICATIONS, "QUALIFICATION_INVALID")
        db.execute("UPDATE enterprise_leads SET qualification = ?, updated_at = ? WHERE id = ?", (qualification, self.now(), lead_id))
        self._interaction(db, organization_id, event_id, company_id, lead_id, "QUALIFIED", metadata={"qualification": qualification})
        return self._row(db, "enterprise_leads", lead_id)

    def add_note(self, db, *, organization_id: int, event_id: int, company_id: int, lead_id: int, note: str, tags: list[str] | None = None) -> dict:
        self._lead(db, organization_id, event_id, company_id, lead_id)
        return self._interaction(db, organization_id, event_id, company_id, lead_id, "NOTE_ADDED", note=note, tags=tags or [])

    def set_follow_up(self, db, *, organization_id: int, event_id: int, company_id: int, lead_id: int, status: str, assigned_user_id: int | None = None) -> dict:
        self._lead(db, organization_id, event_id, company_id, lead_id)
        status = self._choice(status, FOLLOW_UP, "FOLLOW_UP_INVALID")
        db.execute("UPDATE enterprise_leads SET follow_up_status = ?, assigned_user_id = ?, updated_at = ? WHERE id = ?", (status, assigned_user_id, self.now(), lead_id))
        self._interaction(db, organization_id, event_id, company_id, lead_id, "FOLLOW_UP_CHANGED", metadata={"status": status})
        return self._row(db, "enterprise_leads", lead_id)

    def list_leads(self, db, *, organization_id: int, event_id: int, company_id: int) -> list[dict]:
        return [dict(r) for r in db.execute("SELECT * FROM enterprise_leads WHERE organization_id = ? AND event_id = ? AND company_id = ? ORDER BY id", (organization_id, event_id, company_id)).fetchall()]

    def export_csv(self, db, *, organization_id: int, event_id: int, company_id: int, fields: list[str], exported_by: str = "", idempotency_key: str = "") -> dict:
        fields = self._fields(fields)
        leads = self.list_leads(db, organization_id=organization_id, event_id=event_id, company_id=company_id)
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=[*fields, "qualification", "follow_up_status", "captured_at"])
        writer.writeheader()
        for lead in leads:
            snap = json.loads(lead["data_snapshot_json"] or "{}")
            writer.writerow({**{f: snap.get(f, "") for f in fields}, "qualification": lead["qualification"], "follow_up_status": lead["follow_up_status"], "captured_at": lead["captured_at"]})
        db.execute("INSERT INTO enterprise_lead_exports (organization_id, event_id, company_id, exported_by, lead_count, fields_json, policy_version, idempotency_key, created_at) VALUES (?, ?, ?, ?, ?, ?, 'v1', ?, ?)", (organization_id, event_id, company_id, self._clean_text(exported_by, 120), len(leads), self._json(fields), idempotency_key, self.now()))
        return {"ok": True, "csv": output.getvalue(), "count": len(leads), "fields": fields}

    def reconcile_offline_capture(self, db, *, organization_id: int, event_id: int, device_id: int, secret: str, operation: dict) -> dict:
        if self.edge_sync and not self.edge_sync.authenticate_device(db, organization_id=organization_id, event_id=event_id, device_id=device_id, secret=secret, capability="CAPTURE_LEAD").ok:
            return {"ok": False, "conflict_type": "DEVICE_NOT_ALLOWED"}
        payload = operation.get("payload", {})
        if not payload.get("consent_evidence"):
            return {"ok": False, "conflict_type": "CONSENT_REQUIRED"}
        result = self.capture(db, organization_id=organization_id, event_id=event_id, company_id=int(payload.get("company_id")), stand_id=payload.get("stand_id"), token=payload.get("token", ""), consent_id=payload.get("consent_id"), device_id=device_id, idempotency_key=operation.get("idempotency_key", ""), source="OFFLINE")
        return {"ok": True, "server_result": result, "conflict_type": "NO_CONFLICT" if result.get("ok") else result.get("reason_code")}

    def analytics(self, db, *, organization_id: int, event_id: int) -> dict:
        q = lambda sql, p: int(db.execute(sql, p).fetchone()["c"])
        return {
            "licensed_companies": q("SELECT COUNT(DISTINCT company_id) c FROM enterprise_lead_licenses WHERE organization_id = ? AND event_id = ? AND status = 'ACTIVE'", (organization_id, event_id)),
            "stands": q("SELECT COUNT(*) c FROM enterprise_stands WHERE organization_id = ? AND event_id = ?", (organization_id, event_id)),
            "scans": q("SELECT COUNT(*) c FROM enterprise_lead_interactions WHERE organization_id = ? AND event_id = ? AND interaction_type = 'SCAN'", (organization_id, event_id)),
            "unique_leads": q("SELECT COUNT(*) c FROM enterprise_leads WHERE organization_id = ? AND event_id = ?", (organization_id, event_id)),
            "exports": q("SELECT COUNT(*) c FROM enterprise_lead_exports WHERE organization_id = ? AND event_id = ?", (organization_id, event_id)),
        }

    def _interaction(self, db, organization_id, event_id, company_id, lead_id, interaction_type, actor_user_id=None, device_id=None, note="", tags=None, idempotency_key="", metadata=None):
        if idempotency_key:
            row = db.execute("SELECT * FROM enterprise_lead_interactions WHERE organization_id = ? AND idempotency_key = ?", (organization_id, idempotency_key)).fetchone()
            if row:
                return dict(row)
        now = self.now()
        cur = db.execute("INSERT INTO enterprise_lead_interactions (organization_id, event_id, company_id, lead_id, interaction_type, actor_user_id, device_id, note, tags_json, idempotency_key, metadata_json, occurred_at, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (organization_id, event_id, company_id, lead_id, interaction_type, actor_user_id, device_id, self._clean_text(note, 1000), self._json(tags or []), idempotency_key, self._json(metadata or {}), now, now))
        return self._row(db, "enterprise_lead_interactions", int(cur.lastrowid))

    def _credential_by_token(self, db, organization_id, event_id, token):
        token_hash = hashlib.sha256(str(token or "").encode("utf-8")).hexdigest() if token else ""
        return db.execute("SELECT * FROM enterprise_credentials WHERE organization_id = ? AND event_id = ? AND legacy_token_hash = ? AND status = 'ACTIVE'", (organization_id, event_id, token_hash)).fetchone()

    def _participant_snapshot(self, db, entity_id, fields):
        entity = db.execute("SELECT legacy_id FROM enterprise_entities WHERE id = ?", (entity_id,)).fetchone()
        person = db.execute("SELECT * FROM people WHERE id = ?", (entity["legacy_id"],)).fetchone() if entity else None
        return {f: (person[f] if person and f in person.keys() else "") for f in fields}

    def _license_active(self, db, organization_id, event_id, company_id, stand_id=None):
        row = db.execute("SELECT * FROM enterprise_lead_licenses WHERE organization_id = ? AND event_id = ? AND company_id = ? AND status = 'ACTIVE' AND (stand_id IS NULL OR COALESCE(stand_id,0)=COALESCE(?,0))", (organization_id, event_id, company_id, stand_id)).fetchone()
        return bool(row)

    def _consent(self, db, organization_id, event_id, entity_id, company_id, consent_id=None):
        if consent_id:
            return db.execute(
                "SELECT * FROM enterprise_lead_consents WHERE id = ? AND organization_id = ? AND event_id = ? AND participant_entity_id = ? AND (company_id IS NULL OR company_id = ?) AND status = 'GRANTED'",
                (consent_id, organization_id, event_id, entity_id, company_id),
            ).fetchone()
        return db.execute("SELECT * FROM enterprise_lead_consents WHERE organization_id = ? AND event_id = ? AND participant_entity_id = ? AND (company_id IS NULL OR company_id = ?) AND status = 'GRANTED' ORDER BY id DESC LIMIT 1", (organization_id, event_id, entity_id, company_id)).fetchone()

    def _company_user_allowed(self, db, organization_id, event_id, company_id, email):
        return bool(db.execute("SELECT id FROM enterprise_company_users WHERE organization_id = ? AND event_id = ? AND company_id = ? AND email = ? AND status = 'ACTIVE'", (organization_id, event_id, company_id, str(email).lower())).fetchone())

    def _device_allowed(self, db, organization_id, event_id, device_id):
        row = db.execute("SELECT capabilities_json FROM enterprise_devices WHERE id = ? AND organization_id = ? AND event_id = ? AND status = 'ACTIVE'", (device_id, organization_id, event_id)).fetchone()
        return bool(row and "CAPTURE_LEAD" in json.loads(row["capabilities_json"] or "[]"))

    def _participation(self, db, organization_id, event_id, company_id):
        row = db.execute("SELECT * FROM enterprise_company_event_participation WHERE organization_id = ? AND event_id = ? AND company_id = ?", (organization_id, event_id, company_id)).fetchone()
        if not row:
            raise LeadRetrievalError("COMPANY_SCOPE_ERROR", "Company fuera de evento", 403)
        return row

    def _entity(self, db, organization_id, event_id, entity_id):
        row = db.execute("SELECT * FROM enterprise_entities WHERE id = ? AND organization_id = ? AND event_id = ?", (entity_id, organization_id, event_id)).fetchone()
        if not row:
            raise LeadRetrievalError("ENTITY_SCOPE_ERROR", "Entity fuera de evento", 403)
        return row

    def _lead(self, db, organization_id, event_id, company_id, lead_id):
        row = db.execute("SELECT * FROM enterprise_leads WHERE id = ? AND organization_id = ? AND event_id = ? AND company_id = ?", (lead_id, organization_id, event_id, company_id)).fetchone()
        if not row:
            raise LeadRetrievalError("LEAD_SCOPE_ERROR", "Lead fuera de alcance", 403)
        return row

    def _domain(self, db, organization_id, event_id, event_type, entity_id=None, device_id=None, metadata=None):
        if self.enterprise_core:
            self.enterprise_core.record_domain_event(db, organization_id=organization_id, event_id=event_id, event_type=event_type, entity_id=entity_id, device_id=device_id, metadata=metadata or {})

    def _row(self, db, table, row_id):
        row = db.execute(f"SELECT * FROM {table} WHERE id = ?", (row_id,)).fetchone()
        if not row:
            raise LeadRetrievalError("ROW_NOT_FOUND", "Registro no encontrado", 404)
        return dict(row)

    def _fields(self, fields):
        return [f for f in fields if f in SAFE_FIELDS]

    def _choice(self, value, allowed, code):
        normalized = str(value or "").strip().upper()
        if normalized not in allowed:
            raise LeadRetrievalError(code, "Valor invalido", 400)
        return normalized

    def _clean_key(self, value, limit):
        return re.sub(r"[^A-Za-z0-9_.:-]+", "_", str(value or "").strip()).strip("_")[:limit]

    def _clean_text(self, value, limit):
        return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(value or "")).strip()[:limit]

    def _json(self, value: Any):
        return json.dumps(value, ensure_ascii=True, sort_keys=True)
