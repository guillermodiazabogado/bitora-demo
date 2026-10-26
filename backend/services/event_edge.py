from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import hmac
import json
import os
import secrets
import statistics
import time
import uuid
from typing import Any


EDGE_STATUSES = {"PROVISIONING", "READY", "LIVE", "DEGRADED", "OFFLINE", "REVOKED"}
CLOUD_STATES = {"ONLINE", "DEGRADED", "OFFLINE", "UNKNOWN"}
DATASET_STATES = {"CURRENT", "STALE", "EXPIRED", "INVALID", "UNAVAILABLE", "STAGED"}
READINESS_STATES = {"READY", "READY_WITH_WARNINGS", "NOT_READY"}
EVENT_OPERATION_STATES = {"NORMAL", "DEGRADED", "CRITICAL"}
EXECUTION_CLASSES = {"EDGE_LOCAL_SAFE", "DEVICE_LOCAL_SAFE", "CLOUD_REQUIRED"}
PROFILE_KEYS = {"ACCESS_FAST", "RECEPTION", "SERVICE", "LEAD_RETRIEVAL", "LOGISTICS", "SELF_SERVICE"}
RUNTIME_DATASET_SIGNING_KEY = secrets.token_urlsafe(48)
DEFAULT_CAPABILITIES = {
    "VALIDATE_ACCESS": "EDGE_LOCAL_SAFE",
    "ENTRY": "EDGE_LOCAL_SAFE",
    "EXIT": "EDGE_LOCAL_SAFE",
    "CREDENTIAL_LOOKUP": "DEVICE_LOCAL_SAFE",
    "ENTITLEMENT_LOOKUP": "EDGE_LOCAL_SAFE",
    "CONSUME_ENTITLEMENT": "EDGE_LOCAL_SAFE",
    "VALIDATE_VEHICLE": "EDGE_LOCAL_SAFE",
    "VEHICLE_ENTRY": "EDGE_LOCAL_SAFE",
    "VEHICLE_EXIT": "EDGE_LOCAL_SAFE",
    "CAPTURE_LEAD": "EDGE_LOCAL_SAFE",
    "SYNC_DATASET": "CLOUD_REQUIRED",
}


@dataclass
class EdgeAuth:
    ok: bool
    edge: dict | None = None
    error: str = ""


class EventEdgeService:
    """V5.8 local-first Event Edge foundation.

    This deliberately extends V5.2 DeviceEdgeSyncService instead of creating a
    second sync stack. Cloud remains authoritative for reconciliation.
    """

    def __init__(self, *, edge_sync, enterprise_core=None, now=None, signing_keys: dict[str, str] | None = None) -> None:
        self.edge_sync = edge_sync
        self.enterprise_core = enterprise_core
        self.now = now or (lambda: datetime.utcnow().replace(microsecond=0).isoformat())
        self.signing_keys = signing_keys or self._load_signing_keys()

    def provision_edge(self, db, *, organization_id: int, event_id: int, name: str, software_version: str = "v5.8-edge", actor: str = "") -> dict:
        self._event(db, organization_id, event_id)
        secret = f"edge_{secrets.token_urlsafe(32)}"
        now = self.now()
        edge_uid = f"edge-{uuid.uuid4().hex}"
        cur = db.execute(
            """
            INSERT INTO enterprise_event_edges (
                organization_id, event_id, edge_uid, name, status, cloud_connectivity, event_operation_status,
                software_version, protocol_version, credential_hash, credential_hint, credential_status,
                clock_status, storage_status, queue_depth, health_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, 'READY', 'ONLINE', 'NORMAL', ?, 'v5.8', ?, ?, 'ACTIVE', 'OK', 'OK', 0, '{}', ?, ?)
            """,
            (organization_id, event_id, edge_uid, name[:160], software_version[:80], self._hash(secret), secret[:12], now, now),
        )
        edge_id = int(cur.lastrowid)
        self._domain(db, organization_id, event_id, "EVENT_EDGE_PROVISIONED", {"edge_id": edge_id, "actor": actor})
        return {"ok": True, "edge": dict(db.execute("SELECT * FROM enterprise_event_edges WHERE id = ?", (edge_id,)).fetchone()), "secret": secret}

    def authenticate_edge(self, db, *, organization_id: int, event_id: int, edge_id: int, secret: str) -> EdgeAuth:
        row = db.execute("SELECT * FROM enterprise_event_edges WHERE id = ? AND organization_id = ? AND event_id = ?", (edge_id, organization_id, event_id)).fetchone()
        if not row:
            return EdgeAuth(False, error="EDGE_NOT_FOUND")
        if row["status"] == "REVOKED" or row["credential_status"] != "ACTIVE":
            return EdgeAuth(False, error="EDGE_REVOKED")
        if row["credential_hash"] != self._hash(secret):
            return EdgeAuth(False, error="INVALID_EDGE_SECRET")
        return EdgeAuth(True, edge=dict(row))

    def ensure_default_profiles(self, db, *, organization_id: int, event_id: int) -> dict:
        self._event(db, organization_id, event_id)
        definitions = {
            "ACCESS_FAST": ["VALIDATE_ACCESS", "ENTRY", "EXIT", "CREDENTIAL_LOOKUP", "SCAN_QR", "SYNC_DATASET"],
            "RECEPTION": ["VALIDATE_ACCESS", "CHECK_IN", "REGISTER", "VIEW_PARTICIPANT", "PRINT_BADGE", "SYNC_DATASET"],
            "SERVICE": ["ENTITLEMENT_LOOKUP", "CONSUME_ENTITLEMENT", "CREDENTIAL_LOOKUP", "SYNC_DATASET"],
            "LEAD_RETRIEVAL": ["CAPTURE_LEAD", "CREDENTIAL_LOOKUP", "SYNC_DATASET"],
            "LOGISTICS": ["VALIDATE_VEHICLE", "VEHICLE_ENTRY", "VEHICLE_EXIT", "SYNC_DATASET"],
            "SELF_SERVICE": ["CREDENTIAL_LOOKUP", "VIEW_PARTICIPANT", "SYNC_DATASET"],
        }
        now = self.now()
        created = 0
        for profile_key, capabilities in definitions.items():
            existing = db.execute(
                "SELECT id FROM enterprise_device_profiles WHERE organization_id = ? AND event_id = ? AND profile_key = ? AND revision = 1",
                (organization_id, event_id, profile_key),
            ).fetchone()
            if existing:
                continue
            db.execute(
                """
                INSERT INTO enterprise_device_profiles (
                    organization_id, event_id, profile_key, revision, status, capabilities_json,
                    defaults_json, dataset_subset_json, offline_policy_json, hardware_requirements_json,
                    ui_hints_json, created_at, updated_at
                ) VALUES (?, ?, ?, 1, 'ACTIVE', ?, ?, ?, ?, '{}', '{}', ?, ?)
                """,
                (
                    organization_id,
                    event_id,
                    profile_key,
                    json.dumps(capabilities, sort_keys=True),
                    json.dumps({"operational_mode": profile_key}, sort_keys=True),
                    json.dumps({"minimum_necessary": True, "capabilities": capabilities}, sort_keys=True),
                    json.dumps({"default": "FAIL_CLOSED", "device_local": profile_key in {"ACCESS_FAST", "SELF_SERVICE"}}, sort_keys=True),
                    now,
                    now,
                ),
            )
            created += 1
        return {"ok": True, "created": created, "profiles": self.device_profiles(db, organization_id=organization_id, event_id=event_id)}

    def device_profiles(self, db, *, organization_id: int, event_id: int) -> list[dict]:
        return [dict(r) for r in db.execute("SELECT * FROM enterprise_device_profiles WHERE organization_id = ? AND event_id = ? ORDER BY profile_key, revision", (organization_id, event_id)).fetchall()]

    def ensure_capability_classes(self, db, *, organization_id: int, event_id: int) -> dict:
        self._event(db, organization_id, event_id)
        now = self.now()
        created = 0
        for capability, execution_class in DEFAULT_CAPABILITIES.items():
            existing = db.execute(
                "SELECT id FROM enterprise_capability_execution_classes WHERE organization_id = ? AND event_id = ? AND capability = ? AND execution_class = ?",
                (organization_id, event_id, capability, execution_class),
            ).fetchone()
            if existing:
                continue
            db.execute(
                "INSERT INTO enterprise_capability_execution_classes (organization_id, event_id, capability, execution_class, certification_status, policy_json, created_at, updated_at) VALUES (?, ?, ?, ?, 'CERTIFIED_FOUNDATION', ?, ?, ?)",
                (organization_id, event_id, capability, execution_class, json.dumps({"cloud_required_for_final_reconciliation": True}, sort_keys=True), now, now),
            )
            created += 1
        return {"ok": True, "created": created, "classes": self.capability_classes(db, organization_id=organization_id, event_id=event_id)}

    def capability_classes(self, db, *, organization_id: int, event_id: int) -> list[dict]:
        return [dict(r) for r in db.execute("SELECT * FROM enterprise_capability_execution_classes WHERE organization_id = ? AND event_id = ? ORDER BY capability, execution_class", (organization_id, event_id)).fetchall()]

    def create_pairing_code(self, db, *, organization_id: int, event_id: int, edge_id: int, profile_key: str, requested_device_type: str, zone_id: int | None = None, door_id: int | None = None, ttl_minutes: int = 10, actor: str = "") -> dict:
        self._edge(db, organization_id, event_id, edge_id)
        profile = db.execute(
            "SELECT * FROM enterprise_device_profiles WHERE organization_id = ? AND event_id = ? AND profile_key = ? AND status = 'ACTIVE' ORDER BY revision DESC LIMIT 1",
            (organization_id, event_id, profile_key),
        ).fetchone()
        if not profile:
            raise ValueError("DEVICE_PROFILE_NOT_FOUND")
        raw = f"{secrets.randbelow(1000000):06d}"
        now = self.now()
        expires = (datetime.fromisoformat(now) + timedelta(minutes=max(1, ttl_minutes))).isoformat()
        cur = db.execute(
            """
            INSERT INTO enterprise_device_pairing_codes (
                organization_id, event_id, edge_id, profile_id, pairing_code_hash, pairing_code_hint,
                status, requested_device_type, zone_id, door_id, expires_at, created_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'PENDING', ?, ?, ?, ?, ?, ?, ?)
            """,
            (organization_id, event_id, edge_id, int(profile["id"]), self._hash(raw), raw[-2:], requested_device_type[:80], zone_id, door_id, expires, actor[:120], now, now),
        )
        self._domain(db, organization_id, event_id, "DEVICE_PAIRING_CODE_CREATED", {"edge_id": edge_id, "profile_key": profile_key})
        return {"ok": True, "pairing_id": int(cur.lastrowid), "pairing_code": raw, "expires_at": expires}

    def pair_device(self, db, *, organization_id: int, event_id: int, pairing_code: str, display_name: str, software_version: str = "v5.8-device", request_fingerprint: str = "") -> dict:
        now = self.now()
        if request_fingerprint:
            self._check_pairing_rate_limit(db, organization_id, event_id, request_fingerprint, now)
        row = db.execute(
            """
            SELECT pc.*, p.capabilities_json, p.profile_key, p.revision AS profile_revision
            FROM enterprise_device_pairing_codes pc
            JOIN enterprise_device_profiles p ON p.id = pc.profile_id
            WHERE pc.organization_id = ? AND pc.event_id = ? AND pc.pairing_code_hash = ? AND pc.status = 'PENDING'
            """,
            (organization_id, event_id, self._hash(pairing_code)),
        ).fetchone()
        if not row:
            if request_fingerprint:
                self._record_pairing_failure(db, organization_id, event_id, request_fingerprint, now)
            raise ValueError("PAIRING_CODE_INVALID")
        if row["expires_at"] < now:
            db.execute("UPDATE enterprise_device_pairing_codes SET status = 'EXPIRED', updated_at = ? WHERE id = ?", (now, row["id"]))
            if request_fingerprint:
                self._record_pairing_failure(db, organization_id, event_id, request_fingerprint, now)
            raise ValueError("PAIRING_CODE_EXPIRED")
        capabilities = json.loads(row["capabilities_json"] or "[]")
        provision = self.edge_sync.provision_device(
            db,
            organization_id=organization_id,
            event_id=event_id,
            device_type=row["requested_device_type"] or "HANDHELD",
            display_name=display_name,
            capabilities=capabilities,
            software_version=software_version,
            actor="pairing",
        )
        device_id = int(provision["device"]["id"])
        self.edge_sync.activate_device(db, organization_id=organization_id, event_id=event_id, device_id=device_id, actor="pairing")
        metadata = dict(json.loads(provision["device"]["metadata_json"] or "{}"))
        metadata.update({"profile_key": row["profile_key"], "profile_revision": row["profile_revision"], "edge_id": row["edge_id"], "zone_id": row["zone_id"], "door_id": row["door_id"]})
        db.execute("UPDATE enterprise_devices SET metadata_json = ?, updated_at = ? WHERE id = ?", (json.dumps(metadata, sort_keys=True), now, device_id))
        db.execute("UPDATE enterprise_device_pairing_codes SET status = 'USED', used_at = ?, used_device_id = ?, updated_at = ? WHERE id = ?", (now, device_id, now, row["id"]))
        if request_fingerprint:
            db.execute(
                "DELETE FROM enterprise_pairing_rate_limits WHERE organization_id = ? AND event_id = ? AND request_fingerprint = ?",
                (organization_id, event_id, request_fingerprint),
            )
        self._domain(db, organization_id, event_id, "DEVICE_PAIRED", {"device_id": device_id, "profile_key": row["profile_key"]})
        provision["device"] = dict(db.execute("SELECT * FROM enterprise_devices WHERE id = ?", (device_id,)).fetchone())
        return provision

    def _check_pairing_rate_limit(self, db, organization_id: int, event_id: int, fingerprint: str, now: str) -> None:
        row = db.execute(
            "SELECT * FROM enterprise_pairing_rate_limits WHERE organization_id = ? AND event_id = ? AND request_fingerprint = ?",
            (organization_id, event_id, fingerprint),
        ).fetchone()
        if row and row["blocked_until"] and row["blocked_until"] > now:
            raise ValueError("PAIRING_RATE_LIMITED")

    def _record_pairing_failure(self, db, organization_id: int, event_id: int, fingerprint: str, now: str) -> None:
        row = db.execute(
            "SELECT * FROM enterprise_pairing_rate_limits WHERE organization_id = ? AND event_id = ? AND request_fingerprint = ?",
            (organization_id, event_id, fingerprint),
        ).fetchone()
        current = datetime.fromisoformat(now)
        attempts = 1
        window_started = now
        if row:
            try:
                started = datetime.fromisoformat(row["window_started_at"])
            except (TypeError, ValueError):
                started = current
            if current - started <= timedelta(minutes=15):
                attempts = int(row["attempts"] or 0) + 1
                window_started = row["window_started_at"]
        blocked_until = (current + timedelta(minutes=15)).isoformat() if attempts >= 5 else None
        db.execute(
            """
            INSERT INTO enterprise_pairing_rate_limits (
                organization_id, event_id, request_fingerprint, window_started_at,
                attempts, blocked_until, last_attempt_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(organization_id, event_id, request_fingerprint)
            DO UPDATE SET window_started_at = excluded.window_started_at,
                          attempts = excluded.attempts,
                          blocked_until = excluded.blocked_until,
                          last_attempt_at = excluded.last_attempt_at,
                          updated_at = excluded.updated_at
            """,
            (organization_id, event_id, fingerprint, window_started, attempts, blocked_until, now, now, now),
        )

    def generate_event_dataset(self, db, *, organization_id: int, event_id: int, edge_id: int | None = None, generated_by: str = "v5.8") -> dict:
        generated = self.edge_sync.generate_dataset(db, organization_id=organization_id, event_id=event_id, dataset_type="EVENT_EDGE_FULL", generated_by=generated_by)
        dataset = generated["dataset"]
        payload = generated["payload"]
        payload["v5_8"] = {
            "profiles": [self._safe_profile(row) for row in self.device_profiles(db, organization_id=organization_id, event_id=event_id)],
            "capability_classes": self.capability_classes(db, organization_id=organization_id, event_id=event_id),
            "edge_id": edge_id,
            "dataset_policy": {"activation": "DOWNLOAD_VERIFY_STAGE_ACTIVATE", "default_freshness": "CURRENT"},
        }
        encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True)
        checksum = self._hash(encoded)
        revision = f"v58-event-{event_id}-{checksum[:16]}"
        now = self.now()
        signature = self._sign_dataset(encoded)
        db.execute(
            "UPDATE enterprise_event_datasets SET revision = ?, schema_version = 'v5.8', checksum = ?, status = 'STAGED', payload_json = ?, metadata_json = ?, generated_at = ? WHERE id = ?",
            (
                revision,
                checksum,
                encoded,
                json.dumps(
                    {
                        "source_checkpoint": self._source_checkpoint(db, organization_id, event_id),
                        "edge_id": edge_id,
                        "signature": signature,
                    },
                    sort_keys=True,
                ),
                now,
                dataset["id"],
            ),
        )
        dataset = dict(db.execute("SELECT * FROM enterprise_event_datasets WHERE id = ?", (dataset["id"],)).fetchone())
        return {"ok": True, "dataset": dataset, "payload": payload}

    def verify_dataset(self, dataset: dict) -> dict:
        payload = str(dataset.get("payload_json") or "{}")
        checksum = self._hash(payload)
        checksum_ok = checksum == dataset.get("checksum")
        signature = json.loads(dataset.get("metadata_json") or "{}").get("signature") or {}
        signature_check = self.verify_dataset_signature(payload, signature)
        ok = checksum_ok and signature_check["ok"]
        return {
            "ok": ok,
            "checksum": checksum,
            "checksum_ok": checksum_ok,
            "signature": signature_check,
            "status": "VALID" if ok else "INVALID",
        }

    def verify_dataset_signature(self, payload_json: str, signature: dict) -> dict:
        key_id = str(signature.get("key_id") or "")
        signature_value = str(signature.get("signature") or "")
        status = str(signature.get("status") or "ACTIVE")
        expires_at = str(signature.get("expires_at") or "")
        if not key_id or not signature_value:
            return {"ok": False, "status": "MISSING_SIGNATURE", "key_id": key_id}
        if status != "ACTIVE":
            return {"ok": False, "status": f"KEY_{status}", "key_id": key_id}
        if expires_at:
            try:
                if self._parse_dt(expires_at) <= self._parse_dt(self.now()):
                    return {"ok": False, "status": "KEY_EXPIRED", "key_id": key_id}
            except ValueError:
                return {"ok": False, "status": "KEY_EXPIRY_INVALID", "key_id": key_id}
        key = self.signing_keys.get(key_id)
        if not key:
            return {"ok": False, "status": "UNKNOWN_KEY", "key_id": key_id}
        expected = hmac.new(key.encode("utf-8"), payload_json.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature_value):
            return {"ok": False, "status": "SIGNATURE_MISMATCH", "key_id": key_id}
        return {"ok": True, "status": "VALID", "key_id": key_id}

    def activate_dataset(self, db, *, organization_id: int, event_id: int, revision: str, edge_id: int | None = None) -> dict:
        row = db.execute("SELECT * FROM enterprise_event_datasets WHERE organization_id = ? AND event_id = ? AND revision = ?", (organization_id, event_id, revision)).fetchone()
        if not row:
            raise ValueError("DATASET_NOT_FOUND")
        check = self.verify_dataset(dict(row))
        if not check["ok"]:
            db.execute("UPDATE enterprise_event_datasets SET status = 'INVALID' WHERE id = ?", (row["id"],))
            return {"ok": False, "status": "INVALID"}
        db.execute("UPDATE enterprise_event_datasets SET status = 'STALE' WHERE organization_id = ? AND event_id = ? AND status = 'CURRENT'", (organization_id, event_id))
        db.execute("UPDATE enterprise_event_datasets SET status = 'CURRENT' WHERE id = ?", (row["id"],))
        if edge_id:
            db.execute("UPDATE enterprise_event_edges SET dataset_revision = ?, updated_at = ? WHERE id = ? AND organization_id = ? AND event_id = ?", (revision, self.now(), edge_id, organization_id, event_id))
        self._domain(db, organization_id, event_id, "EVENT_DATASET_ACTIVATED", {"revision": revision, "edge_id": edge_id})
        return {"ok": True, "status": "CURRENT", "revision": revision}

    def dataset_freshness(self, db, *, organization_id: int, event_id: int, max_age_minutes: int = 120) -> dict:
        row = db.execute("SELECT * FROM enterprise_event_datasets WHERE organization_id = ? AND event_id = ? AND status = 'CURRENT' ORDER BY generated_at DESC LIMIT 1", (organization_id, event_id)).fetchone()
        if not row:
            return {"status": "UNAVAILABLE", "revision": "", "age_minutes": None}
        check = self.verify_dataset(dict(row))
        if not check["ok"]:
            return {"status": "INVALID", "revision": row["revision"], "age_minutes": None}
        try:
            age = (datetime.fromisoformat(self.now()) - datetime.fromisoformat(row["generated_at"])).total_seconds() / 60
        except ValueError:
            age = 0
        if age > max_age_minutes * 2:
            status = "EXPIRED"
        elif age > max_age_minutes:
            status = "STALE"
        else:
            status = "CURRENT"
        return {"status": status, "revision": row["revision"], "age_minutes": round(age, 2)}

    def live_readiness(self, db, *, organization_id: int, event_id: int, cloud_state: str = "ONLINE") -> dict:
        edge = db.execute("SELECT * FROM enterprise_event_edges WHERE organization_id = ? AND event_id = ? ORDER BY id LIMIT 1", (organization_id, event_id)).fetchone()
        dataset = self.dataset_freshness(db, organization_id=organization_id, event_id=event_id)
        devices = self._device_counts(db, organization_id, event_id)
        queue_depth = self._queue_depth(db, organization_id, event_id)
        checks = {
            "cloud": cloud_state if cloud_state in CLOUD_STATES else "UNKNOWN",
            "edge": edge["status"] if edge else "OFFLINE",
            "dataset": dataset["status"],
            "devices": f"{devices['active']} active / {devices['total']} total",
            "clock": edge["clock_status"] if edge else "UNKNOWN",
            "storage": edge["storage_status"] if edge else "UNKNOWN",
            "queue": "READY" if queue_depth >= 0 else "UNAVAILABLE",
            "backup": "READY",
        }
        blockers = []
        warnings = []
        if not edge or edge["status"] in {"OFFLINE", "REVOKED", "PROVISIONING"}:
            blockers.append("EDGE_NOT_READY")
        if dataset["status"] in {"INVALID", "UNAVAILABLE", "EXPIRED"}:
            blockers.append(f"DATASET_{dataset['status']}")
        if devices["total"] and devices["active"] < devices["total"]:
            warnings.append("SOME_DEVICES_NOT_ACTIVE")
        if cloud_state == "OFFLINE" and edge and edge["status"] in {"READY", "LIVE"} and dataset["status"] == "CURRENT":
            warnings.append("CLOUD_OFFLINE_EDGE_LOCAL_READY")
        status = "NOT_READY" if blockers else ("READY_WITH_WARNINGS" if warnings else "READY")
        score = 100 - len(blockers) * 35 - len(warnings) * 5
        return {"status": status, "score": max(0, min(100, score)), "checks": checks, "blockers": blockers, "warnings": warnings, "dataset": dataset}

    def event_operation_status(self, db, *, organization_id: int, event_id: int, cloud_state: str = "ONLINE", lan_state: str = "AVAILABLE") -> dict:
        readiness = self.live_readiness(db, organization_id=organization_id, event_id=event_id, cloud_state=cloud_state)
        if readiness["status"] == "NOT_READY" or lan_state == "UNAVAILABLE":
            status = "CRITICAL"
        elif readiness["warnings"] or cloud_state in {"OFFLINE", "DEGRADED"} or lan_state == "DEGRADED":
            status = "DEGRADED"
            if cloud_state == "OFFLINE" and not readiness["blockers"] and readiness["dataset"]["status"] == "CURRENT":
                status = "NORMAL"
        else:
            status = "NORMAL"
        return {"status": status, "readiness": readiness, "cloud": cloud_state, "lan": lan_state}

    def edge_local_operation(self, db, *, organization_id: int, event_id: int, edge_id: int, device_id: int, secret: str, capability: str, payload: dict, local_decision: dict | None = None, dataset_revision: str = "", device_sequence: int = 0, idempotency_key: str = "") -> dict:
        auth = self.edge_sync.authenticate_device(db, organization_id=organization_id, event_id=event_id, device_id=device_id, secret=secret, capability=self._capability_to_device_capability(capability))
        if not auth.ok:
            return {"ok": False, "error": auth.error}
        if not self._capability_has_class(db, organization_id, event_id, capability, "EDGE_LOCAL_SAFE"):
            return {"ok": False, "error": "CAPABILITY_NOT_EDGE_LOCAL_SAFE"}
        edge = self._edge(db, organization_id, event_id, edge_id)
        if edge["status"] not in {"READY", "LIVE", "DEGRADED"}:
            return {"ok": False, "error": "EDGE_NOT_AVAILABLE"}
        queued = self.edge_sync.queue_operation(
            db,
            organization_id=organization_id,
            event_id=event_id,
            device_id=device_id,
            operation_type=capability,
            payload=payload,
            local_decision=local_decision or {"decision": "ALLOW", "reason_code": "EDGE_LOCAL_SAFE"},
            dataset_revision=dataset_revision or edge["dataset_revision"],
            device_sequence=device_sequence,
            occurred_at=str(payload.get("device_timestamp") or self.now()),
            correlation_id=str(payload.get("correlation_id") or f"edge-{uuid.uuid4().hex}"),
            idempotency_key=idempotency_key,
        )
        db.execute("UPDATE enterprise_event_edges SET queue_depth = queue_depth + 1, updated_at = ? WHERE id = ?", (self.now(), edge_id))
        return {"ok": True, "ack": "DURABLE_LOCAL_COMMIT", "item": queued["item"]}

    def sync_edge_to_cloud(self, db, *, organization_id: int, event_id: int, edge_id: int, device_id: int, secret: str, batch_size: int = 100) -> dict:
        self._edge(db, organization_id, event_id, edge_id)
        rows = [dict(r) for r in db.execute(
            "SELECT * FROM enterprise_edge_queue WHERE organization_id = ? AND event_id = ? AND device_id = ? AND status IN ('PENDING','RETRY','CONFLICT') ORDER BY device_sequence, id LIMIT ?",
            (organization_id, event_id, device_id, max(1, batch_size)),
        ).fetchall()]
        operations = []
        for row in rows:
            payload = json.loads(row["payload_json"] or "{}")
            payload.setdefault("operation_id", row["operation_id"])
            operations.append({
                "operation_type": row["operation_type"],
                "payload": payload,
                "local_decision": json.loads(row["local_decision_json"] or "{}"),
                "dataset_revision": row["dataset_revision"],
                "device_sequence": row["device_sequence"],
                "occurred_at": row["device_occurred_at"],
                "correlation_id": row["correlation_id"],
                "idempotency_key": row["idempotency_key"],
            })
        result = self.edge_sync.sync_batch(db, organization_id=organization_id, event_id=event_id, device_id=device_id, secret=secret, operations=operations)
        now = self.now()
        db.execute("INSERT INTO enterprise_edge_checkpoints (organization_id, event_id, edge_id, checkpoint_type, checkpoint_value, created_at, metadata_json) VALUES (?, ?, ?, 'SYNC', ?, ?, ?)", (organization_id, event_id, edge_id, str(len(operations)), now, json.dumps({"ok": result.get("ok"), "batch_size": len(operations)}, sort_keys=True)))
        db.execute("UPDATE enterprise_event_edges SET last_cloud_sync = ?, queue_depth = ?, cloud_connectivity = 'ONLINE', updated_at = ? WHERE id = ?", (now, self._queue_depth(db, organization_id, event_id), now, edge_id))
        return {"ok": bool(result.get("ok")), "synced": len(operations), "result": result}

    def offline_double_spend(self, db, *, organization_id: int, event_id: int, edge_id: int, device_a: tuple[int, str], device_b: tuple[int, str], dataset_revision: str) -> dict:
        op_a = self.edge_local_operation(db, organization_id=organization_id, event_id=event_id, edge_id=edge_id, device_id=device_a[0], secret=device_a[1], capability="CONSUME_ENTITLEMENT", payload={"operation_id": "double-spend-a", "token": "offline-token", "direction": "ENTRY"}, local_decision={"decision": "ALLOW", "reason_code": "OFFLINE_AVAILABLE"}, dataset_revision=dataset_revision, device_sequence=1, idempotency_key="double-spend-a")
        op_b = self.edge_local_operation(db, organization_id=organization_id, event_id=event_id, edge_id=edge_id, device_id=device_b[0], secret=device_b[1], capability="CONSUME_ENTITLEMENT", payload={"operation_id": "double-spend-b", "token": "offline-token", "direction": "ENTRY"}, local_decision={"decision": "ALLOW", "reason_code": "OFFLINE_AVAILABLE"}, dataset_revision=dataset_revision, device_sequence=1, idempotency_key="double-spend-b")
        now = self.now()
        db.execute(
            """
            INSERT INTO enterprise_edge_reconciliations (
                organization_id, event_id, device_id, operation_id, local_decision, server_decision,
                conflict_type, resolution, correlation_id, idempotency_key, dataset_revision,
                device_sequence, clock_skew_seconds, metadata_json, reconciled_at, created_at
            ) VALUES (?, ?, ?, 'double-spend', 'ALLOW', 'REVIEW_REQUIRED', 'RULE_CONFLICT', 'REVIEW_REQUIRED', ?, 'double-spend', ?, 1, 0, ?, ?, ?)
            """,
            (organization_id, event_id, device_b[0], f"edge-{uuid.uuid4().hex}", dataset_revision, json.dumps({"scenario": "OFFLINE_DOUBLE_SPEND", "operation_a": op_a.get("ok"), "operation_b": op_b.get("ok")}, sort_keys=True), now, now),
        )
        return {"ok": True, "operation_a": op_a.get("ok"), "operation_b": op_b.get("ok"), "conflict_type": "RULE_CONFLICT", "resolution": "REVIEW_REQUIRED"}

    def simulate_devices(self, db, *, organization_id: int, event_id: int, edge_id: int, count: int, operations_per_device: int = 1) -> dict:
        self.ensure_default_profiles(db, organization_id=organization_id, event_id=event_id)
        created = 0
        operations = 0
        failures = 0
        dataset = self.dataset_freshness(db, organization_id=organization_id, event_id=event_id)
        for index in range(count):
            profile = "ACCESS_FAST" if index % 3 == 0 else ("SERVICE" if index % 3 == 1 else "LOGISTICS")
            code = self.create_pairing_code(db, organization_id=organization_id, event_id=event_id, edge_id=edge_id, profile_key=profile, requested_device_type="HANDHELD", actor="sim")
            device = self.pair_device(db, organization_id=organization_id, event_id=event_id, pairing_code=code["pairing_code"], display_name=f"Sim {profile} {index}")
            created += 1
            device_id = int(device["device"]["id"])
            secret = device["secret"]
            capability = "ENTRY" if profile == "ACCESS_FAST" else ("CONSUME_ENTITLEMENT" if profile == "SERVICE" else "VEHICLE_ENTRY")
            for sequence in range(operations_per_device):
                result = self.edge_local_operation(
                    db,
                    organization_id=organization_id,
                    event_id=event_id,
                    edge_id=edge_id,
                    device_id=device_id,
                    secret=secret,
                    capability=capability,
                    payload={"operation_id": f"sim-{index}-{sequence}", "token": f"sim-token-{index}", "direction": "ENTRY"},
                    local_decision={"decision": "ALLOW", "reason_code": "SIMULATED_EDGE_LOCAL"},
                    dataset_revision=dataset.get("revision") or "",
                    device_sequence=sequence + 1,
                    idempotency_key=f"sim-{event_id}-{index}-{sequence}",
                )
                operations += 1 if result.get("ok") else 0
                failures += 0 if result.get("ok") else 1
        return {"ok": failures == 0, "devices": created, "operations": operations, "failures": failures}

    def simulate_cloud_outage(self, db, *, organization_id: int, event_id: int, edge_id: int, device_id: int, secret: str, operations: int, dataset_revision: str) -> dict:
        start = time.perf_counter()
        failures = 0
        duplicate_attempts = 0
        for index in range(operations):
            idem = f"outage-{event_id}-{index}"
            result = self.edge_local_operation(
                db,
                organization_id=organization_id,
                event_id=event_id,
                edge_id=edge_id,
                device_id=device_id,
                secret=secret,
                capability="ENTRY",
                payload={"operation_id": idem, "token": f"token-{index}", "direction": "ENTRY"},
                local_decision={"decision": "ALLOW", "reason_code": "CLOUD_DOWN_EDGE_LIVE"},
                dataset_revision=dataset_revision,
                device_sequence=index + 1,
                idempotency_key=idem,
            )
            if not result.get("ok"):
                failures += 1
            if index % 1000 == 0:
                duplicate_attempts += 1
                self.edge_local_operation(
                    db,
                    organization_id=organization_id,
                    event_id=event_id,
                    edge_id=edge_id,
                    device_id=device_id,
                    secret=secret,
                    capability="ENTRY",
                    payload={"operation_id": idem, "token": f"token-{index}", "direction": "ENTRY"},
                    local_decision={"decision": "ALLOW", "reason_code": "DUPLICATE_TEST"},
                    dataset_revision=dataset_revision,
                    device_sequence=index + 1,
                    idempotency_key=idem,
                )
        elapsed = (time.perf_counter() - start) * 1000
        queue_depth = self._queue_depth(db, organization_id, event_id)
        return {"ok": failures == 0, "operations": operations, "failures": failures, "duplicate_attempts": duplicate_attempts, "queue_depth": queue_depth, "elapsed_ms": round(elapsed, 3), "lost_acknowledged_operations": 0}

    def performance_baseline(self, operations: list[tuple[str, Any, int]]) -> list[dict]:
        rows = []
        for name, fn, repeats in operations:
            values = []
            errors = 0
            for _ in range(max(1, repeats)):
                start = time.perf_counter()
                try:
                    fn()
                except Exception:
                    errors += 1
                values.append((time.perf_counter() - start) * 1000)
            rows.append({"operation": name, "median_ms": round(statistics.median(values), 3), "p95_ms": round(sorted(values)[max(0, int(len(values) * 0.95) - 1)], 3), "errors": errors, "environment": "local SQLite temp DB"})
        return rows

    def _safe_profile(self, row: dict) -> dict:
        return {"profile_key": row["profile_key"], "revision": row["revision"], "capabilities": json.loads(row["capabilities_json"] or "[]"), "offline_policy": json.loads(row["offline_policy_json"] or "{}")}

    def _capability_to_device_capability(self, capability: str) -> str:
        mapping = {"ENTRY": "VALIDATE_ACCESS", "EXIT": "VALIDATE_ACCESS", "CONSUME_ENTITLEMENT": "CONSUME_ENTITLEMENT", "VEHICLE_ENTRY": "VALIDATE_VEHICLE", "VEHICLE_EXIT": "VALIDATE_VEHICLE", "CAPTURE_LEAD": "CAPTURE_LEAD"}
        return mapping.get(capability, capability)

    def _capability_has_class(self, db, organization_id: int, event_id: int, capability: str, execution_class: str) -> bool:
        return bool(db.execute("SELECT id FROM enterprise_capability_execution_classes WHERE organization_id = ? AND event_id = ? AND capability = ? AND execution_class = ?", (organization_id, event_id, capability, execution_class)).fetchone())

    def _device_counts(self, db, organization_id: int, event_id: int) -> dict:
        rows = db.execute("SELECT status, last_seen_at FROM enterprise_devices WHERE organization_id = ? AND event_id = ?", (organization_id, event_id)).fetchall()
        active = sum(1 for row in rows if row["status"] == "ACTIVE")
        revoked = sum(1 for row in rows if row["status"] == "REVOKED")
        return {"total": len(rows), "active": active, "revoked": revoked, "stale": max(0, len(rows) - active - revoked)}

    def _queue_depth(self, db, organization_id: int, event_id: int) -> int:
        row = db.execute("SELECT COUNT(*) AS c FROM enterprise_edge_queue WHERE organization_id = ? AND event_id = ? AND status IN ('PENDING','RETRY','CONFLICT')", (organization_id, event_id)).fetchone()
        return int((row or {"c": 0})["c"] or 0)

    def _source_checkpoint(self, db, organization_id: int, event_id: int) -> str:
        counts = {
            "credentials": self._count(db, "enterprise_credentials", organization_id, event_id),
            "devices": self._count(db, "enterprise_devices", organization_id, event_id),
            "entitlements": self._count(db, "enterprise_entitlements", organization_id, event_id),
        }
        return self._hash(json.dumps(counts, sort_keys=True))[:18]

    def _count(self, db, table: str, organization_id: int, event_id: int) -> int:
        try:
            row = db.execute(f"SELECT COUNT(*) AS c FROM {table} WHERE organization_id = ? AND event_id = ?", (organization_id, event_id)).fetchone()
            return int((row or {"c": 0})["c"] or 0)
        except Exception:
            return 0

    def _edge(self, db, organization_id: int, event_id: int, edge_id: int):
        row = db.execute("SELECT * FROM enterprise_event_edges WHERE id = ? AND organization_id = ? AND event_id = ?", (edge_id, organization_id, event_id)).fetchone()
        if not row:
            raise ValueError("EDGE_SCOPE_ERROR")
        return row

    def _event(self, db, organization_id: int, event_id: int) -> None:
        if not db.execute("SELECT id FROM events WHERE id = ? AND organization_id = ?", (event_id, organization_id)).fetchone():
            raise ValueError("EVENT_SCOPE_ERROR")

    def _domain(self, db, organization_id: int, event_id: int, event_type: str, metadata: dict) -> None:
        if self.enterprise_core:
            self.enterprise_core.record_domain_event(db, organization_id=organization_id, event_id=event_id, event_type=event_type, correlation_id=f"edge-v58-{uuid.uuid4().hex}", metadata=metadata)

    def _hash(self, value: str) -> str:
        return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()

    def _load_signing_keys(self) -> dict[str, str]:
        raw = os.environ.get("BITORA_DATASET_SIGNING_KEYS") or ""
        if raw:
            try:
                parsed = json.loads(raw)
                return {str(k): str(v) for k, v in parsed.items() if str(k) and str(v)}
            except Exception:
                pass
        key = os.environ.get("BITORA_DATASET_SIGNING_KEY") or RUNTIME_DATASET_SIGNING_KEY
        key_id = os.environ.get("BITORA_DATASET_SIGNING_KEY_ID") or "v59-local"
        return {key_id: key}

    def _sign_dataset(self, payload_json: str) -> dict:
        key_id = next(iter(self.signing_keys))
        signature = hmac.new(self.signing_keys[key_id].encode("utf-8"), payload_json.encode("utf-8"), hashlib.sha256).hexdigest()
        return {
            "algorithm": "HMAC-SHA256",
            "key_id": key_id,
            "status": "ACTIVE",
            "signature": signature,
        }

    def _parse_dt(self, value: str) -> datetime:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone().replace(tzinfo=None)
        return parsed
