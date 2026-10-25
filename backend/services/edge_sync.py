from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import secrets
import uuid
from typing import Any

from backend.services.access_state_engine import AccessStateContext, AccessStateEngine


DEVICE_TYPES = {"ACCESS_TERMINAL", "RECEPTION_TERMINAL", "KIOSK", "HANDHELD", "EDGE_NODE", "PRINTER", "SCANNER", "TURNSTILE", "CAMERA", "NFC_READER", "RFID_READER"}
DEVICE_STATUSES = {"PROVISIONED", "ACTIVE", "SUSPENDED", "REVOKED"}
CAPABILITIES = {"VALIDATE_ACCESS", "ENTRY", "EXIT", "CHECK_IN", "CHECK_OUT", "SCAN_QR", "PRINT_BADGE", "REGISTER", "VIEW_PARTICIPANT", "CONSUME_ENTITLEMENT", "SYNC_DATASET", "CREDENTIAL_LOOKUP", "ENTITLEMENT_LOOKUP", "VALIDATE_VEHICLE", "VEHICLE_ENTRY", "VEHICLE_EXIT", "CAPTURE_LEAD"}
CONFLICTS = {"NO_CONFLICT", "DUPLICATE", "STALE_DATASET", "REVOCATION_CONFLICT", "ANTI_PASSBACK_CONFLICT", "STATE_CONFLICT", "RULE_CONFLICT", "UNKNOWN_CREDENTIAL", "DEVICE_REVOKED", "EVENT_SCOPE_ERROR"}


@dataclass
class DeviceAuth:
    ok: bool
    device: dict | None = None
    error: str = ""


class DeviceEdgeSyncService:
    def __init__(self, access_engine: AccessStateEngine, enterprise_core=None, now=None) -> None:
        self.access_engine = access_engine
        self.enterprise_core = enterprise_core
        self.now = now or (lambda: datetime.utcnow().replace(microsecond=0).isoformat())

    def provision_device(self, db, *, organization_id: int, event_id: int, device_type: str, display_name: str, capabilities: list[str], software_version: str = "", actor: str = "") -> dict:
        self._validate_event(db, organization_id, event_id)
        device_type = self._choice(device_type, DEVICE_TYPES, "DEVICE_TYPE_INVALID")
        caps = sorted({self._choice(item, CAPABILITIES, "DEVICE_CAPABILITY_INVALID") for item in capabilities})
        secret = f"dev_{secrets.token_urlsafe(32)}"
        now = self.now()
        cur = db.execute(
            """
            INSERT INTO enterprise_devices (
                organization_id, event_id, device_uid, device_type, display_name, status,
                capabilities_json, credential_hash, credential_hint, credential_rotated_at,
                last_seen_at, version, dataset_revision, sync_state, metadata_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 'PROVISIONED', ?, ?, ?, ?, '', ?, '', 'NOT_CONFIGURED', '{}', ?, ?)
            """,
            (organization_id, event_id, f"dev-{uuid.uuid4().hex}", device_type, display_name[:160], json.dumps(caps), self._hash(secret), secret[:12], now, software_version[:80], now, now),
        )
        device_id = int(cur.lastrowid)
        self._domain(db, organization_id, event_id, device_id, "DEVICE_PROVISIONED", {"device_type": device_type, "capabilities": caps, "actor": actor})
        return {"ok": True, "device": dict(db.execute("SELECT * FROM enterprise_devices WHERE id = ?", (device_id,)).fetchone()), "secret": secret}

    def activate_device(self, db, *, organization_id: int, event_id: int, device_id: int, actor: str = "") -> dict:
        device = self._device(db, organization_id, event_id, device_id)
        now = self.now()
        db.execute("UPDATE enterprise_devices SET status = 'ACTIVE', updated_at = ? WHERE id = ?", (now, device_id))
        self._domain(db, organization_id, event_id, device_id, "DEVICE_ACTIVATED", {"actor": actor})
        return {"ok": True, "device": dict(db.execute("SELECT * FROM enterprise_devices WHERE id = ?", (device_id,)).fetchone())}

    def rotate_credential(self, db, *, organization_id: int, event_id: int, device_id: int, actor: str = "") -> dict:
        self._device(db, organization_id, event_id, device_id)
        secret = f"dev_{secrets.token_urlsafe(32)}"
        now = self.now()
        db.execute("UPDATE enterprise_devices SET credential_hash = ?, credential_hint = ?, credential_rotated_at = ?, updated_at = ? WHERE id = ?", (self._hash(secret), secret[:12], now, now, device_id))
        self._domain(db, organization_id, event_id, device_id, "DEVICE_CREDENTIAL_ROTATED", {"actor": actor})
        return {"ok": True, "secret": secret}

    def revoke_device(self, db, *, organization_id: int, event_id: int, device_id: int, reason: str = "", actor: str = "") -> dict:
        self._device(db, organization_id, event_id, device_id)
        now = self.now()
        db.execute("UPDATE enterprise_devices SET status = 'REVOKED', revoked_at = ?, revoked_reason = ?, updated_at = ? WHERE id = ?", (now, reason[:240], now, device_id))
        self._domain(db, organization_id, event_id, device_id, "DEVICE_REVOKED", {"actor": actor, "reason": reason[:240]})
        return {"ok": True}

    def authenticate_device(self, db, *, organization_id: int, event_id: int, device_id: int, secret: str, capability: str = "") -> DeviceAuth:
        row = db.execute("SELECT * FROM enterprise_devices WHERE id = ? AND organization_id = ? AND event_id = ?", (device_id, organization_id, event_id)).fetchone()
        if not row:
            return DeviceAuth(False, error="DEVICE_NOT_FOUND")
        if row["status"] == "REVOKED":
            return DeviceAuth(False, error="DEVICE_REVOKED")
        if row["status"] not in {"ACTIVE", "PROVISIONED"}:
            return DeviceAuth(False, error="DEVICE_INACTIVE")
        if row["credential_hash"] != self._hash(secret):
            return DeviceAuth(False, error="INVALID_DEVICE_SECRET")
        caps = set(json.loads(row["capabilities_json"] or "[]"))
        if capability and capability not in caps:
            return DeviceAuth(False, error="CAPABILITY_DENIED")
        return DeviceAuth(True, device=dict(row))

    def generate_dataset(self, db, *, organization_id: int, event_id: int, dataset_type: str = "ACCESS_FULL", generated_by: str = "") -> dict:
        self._validate_event(db, organization_id, event_id)
        credentials = [
            {"credential_id": int(r["id"]), "entity_id": int(r["entity_id"]), "accreditation_id": r["accreditation_id"], "status": r["status"], "token_hash": r["legacy_token_hash"], "token_hint": r["token_hint"]}
            for r in db.execute("SELECT * FROM enterprise_credentials WHERE organization_id = ? AND event_id = ? AND status IN ('ACTIVE','REVOKED','INACTIVE') ORDER BY id", (organization_id, event_id)).fetchall()
        ]
        payload = {
            "event": dict(db.execute("SELECT id, organization_id, name, starts_at, ends_at FROM events WHERE id = ? AND organization_id = ?", (event_id, organization_id)).fetchone()),
            "credentials": credentials,
            "revocations": [dict(r) for r in db.execute("SELECT credential_id, reason_code, revoked_at FROM enterprise_credential_revocations WHERE organization_id = ? AND event_id = ? AND status = 'ACTIVE'", (organization_id, event_id)).fetchall()],
            "doors": [dict(r) for r in db.execute("SELECT id, code, name, zone_id, status FROM enterprise_doors WHERE organization_id = ? AND event_id = ? ORDER BY id", (organization_id, event_id)).fetchall()],
            "zones": [dict(r) for r in db.execute("SELECT id, name, code, status FROM event_zones WHERE organization_id = ? AND event_id = ? ORDER BY id", (organization_id, event_id)).fetchall()],
            "entitlements": [dict(r) for r in db.execute("SELECT id, entity_id, entitlement_type, scope_type, scope_id, allocated, consumed, consumable, status, valid_from, valid_until FROM enterprise_entitlements WHERE organization_id = ? AND event_id = ? ORDER BY id", (organization_id, event_id)).fetchall()],
            "entitlement_types": [dict(r) for r in db.execute("SELECT code, consumable, default_quantity, offline_policy, status FROM enterprise_entitlement_types WHERE organization_id = ? AND event_id = ? AND status = 'ACTIVE' ORDER BY code", (organization_id, event_id)).fetchall()] if self._table_exists(db, "enterprise_entitlement_types") else [],
            "service_points": [dict(r) for r in db.execute("SELECT id, code, name, service_type, zone_id, device_id, status FROM enterprise_service_points WHERE organization_id = ? AND event_id = ? AND status = 'ACTIVE' ORDER BY id", (organization_id, event_id)).fetchall()] if self._table_exists(db, "enterprise_service_points") else [],
            "rules": [dict(r) for r in db.execute("SELECT id, entitlement_id, rule_type, scope_json, status, valid_from, valid_until FROM enterprise_rules WHERE organization_id = ? AND event_id = ? ORDER BY id", (organization_id, event_id)).fetchall()],
            "config": {"stale_policy": "FAIL_CLOSED", "schema_version": "v5.2", "data_minimization": "ACCESS_ONLY"},
        }
        encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True)
        checksum = self._hash(encoded)
        revision = f"event-{event_id}-{checksum[:16]}"
        now = self.now()
        db.execute("UPDATE enterprise_event_datasets SET status = 'STALE' WHERE organization_id = ? AND event_id = ? AND status = 'CURRENT'", (organization_id, event_id))
        cur = db.execute(
            "INSERT INTO enterprise_event_datasets (organization_id, event_id, revision, dataset_type, schema_version, checksum, status, generated_at, generated_by, payload_json, metadata_json, created_at) VALUES (?, ?, ?, ?, 'v5.2', ?, 'CURRENT', ?, ?, ?, '{}', ?)",
            (organization_id, event_id, revision, dataset_type, checksum, now, generated_by, encoded, now),
        )
        self._domain(db, organization_id, event_id, None, "DATASET_GENERATED", {"revision": revision, "checksum": checksum, "dataset_type": dataset_type})
        return {"ok": True, "dataset": dict(db.execute("SELECT * FROM enterprise_event_datasets WHERE id = ?", (int(cur.lastrowid),)).fetchone()), "payload": payload}

    def dataset_status(self, db, *, organization_id: int, event_id: int, revision: str) -> str:
        row = db.execute("SELECT status FROM enterprise_event_datasets WHERE organization_id = ? AND event_id = ? AND revision = ?", (organization_id, event_id, revision)).fetchone()
        return str(row["status"]) if row else "UNKNOWN"

    def queue_operation(self, db, *, organization_id: int, event_id: int, device_id: int, operation_type: str, payload: dict, local_decision: dict, dataset_revision: str, device_sequence: int, occurred_at: str = "", correlation_id: str = "", idempotency_key: str = "") -> dict:
        self._device(db, organization_id, event_id, device_id)
        now = self.now()
        operation_id = str(payload.get("operation_id") or f"op-{uuid.uuid4().hex}")
        correlation_id = correlation_id or f"edge-{uuid.uuid4().hex}"
        idempotency_key = idempotency_key or f"{device_id}:{operation_id}"
        row = db.execute("SELECT * FROM enterprise_edge_queue WHERE organization_id = ? AND idempotency_key = ?", (organization_id, idempotency_key)).fetchone()
        if row:
            return {"ok": True, "duplicate": True, "item": dict(row)}
        cur = db.execute(
            """
            INSERT INTO enterprise_edge_queue (
                organization_id, event_id, device_id, operation_id, idempotency_key, correlation_id, device_sequence,
                operation_type, payload_json, local_decision_json, dataset_revision, device_occurred_at,
                queued_at, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', ?, ?)
            """,
            (organization_id, event_id, device_id, operation_id, idempotency_key, correlation_id, int(device_sequence), operation_type, json.dumps(payload, sort_keys=True), json.dumps(local_decision, sort_keys=True), dataset_revision, occurred_at or now, now, now, now),
        )
        self._domain(db, organization_id, event_id, device_id, "EDGE_OPERATION_QUEUED", {"operation_id": operation_id, "operation_type": operation_type})
        return {"ok": True, "item": dict(db.execute("SELECT * FROM enterprise_edge_queue WHERE id = ?", (int(cur.lastrowid),)).fetchone())}

    def local_access_decision(self, dataset: dict, *, token_hash: str, direction: str = "ENTRY") -> dict:
        credential = next((item for item in dataset.get("credentials", []) if item.get("token_hash") == token_hash), None)
        if not credential:
            return {"decision": "DENY", "reason_code": "UNKNOWN_CREDENTIAL"}
        if credential.get("status") != "ACTIVE":
            return {"decision": "DENY", "reason_code": "INACTIVE_CREDENTIAL"}
        if any(int(r.get("credential_id") or 0) == int(credential["credential_id"]) for r in dataset.get("revocations", [])):
            return {"decision": "DENY", "reason_code": "REVOKED"}
        return {"decision": "ALLOW", "reason_code": "VALID", "direction": direction, "credential_id": credential["credential_id"]}

    def sync_batch(self, db, *, organization_id: int, event_id: int, device_id: int, secret: str, operations: list[dict]) -> dict:
        auth = self.authenticate_device(db, organization_id=organization_id, event_id=event_id, device_id=device_id, secret=secret, capability="SYNC_DATASET")
        if not auth.ok:
            return {"ok": False, "error": auth.error, "results": []}
        self._touch_device(db, organization_id, event_id, device_id, auth.device)
        results = []
        for operation in operations:
            results.append(self._reconcile_one(db, organization_id, event_id, device_id, operation))
        return {"ok": True, "results": results}

    def heartbeat(self, db, *, organization_id: int, event_id: int, device_id: int, secret: str, dataset_revision: str, queue_depth: int, sync_status: str, software_version: str = "", device_timestamp: str = "") -> dict:
        auth = self.authenticate_device(db, organization_id=organization_id, event_id=event_id, device_id=device_id, secret=secret)
        if not auth.ok:
            return {"ok": False, "error": auth.error}
        now = self.now()
        skew = self._clock_skew(device_timestamp, now)
        db.execute(
            "INSERT INTO enterprise_device_heartbeats (organization_id, event_id, device_id, software_version, dataset_revision, queue_depth, sync_status, clock_skew_seconds, received_at, metadata_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '{}', ?)",
            (organization_id, event_id, device_id, software_version[:80], dataset_revision, int(queue_depth), sync_status[:80], skew, now, now),
        )
        db.execute("UPDATE enterprise_devices SET last_seen_at = ?, version = COALESCE(NULLIF(?, ''), version), dataset_revision = ?, sync_state = ?, updated_at = ? WHERE id = ?", (now, software_version[:80], dataset_revision, sync_status[:80], now, device_id))
        return {"ok": True, "clock_skew_seconds": skew}

    def telemetry(self, db, *, organization_id: int, event_id: int) -> dict:
        def count(sql, params):
            return int(db.execute(sql, params).fetchone()["c"] or 0)
        p = (organization_id, event_id)
        oldest = db.execute("SELECT queued_at FROM enterprise_edge_queue WHERE organization_id = ? AND event_id = ? AND status IN ('PENDING','RETRY') ORDER BY queued_at LIMIT 1", p).fetchone()
        return {
            "devices_active": count("SELECT COUNT(*) AS c FROM enterprise_devices WHERE organization_id = ? AND event_id = ? AND status = 'ACTIVE'", p),
            "devices_revoked": count("SELECT COUNT(*) AS c FROM enterprise_devices WHERE organization_id = ? AND event_id = ? AND status = 'REVOKED'", p),
            "queue_depth": count("SELECT COUNT(*) AS c FROM enterprise_edge_queue WHERE organization_id = ? AND event_id = ? AND status IN ('PENDING','RETRY')", p),
            "oldest_pending_operation": oldest["queued_at"] if oldest else "",
            "sync_successes": count("SELECT COUNT(*) AS c FROM enterprise_edge_queue WHERE organization_id = ? AND event_id = ? AND status = 'ACKNOWLEDGED'", p),
            "sync_failures": count("SELECT COUNT(*) AS c FROM enterprise_edge_queue WHERE organization_id = ? AND event_id = ? AND status IN ('REJECTED','CONFLICT')", p),
            "conflicts": count("SELECT COUNT(*) AS c FROM enterprise_edge_reconciliations WHERE organization_id = ? AND event_id = ? AND conflict_type <> 'NO_CONFLICT'", p),
            "duplicate_suppressions": count("SELECT COUNT(*) AS c FROM enterprise_edge_reconciliations WHERE organization_id = ? AND event_id = ? AND conflict_type = 'DUPLICATE'", p),
        }

    def bootstrap_access_state_from_v4(self, db, *, organization_id: int, event_id: int, actor: str = "v5.2-bootstrap") -> dict:
        now = self.now()
        created = 0
        for row in db.execute(
            """
            SELECT ec.entity_id, ec.id AS credential_id, a.id AS accreditation_id, a.checked_in_at
            FROM enterprise_credentials ec
            JOIN accreditations a ON a.id = ec.accreditation_id
            WHERE ec.organization_id = ? AND ec.event_id = ? AND a.checked_in_at IS NOT NULL AND a.checked_in_at <> ''
            """,
            (organization_id, event_id),
        ).fetchall():
            existing = db.execute("SELECT id FROM enterprise_access_state_snapshots WHERE organization_id = ? AND event_id = ? AND entity_id = ?", (organization_id, event_id, row["entity_id"])).fetchone()
            if existing:
                continue
            db.execute(
                """
                INSERT INTO enterprise_access_state_snapshots (
                    organization_id, event_id, entity_id, credential_id, accreditation_id, current_state, current_zone_id,
                    last_decision, last_reason_code, last_direction, last_transition_at, metadata_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'INSIDE', NULL, 'ALLOW', 'VALID', 'ENTRY', ?, ?, ?, ?)
                """,
                (organization_id, event_id, row["entity_id"], row["credential_id"], row["accreditation_id"], row["checked_in_at"], json.dumps({"source": "V4_CHECKED_IN_BOOTSTRAP", "actor": actor}), now, now),
            )
            created += 1
        return {"ok": True, "created": created}

    def _reconcile_one(self, db, organization_id: int, event_id: int, device_id: int, operation: dict) -> dict:
        idem = str(operation.get("idempotency_key") or "")
        existing = db.execute("SELECT * FROM enterprise_edge_queue WHERE organization_id = ? AND idempotency_key = ?", (organization_id, idem)).fetchone() if idem else None
        if existing and existing["status"] == "ACKNOWLEDGED":
            return self._reconciliation_payload(db, organization_id, event_id, device_id, dict(existing), "DUPLICATE", "ACKNOWLEDGED")
        queued = self.queue_operation(db, organization_id=organization_id, event_id=event_id, device_id=device_id, operation_type=str(operation.get("operation_type") or "ACCESS_ATTEMPT"), payload=operation.get("payload") or {}, local_decision=operation.get("local_decision") or {}, dataset_revision=str(operation.get("dataset_revision") or ""), device_sequence=int(operation.get("device_sequence") or 0), occurred_at=str(operation.get("occurred_at") or ""), correlation_id=str(operation.get("correlation_id") or ""), idempotency_key=idem)
        item = queued["item"]
        dataset_status = self.dataset_status(db, organization_id=organization_id, event_id=event_id, revision=item["dataset_revision"])
        payload = json.loads(item["payload_json"] or "{}")
        token = str(payload.get("token") or "")
        local = json.loads(item["local_decision_json"] or "{}")
        conflict = "NO_CONFLICT"
        status = "ACKNOWLEDGED"
        if dataset_status != "CURRENT":
            conflict, status = "STALE_DATASET", "CONFLICT"
        else:
            server_decision = self.access_engine.evaluate(db, AccessStateContext(organization_id=organization_id, event_id=event_id, token=token, direction=str(payload.get("direction") or "ENTRY"), device_id=device_id, correlation_id=item["correlation_id"], idempotency_key=item["idempotency_key"]))
            if server_decision.reason_code == "UNKNOWN_CREDENTIAL":
                conflict, status = "UNKNOWN_CREDENTIAL", "REJECTED"
            elif server_decision.reason_code == "REVOKED":
                conflict, status = "REVOCATION_CONFLICT", "CONFLICT"
            elif server_decision.reason_code == "ANTI_PASSBACK":
                conflict, status = "ANTI_PASSBACK_CONFLICT", "CONFLICT"
            elif local.get("decision") and local.get("decision") != server_decision.decision:
                conflict, status = "STATE_CONFLICT", "CONFLICT"
            if status == "ACKNOWLEDGED":
                event = self.access_engine.record_access_event(db, AccessStateContext(organization_id=organization_id, event_id=event_id, token=token, direction=str(payload.get("direction") or "ENTRY"), device_id=device_id, correlation_id=item["correlation_id"], idempotency_key=item["idempotency_key"], source="edge.sync"), server_decision)
                server_result = {"decision": server_decision.decision, "reason_code": server_decision.reason_code, "access_event_id": event["id"]}
            else:
                server_result = {"decision": server_decision.decision if 'server_decision' in locals() else "DENY", "reason_code": server_decision.reason_code if 'server_decision' in locals() else conflict}
            db.execute("UPDATE enterprise_edge_queue SET status = ?, server_received_at = ?, server_result_json = ?, updated_at = ? WHERE id = ?", (status, self.now(), json.dumps(server_result, sort_keys=True), self.now(), item["id"]))
        return self._reconciliation_payload(db, organization_id, event_id, device_id, item, conflict, status)

    def _reconciliation_payload(self, db, organization_id: int, event_id: int, device_id: int, item: dict, conflict: str, status: str) -> dict:
        conflict = conflict if conflict in CONFLICTS else "STATE_CONFLICT"
        now = self.now()
        local = json.loads(item.get("local_decision_json") or "{}")
        server_result = json.loads(item.get("server_result_json") or "{}")
        skew = self._clock_skew(item.get("device_occurred_at") or "", now)
        db.execute(
            "INSERT INTO enterprise_edge_reconciliations (organization_id, event_id, device_id, queue_id, operation_id, local_decision, server_decision, conflict_type, resolution, correlation_id, idempotency_key, dataset_revision, device_sequence, clock_skew_seconds, metadata_json, reconciled_at, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '{}', ?, ?)",
            (organization_id, event_id, device_id, item.get("id"), item.get("operation_id", ""), local.get("decision", ""), server_result.get("decision", ""), conflict, status, item.get("correlation_id", ""), item.get("idempotency_key", ""), item.get("dataset_revision", ""), int(item.get("device_sequence") or 0), skew, now, now),
        )
        if conflict != "NO_CONFLICT":
            self._domain(db, organization_id, event_id, device_id, "EDGE_CONFLICT_DETECTED", {"conflict_type": conflict, "operation_id": item.get("operation_id")})
        else:
            self._domain(db, organization_id, event_id, device_id, "EDGE_OPERATION_RECONCILED", {"operation_id": item.get("operation_id")})
        return {"operation_id": item.get("operation_id"), "status": status, "conflict_type": conflict}

    def _touch_device(self, db, organization_id, event_id, device_id, device):
        now = self.now()
        db.execute("UPDATE enterprise_devices SET last_seen_at = ?, updated_at = ? WHERE id = ? AND organization_id = ? AND event_id = ?", (now, now, device_id, organization_id, event_id))

    def _device(self, db, organization_id: int, event_id: int, device_id: int):
        row = db.execute("SELECT * FROM enterprise_devices WHERE id = ? AND organization_id = ? AND event_id = ?", (device_id, organization_id, event_id)).fetchone()
        if not row:
            raise ValueError("DEVICE_SCOPE_ERROR")
        return row

    def _validate_event(self, db, organization_id: int, event_id: int) -> None:
        row = db.execute("SELECT id FROM events WHERE id = ? AND organization_id = ?", (event_id, organization_id)).fetchone()
        if not row:
            raise ValueError("EVENT_SCOPE_ERROR")

    def _choice(self, value: str, allowed: set[str], code: str) -> str:
        normalized = str(value or "").strip().upper()
        if normalized not in allowed:
            raise ValueError(code)
        return normalized

    def _clock_skew(self, device_time: str, server_time: str) -> int:
        if not device_time:
            return 0
        try:
            return int((datetime.fromisoformat(server_time.replace("Z", "+00:00")).replace(tzinfo=None) - datetime.fromisoformat(device_time.replace("Z", "+00:00")).replace(tzinfo=None)).total_seconds())
        except ValueError:
            return 0

    def _domain(self, db, organization_id: int, event_id: int, device_id: int | None, event_type: str, metadata: dict) -> None:
        if self.enterprise_core:
            self.enterprise_core.record_domain_event(db, organization_id=organization_id, event_id=event_id, device_id=device_id, event_type=event_type, correlation_id=f"edge-{uuid.uuid4().hex}", metadata=metadata)

    def _table_exists(self, db, name: str) -> bool:
        try:
            return bool(db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name = ?", (name,)).fetchone())
        except Exception:
            return bool(db.execute("SELECT table_name AS name FROM information_schema.tables WHERE table_schema = 'public' AND table_name = ?", (name,)).fetchone())

    def _hash(self, value: str) -> str:
        return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()
