from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import time
from datetime import datetime, timezone


PAIRING_TTL_SECONDS = 10 * 60
PAIRING_CODE_PATTERN = re.compile(r"^BTR-[A-Z0-9]{4}-[A-Z0-9]{4}$")


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def profile_capabilities(profile: str) -> list[str]:
    return {
        "DISPLAY": ["DISPLAY_CONTENT", "SYNC_DATASET"],
        "RECEPTION": ["CHECK_IN", "SCAN_QR", "VIEW_PARTICIPANT", "PRINT_BADGE", "SYNC_DATASET"],
        "SELF_SERVICE": ["CHECK_IN", "SCAN_QR", "VIEW_PARTICIPANT", "PRINT_BADGE", "SYNC_DATASET"],
        "SERVICE": ["CONSUME_ENTITLEMENT", "SCAN_QR", "SYNC_DATASET"],
        "LEAD_RETRIEVAL": ["SCAN_QR", "VIEW_PARTICIPANT", "SYNC_DATASET"],
        "LOGISTICS": ["VALIDATE_ACCESS", "SCAN_QR", "SYNC_DATASET"],
        "ACCESS_FAST": ["VALIDATE_ACCESS", "SCAN_QR", "SYNC_DATASET"],
    }.get(profile.upper(), ["SYNC_DATASET"])


class AndroidEdgeService:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def register_pairing(self, db, data: dict) -> dict:
        code = str(data.get("pairingCode") or "").strip().upper()
        nonce = str(data.get("nonce") or "")
        if not PAIRING_CODE_PATTERN.fullmatch(code):
            return {"ok": False, "decision": "UNKNOWN", "error": "invalid_code"}
        if len(nonce) < 16:
            return {"ok": False, "decision": "UNKNOWN", "error": "invalid_nonce"}
        code_hash = _sha(code)
        existing = db.execute("SELECT * FROM android_pairings WHERE code_hash = ?", (code_hash,)).fetchone()
        if existing and existing["status"] in {"APPROVED", "USED"}:
            return {"ok": True, **self._public_pairing(existing)}
        now = _now_iso()
        expires = int(time.time()) + PAIRING_TTL_SECONDS
        values = (
            code_hash, code, _sha(nonce), str(data.get("deviceKind") or "OPERATION")[:40],
            str(data.get("requestedProfile") or "ACCESS_FAST")[:80].upper(),
            str(data.get("softwareVersion") or "")[:120], now, expires,
        )
        db.execute(
            """
            INSERT INTO android_pairings (
                code_hash, pairing_code, nonce_hash, device_kind, requested_profile,
                software_version, status, created_at, expires_at_epoch
            ) VALUES (?, ?, ?, ?, ?, ?, 'PENDING', ?, ?)
            ON CONFLICT (code_hash) DO UPDATE SET
                nonce_hash = excluded.nonce_hash,
                device_kind = excluded.device_kind,
                requested_profile = excluded.requested_profile,
                software_version = excluded.software_version,
                status = 'PENDING',
                created_at = excluded.created_at,
                expires_at_epoch = excluded.expires_at_epoch,
                organization_id = NULL,
                event_id = NULL,
                event_name = '',
                profile = '',
                scope = '',
                capabilities_json = '[]',
                approved_at = NULL,
                used_device_id = NULL
            """,
            values,
        )
        row = db.execute("SELECT * FROM android_pairings WHERE code_hash = ?", (code_hash,)).fetchone()
        return {"ok": True, **self._public_pairing(row)}

    def pairing_status(self, db, code: str, nonce: str) -> dict:
        row = db.execute("SELECT * FROM android_pairings WHERE code_hash = ?", (_sha(code.strip().upper()),)).fetchone()
        if not row:
            return {"ok": False, "decision": "UNKNOWN", "error": "invalid_code"}
        if not hmac.compare_digest(str(row["nonce_hash"]), _sha(nonce)):
            return {"ok": False, "decision": "UNKNOWN", "error": "invalid_nonce"}
        status = self._effective_status(db, row)
        current = dict(row)
        current["status"] = status
        return {"ok": True, "decision": status, **self._public_pairing(current)}

    def list_pairings(self, db) -> dict:
        rows = db.execute("SELECT * FROM android_pairings ORDER BY created_at DESC LIMIT 200").fetchall()
        return {"ok": True, "items": [self._public_pairing(row) for row in rows]}

    def approve(self, db, data: dict) -> dict:
        code = str(data.get("pairingCode") or "").strip().upper()
        row = db.execute("SELECT * FROM android_pairings WHERE code_hash = ?", (_sha(code),)).fetchone()
        if not row:
            return {"ok": False, "error": "invalid_code"}
        if self._effective_status(db, row) in {"EXPIRED", "USED"}:
            return {"ok": False, "error": "pairing_not_approvable"}
        event_id = int(data.get("eventId") or 0)
        event = db.execute("SELECT id, name, organization_id FROM events WHERE id = ?", (event_id,)).fetchone()
        if not event:
            return {"ok": False, "error": "event_not_found"}
        profile = str(data.get("profile") or row["requested_profile"] or "ACCESS_FAST").strip().upper()
        capabilities = data.get("capabilities") if isinstance(data.get("capabilities"), list) else profile_capabilities(profile)
        organization_id = int(event["organization_id"] or 1)
        scope = str(data.get("scope") or f"event:{event_id}:{profile}")
        db.execute(
            """
            UPDATE android_pairings
            SET status = 'APPROVED', organization_id = ?, event_id = ?, event_name = ?,
                profile = ?, scope = ?, capabilities_json = ?, approved_at = ?
            WHERE code_hash = ?
            """,
            (organization_id, event_id, event["name"], profile, scope, json.dumps(capabilities), _now_iso(), _sha(code)),
        )
        return {"ok": True, **self._public_pairing(db.execute("SELECT * FROM android_pairings WHERE code_hash = ?", (_sha(code),)).fetchone())}

    def reject(self, db, data: dict) -> dict:
        code_hash = _sha(str(data.get("pairingCode") or "").strip().upper())
        row = db.execute("SELECT * FROM android_pairings WHERE code_hash = ?", (code_hash,)).fetchone()
        if not row:
            return {"ok": False, "error": "invalid_code"}
        db.execute("UPDATE android_pairings SET status = 'REJECTED' WHERE code_hash = ?", (code_hash,))
        return {"ok": True, "decision": "REJECTED"}

    def exchange(self, db, data: dict) -> dict:
        code = str(data.get("pairingCode") or "").strip().upper()
        nonce = str(data.get("nonce") or "")
        row = db.execute("SELECT * FROM android_pairings WHERE code_hash = ?", (_sha(code),)).fetchone()
        if not row or not hmac.compare_digest(str(row["nonce_hash"]), _sha(nonce)):
            return {"ok": False, "error": "invalid_pairing"}
        if self._effective_status(db, row) != "APPROVED":
            return {"ok": False, "error": f"not_approved:{self._effective_status(db, row)}"}
        device_id = f"prd-{secrets.token_hex(6)}"
        token = secrets.token_urlsafe(32)
        credential_hash = _sha(token)
        capabilities = json.loads(row["capabilities_json"] or "[]")
        revision = self._dataset_revision(db, int(row["event_id"]))
        db.execute(
            """
            INSERT INTO android_devices (
                device_id, organization_id, event_id, event_name, profile, scope,
                capabilities_json, credential_hash, status, software_version,
                dataset_revision, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE', ?, ?, ?)
            """,
            (device_id, int(row["organization_id"]), int(row["event_id"]), row["event_name"], row["profile"], row["scope"], row["capabilities_json"], credential_hash, row["software_version"], revision, _now_iso()),
        )
        db.execute("UPDATE android_pairings SET status = 'USED', used_device_id = ? WHERE code_hash = ?", (device_id, _sha(code)))
        return {
            "ok": True, "deviceId": device_id, "organizationId": int(row["organization_id"]),
            "eventId": int(row["event_id"]), "eventName": row["event_name"], "profile": row["profile"],
            "scope": row["scope"], "capabilities": capabilities, "edgeBaseUrl": self.base_url,
            "datasetRevision": revision, "credentialToken": token,
        }

    def authenticate_device(self, db, device_id: str, token: str):
        row = db.execute("SELECT * FROM android_devices WHERE device_id = ? AND status = 'ACTIVE'", (device_id,)).fetchone()
        if not row or not token or not hmac.compare_digest(str(row["credential_hash"]), _sha(token)):
            return None
        return row

    def dataset(self, db, device) -> dict:
        event_id = int(device["event_id"])
        organization_id = int(device["organization_id"])
        event = db.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
        people = db.execute(
            """
            SELECT a.token, a.status, a.checked_in_at, p.first_name, p.last_name
            FROM accreditations a JOIN people p ON p.id = a.person_id
            WHERE a.event_id = ? ORDER BY a.id
            """,
            (event_id,),
        ).fetchall()
        participants = [
            {"token": row["token"], "event_id": event_id, "status": str(row["status"]).upper(),
             "display_name": f"{row['first_name']} {row['last_name']}".strip(), "checked_in": bool(row["checked_in_at"])}
            for row in people
        ]
        credentials = [
            {"token": item["token"], "event_id": event_id, "status": item["status"], "name": item["display_name"],
             "entitlements": ["ACCESS_FAST"], "doors": ["main"], "zones": ["general"]}
            for item in participants
        ]
        display = db.execute("SELECT * FROM public_display_config WHERE event_id = ?", (event_id,)).fetchone()
        revision = self._dataset_revision(db, event_id)
        payload = {
            "event": {"organization_id": organization_id, "event_id": event_id, "name": event["name"]},
            "doors": [{"id": "main", "name": "Main", "direction": "ENTRY"}],
            "device": {"profile": device["profile"], "door": "main", "zone": "general", "direction": "ENTRY"},
            "zones": [{"id": "general", "name": "General"}], "credentials": credentials,
            "participants": participants, "service_entitlements": [], "lead_participants": [], "vehicle_permits": [],
            "capabilities": json.loads(device["capabilities_json"] or "[]"),
            "configuration": {"offline_policy": "EDGE_LOCAL_SAFE_ONLY", "cooldown_seconds": 2},
            "display_content": {"title": "BITORA LIVE", "message": (display["message"] if display else event["name"]), "screen": (display["room_filter"] if display else "MAIN_HALL") or "MAIN_HALL", "duration_seconds": int(display["refresh_seconds"] if display else 10)},
        }
        payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        checksum = _sha(payload_json)
        expires = int(time.time()) + 3600
        signed = f"{organization_id}|{event_id}|{revision}|{checksum}|{expires}"
        signature = hmac.new(str(device["credential_hash"]).encode(), signed.encode(), hashlib.sha256).hexdigest()
        return {"ok": True, "organizationId": organization_id, "eventId": event_id, "revision": revision,
                "schemaVersion": "v5.8", "generatedAt": int(time.time()), "expiresAtEpochSeconds": expires,
                "payloadJson": payload_json, "checksum": checksum, "signature": signature, "signingKeyId": device["device_id"]}

    def heartbeat(self, db, device, data: dict) -> dict:
        telemetry = data.get("telemetry") if isinstance(data.get("telemetry"), dict) else {}
        now = _now_iso()
        db.execute("UPDATE android_devices SET last_seen_at = ?, dataset_revision = ?, telemetry_json = ? WHERE device_id = ?",
                   (now, str(data.get("datasetRevision") or ""), json.dumps(telemetry), device["device_id"]))
        return {"ok": True, "edgeStatus": "ONLINE", "lastSeen": now}

    def sync(self, db, device, data: dict) -> dict:
        results = []
        for operation in data.get("operations") or []:
            operation_id = str(operation.get("operationId") or secrets.token_hex(16))
            idempotency_key = str(operation.get("idempotencyKey") or operation_id)
            existing = db.execute("SELECT operation_id FROM android_edge_operations WHERE device_id = ? AND idempotency_key = ?", (device["device_id"], idempotency_key)).fetchone()
            if existing:
                results.append({"operationId": operation_id, "status": "DUPLICATE", "conflict": "DUPLICATE"})
                continue
            db.execute(
                """INSERT INTO android_edge_operations
                   (operation_id, device_id, idempotency_key, operation_type, correlation_id, sequence_number, payload_json, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'ACKNOWLEDGED', ?)""",
                (operation_id, device["device_id"], idempotency_key, str(operation.get("operationType") or "UNKNOWN"), str(operation.get("correlationId") or ""), int(operation.get("sequence") or 0), json.dumps(operation.get("payload") or {}), _now_iso()),
            )
            results.append({"operationId": operation_id, "status": "ACKNOWLEDGED", "conflict": "NO_CONFLICT"})
        return {"ok": True, "results": results, "checkpoint": f"PRD-CHK-{int(time.time())}"}

    def telemetry(self, db, device_id: str = "") -> dict:
        if device_id:
            rows = db.execute("SELECT * FROM android_devices WHERE device_id = ? ORDER BY created_at DESC", (device_id,)).fetchall()
        else:
            rows = db.execute("SELECT * FROM android_devices ORDER BY created_at DESC LIMIT 250").fetchall()
        items = []
        for row in rows:
            last_seen = row["last_seen_at"]
            age = None
            if last_seen:
                age = max(0, int(time.time() - datetime.fromisoformat(str(last_seen).replace("Z", "+00:00")).timestamp()))
            telemetry = json.loads(row["telemetry_json"] or "{}")
            alerts = []
            if age is None or age > 20 * 60: alerts.append("HEARTBEAT_STALE")
            if not row["dataset_revision"]: alerts.append("DATASET_MISSING")
            if int(telemetry.get("queuePending") or 0) > 100: alerts.append("QUEUE_DEPTH_HIGH")
            items.append({"deviceId": row["device_id"], "profile": row["profile"], "status": row["status"], "lastSeen": last_seen, "heartbeatAgeSeconds": age, "datasetRevision": row["dataset_revision"], "telemetry": telemetry, "alerts": alerts})
        active_items = [item for item in items if item["status"] == "ACTIVE"]
        status = "EMPTY" if not active_items else ("HEALTHY" if not any(item["alerts"] for item in active_items) else "ALERT")
        return {"ok": True, "status": status, "items": items}

    def revoke(self, db, data: dict) -> dict:
        device_id = str(data.get("deviceId") or "")
        db.execute("UPDATE android_devices SET status = 'REVOKED', revoked_at = ? WHERE device_id = ?", (_now_iso(), device_id))
        return {"ok": True, "deviceId": device_id, "status": "REVOKED"}

    def _effective_status(self, db, row) -> str:
        status = str(row["status"])
        if status == "PENDING" and int(row["expires_at_epoch"]) < int(time.time()):
            db.execute("UPDATE android_pairings SET status = 'EXPIRED' WHERE code_hash = ?", (row["code_hash"],))
            return "EXPIRED"
        return status

    def _public_pairing(self, row) -> dict:
        capabilities = json.loads(row["capabilities_json"] or "[]")
        expires = datetime.fromtimestamp(int(row["expires_at_epoch"]), timezone.utc).isoformat(timespec="seconds")
        return {"pairingCode": row["pairing_code"], "deviceKind": row["device_kind"], "requestedProfile": row["requested_profile"], "softwareVersion": row["software_version"], "status": row["status"], "eventId": row["event_id"], "eventName": row["event_name"], "profile": row["profile"], "scope": row["scope"], "capabilities": capabilities, "createdAt": row["created_at"], "expiresAt": expires, "usedDeviceId": row["used_device_id"]}

    def _dataset_revision(self, db, event_id: int) -> str:
        return f"PRD-{event_id}-{int(time.time()):010d}"
