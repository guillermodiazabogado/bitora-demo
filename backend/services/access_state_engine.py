from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
import re
import uuid
from typing import Any


ALLOW = "ALLOW"
DENY = "DENY"
VALID = "VALID"


REASON_CODES = {
    "VALID",
    "UNKNOWN_CREDENTIAL",
    "WRONG_EVENT",
    "INACTIVE_CREDENTIAL",
    "REVOKED",
    "NO_ENTITLEMENT",
    "RULE_DENIED",
    "OUTSIDE_TIME_WINDOW",
    "ANTI_PASSBACK",
    "COOLDOWN",
    "WRONG_ZONE",
    "WRONG_DOOR",
    "CAPACITY_REACHED",
    "INVALID_STATE_TRANSITION",
    "V5_ERROR",
}


@dataclass
class AccessStateContext:
    organization_id: int
    event_id: int
    token: str
    direction: str = "ENTRY"
    checkpoint: str = "Acceso principal"
    activity_id: int | None = None
    door_id: int | None = None
    zone_id: int | None = None
    device_id: int | None = None
    source: str = "shadow"
    timestamp: str = ""
    correlation_id: str = ""
    idempotency_key: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    cooldown_seconds: int = 0
    anti_passback_enabled: bool = True
    current_occupancy: int | None = None
    capacity: int | None = None
    force_error: bool = False


@dataclass
class AccessStateDecision:
    decision: str
    reason_code: str
    previous_state: str = "OUTSIDE"
    proposed_state: str = "OUTSIDE"
    current_zone_id: int | None = None
    proposed_zone_id: int | None = None
    entity_id: int | None = None
    credential_id: int | None = None
    accreditation_id: int | None = None
    door_id: int | None = None
    zone_id: int | None = None
    device_id: int | None = None
    direction: str = "ENTRY"
    correlation_id: str = ""
    idempotency_key: str = ""
    rule_results: list[dict[str, Any]] = field(default_factory=list)
    entitlement_results: list[dict[str, Any]] = field(default_factory=list)
    revocation_status: str = "NOT_REVOKED"
    cooldown_status: str = "NOT_APPLICABLE"
    anti_passback_status: str = "NOT_APPLICABLE"
    capacity_status: str = "NOT_APPLICABLE"
    occurred_at: str = ""
    access_event_id: int | None = None
    error: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "reason_code": self.reason_code,
            "previous_state": self.previous_state,
            "proposed_state": self.proposed_state,
            "current_zone_id": self.current_zone_id,
            "proposed_zone_id": self.proposed_zone_id,
            "entity_id": self.entity_id,
            "credential_id": self.credential_id,
            "accreditation_id": self.accreditation_id,
            "door_id": self.door_id,
            "zone_id": self.zone_id,
            "device_id": self.device_id,
            "direction": self.direction,
            "correlation_id": self.correlation_id,
            "idempotency_key": self.idempotency_key,
            "rule_results": self.rule_results,
            "entitlement_results": self.entitlement_results,
            "revocation_status": self.revocation_status,
            "cooldown_status": self.cooldown_status,
            "anti_passback_status": self.anti_passback_status,
            "capacity_status": self.capacity_status,
            "occurred_at": self.occurred_at,
            "access_event_id": self.access_event_id,
            "error": self.error,
        }


class AccessStateEngine:
    def __init__(self, enterprise_core=None, now=None) -> None:
        self.enterprise_core = enterprise_core
        self.now = now or (lambda: datetime.utcnow().replace(microsecond=0).isoformat())

    def evaluate(self, db, context: AccessStateContext) -> AccessStateDecision:
        if context.force_error:
            raise RuntimeError("forced V5.1 shadow failure")
        context = self._normalize_context(context)
        credential = self._credential_for_token(db, context)
        if not credential:
            return self._decision(context, DENY, "UNKNOWN_CREDENTIAL")
        accreditation = db.execute(
            """
            SELECT a.*, e.organization_id, COALESCE(t.access_enabled, 1) AS type_access_enabled
            FROM accreditations a
            JOIN events e ON e.id = a.event_id
            LEFT JOIN accreditation_types t ON t.event_id = a.event_id AND t.name = a.type
            WHERE a.id = ?
            """,
            (credential["accreditation_id"],),
        ).fetchone()
        if not accreditation or int(accreditation["event_id"]) != context.event_id or int(accreditation["organization_id"]) != context.organization_id:
            return self._decision(context, DENY, "WRONG_EVENT", credential=credential)
        snapshot = self._snapshot(db, context, int(credential["entity_id"]))
        previous_state = str(snapshot["current_state"]) if snapshot else "OUTSIDE"
        current_zone_id = int(snapshot["current_zone_id"]) if snapshot and snapshot["current_zone_id"] is not None else None
        decision = self._decision(context, ALLOW, VALID, credential=credential, accreditation=accreditation, previous_state=previous_state, current_zone_id=current_zone_id)
        if self._is_revoked(db, context, int(credential["id"])):
            decision.revocation_status = "REVOKED"
            return self._deny(decision, "REVOKED")
        if str(credential["status"]) != "ACTIVE" or str(accreditation["status"]) != "active":
            return self._deny(decision, "INACTIVE_CREDENTIAL")
        if not int(accreditation["type_access_enabled"] or 0):
            return self._deny(decision, "RULE_DENIED")
        if context.activity_id:
            if not accreditation["checked_in_at"]:
                return self._deny(decision, "RULE_DENIED")
            activity = db.execute(
                """
                SELECT a.*, e.activity_access_open_minutes_before AS event_access_open_minutes_before
                FROM activities a
                JOIN events e ON e.id = a.event_id
                WHERE a.id = ? AND a.event_id = ? AND a.status <> 'cancelled'
                """,
                (context.activity_id, context.event_id),
            ).fetchone()
            if not activity:
                return self._deny(decision, "WRONG_EVENT")
            if str(activity["reservation_mode"] or "") in {"required", "invited"}:
                reservation = db.execute(
                    "SELECT id FROM reservations WHERE activity_id = ? AND accreditation_id = ? AND status = 'confirmed'",
                    (context.activity_id, accreditation["id"]),
                ).fetchone()
                if not reservation:
                    return self._deny(decision, "NO_ENTITLEMENT")
            legacy_duplicate = db.execute(
                """
                SELECT id FROM access_logs
                WHERE event_id = ? AND activity_id = ? AND accreditation_id = ?
                  AND access_context = 'activity_entry' AND result = 'granted'
                LIMIT 1
                """,
                (context.event_id, context.activity_id, accreditation["id"]),
            ).fetchone()
            if legacy_duplicate:
                return self._deny(decision, "ANTI_PASSBACK")
            open_at = self._activity_open_at(activity)
            if self._parse_time(context.timestamp) < open_at:
                return self._deny(decision, "OUTSIDE_TIME_WINDOW")
        if context.current_occupancy is not None and context.capacity is not None and int(context.current_occupancy) >= int(context.capacity):
            decision.capacity_status = "CAPACITY_REACHED"
            return self._deny(decision, "CAPACITY_REACHED")
        if context.door_id and not self._door_allowed(db, context):
            return self._deny(decision, "WRONG_DOOR")
        entitlement_result = self._evaluate_entitlements(db, context, int(credential["entity_id"]))
        decision.entitlement_results.append(entitlement_result)
        if not entitlement_result["allowed"]:
            return self._deny(decision, "NO_ENTITLEMENT")
        rule_result = self._evaluate_rules(db, context, int(credential["entity_id"]))
        decision.rule_results.extend(rule_result["rules"])
        if not rule_result["allowed"]:
            return self._deny(decision, rule_result["reason_code"])
        if context.cooldown_seconds > 0 and snapshot and snapshot["last_transition_at"]:
            if self._parse_time(context.timestamp) < self._parse_time(str(snapshot["last_transition_at"])) + timedelta(seconds=context.cooldown_seconds):
                decision.cooldown_status = "ACTIVE"
                return self._deny(decision, "COOLDOWN")
            decision.cooldown_status = "PASSED"
        if context.direction == "ENTRY":
            if context.anti_passback_enabled and previous_state == "INSIDE" and not context.activity_id:
                decision.anti_passback_status = "DETECTED"
                return self._deny(decision, "ANTI_PASSBACK")
            decision.proposed_state = "INSIDE"
            decision.proposed_zone_id = context.zone_id
        elif context.direction == "EXIT":
            if previous_state != "INSIDE":
                return self._deny(decision, "INVALID_STATE_TRANSITION")
            decision.proposed_state = "OUTSIDE"
            decision.proposed_zone_id = None
        else:
            return self._deny(decision, "INVALID_STATE_TRANSITION")
        return decision

    def evaluate_and_record(self, db, context: AccessStateContext, v4_result: dict) -> dict:
        try:
            decision = self.evaluate(db, context)
            event_row = self.record_access_event(db, context, decision)
            decision.access_event_id = event_row["id"]
            comparison = self.record_comparison(db, context, decision, v4_result)
            event_type = "ACCESS_DECISION_MATCHED" if comparison["comparison"].startswith("MATCH") else "ACCESS_DECISION_DIVERGED"
            self._record_domain_event(db, context, decision, event_type, {"comparison": comparison["comparison"]})
            return {"ok": True, "decision": decision.as_dict(), "comparison": comparison}
        except Exception as exc:
            fallback = AccessStateDecision(decision=DENY, reason_code="V5_ERROR", correlation_id=context.correlation_id or self._correlation_id(), idempotency_key=context.idempotency_key, occurred_at=context.timestamp or self.now(), error=str(exc))
            self.record_comparison(db, context, fallback, v4_result, comparison_override="V5_ERROR")
            return {"ok": False, "decision": fallback.as_dict(), "comparison": {"comparison": "V5_ERROR"}, "error": str(exc)}

    def record_access_event(self, db, context: AccessStateContext, decision: AccessStateDecision) -> dict:
        metadata = {
            "checkpoint": context.checkpoint,
            "activity_id": context.activity_id,
            "rule_results": decision.rule_results,
            "entitlement_results": decision.entitlement_results,
            "revocation_status": decision.revocation_status,
            "cooldown_status": decision.cooldown_status,
            "anti_passback_status": decision.anti_passback_status,
            "capacity_status": decision.capacity_status,
            **(context.metadata or {}),
        }
        if context.idempotency_key:
            row = db.execute("SELECT * FROM enterprise_access_events WHERE organization_id = ? AND idempotency_key = ?", (context.organization_id, context.idempotency_key)).fetchone()
            if row:
                return dict(row)
        cur = db.execute(
            """
            INSERT INTO enterprise_access_events (
                organization_id, event_id, entity_id, credential_id, accreditation_id, door_id, zone_id, device_id,
                direction, decision, reason_code, previous_state, proposed_state, previous_zone_id, proposed_zone_id,
                correlation_id, idempotency_key, source, metadata_json, occurred_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                context.organization_id, context.event_id, decision.entity_id, decision.credential_id, decision.accreditation_id,
                context.door_id, context.zone_id, context.device_id, context.direction, decision.decision, decision.reason_code,
                decision.previous_state, decision.proposed_state, decision.current_zone_id, decision.proposed_zone_id,
                decision.correlation_id, context.idempotency_key, context.source, json.dumps(metadata, ensure_ascii=True, sort_keys=True),
                decision.occurred_at or context.timestamp, self.now(),
            ),
        )
        event_id = int(getattr(cur, "lastrowid", 0) or 0)
        if decision.decision == ALLOW and decision.entity_id:
            self._upsert_snapshot(db, context, decision, event_id)
        return dict(db.execute("SELECT * FROM enterprise_access_events WHERE id = ?", (event_id,)).fetchone())

    def record_comparison(self, db, context: AccessStateContext, decision: AccessStateDecision, v4_result: dict, comparison_override: str = "") -> dict:
        v4 = "ALLOW" if str(v4_result.get("result")) == "granted" else "DENY"
        if comparison_override:
            comparison = comparison_override
        elif v4 == decision.decision == ALLOW:
            comparison = "MATCH_ALLOW"
        elif v4 == decision.decision == DENY:
            comparison = "MATCH_DENY"
        elif v4 == ALLOW and decision.decision == DENY:
            comparison = "DIVERGENCE_V4_ALLOW_V5_DENY"
        else:
            comparison = "DIVERGENCE_V4_DENY_V5_ALLOW"
        classification = "MATCH" if comparison.startswith("MATCH") else ("V5_ERROR" if comparison == "V5_ERROR" else "EXPECTED_DIVERGENCE")
        idem = f"comparison:{context.idempotency_key}" if context.idempotency_key else ""
        if idem:
            row = db.execute("SELECT * FROM enterprise_access_comparisons WHERE organization_id = ? AND idempotency_key = ?", (context.organization_id, idem)).fetchone()
            if row:
                return dict(row)
        cur = db.execute(
            """
            INSERT INTO enterprise_access_comparisons (
                organization_id, event_id, entity_id, credential_id, accreditation_id, access_event_id,
                v4_result, v4_reason, v5_decision, v5_reason_code, comparison, classification,
                correlation_id, idempotency_key, metadata_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                context.organization_id, context.event_id, decision.entity_id, decision.credential_id, decision.accreditation_id,
                decision.access_event_id, str(v4_result.get("result") or ""), str(v4_result.get("reason") or ""),
                decision.decision, decision.reason_code, comparison, classification, decision.correlation_id, idem,
                json.dumps({"checkpoint": context.checkpoint, "activity_id": context.activity_id}, ensure_ascii=True, sort_keys=True),
                self.now(),
            ),
        )
        return dict(db.execute("SELECT * FROM enterprise_access_comparisons WHERE id = ?", (int(getattr(cur, "lastrowid", 0) or 0),)).fetchone())

    def revoke_credential(self, db, *, organization_id: int, event_id: int, credential_id: int, actor: str = "", reason: str = "", reason_code: str = "REVOKED") -> dict:
        credential = db.execute("SELECT * FROM enterprise_credentials WHERE id = ? AND organization_id = ? AND event_id = ?", (credential_id, organization_id, event_id)).fetchone()
        if not credential:
            raise ValueError("credential out of scope")
        now = self.now()
        db.execute("UPDATE enterprise_credentials SET status = 'REVOKED', revoked_at = ?, updated_at = ? WHERE id = ?", (now, now, credential_id))
        cur = db.execute(
            """
            INSERT OR IGNORE INTO enterprise_credential_revocations (
                organization_id, event_id, credential_id, accreditation_id, status, reason_code, reason, actor, revoked_at, metadata_json, created_at
            ) VALUES (?, ?, ?, ?, 'ACTIVE', ?, ?, ?, ?, '{}', ?)
            """,
            (organization_id, event_id, credential_id, credential["accreditation_id"], reason_code, reason, actor, now, now),
        )
        self._record_domain_event_raw(db, organization_id, event_id, int(credential["entity_id"]), None, "CREDENTIAL_REVOKED", self._correlation_id(), "", {"credential_id": credential_id, "actor": actor, "reason_code": reason_code})
        revocation_id = int(getattr(cur, "lastrowid", 0) or 0)
        if not revocation_id:
            row = db.execute("SELECT * FROM enterprise_credential_revocations WHERE organization_id = ? AND event_id = ? AND credential_id = ? AND status = 'ACTIVE'", (organization_id, event_id, credential_id)).fetchone()
            revocation_id = int(row["id"])
        return {"ok": True, "id": revocation_id}

    def telemetry(self, db, *, organization_id: int, event_id: int) -> dict:
        def count(sql: str, params: tuple = ()) -> int:
            return int(db.execute(sql, params).fetchone()["c"] or 0)
        params = (organization_id, event_id)
        return {
            "total_evaluations": count("SELECT COUNT(*) AS c FROM enterprise_access_comparisons WHERE organization_id = ? AND event_id = ?", params),
            "v4_allow": count("SELECT COUNT(*) AS c FROM enterprise_access_comparisons WHERE organization_id = ? AND event_id = ? AND v4_result = 'granted'", params),
            "v4_deny": count("SELECT COUNT(*) AS c FROM enterprise_access_comparisons WHERE organization_id = ? AND event_id = ? AND v4_result <> 'granted'", params),
            "v5_allow": count("SELECT COUNT(*) AS c FROM enterprise_access_comparisons WHERE organization_id = ? AND event_id = ? AND v5_decision = 'ALLOW'", params),
            "v5_deny": count("SELECT COUNT(*) AS c FROM enterprise_access_comparisons WHERE organization_id = ? AND event_id = ? AND v5_decision = 'DENY'", params),
            "matches": count("SELECT COUNT(*) AS c FROM enterprise_access_comparisons WHERE organization_id = ? AND event_id = ? AND comparison LIKE 'MATCH%'", params),
            "divergences": count("SELECT COUNT(*) AS c FROM enterprise_access_comparisons WHERE organization_id = ? AND event_id = ? AND comparison LIKE 'DIVERGENCE%'", params),
            "v5_errors": count("SELECT COUNT(*) AS c FROM enterprise_access_comparisons WHERE organization_id = ? AND event_id = ? AND comparison = 'V5_ERROR'", params),
            "anti_passback_detections": count("SELECT COUNT(*) AS c FROM enterprise_access_events WHERE organization_id = ? AND event_id = ? AND reason_code = 'ANTI_PASSBACK'", params),
            "cooldown_detections": count("SELECT COUNT(*) AS c FROM enterprise_access_events WHERE organization_id = ? AND event_id = ? AND reason_code = 'COOLDOWN'", params),
            "revocation_detections": count("SELECT COUNT(*) AS c FROM enterprise_access_events WHERE organization_id = ? AND event_id = ? AND reason_code = 'REVOKED'", params),
            "entitlement_denials": count("SELECT COUNT(*) AS c FROM enterprise_access_events WHERE organization_id = ? AND event_id = ? AND reason_code = 'NO_ENTITLEMENT'", params),
            "rule_denials": count("SELECT COUNT(*) AS c FROM enterprise_access_events WHERE organization_id = ? AND event_id = ? AND reason_code = 'RULE_DENIED'", params),
        }

    def _normalize_context(self, context: AccessStateContext) -> AccessStateContext:
        direction = str(context.direction or "ENTRY").strip().upper()
        if direction not in {"ENTRY", "EXIT", "ZONE_ENTRY", "ZONE_EXIT"}:
            direction = "ENTRY"
        context.direction = "EXIT" if direction == "ZONE_EXIT" else ("ENTRY" if direction == "ZONE_ENTRY" else direction)
        context.timestamp = context.timestamp or self.now()
        context.correlation_id = self._clean_key(context.correlation_id or self._correlation_id(), 120)
        context.idempotency_key = self._clean_key(context.idempotency_key, 160)
        return context

    def _credential_for_token(self, db, context: AccessStateContext):
        import hashlib
        token_hash = hashlib.sha256(str(context.token or "").encode("utf-8")).hexdigest() if context.token else ""
        return db.execute(
            """
            SELECT * FROM enterprise_credentials
            WHERE organization_id = ? AND event_id = ? AND credential_type = 'QR_TOKEN' AND legacy_token_hash = ?
            """,
            (context.organization_id, context.event_id, token_hash),
        ).fetchone()

    def _snapshot(self, db, context: AccessStateContext, entity_id: int):
        return db.execute(
            "SELECT * FROM enterprise_access_state_snapshots WHERE organization_id = ? AND event_id = ? AND entity_id = ?",
            (context.organization_id, context.event_id, entity_id),
        ).fetchone()

    def _is_revoked(self, db, context: AccessStateContext, credential_id: int) -> bool:
        row = db.execute(
            "SELECT id FROM enterprise_credential_revocations WHERE organization_id = ? AND event_id = ? AND credential_id = ? AND status = 'ACTIVE'",
            (context.organization_id, context.event_id, credential_id),
        ).fetchone()
        return row is not None

    def _door_allowed(self, db, context: AccessStateContext) -> bool:
        row = db.execute(
            "SELECT * FROM enterprise_doors WHERE id = ? AND organization_id = ? AND event_id = ? AND status = 'ACTIVE'",
            (context.door_id, context.organization_id, context.event_id),
        ).fetchone()
        if not row:
            return False
        return context.zone_id in {None, row["zone_id"]}

    def _evaluate_entitlements(self, db, context: AccessStateContext, entity_id: int) -> dict:
        rows = db.execute(
            """
            SELECT * FROM enterprise_entitlements
            WHERE organization_id = ? AND event_id = ? AND entity_id = ? AND status = 'ACTIVE'
            """,
            (context.organization_id, context.event_id, entity_id),
        ).fetchall()
        if not rows:
            return {"allowed": True, "mode": "NO_ENTITLEMENTS_CONFIGURED"}
        now = self._parse_time(context.timestamp)
        for row in rows:
            scope_type = str(row["scope_type"] or "EVENT").upper()
            scope_id = str(row["scope_id"] or "")
            if scope_type == "ZONE" and context.zone_id and scope_id not in {str(context.zone_id), ""}:
                continue
            if scope_type == "DOOR" and context.door_id and scope_id not in {str(context.door_id), ""}:
                continue
            if row["valid_from"] and now < self._parse_time(str(row["valid_from"])):
                continue
            if row["valid_until"] and now > self._parse_time(str(row["valid_until"])):
                continue
            return {"allowed": True, "entitlement_id": int(row["id"]), "type": row["entitlement_type"], "scope_type": scope_type, "scope_id": scope_id}
        return {"allowed": False, "mode": "ENTITLEMENTS_PRESENT_NO_MATCH"}

    def _evaluate_rules(self, db, context: AccessStateContext, entity_id: int) -> dict:
        rows = db.execute(
            """
            SELECT r.*
            FROM enterprise_rules r
            LEFT JOIN enterprise_entitlements e ON e.id = r.entitlement_id
            WHERE r.organization_id = ? AND r.event_id = ? AND r.status = 'ACTIVE'
              AND (r.entitlement_id IS NULL OR e.entity_id = ?)
            """,
            (context.organization_id, context.event_id, entity_id),
        ).fetchall()
        results = []
        now = self._parse_time(context.timestamp)
        for row in rows:
            scope = self._json_loads(row["scope_json"])
            rule_type = str(row["rule_type"] or "").upper()
            passed = True
            reason = VALID
            if rule_type == "TIME_WINDOW":
                start = str(scope.get("starts_at") or row["valid_from"] or "")
                end = str(scope.get("ends_at") or row["valid_until"] or "")
                if start and now < self._parse_time(start):
                    passed, reason = False, "OUTSIDE_TIME_WINDOW"
                if end and now > self._parse_time(end):
                    passed, reason = False, "OUTSIDE_TIME_WINDOW"
            elif rule_type == "DOOR":
                allowed = {str(item) for item in scope.get("door_ids", [])}
                if allowed and str(context.door_id or "") not in allowed:
                    passed, reason = False, "WRONG_DOOR"
            elif rule_type == "ZONE":
                allowed = {str(item) for item in scope.get("zone_ids", [])}
                if allowed and str(context.zone_id or "") not in allowed:
                    passed, reason = False, "WRONG_ZONE"
            elif rule_type == "ACCREDITATION_STATE":
                allowed = {str(item).lower() for item in scope.get("statuses", ["active"])}
                acc = db.execute("SELECT status FROM accreditations WHERE id = ?", (self._credential_for_entity(db, context, entity_id) or 0,)).fetchone()
                if acc and str(acc["status"]).lower() not in allowed:
                    passed, reason = False, "INACTIVE_CREDENTIAL"
            results.append({"rule_id": int(row["id"]), "rule_type": rule_type, "passed": passed, "reason_code": reason})
            if not passed:
                return {"allowed": False, "reason_code": reason, "rules": results}
        return {"allowed": True, "reason_code": VALID, "rules": results}

    def _credential_for_entity(self, db, context: AccessStateContext, entity_id: int) -> int | None:
        row = db.execute(
            "SELECT accreditation_id FROM enterprise_credentials WHERE organization_id = ? AND event_id = ? AND entity_id = ? LIMIT 1",
            (context.organization_id, context.event_id, entity_id),
        ).fetchone()
        return int(row["accreditation_id"]) if row and row["accreditation_id"] is not None else None

    def _upsert_snapshot(self, db, context: AccessStateContext, decision: AccessStateDecision, access_event_id: int) -> None:
        now = self.now()
        row = db.execute(
            "SELECT id FROM enterprise_access_state_snapshots WHERE organization_id = ? AND event_id = ? AND entity_id = ?",
            (context.organization_id, context.event_id, decision.entity_id),
        ).fetchone()
        values = (
            decision.credential_id, decision.accreditation_id, decision.proposed_state, decision.proposed_zone_id,
            access_event_id, decision.decision, decision.reason_code, context.direction, context.door_id,
            context.device_id, decision.occurred_at or context.timestamp,
            self._next_allowed_at(decision.occurred_at or context.timestamp, context.cooldown_seconds),
            json.dumps({"source": context.source}, ensure_ascii=True, sort_keys=True), now,
        )
        if row:
            db.execute(
                """
                UPDATE enterprise_access_state_snapshots
                SET credential_id = ?, accreditation_id = ?, current_state = ?, current_zone_id = ?,
                    last_access_event_id = ?, last_decision = ?, last_reason_code = ?, last_direction = ?,
                    last_door_id = ?, last_device_id = ?, last_transition_at = ?, next_allowed_at = ?,
                    metadata_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (*values, row["id"]),
            )
        else:
            db.execute(
                """
                INSERT INTO enterprise_access_state_snapshots (
                    organization_id, event_id, entity_id, credential_id, accreditation_id, current_state, current_zone_id,
                    last_access_event_id, last_decision, last_reason_code, last_direction, last_door_id, last_device_id,
                    last_transition_at, next_allowed_at, metadata_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (context.organization_id, context.event_id, decision.entity_id, *values, now),
            )

    def _decision(self, context: AccessStateContext, decision: str, reason_code: str, credential=None, accreditation=None, previous_state: str = "OUTSIDE", current_zone_id: int | None = None) -> AccessStateDecision:
        return AccessStateDecision(
            decision=decision,
            reason_code=reason_code,
            previous_state=previous_state,
            proposed_state=previous_state,
            current_zone_id=current_zone_id,
            proposed_zone_id=current_zone_id,
            entity_id=int(credential["entity_id"]) if credential else None,
            credential_id=int(credential["id"]) if credential else None,
            accreditation_id=int(accreditation["id"]) if accreditation else (int(credential["accreditation_id"]) if credential and credential["accreditation_id"] is not None else None),
            door_id=context.door_id,
            zone_id=context.zone_id,
            device_id=context.device_id,
            direction=context.direction,
            correlation_id=context.correlation_id,
            idempotency_key=context.idempotency_key,
            occurred_at=context.timestamp,
        )

    def _deny(self, decision: AccessStateDecision, reason_code: str) -> AccessStateDecision:
        decision.decision = DENY
        decision.reason_code = reason_code if reason_code in REASON_CODES else "RULE_DENIED"
        decision.proposed_state = decision.previous_state
        decision.proposed_zone_id = decision.current_zone_id
        return decision

    def _record_domain_event(self, db, context: AccessStateContext, decision: AccessStateDecision, event_type: str, metadata: dict) -> None:
        self._record_domain_event_raw(db, context.organization_id, context.event_id, decision.entity_id, context.device_id, event_type, decision.correlation_id, f"{event_type}:{context.idempotency_key}" if context.idempotency_key else "", {**metadata, "reason_code": decision.reason_code})

    def _record_domain_event_raw(self, db, organization_id: int, event_id: int, entity_id: int | None, device_id: int | None, event_type: str, correlation_id: str, idempotency_key: str, metadata: dict) -> None:
        if self.enterprise_core:
            self.enterprise_core.record_domain_event(db, organization_id=organization_id, event_id=event_id, entity_id=entity_id, device_id=device_id, event_type=event_type, correlation_id=correlation_id, idempotency_key=idempotency_key, metadata=metadata)

    def _next_allowed_at(self, occurred_at: str, cooldown_seconds: int) -> str:
        if cooldown_seconds <= 0:
            return ""
        return (self._parse_time(occurred_at) + timedelta(seconds=cooldown_seconds)).isoformat()

    def _activity_open_at(self, activity) -> datetime:
        raw_activity_minutes = activity["access_open_minutes_before"]
        raw_event_minutes = activity["event_access_open_minutes_before"]
        minutes = raw_activity_minutes if raw_activity_minutes is not None and str(raw_activity_minutes) != "" else raw_event_minutes
        minutes = max(0, int(minutes if minutes is not None else 10))
        return self._parse_time(str(activity["starts_at"])) - timedelta(minutes=minutes)

    def _parse_time(self, value: str) -> datetime:
        text = str(value or self.now()).replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        return dt.replace(tzinfo=None) if dt.tzinfo else dt

    def _json_loads(self, value: str) -> dict:
        try:
            parsed = json.loads(value or "{}")
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}

    def _clean_key(self, value: str, limit: int) -> str:
        return re.sub(r"[^A-Za-z0-9_.:-]+", "_", str(value or "").strip()).strip("_")[:limit]

    def _correlation_id(self) -> str:
        return f"v5-{uuid.uuid4().hex}"
