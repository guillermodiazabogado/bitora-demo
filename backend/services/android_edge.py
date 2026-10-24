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
            SELECT a.id AS accreditation_id, a.token, a.status, a.checked_in_at,
                   p.first_name, p.last_name
            FROM accreditations a JOIN people p ON p.id = a.person_id
            WHERE a.event_id = ? ORDER BY a.id
            """,
            (event_id,),
        ).fetchall()
        now = _now_iso()
        for row in people:
            db.execute(
                """
                INSERT INTO android_edge_credentials (event_id, accreditation_id, token_hash, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT (event_id, accreditation_id) DO UPDATE SET
                    token_hash = excluded.token_hash, updated_at = excluded.updated_at
                """,
                (event_id, int(row["accreditation_id"]), _sha(str(row["token"])), now),
            )
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
        service_rows = db.execute(
            """
            SELECT a.token, p.first_name, p.last_name, e.entitlement_type, e.service_point,
                   e.status, e.quantity, e.consumed_quantity
            FROM android_service_entitlements e
            JOIN accreditations a ON a.id = e.accreditation_id AND a.event_id = e.event_id
            JOIN people p ON p.id = a.person_id
            WHERE e.event_id = ? ORDER BY e.id
            """,
            (event_id,),
        ).fetchall()
        lead_rows = db.execute(
            """
            SELECT a.token, a.status, p.first_name, p.last_name, l.consent_status
            FROM android_lead_participants l
            JOIN accreditations a ON a.id = l.accreditation_id AND a.event_id = l.event_id
            JOIN people p ON p.id = a.person_id
            WHERE l.event_id = ? ORDER BY l.id
            """,
            (event_id,),
        ).fetchall()
        vehicle_rows = db.execute(
            """
            SELECT permit_token, display_label, checkpoint, status
            FROM android_vehicle_permits WHERE event_id = ? ORDER BY id
            """,
            (event_id,),
        ).fetchall()
        service_entitlements = [
            {
                "token": row["token"], "event_id": event_id,
                "display_name": f"{row['first_name']} {row['last_name']}".strip(),
                "entitlement_type": row["entitlement_type"], "service_point": row["service_point"],
                "status": str(row["status"]).upper(),
                "available": max(0, int(row["quantity"]) - int(row["consumed_quantity"])),
            }
            for row in service_rows
        ]
        lead_participants = [
            {
                "token": row["token"], "event_id": event_id, "status": str(row["status"]).upper(),
                "display_name": f"{row['first_name']} {row['last_name']}".strip(),
                "lead_consent": str(row["consent_status"]).upper() == "GRANTED",
            }
            for row in lead_rows
        ]
        vehicle_permits = [
            {
                "token": row["permit_token"], "event_id": event_id,
                "display_label": row["display_label"], "checkpoint": row["checkpoint"],
                "status": str(row["status"]).upper(),
            }
            for row in vehicle_rows
        ]
        display = db.execute("SELECT * FROM public_display_config WHERE event_id = ?", (event_id,)).fetchone()
        revision = self._dataset_revision(db, event_id)
        profile = str(device["profile"]).upper()
        payload = {
            "event": {"organization_id": organization_id, "event_id": event_id, "name": event["name"]},
            "doors": [{"id": "main", "name": "Main", "direction": "ENTRY"}],
            "device": {"profile": device["profile"], "door": "main", "zone": "general", "direction": "ENTRY"},
            "zones": [{"id": "general", "name": "General"}],
            "credentials": credentials if profile == "ACCESS_FAST" else [],
            "participants": participants if profile in {"RECEPTION", "SELF_SERVICE"} else [],
            "service_entitlements": service_entitlements if profile == "SERVICE" else [],
            "lead_participants": lead_participants if profile == "LEAD_RETRIEVAL" else [],
            "vehicle_permits": vehicle_permits if profile == "LOGISTICS" else [],
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
            operation_type = str(operation.get("operationType") or "UNKNOWN").upper()
            payload = operation.get("payload") if isinstance(operation.get("payload"), dict) else {}
            db.execute(
                """INSERT INTO android_edge_operations
                   (operation_id, device_id, idempotency_key, operation_type, correlation_id, sequence_number, payload_json, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'ACKNOWLEDGED', ?)""",
                (operation_id, device["device_id"], idempotency_key, operation_type, str(operation.get("correlationId") or ""), int(operation.get("sequence") or 0), json.dumps(payload), _now_iso()),
            )
            try:
                conflict = self._apply_operation(db, device, operation_id, operation_type, payload)
                results.append({"operationId": operation_id, "status": "ACKNOWLEDGED", "conflict": conflict})
            except ValueError as exc:
                reason = str(exc)[:120] or "INVALID_OPERATION"
                db.execute("UPDATE android_edge_operations SET status = 'REJECTED' WHERE operation_id = ?", (operation_id,))
                results.append({"operationId": operation_id, "status": "REJECTED", "conflict": reason})
        return {"ok": True, "results": results, "checkpoint": f"PRD-CHK-{int(time.time())}"}

    def resources(self, db, event_id: int) -> dict:
        event = db.execute("SELECT id, name, organization_id FROM events WHERE id = ?", (event_id,)).fetchone()
        if not event:
            return {"ok": False, "error": "event_not_found"}
        participants = db.execute(
            """
            SELECT a.id AS accreditation_id, a.status, p.first_name, p.last_name, p.email,
                   COALESCE(se.status, '') AS service_status,
                   COALESCE(se.quantity, 0) AS service_quantity,
                   COALESCE(se.consumed_quantity, 0) AS service_consumed,
                   COALESCE(lp.consent_status, '') AS lead_consent
            FROM accreditations a JOIN people p ON p.id = a.person_id
            LEFT JOIN android_service_entitlements se ON se.event_id = a.event_id
                AND se.accreditation_id = a.id AND se.entitlement_type = 'COFFEE'
                AND se.service_point = 'coffee-main'
            LEFT JOIN android_lead_participants lp ON lp.event_id = a.event_id
                AND lp.accreditation_id = a.id
            WHERE a.event_id = ? ORDER BY p.last_name, p.first_name, a.id
            """,
            (event_id,),
        ).fetchall()
        vehicles = db.execute(
            """SELECT id, display_label, checkpoint, status, permit_token, created_at
               FROM android_vehicle_permits WHERE event_id = ? ORDER BY display_label, id""",
            (event_id,),
        ).fetchall()
        counts = {
            "serviceConsumptions": int(db.execute("SELECT COUNT(*) AS c FROM android_service_consumptions WHERE event_id = ?", (event_id,)).fetchone()["c"] or 0),
            "leadCaptures": int(db.execute("SELECT COUNT(*) AS c FROM android_lead_captures WHERE event_id = ?", (event_id,)).fetchone()["c"] or 0),
            "vehicleAccesses": int(db.execute("SELECT COUNT(*) AS c FROM android_vehicle_access WHERE event_id = ? AND decision = 'ALLOW'", (event_id,)).fetchone()["c"] or 0),
        }
        return {
            "ok": True,
            "event": {"id": int(event["id"]), "name": event["name"]},
            "participants": [dict(row) for row in participants],
            "vehicles": [dict(row) for row in vehicles],
            "counts": counts,
        }

    def configure_resource(self, db, data: dict) -> dict:
        event_id = int(data.get("eventId") or 0)
        event = db.execute("SELECT id, organization_id FROM events WHERE id = ?", (event_id,)).fetchone()
        if not event:
            return {"ok": False, "error": "event_not_found"}
        organization_id = int(event["organization_id"] or 1)
        kind = str(data.get("kind") or "").strip().upper()
        now = _now_iso()
        if kind in {"SERVICE", "LEAD"}:
            accreditation_id = int(data.get("accreditationId") or 0)
            accreditation = db.execute(
                "SELECT id FROM accreditations WHERE id = ? AND event_id = ?",
                (accreditation_id, event_id),
            ).fetchone()
            if not accreditation:
                return {"ok": False, "error": "accreditation_not_found"}
            enabled = bool(data.get("enabled"))
            if kind == "SERVICE":
                status = "ACTIVE" if enabled else "REVOKED"
                quantity = max(1, min(100, int(data.get("quantity") or 1)))
                db.execute(
                    """
                    INSERT INTO android_service_entitlements
                        (organization_id, event_id, accreditation_id, entitlement_type, service_point,
                         status, quantity, consumed_quantity, created_at, updated_at)
                    VALUES (?, ?, ?, 'COFFEE', 'coffee-main', ?, ?, 0, ?, ?)
                    ON CONFLICT (event_id, accreditation_id, entitlement_type, service_point) DO UPDATE SET
                        status = excluded.status, quantity = excluded.quantity, updated_at = excluded.updated_at
                    """,
                    (organization_id, event_id, accreditation_id, status, quantity, now, now),
                )
            else:
                consent = "GRANTED" if enabled else "REVOKED"
                db.execute(
                    """
                    INSERT INTO android_lead_participants
                        (organization_id, event_id, accreditation_id, consent_status, source, created_at, updated_at)
                    VALUES (?, ?, ?, ?, 'admin', ?, ?)
                    ON CONFLICT (event_id, accreditation_id) DO UPDATE SET
                        consent_status = excluded.consent_status, source = excluded.source,
                        updated_at = excluded.updated_at
                    """,
                    (organization_id, event_id, accreditation_id, consent, now, now),
                )
        elif kind == "VEHICLE":
            label = str(data.get("displayLabel") or "").strip()[:120]
            if not label:
                return {"ok": False, "error": "display_label_required"}
            permit_id = int(data.get("permitId") or 0)
            status = "ACTIVE" if bool(data.get("enabled", True)) else "REVOKED"
            checkpoint = str(data.get("checkpoint") or "logistics-main").strip()[:80]
            if permit_id:
                db.execute(
                    """UPDATE android_vehicle_permits SET display_label = ?, checkpoint = ?, status = ?, updated_at = ?
                       WHERE id = ? AND event_id = ?""",
                    (label, checkpoint, status, now, permit_id, event_id),
                )
            else:
                token = f"BITORA:VEHICLE:{secrets.token_urlsafe(12).upper()}"
                db.execute(
                    """
                    INSERT INTO android_vehicle_permits
                        (organization_id, event_id, permit_token, token_hash, display_label, checkpoint, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (organization_id, event_id, token, _sha(token), label, checkpoint, status, now, now),
                )
        else:
            return {"ok": False, "error": "invalid_resource_kind"}
        return self.resources(db, event_id)

    def _apply_operation(self, db, device, operation_id: str, operation_type: str, payload: dict) -> str:
        event_id = int(device["event_id"])
        organization_id = int(device["organization_id"])
        allowed_profiles = {
            "ACCESS_ATTEMPT": {"ACCESS_FAST"},
            "PARTICIPANT_CHECK_IN": {"RECEPTION", "SELF_SERVICE"},
            "ENTITLEMENT_CONSUMPTION": {"SERVICE"},
            "LEAD_CAPTURE": {"LEAD_RETRIEVAL"},
            "VEHICLE_ACCESS": {"LOGISTICS"},
        }
        if str(device["profile"]).upper() not in allowed_profiles.get(operation_type, set()):
            raise ValueError("DEVICE_NOT_AUTHORIZED")
        payload_event_id = int(payload.get("event_id") or 0)
        if payload_event_id != event_id:
            raise ValueError("WRONG_EVENT")
        if str(payload.get("device_id") or "") != str(device["device_id"]):
            raise ValueError("WRONG_DEVICE")
        decision = str(payload.get("decision") or "DENY").upper()
        reason = str(payload.get("reason_code") or "")[:120]
        occurred_at = str(payload.get("device_timestamp") or _now_iso())[:80]
        if operation_type == "ACCESS_ATTEMPT":
            accreditation = self._accreditation_for_ref(db, event_id, str(payload.get("token_hash") or ""))
            token = accreditation["token"] if accreditation else ""
            conflict = "NO_CONFLICT"
            if decision == "ALLOW" and not accreditation:
                conflict = "UNKNOWN_CREDENTIAL"
            elif decision == "ALLOW" and str(accreditation["status"]).lower() not in {"active", "confirmed", "checked_in"}:
                conflict = "INACTIVE_ACCREDITATION"
            granted = decision == "ALLOW" and conflict == "NO_CONFLICT"
            db.execute(
                """
                INSERT INTO access_logs
                    (accreditation_id, event_id, token, operator, checkpoint, result, reason,
                     created_at, access_point, access_context)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'event_entry')
                """,
                (
                    int(accreditation["id"]) if accreditation else None, event_id, token,
                    f"android:{device['device_id']}", str(payload.get("door") or "main")[:80],
                    "granted" if granted else "denied", conflict if conflict != "NO_CONFLICT" else reason, occurred_at,
                    str(payload.get("zone") or "general")[:80],
                ),
            )
            if granted and accreditation:
                if str(payload.get("direction") or "ENTRY").upper() == "ENTRY":
                    db.execute(
                        """UPDATE accreditations SET checked_in_at = COALESCE(checked_in_at, ?),
                           checked_in_by = ?, access_count = access_count + 1 WHERE id = ?""",
                        (occurred_at, f"android:{device['device_id']}", int(accreditation["id"])),
                    )
                else:
                    db.execute("UPDATE accreditations SET access_count = access_count + 1 WHERE id = ?", (int(accreditation["id"]),))
            return conflict if decision == "ALLOW" else (reason or "DEVICE_DENIED")

        if operation_type == "PARTICIPANT_CHECK_IN":
            accreditation = self._accreditation_for_ref(db, event_id, str(payload.get("credential_ref") or ""))
            if decision != "ALLOW":
                return reason or "DEVICE_DENIED"
            if not accreditation:
                return "UNKNOWN_CREDENTIAL"
            if str(accreditation["status"]).lower() not in {"active", "confirmed", "checked_in"}:
                return "INACTIVE_ACCREDITATION"
            already = bool(accreditation["checked_in_at"])
            db.execute(
                """UPDATE accreditations SET checked_in_at = COALESCE(checked_in_at, ?),
                   checked_in_by = COALESCE(NULLIF(checked_in_by, ''), ?),
                   access_count = CASE WHEN checked_in_at IS NULL THEN access_count + 1 ELSE access_count END
                   WHERE id = ?""",
                (occurred_at, f"android:{device['device_id']}", int(accreditation["id"])),
            )
            db.execute(
                """INSERT INTO access_logs
                   (accreditation_id, event_id, token, operator, checkpoint, result, reason,
                    created_at, access_point, access_context)
                   VALUES (?, ?, ?, ?, 'check-in', 'granted', ?, ?, 'reception', 'event_entry')""",
                (int(accreditation["id"]), event_id, accreditation["token"], f"android:{device['device_id']}", reason or "CHECKED_IN", occurred_at),
            )
            return "ALREADY_CHECKED_IN" if already else "NO_CONFLICT"

        if operation_type == "ENTITLEMENT_CONSUMPTION":
            if decision != "ALLOW":
                return reason or "DEVICE_DENIED"
            accreditation = self._accreditation_for_ref(db, event_id, str(payload.get("credential_ref") or ""))
            if not accreditation:
                return "UNKNOWN_CREDENTIAL"
            if str(accreditation["status"]).lower() not in {"active", "confirmed", "checked_in"}:
                return "INACTIVE_ACCREDITATION"
            entitlement_type = str(payload.get("entitlement_type") or "COFFEE").upper()[:80]
            service_point = str(payload.get("service_point") or "coffee-main")[:80]
            quantity = max(1, min(100, int(payload.get("quantity") or 1)))
            entitlement = db.execute(
                """SELECT * FROM android_service_entitlements
                   WHERE event_id = ? AND accreditation_id = ? AND entitlement_type = ? AND service_point = ?""",
                (event_id, int(accreditation["id"]), entitlement_type, service_point),
            ).fetchone()
            if not entitlement or str(entitlement["status"]).upper() != "ACTIVE":
                return "NO_ENTITLEMENT"
            updated = db.execute(
                """UPDATE android_service_entitlements
                   SET consumed_quantity = consumed_quantity + ?, updated_at = ?
                   WHERE id = ? AND status = 'ACTIVE' AND consumed_quantity + ? <= quantity""",
                (quantity, _now_iso(), int(entitlement["id"]), quantity),
            )
            if updated.rowcount != 1:
                return "ALREADY_CONSUMED"
            db.execute(
                """INSERT INTO android_service_consumptions
                   (organization_id, event_id, entitlement_id, accreditation_id, device_id,
                    operation_id, quantity, service_point, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (organization_id, event_id, int(entitlement["id"]), int(accreditation["id"]), device["device_id"], operation_id, quantity, service_point, occurred_at),
            )
            return "NO_CONFLICT"

        if operation_type == "LEAD_CAPTURE":
            if decision != "ALLOW":
                return reason or "DEVICE_DENIED"
            accreditation = self._accreditation_for_ref(db, event_id, str(payload.get("participant_ref") or ""))
            if not accreditation:
                return "UNKNOWN_CREDENTIAL"
            if str(accreditation["status"]).lower() not in {"active", "confirmed", "checked_in"}:
                return "INACTIVE_ACCREDITATION"
            consent = db.execute(
                "SELECT consent_status FROM android_lead_participants WHERE event_id = ? AND accreditation_id = ?",
                (event_id, int(accreditation["id"])),
            ).fetchone()
            if not consent or str(consent["consent_status"]).upper() != "GRANTED":
                return "CONSENT_REQUIRED"
            duplicate = db.execute(
                "SELECT id FROM android_lead_captures WHERE event_id = ? AND device_id = ? AND accreditation_id = ?",
                (event_id, device["device_id"], int(accreditation["id"])),
            ).fetchone()
            if duplicate:
                return "ALREADY_CAPTURED"
            db.execute(
                """INSERT INTO android_lead_captures
                   (organization_id, event_id, accreditation_id, device_id, operation_id,
                    consent_verified, created_at) VALUES (?, ?, ?, ?, ?, 1, ?)""",
                (organization_id, event_id, int(accreditation["id"]), device["device_id"], operation_id, occurred_at),
            )
            return "NO_CONFLICT"

        if operation_type == "VEHICLE_ACCESS":
            permit_ref = str(payload.get("vehicle_ref") or "")
            permit = db.execute(
                "SELECT * FROM android_vehicle_permits WHERE event_id = ? AND token_hash = ?",
                (event_id, permit_ref),
            ).fetchone()
            conflict = "NO_CONFLICT"
            if decision == "ALLOW":
                if not permit:
                    conflict = "UNKNOWN_VEHICLE"
                elif str(permit["status"]).upper() != "ACTIVE":
                    conflict = "PERMIT_REVOKED"
                elif db.execute(
                    "SELECT id FROM android_vehicle_access WHERE event_id = ? AND permit_id = ? AND decision = 'ALLOW'",
                    (event_id, int(permit["id"])),
                ).fetchone():
                    conflict = "ALREADY_ENTERED"
            projected_decision = "DENY" if decision == "ALLOW" and conflict != "NO_CONFLICT" else decision
            db.execute(
                """INSERT INTO android_vehicle_access
                   (organization_id, event_id, permit_id, device_id, operation_id, checkpoint,
                    decision, reason_code, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (organization_id, event_id, int(permit["id"]) if permit else None, device["device_id"], operation_id, str(payload.get("checkpoint") or "logistics-main")[:80], projected_decision, conflict if conflict != "NO_CONFLICT" else reason, occurred_at),
            )
            return conflict

        raise ValueError("UNSUPPORTED_OPERATION")

    def _accreditation_for_ref(self, db, event_id: int, token_hash: str):
        if not token_hash:
            return None
        row = db.execute(
            """SELECT a.* FROM android_edge_credentials c
               JOIN accreditations a ON a.id = c.accreditation_id
               WHERE c.event_id = ? AND c.token_hash = ?""",
            (event_id, token_hash),
        ).fetchone()
        if row:
            return row
        candidates = db.execute("SELECT * FROM accreditations WHERE event_id = ?", (event_id,)).fetchall()
        for candidate in candidates:
            if hmac.compare_digest(_sha(str(candidate["token"])), token_hash):
                db.execute(
                    """INSERT INTO android_edge_credentials (event_id, accreditation_id, token_hash, updated_at)
                       VALUES (?, ?, ?, ?)
                       ON CONFLICT (event_id, accreditation_id) DO UPDATE SET
                           token_hash = excluded.token_hash, updated_at = excluded.updated_at""",
                    (event_id, int(candidate["id"]), token_hash, _now_iso()),
                )
                return candidate
        return None

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
