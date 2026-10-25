from __future__ import annotations

import hashlib
import json
import re
from typing import Any


ENTITY_TYPES = {"PERSON", "CREDENTIAL", "COMPANY", "DEVICE", "VEHICLE", "STAND", "DELEGATION"}
ENTITY_STATUSES = {"ACTIVE", "INACTIVE", "ARCHIVED"}
CREDENTIAL_TYPES = {"QR_TOKEN", "PRINTED_BADGE", "PORTAL_TOKEN", "DYNAMIC_QR", "NFC", "RFID"}
ENTITLEMENT_STATUSES = {"ACTIVE", "SUSPENDED", "REVOKED", "EXPIRED"}
RULE_STATUSES = {"ACTIVE", "INACTIVE", "ARCHIVED"}
DOOR_STATUSES = {"ACTIVE", "INACTIVE", "ARCHIVED"}
DEVICE_STATUSES = {"REGISTERED", "ACTIVE", "INACTIVE", "REVOKED"}


class EnterpriseCoreError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class EnterpriseCoreService:
    def __init__(self, audit_service=None, now=None) -> None:
        self.audit_service = audit_service
        self.now = now or (lambda: "")

    def backfill_event(self, db, *, organization_id: int, event_id: int, actor: str = "enterprise-core") -> dict:
        self._validate_event(db, organization_id, event_id)
        stats = {"created": 0, "mapped": 0, "skipped": 0, "conflicts": [], "errors": []}
        people = db.execute(
            """
            SELECT p.*, a.id AS accreditation_id, a.token, a.status AS accreditation_status
            FROM accreditations a
            JOIN people p ON p.id = a.person_id
            WHERE a.event_id = ?
            ORDER BY a.id
            """,
            (event_id,),
        ).fetchall()
        for row in people:
            try:
                before = self._counts(db, organization_id, event_id)
                person = self.ensure_entity(
                    db,
                    organization_id=organization_id,
                    event_id=event_id,
                    entity_type="PERSON",
                    legacy_table="people",
                    legacy_id=int(row["id"]),
                    actor=actor,
                    metadata={"source": "backfill", "accreditation_id": int(row["accreditation_id"])},
                )
                self.ensure_identity(
                    db,
                    organization_id=organization_id,
                    event_id=event_id,
                    entity_id=person["id"],
                    display_name=f"{row['first_name']} {row['last_name']}".strip(),
                    identity_hash=self._hash(str(row["email"] or "").strip().lower() or str(row["dni"] or "")),
                )
                credential_entity = self.ensure_entity(
                    db,
                    organization_id=organization_id,
                    event_id=event_id,
                    entity_type="CREDENTIAL",
                    legacy_table="accreditations",
                    legacy_id=int(row["accreditation_id"]),
                    actor=actor,
                    metadata={"person_entity_id": person["id"], "source": "backfill"},
                )
                self.ensure_credential(
                    db,
                    organization_id=organization_id,
                    event_id=event_id,
                    entity_id=credential_entity["id"],
                    accreditation_id=int(row["accreditation_id"]),
                    token=str(row["token"] or ""),
                    status="ACTIVE" if str(row["accreditation_status"]) == "active" else "INACTIVE",
                )
                after = self._counts(db, organization_id, event_id)
                stats["created"] += max(0, after["entities"] + after["credentials"] - before["entities"] - before["credentials"])
                stats["mapped"] += 1
            except Exception as exc:
                stats["errors"].append({"legacy_table": "people", "legacy_id": int(row["id"]), "error": str(exc)})
        companies = sorted({str(row["company"] or "").strip() for row in people if str(row["company"] or "").strip()})
        for company in companies:
            self.ensure_entity(
                db,
                organization_id=organization_id,
                event_id=event_id,
                entity_type="COMPANY",
                legacy_table="people.company",
                legacy_id=0,
                external_key=self._slug(company),
                actor=actor,
                metadata={"name": company, "source": "backfill"},
            )
        if self.audit_service:
            self.audit_service.record(db, actor, "enterprise_core.backfilled", "event", event_id, {"organization_id": organization_id, **stats})
        return {"ok": not stats["errors"], "stats": stats, "summary": self.summary(db, organization_id=organization_id, event_id=event_id)}

    def ensure_entity(self, db, *, organization_id: int, event_id: int, entity_type: str, legacy_table: str = "", legacy_id: int | None = None, external_key: str = "", actor: str = "", metadata: dict | None = None) -> dict:
        entity_type = self._choice(entity_type, ENTITY_TYPES, "ENTITY_TYPE_INVALID")
        legacy_table = self._clean_key(legacy_table, 80)
        external_key = self._clean_key(external_key, 160)
        legacy_id = int(legacy_id or 0)
        row = db.execute(
            """
            SELECT * FROM enterprise_entities
            WHERE organization_id = ? AND event_id = ? AND entity_type = ? AND legacy_table = ? AND legacy_id = ? AND external_key = ?
            """,
            (organization_id, event_id, entity_type, legacy_table, legacy_id, external_key),
        ).fetchone()
        now = self.now()
        metadata_json = self._json(metadata or {})
        if row:
            db.execute(
                "UPDATE enterprise_entities SET external_key = COALESCE(NULLIF(?, ''), external_key), metadata_json = ?, updated_at = ? WHERE id = ?",
                (external_key, metadata_json, now, row["id"]),
            )
            return self._entity_payload(db.execute("SELECT * FROM enterprise_entities WHERE id = ?", (row["id"],)).fetchone())
        cur = db.execute(
            """
            INSERT INTO enterprise_entities (
                organization_id, event_id, entity_type, legacy_table, legacy_id, external_key,
                status, metadata_json, created_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'ACTIVE', ?, ?, ?, ?)
            """,
            (organization_id, event_id, entity_type, legacy_table, legacy_id, external_key, metadata_json, actor, now, now),
        )
        entity_id = int(getattr(cur, "lastrowid", 0) or 0)
        if self.audit_service:
            self.audit_service.record(db, actor or "enterprise-core", "enterprise_core.entity.created", "enterprise_entity", entity_id, {"organization_id": organization_id, "event_id": event_id, "entity_type": entity_type})
        return self._entity_payload(db.execute("SELECT * FROM enterprise_entities WHERE id = ?", (entity_id,)).fetchone())

    def ensure_identity(self, db, *, organization_id: int, event_id: int, entity_id: int, display_name: str = "", identity_hash: str = "", identity_type: str = "PROFILE") -> dict:
        self._get_entity(db, organization_id, event_id, entity_id)
        identity_type = self._clean_key(identity_type, 60) or "PROFILE"
        now = self.now()
        row = db.execute("SELECT * FROM enterprise_identities WHERE entity_id = ? AND identity_type = ?", (entity_id, identity_type)).fetchone()
        if row:
            db.execute("UPDATE enterprise_identities SET display_name = ?, identity_hash = ?, updated_at = ? WHERE id = ?", (self._clean_text(display_name, 240), identity_hash, now, row["id"]))
            identity_id = int(row["id"])
        else:
            cur = db.execute(
                """
                INSERT INTO enterprise_identities (
                    organization_id, event_id, entity_id, identity_type, display_name,
                    identity_hash, verification_status, metadata_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'UNVERIFIED', '{}', ?, ?)
                """,
                (organization_id, event_id, entity_id, identity_type, self._clean_text(display_name, 240), identity_hash, now, now),
            )
            identity_id = int(getattr(cur, "lastrowid", 0) or 0)
        return dict(db.execute("SELECT * FROM enterprise_identities WHERE id = ?", (identity_id,)).fetchone())

    def ensure_credential(self, db, *, organization_id: int, event_id: int, entity_id: int, accreditation_id: int, token: str, credential_type: str = "QR_TOKEN", status: str = "ACTIVE") -> dict:
        self._get_entity(db, organization_id, event_id, entity_id)
        credential_type = self._choice(credential_type, CREDENTIAL_TYPES, "CREDENTIAL_TYPE_INVALID")
        status = self._choice(status, {"ACTIVE", "INACTIVE", "REVOKED", "EXPIRED"}, "CREDENTIAL_STATUS_INVALID")
        token = str(token or "")
        now = self.now()
        row = db.execute(
            "SELECT * FROM enterprise_credentials WHERE organization_id = ? AND event_id = ? AND credential_type = ? AND accreditation_id = ?",
            (organization_id, event_id, credential_type, accreditation_id),
        ).fetchone()
        token_hash = self._hash(token)
        token_hint = token[:8]
        if row:
            db.execute("UPDATE enterprise_credentials SET entity_id = ?, legacy_token_hash = ?, token_hint = ?, status = ?, updated_at = ? WHERE id = ?", (entity_id, token_hash, token_hint, status, now, row["id"]))
            credential_id = int(row["id"])
        else:
            cur = db.execute(
                """
                INSERT INTO enterprise_credentials (
                    organization_id, event_id, entity_id, accreditation_id, credential_type,
                    legacy_token_hash, token_hint, status, issued_at, metadata_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '{}', ?, ?)
                """,
                (organization_id, event_id, entity_id, accreditation_id, credential_type, token_hash, token_hint, status, now, now, now),
            )
            credential_id = int(getattr(cur, "lastrowid", 0) or 0)
        return dict(db.execute("SELECT * FROM enterprise_credentials WHERE id = ?", (credential_id,)).fetchone())

    def grant_entitlement(self, db, *, organization_id: int, event_id: int, entity_id: int, entitlement_type: str, scope_type: str = "EVENT", scope_id: str = "", allocated: int = 0, consumable: bool = False, valid_from: str = "", valid_until: str = "", idempotency_key: str = "", actor: str = "", metadata: dict | None = None) -> dict:
        self._get_entity(db, organization_id, event_id, entity_id)
        now = self.now()
        if idempotency_key:
            existing = db.execute("SELECT * FROM enterprise_entitlements WHERE organization_id = ? AND idempotency_key = ?", (organization_id, idempotency_key)).fetchone()
            if existing:
                return {"ok": True, "idempotent": True, "item": dict(existing)}
        row = db.execute(
            """
            SELECT * FROM enterprise_entitlements
            WHERE organization_id = ? AND event_id = ? AND entity_id = ? AND entitlement_type = ? AND scope_type = ? AND scope_id = ?
            """,
            (organization_id, event_id, entity_id, self._clean_key(entitlement_type, 80), self._clean_key(scope_type, 60) or "EVENT", str(scope_id or "")),
        ).fetchone()
        values = (
            max(0, int(allocated or 0)),
            1 if consumable else 0,
            self._choice("ACTIVE", ENTITLEMENT_STATUSES, "ENTITLEMENT_STATUS_INVALID"),
            valid_from,
            valid_until,
            idempotency_key,
            self._json(metadata or {}),
            actor,
            now,
        )
        if row:
            db.execute(
                "UPDATE enterprise_entitlements SET allocated = ?, consumable = ?, status = ?, valid_from = ?, valid_until = ?, idempotency_key = COALESCE(NULLIF(?, ''), idempotency_key), metadata_json = ?, created_by = COALESCE(NULLIF(?, ''), created_by), updated_at = ? WHERE id = ?",
                (*values, row["id"]),
            )
            entitlement_id = int(row["id"])
        else:
            cur = db.execute(
                """
                INSERT INTO enterprise_entitlements (
                    organization_id, event_id, entity_id, entitlement_type, scope_type, scope_id,
                    allocated, consumed, consumable, status, valid_from, valid_until, idempotency_key,
                    metadata_json, created_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (organization_id, event_id, entity_id, self._clean_key(entitlement_type, 80), self._clean_key(scope_type, 60) or "EVENT", str(scope_id or ""), max(0, int(allocated or 0)), 1 if consumable else 0, "ACTIVE", valid_from, valid_until, idempotency_key, self._json(metadata or {}), actor, now, now),
            )
            entitlement_id = int(getattr(cur, "lastrowid", 0) or 0)
        if self.audit_service:
            self.audit_service.record(db, actor or "enterprise-core", "enterprise_core.entitlement.granted", "enterprise_entitlement", entitlement_id, {"organization_id": organization_id, "event_id": event_id, "entity_id": entity_id})
        return {"ok": True, "item": dict(db.execute("SELECT * FROM enterprise_entitlements WHERE id = ?", (entitlement_id,)).fetchone())}

    def create_rule(self, db, *, organization_id: int, event_id: int, entitlement_id: int | None, rule_type: str, scope: dict | None = None, actor: str = "", valid_from: str = "", valid_until: str = "") -> dict:
        now = self.now()
        if entitlement_id:
            row = db.execute("SELECT id FROM enterprise_entitlements WHERE id = ? AND organization_id = ? AND event_id = ?", (entitlement_id, organization_id, event_id)).fetchone()
            if not row:
                raise EnterpriseCoreError("RULE_ENTITLEMENT_NOT_FOUND", "Entitlement fuera de alcance", 404)
        cur = db.execute(
            """
            INSERT INTO enterprise_rules (
                organization_id, event_id, entitlement_id, rule_type, scope_json, status,
                valid_from, valid_until, metadata_json, created_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 'ACTIVE', ?, ?, '{}', ?, ?, ?)
            """,
            (organization_id, event_id, entitlement_id, self._clean_key(rule_type, 80), self._json(scope or {}), valid_from, valid_until, actor, now, now),
        )
        rule_id = int(getattr(cur, "lastrowid", 0) or 0)
        return {"ok": True, "item": dict(db.execute("SELECT * FROM enterprise_rules WHERE id = ?", (rule_id,)).fetchone())}

    def ensure_door(self, db, *, organization_id: int, event_id: int, code: str, name: str, zone_id: int | None = None) -> dict:
        self._validate_event(db, organization_id, event_id)
        if zone_id:
            zone = db.execute("SELECT id FROM event_zones WHERE id = ? AND organization_id = ? AND event_id = ?", (zone_id, organization_id, event_id)).fetchone()
            if not zone:
                raise EnterpriseCoreError("DOOR_ZONE_NOT_FOUND", "Zona fuera de alcance", 404)
        code = self._clean_key(code, 80)
        now = self.now()
        row = db.execute("SELECT * FROM enterprise_doors WHERE organization_id = ? AND event_id = ? AND code = ?", (organization_id, event_id, code)).fetchone()
        if row:
            db.execute("UPDATE enterprise_doors SET name = ?, zone_id = ?, updated_at = ? WHERE id = ?", (self._clean_text(name, 160), zone_id, now, row["id"]))
            door_id = int(row["id"])
        else:
            cur = db.execute("INSERT INTO enterprise_doors (organization_id, event_id, zone_id, code, name, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)", (organization_id, event_id, zone_id, code, self._clean_text(name, 160), now, now))
            door_id = int(getattr(cur, "lastrowid", 0) or 0)
        return {"ok": True, "item": dict(db.execute("SELECT * FROM enterprise_doors WHERE id = ?", (door_id,)).fetchone())}

    def register_device(self, db, *, organization_id: int, event_id: int, device_uid: str, device_type: str = "GENERIC", version: str = "") -> dict:
        self._validate_event(db, organization_id, event_id)
        device_uid = self._clean_key(device_uid, 160)
        if not device_uid:
            raise EnterpriseCoreError("DEVICE_UID_REQUIRED", "device_uid obligatorio", 400)
        now = self.now()
        row = db.execute("SELECT * FROM enterprise_devices WHERE organization_id = ? AND event_id = ? AND device_uid = ?", (organization_id, event_id, device_uid)).fetchone()
        if row:
            db.execute("UPDATE enterprise_devices SET device_type = ?, version = ?, last_seen_at = ?, updated_at = ? WHERE id = ?", (self._clean_key(device_type, 80) or "GENERIC", self._clean_text(version, 80), now, now, row["id"]))
            device_id = int(row["id"])
        else:
            cur = db.execute("INSERT INTO enterprise_devices (organization_id, event_id, device_uid, device_type, status, last_seen_at, version, created_at, updated_at) VALUES (?, ?, ?, ?, 'REGISTERED', ?, ?, ?, ?)", (organization_id, event_id, device_uid, self._clean_key(device_type, 80) or "GENERIC", now, self._clean_text(version, 80), now, now))
            device_id = int(getattr(cur, "lastrowid", 0) or 0)
        return {"ok": True, "item": dict(db.execute("SELECT * FROM enterprise_devices WHERE id = ?", (device_id,)).fetchone())}

    def record_domain_event(self, db, *, organization_id: int, event_id: int, event_type: str, entity_id: int | None = None, device_id: int | None = None, correlation_id: str = "", idempotency_key: str = "", metadata: dict | None = None) -> dict:
        now = self.now()
        if idempotency_key:
            row = db.execute("SELECT * FROM enterprise_domain_events WHERE organization_id = ? AND idempotency_key = ?", (organization_id, idempotency_key)).fetchone()
            if row:
                return {"ok": True, "idempotent": True, "item": dict(row)}
        cur = db.execute(
            "INSERT INTO enterprise_domain_events (organization_id, event_id, entity_id, device_id, event_type, correlation_id, idempotency_key, metadata_json, occurred_at, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (organization_id, event_id, entity_id, device_id, self._clean_key(event_type, 120), self._clean_text(correlation_id, 120), idempotency_key, self._json(metadata or {}), now, now),
        )
        event_row_id = int(getattr(cur, "lastrowid", 0) or 0)
        return {"ok": True, "item": dict(db.execute("SELECT * FROM enterprise_domain_events WHERE id = ?", (event_row_id,)).fetchone())}

    def summary(self, db, *, organization_id: int, event_id: int) -> dict:
        return {"ok": True, **self._counts(db, organization_id, event_id)}

    def _counts(self, db, organization_id: int, event_id: int) -> dict:
        result = {}
        for key, table in {
            "entities": "enterprise_entities",
            "credentials": "enterprise_credentials",
            "entitlements": "enterprise_entitlements",
            "rules": "enterprise_rules",
            "doors": "enterprise_doors",
            "devices": "enterprise_devices",
            "domain_events": "enterprise_domain_events",
        }.items():
            try:
                result[key] = int(db.execute(f"SELECT COUNT(*) AS c FROM {table} WHERE organization_id = ? AND event_id = ?", (organization_id, event_id)).fetchone()["c"])
            except Exception:
                result[key] = 0
        return result

    def _validate_event(self, db, organization_id: int, event_id: int) -> None:
        row = db.execute("SELECT id FROM events WHERE id = ? AND organization_id = ?", (event_id, organization_id)).fetchone()
        if not row:
            raise EnterpriseCoreError("ENTERPRISE_SCOPE_MISMATCH", "Evento fuera de alcance", 403)

    def _get_entity(self, db, organization_id: int, event_id: int, entity_id: int):
        row = db.execute("SELECT * FROM enterprise_entities WHERE id = ? AND organization_id = ? AND event_id = ?", (entity_id, organization_id, event_id)).fetchone()
        if not row:
            raise EnterpriseCoreError("ENTITY_NOT_FOUND", "Entity fuera de alcance", 404)
        return row

    def _entity_payload(self, row) -> dict:
        return {"id": int(row["id"]), "organization_id": int(row["organization_id"]), "event_id": int(row["event_id"]), "entity_type": row["entity_type"], "legacy_table": row["legacy_table"], "legacy_id": row["legacy_id"], "status": row["status"]}

    def _choice(self, value: str, allowed: set[str], code: str) -> str:
        normalized = str(value or "").strip().upper()
        if normalized not in allowed:
            raise EnterpriseCoreError(code, "Valor invalido", 400)
        return normalized

    def _clean_key(self, value: str, limit: int) -> str:
        text = re.sub(r"[^A-Za-z0-9_.:-]+", "_", str(value or "").strip()).strip("_")
        return text[:limit]

    def _clean_text(self, value: str, limit: int) -> str:
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(value or "")).strip()
        return text[:limit]

    def _json(self, value: dict[str, Any]) -> str:
        return json.dumps(value, ensure_ascii=True, sort_keys=True)

    def _hash(self, value: str) -> str:
        return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest() if value else ""

    def _slug(self, value: str) -> str:
        return self._clean_key(value.lower(), 160)
