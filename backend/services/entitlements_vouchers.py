from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime
from typing import Any


REASON_CODES = {
    "VALID", "UNKNOWN_CREDENTIAL", "NO_ENTITLEMENT", "EXHAUSTED", "REVOKED", "SUSPENDED", "EXPIRED",
    "OUTSIDE_TIME_WINDOW", "WRONG_SCOPE", "WRONG_SERVICE_POINT", "INVALID_QUANTITY", "DUPLICATE",
    "RULE_DENIED", "DEVICE_NOT_ALLOWED",
}


class EntitlementsVouchersError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class EntitlementsVouchersService:
    def __init__(self, enterprise_core=None, audit_service=None, edge_sync=None, now=None) -> None:
        self.enterprise_core = enterprise_core
        self.audit_service = audit_service
        self.edge_sync = edge_sync
        self.now = now or (lambda: "")

    def ensure_type(self, db, *, organization_id: int, event_id: int, code: str, name: str = "", consumable: bool = True, default_quantity: int = 1, offline_policy: str = "ONLINE_REQUIRED") -> dict:
        self._validate_event(db, organization_id, event_id)
        code = self._clean_key(code, 80)
        if not code:
            raise EntitlementsVouchersError("TYPE_CODE_REQUIRED", "Tipo obligatorio")
        offline_policy = self._choice(offline_policy, {"ONLINE_REQUIRED", "OFFLINE_ALLOWED", "OFFLINE_ALLOWED_WITH_RISK"}, "OFFLINE_POLICY_INVALID")
        now = self.now()
        row = db.execute("SELECT * FROM enterprise_entitlement_types WHERE organization_id = ? AND event_id = ? AND code = ?", (organization_id, event_id, code)).fetchone()
        if row:
            db.execute("UPDATE enterprise_entitlement_types SET name = ?, consumable = ?, default_quantity = ?, offline_policy = ?, updated_at = ? WHERE id = ?", (self._clean_text(name or code, 160), 1 if consumable else 0, max(0, int(default_quantity or 0)), offline_policy, now, row["id"]))
            type_id = int(row["id"])
        else:
            cur = db.execute("INSERT INTO enterprise_entitlement_types (organization_id, event_id, code, name, consumable, default_quantity, offline_policy, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (organization_id, event_id, code, self._clean_text(name or code, 160), 1 if consumable else 0, max(0, int(default_quantity or 0)), offline_policy, now, now))
            type_id = int(getattr(cur, "lastrowid", 0) or 0)
        return self._row(db, "enterprise_entitlement_types", type_id)

    def ensure_service_point(self, db, *, organization_id: int, event_id: int, code: str, name: str, service_type: str = "", zone_id: int | None = None, device_id: int | None = None) -> dict:
        self._validate_event(db, organization_id, event_id)
        code = self._clean_key(code, 80)
        if not code:
            raise EntitlementsVouchersError("SERVICE_POINT_CODE_REQUIRED", "Punto de servicio obligatorio")
        if device_id:
            device = db.execute("SELECT id FROM enterprise_devices WHERE id = ? AND organization_id = ? AND event_id = ? AND status = 'ACTIVE'", (device_id, organization_id, event_id)).fetchone()
            if not device:
                raise EntitlementsVouchersError("DEVICE_SCOPE_ERROR", "Device fuera de alcance", 403)
        now = self.now()
        row = db.execute("SELECT * FROM enterprise_service_points WHERE organization_id = ? AND event_id = ? AND code = ?", (organization_id, event_id, code)).fetchone()
        if row:
            db.execute("UPDATE enterprise_service_points SET name = ?, service_type = ?, zone_id = ?, device_id = ?, updated_at = ? WHERE id = ?", (self._clean_text(name, 160), self._clean_key(service_type, 80), zone_id, device_id, now, row["id"]))
            point_id = int(row["id"])
        else:
            cur = db.execute("INSERT INTO enterprise_service_points (organization_id, event_id, zone_id, device_id, code, name, service_type, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (organization_id, event_id, zone_id, device_id, code, self._clean_text(name, 160), self._clean_key(service_type, 80), now, now))
            point_id = int(getattr(cur, "lastrowid", 0) or 0)
        return self._row(db, "enterprise_service_points", point_id)

    def grant(self, db, *, organization_id: int, event_id: int, entity_id: int, entitlement_type: str, allocated: int = 1, consumable: bool = True, scope_type: str = "EVENT", scope_id: str = "", valid_from: str = "", valid_until: str = "", source: str = "MANUAL", source_reference: str = "", idempotency_key: str = "", actor: str = "") -> dict:
        if idempotency_key:
            row = db.execute("SELECT * FROM enterprise_entitlements WHERE organization_id = ? AND idempotency_key = ?", (organization_id, idempotency_key)).fetchone()
            if row:
                return {"ok": True, "idempotent": True, "entitlement": dict(row)}
        if self.enterprise_core:
            result = self.enterprise_core.grant_entitlement(db, organization_id=organization_id, event_id=event_id, entity_id=entity_id, entitlement_type=self._clean_key(entitlement_type, 80), scope_type=self._clean_key(scope_type, 60) or "EVENT", scope_id=str(scope_id or ""), allocated=max(0, int(allocated or 0)), consumable=consumable, valid_from=valid_from, valid_until=valid_until, idempotency_key=idempotency_key, actor=actor, metadata={"source": source, "source_reference": source_reference})
            entitlement_id = int(result["item"]["id"])
        else:
            raise EntitlementsVouchersError("ENTERPRISE_CORE_REQUIRED", "Enterprise Core requerido", 500)
        db.execute("UPDATE enterprise_entitlements SET source = ?, source_reference = ?, updated_at = ? WHERE id = ?", (self._clean_key(source, 80), self._clean_text(source_reference, 160), self.now(), entitlement_id))
        self._domain(db, organization_id, event_id, "ENTITLEMENT_GRANTED", entity_id=entity_id, metadata={"entitlement_id": entitlement_id, "type": entitlement_type})
        return {"ok": True, "entitlement": self._row(db, "enterprise_entitlements", entitlement_id)}

    def bulk_grant(self, db, *, organization_id: int, event_id: int, entity_ids: list[int], entitlement_type: str, allocated: int = 1, consumable: bool = True, source: str = "MANUAL", source_reference: str = "", grant_id: str = "", idempotency_key: str = "", actor: str = "") -> dict:
        grant_id = self._clean_key(grant_id or uuid.uuid4().hex, 120)
        existing = db.execute("SELECT * FROM enterprise_entitlement_grant_batches WHERE organization_id = ? AND event_id = ? AND grant_id = ?", (organization_id, event_id, grant_id)).fetchone()
        if existing:
            return {"ok": True, "idempotent": True, "summary": self._loads(existing["summary_json"], {})}
        created = 0
        for entity_id in entity_ids:
            self.grant(db, organization_id=organization_id, event_id=event_id, entity_id=int(entity_id), entitlement_type=entitlement_type, allocated=allocated, consumable=consumable, source=source, source_reference=source_reference, idempotency_key=f"{grant_id}:{entity_id}:{entitlement_type}", actor=actor)
            created += 1
        summary = {"created": created, "requested": len(entity_ids)}
        now = self.now()
        db.execute("INSERT INTO enterprise_entitlement_grant_batches (organization_id, event_id, grant_id, source, source_reference, entitlement_type, summary_json, idempotency_key, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (organization_id, event_id, grant_id, self._clean_key(source, 80), self._clean_text(source_reference, 160), self._clean_key(entitlement_type, 80), self._json(summary), idempotency_key, now, now))
        return {"ok": True, "summary": summary}

    def grant_to_company(self, db, *, organization_id: int, event_id: int, company_id: int, entitlement_type: str, allocated: int = 1, consumable: bool = True, actor: str = "") -> dict:
        rows = db.execute("SELECT DISTINCT entity_id FROM enterprise_delegation_members WHERE organization_id = ? AND event_id = ? AND company_id = ? AND entity_id IS NOT NULL", (organization_id, event_id, company_id)).fetchall()
        return self.bulk_grant(db, organization_id=organization_id, event_id=event_id, entity_ids=[int(r["entity_id"]) for r in rows], entitlement_type=entitlement_type, allocated=allocated, consumable=consumable, source="COMPANY", source_reference=str(company_id), grant_id=f"company:{company_id}:{entitlement_type}", actor=actor)

    def grant_to_delegation(self, db, *, organization_id: int, event_id: int, delegation_id: int, entitlement_type: str, allocated: int = 1, consumable: bool = True, actor: str = "") -> dict:
        rows = db.execute("SELECT DISTINCT entity_id FROM enterprise_delegation_members WHERE organization_id = ? AND event_id = ? AND delegation_id = ? AND entity_id IS NOT NULL", (organization_id, event_id, delegation_id)).fetchall()
        return self.bulk_grant(db, organization_id=organization_id, event_id=event_id, entity_ids=[int(r["entity_id"]) for r in rows], entitlement_type=entitlement_type, allocated=allocated, consumable=consumable, source="DELEGATION", source_reference=str(delegation_id), grant_id=f"delegation:{delegation_id}:{entitlement_type}", actor=actor)

    def revoke(self, db, *, organization_id: int, event_id: int, entitlement_id: int, actor: str = "", reason: str = "") -> dict:
        ent = self._entitlement(db, organization_id, event_id, entitlement_id)
        db.execute("UPDATE enterprise_entitlements SET status = 'REVOKED', updated_at = ?, metadata_json = ? WHERE id = ?", (self.now(), self._json({**self._loads(ent["metadata_json"], {}), "revoke_reason": reason}), entitlement_id))
        self._domain(db, organization_id, event_id, "ENTITLEMENT_REVOKED", entity_id=ent["entity_id"], metadata={"entitlement_id": entitlement_id})
        self._audit(db, actor, "entitlement.revoked", "enterprise_entitlement", entitlement_id, {"reason": reason})
        return self._row(db, "enterprise_entitlements", entitlement_id)

    def suspend(self, db, *, organization_id: int, event_id: int, entitlement_id: int, actor: str = "") -> dict:
        self._entitlement(db, organization_id, event_id, entitlement_id)
        db.execute("UPDATE enterprise_entitlements SET status = 'SUSPENDED', updated_at = ? WHERE id = ?", (self.now(), entitlement_id))
        self._audit(db, actor, "entitlement.suspended", "enterprise_entitlement", entitlement_id, {})
        return self._row(db, "enterprise_entitlements", entitlement_id)

    def consume(self, db, *, organization_id: int, event_id: int, token: str, entitlement_type: str, service_point_id: int | None = None, quantity: int = 1, device_id: int | None = None, idempotency_key: str = "", correlation_id: str = "", source: str = "ONLINE", occurred_at: str = "", local_decision: dict | None = None) -> dict:
        now = self.now()
        if idempotency_key:
            existing = db.execute("SELECT * FROM enterprise_entitlement_consumptions WHERE organization_id = ? AND idempotency_key = ?", (organization_id, idempotency_key)).fetchone()
            if existing:
                return {"ok": existing["result"] == "ACCEPTED", "duplicate": True, "result": existing["result"], "reason_code": "DUPLICATE", "consumption": dict(existing)}
        if quantity <= 0:
            return self._record_consumption(db, organization_id, event_id, None, None, None, service_point_id, device_id, quantity, "DENIED", "INVALID_QUANTITY", now, idempotency_key, correlation_id, source, local_decision)
        cred = self._credential_by_token(db, organization_id, event_id, token)
        if not cred:
            return self._record_consumption(db, organization_id, event_id, None, None, None, service_point_id, device_id, quantity, "DENIED", "UNKNOWN_CREDENTIAL", now, idempotency_key, correlation_id, source, local_decision)
        if device_id and not self._device_can_consume(db, organization_id, event_id, device_id):
            return self._record_consumption(db, organization_id, event_id, cred["entity_id"], cred["id"], None, service_point_id, device_id, quantity, "DENIED", "DEVICE_NOT_ALLOWED", now, idempotency_key, correlation_id, source, local_decision)
        entitlement = self._find_entitlement(db, organization_id, event_id, int(cred["entity_id"]), entitlement_type)
        if not entitlement:
            return self._record_consumption(db, organization_id, event_id, cred["entity_id"], cred["id"], None, service_point_id, device_id, quantity, "DENIED", "NO_ENTITLEMENT", now, idempotency_key, correlation_id, source, local_decision)
        reason = self._validate_entitlement(db, entitlement, service_point_id, quantity, now)
        if reason != "VALID":
            return self._record_consumption(db, organization_id, event_id, cred["entity_id"], cred["id"], entitlement["id"], service_point_id, device_id, quantity, "DENIED", reason, now, idempotency_key, correlation_id, source, local_decision)
        consumable = int(entitlement["consumable"] or 0) == 1
        if consumable:
            cur = db.execute(
                "UPDATE enterprise_entitlements SET consumed = consumed + ?, status = CASE WHEN consumed + ? >= allocated THEN 'EXHAUSTED' ELSE status END, updated_at = ? WHERE id = ? AND organization_id = ? AND event_id = ? AND status = 'ACTIVE' AND allocated - consumed >= ?",
                (quantity, quantity, now, entitlement["id"], organization_id, event_id, quantity),
            )
            if getattr(cur, "rowcount", 0) < 1:
                return self._record_consumption(db, organization_id, event_id, cred["entity_id"], cred["id"], entitlement["id"], service_point_id, device_id, quantity, "DENIED", "EXHAUSTED", now, idempotency_key, correlation_id, source, local_decision)
        result = self._record_consumption(db, organization_id, event_id, cred["entity_id"], cred["id"], entitlement["id"], service_point_id, device_id, quantity, "ACCEPTED", "VALID", now, idempotency_key, correlation_id, source, local_decision)
        self._domain(db, organization_id, event_id, "ENTITLEMENT_CONSUMED", entity_id=cred["entity_id"], device_id=device_id, metadata={"entitlement_id": entitlement["id"], "quantity": quantity})
        if consumable:
            refreshed = self._row(db, "enterprise_entitlements", int(entitlement["id"]))
            if int(refreshed["consumed"]) >= int(refreshed["allocated"]):
                self._domain(db, organization_id, event_id, "ENTITLEMENT_EXHAUSTED", entity_id=cred["entity_id"], metadata={"entitlement_id": entitlement["id"]})
        return result

    def local_entitlement_decision(self, dataset: dict, *, token_hash: str, entitlement_type: str, quantity: int = 1) -> dict:
        cred = next((c for c in dataset.get("credentials", []) if (c.get("legacy_token_hash") or c.get("token_hash")) == token_hash and c.get("status") == "ACTIVE"), None)
        if not cred:
            return {"decision": "DENY", "reason_code": "UNKNOWN_CREDENTIAL"}
        ent = next((e for e in dataset.get("entitlements", []) if e.get("entity_id") == cred.get("entity_id") and e.get("entitlement_type") == entitlement_type and e.get("status") == "ACTIVE"), None)
        if not ent:
            return {"decision": "DENY", "reason_code": "NO_ENTITLEMENT"}
        if int(ent.get("consumable") or 0) and int(ent.get("allocated") or 0) - int(ent.get("consumed") or 0) < quantity:
            return {"decision": "DENY", "reason_code": "EXHAUSTED"}
        return {"decision": "ALLOW", "reason_code": "VALID", "entitlement_id": ent.get("id")}

    def reconcile_offline_consumption(self, db, *, organization_id: int, event_id: int, device_id: int, secret: str, operation: dict) -> dict:
        if self.edge_sync and not self.edge_sync.authenticate_device(db, organization_id=organization_id, event_id=event_id, device_id=device_id, secret=secret, capability="CONSUME_ENTITLEMENT").ok:
            return {"ok": False, "conflict_type": "DEVICE_NOT_ALLOWED"}
        payload = operation.get("payload", {})
        local = operation.get("local_decision") or {}
        result = self.consume(db, organization_id=organization_id, event_id=event_id, token=payload.get("token", ""), entitlement_type=payload.get("entitlement_type", ""), service_point_id=payload.get("service_point_id"), quantity=int(payload.get("quantity") or 1), device_id=device_id, idempotency_key=operation.get("idempotency_key", ""), correlation_id=operation.get("correlation_id", ""), source="EDGE_SYNC", local_decision=local)
        conflict = "NO_CONFLICT"
        if local.get("decision") == "ALLOW" and not result["ok"]:
            conflict = "ENTITLEMENT_DOUBLE_SPEND" if result["reason_code"] == "EXHAUSTED" else f"ENTITLEMENT_{result['reason_code']}"
            self._domain(db, organization_id, event_id, "ENTITLEMENT_CONFLICT_DETECTED", device_id=device_id, metadata={"conflict_type": conflict, "reason_code": result["reason_code"]})
        return {"ok": True, "server_result": result, "conflict_type": conflict}

    def list_participant_entitlements(self, db, *, organization_id: int, event_id: int, token: str) -> list[dict]:
        cred = self._credential_by_token(db, organization_id, event_id, token)
        if not cred:
            return []
        return [self._entitlement_payload(row) for row in db.execute("SELECT * FROM enterprise_entitlements WHERE organization_id = ? AND event_id = ? AND entity_id = ? ORDER BY entitlement_type", (organization_id, event_id, cred["entity_id"])).fetchall()]

    def organizer_report(self, db, *, organization_id: int, event_id: int) -> dict:
        rows = db.execute("SELECT entitlement_type, SUM(allocated) allocated, SUM(consumed) consumed, COUNT(*) count FROM enterprise_entitlements WHERE organization_id = ? AND event_id = ? GROUP BY entitlement_type", (organization_id, event_id)).fetchall()
        denied = int(db.execute("SELECT COUNT(*) c FROM enterprise_entitlement_consumptions WHERE organization_id = ? AND event_id = ? AND result = 'DENIED'", (organization_id, event_id)).fetchone()["c"])
        return {"types": [dict(r) for r in rows], "denied": denied}

    def adjust(self, db, *, organization_id: int, event_id: int, entitlement_id: int, quantity_delta: int, reason: str, actor: str = "") -> dict:
        ent = self._entitlement(db, organization_id, event_id, entitlement_id)
        now = self.now()
        db.execute("INSERT INTO enterprise_entitlement_adjustments (organization_id, event_id, entitlement_id, quantity_delta, reason, actor, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)", (organization_id, event_id, entitlement_id, int(quantity_delta), self._clean_text(reason, 240), self._clean_text(actor, 120), now))
        db.execute("UPDATE enterprise_entitlements SET allocated = MAX(0, allocated + ?), updated_at = ? WHERE id = ?", (int(quantity_delta), now, entitlement_id))
        self._audit(db, actor, "entitlement.adjusted", "enterprise_entitlement", entitlement_id, {"quantity_delta": quantity_delta, "reason": reason})
        return self._entitlement_payload(self._row(db, "enterprise_entitlements", entitlement_id))

    def _record_consumption(self, db, organization_id, event_id, entity_id, credential_id, entitlement_id, service_point_id, device_id, quantity, result, reason_code, now, idempotency_key, correlation_id, source, local_decision=None):
        reason_code = reason_code if reason_code in REASON_CODES else "RULE_DENIED"
        cur = db.execute(
            "INSERT INTO enterprise_entitlement_consumptions (organization_id, event_id, entity_id, credential_id, entitlement_id, service_point_id, device_id, quantity, occurred_at, server_received_at, idempotency_key, correlation_id, source, result, reason_code, metadata_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (organization_id, event_id, entity_id, credential_id, entitlement_id, service_point_id, device_id, int(quantity or 0), now, now, idempotency_key, correlation_id or f"ent-{uuid.uuid4().hex}", self._clean_key(source, 80), result, reason_code, self._json({"local_decision": local_decision or {}}), now),
        )
        consumption = self._row(db, "enterprise_entitlement_consumptions", int(getattr(cur, "lastrowid", 0) or 0))
        if result == "DENIED":
            self._domain(db, organization_id, event_id, "ENTITLEMENT_CONSUMPTION_DENIED", entity_id=entity_id, device_id=device_id, metadata={"reason_code": reason_code, "entitlement_id": entitlement_id})
        return {"ok": result == "ACCEPTED", "result": result, "reason_code": reason_code, "consumption": consumption}

    def _validate_entitlement(self, db, ent, service_point_id, quantity, now):
        status = ent["status"]
        if status == "REVOKED":
            return "REVOKED"
        if status == "SUSPENDED":
            return "SUSPENDED"
        if status == "EXPIRED":
            return "EXPIRED"
        if status != "ACTIVE":
            return "EXHAUSTED" if status == "EXHAUSTED" else "RULE_DENIED"
        if ent["valid_from"] and ent["valid_from"] > now:
            return "OUTSIDE_TIME_WINDOW"
        if ent["valid_until"] and ent["valid_until"] < now:
            db.execute("UPDATE enterprise_entitlements SET status = 'EXPIRED', updated_at = ? WHERE id = ?", (now, ent["id"]))
            return "EXPIRED"
        if int(ent["consumable"] or 0) and int(ent["allocated"]) - int(ent["consumed"]) < quantity:
            return "EXHAUSTED"
        if ent["scope_type"] == "SERVICE_POINT" and str(ent["scope_id"] or "") != str(service_point_id or ""):
            return "WRONG_SERVICE_POINT"
        return "VALID"

    def _credential_by_token(self, db, organization_id, event_id, token):
        token_hash = hashlib.sha256(str(token or "").encode("utf-8")).hexdigest() if token else ""
        return db.execute("SELECT * FROM enterprise_credentials WHERE organization_id = ? AND event_id = ? AND legacy_token_hash = ? AND status = 'ACTIVE'", (organization_id, event_id, token_hash)).fetchone()

    def _find_entitlement(self, db, organization_id, event_id, entity_id, entitlement_type):
        return db.execute("SELECT * FROM enterprise_entitlements WHERE organization_id = ? AND event_id = ? AND entity_id = ? AND entitlement_type = ? ORDER BY id DESC LIMIT 1", (organization_id, event_id, entity_id, self._clean_key(entitlement_type, 80))).fetchone()

    def _device_can_consume(self, db, organization_id, event_id, device_id):
        row = db.execute("SELECT capabilities_json FROM enterprise_devices WHERE id = ? AND organization_id = ? AND event_id = ? AND status = 'ACTIVE'", (device_id, organization_id, event_id)).fetchone()
        return bool(row and "CONSUME_ENTITLEMENT" in self._loads(row["capabilities_json"], []))

    def _entitlement(self, db, organization_id, event_id, entitlement_id):
        row = db.execute("SELECT * FROM enterprise_entitlements WHERE id = ? AND organization_id = ? AND event_id = ?", (entitlement_id, organization_id, event_id)).fetchone()
        if not row:
            raise EntitlementsVouchersError("ENTITLEMENT_NOT_FOUND", "Entitlement fuera de alcance", 404)
        return row

    def _entitlement_payload(self, row) -> dict:
        data = dict(row)
        data["available"] = None if not int(data.get("consumable") or 0) else max(0, int(data["allocated"]) - int(data["consumed"]))
        return data

    def _validate_event(self, db, organization_id, event_id):
        row = db.execute("SELECT id FROM events WHERE id = ? AND organization_id = ?", (event_id, organization_id)).fetchone()
        if not row:
            raise EntitlementsVouchersError("EVENT_SCOPE_ERROR", "Evento fuera de alcance", 403)

    def _row(self, db, table, row_id):
        row = db.execute(f"SELECT * FROM {table} WHERE id = ?", (row_id,)).fetchone()
        if not row:
            raise EntitlementsVouchersError("ROW_NOT_FOUND", "Registro no encontrado", 404)
        return dict(row)

    def _audit(self, db, actor, action, entity_type, entity_id, payload):
        if self.audit_service:
            self.audit_service.record(db, actor or "entitlements-vouchers", action, entity_type, entity_id, payload)

    def _domain(self, db, organization_id, event_id, event_type, entity_id=None, device_id=None, metadata=None):
        if self.enterprise_core:
            self.enterprise_core.record_domain_event(db, organization_id=organization_id, event_id=event_id, event_type=event_type, entity_id=entity_id, device_id=device_id, metadata=metadata or {})

    def _choice(self, value: str, allowed: set[str], code: str) -> str:
        normalized = str(value or "").strip().upper()
        if normalized not in allowed:
            raise EntitlementsVouchersError(code, "Valor invalido", 400)
        return normalized

    def _clean_key(self, value: str, limit: int) -> str:
        return re.sub(r"[^A-Za-z0-9_.:-]+", "_", str(value or "").strip()).strip("_")[:limit]

    def _clean_text(self, value: str, limit: int) -> str:
        return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(value or "")).strip()[:limit]

    def _json(self, value: Any) -> str:
        return json.dumps(value, ensure_ascii=True, sort_keys=True)

    def _loads(self, value: str, default):
        try:
            return json.loads(value or "")
        except Exception:
            return default
