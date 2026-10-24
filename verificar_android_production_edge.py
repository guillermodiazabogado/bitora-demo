from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
from pathlib import Path

from backend.services.android_edge import AndroidEdgeService


def main() -> None:
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript(
        """
        PRAGMA foreign_keys = ON;
        CREATE TABLE organizations (id INTEGER PRIMARY KEY, name TEXT NOT NULL);
        CREATE TABLE events (id INTEGER PRIMARY KEY, organization_id INTEGER, name TEXT NOT NULL);
        CREATE TABLE people (id INTEGER PRIMARY KEY, first_name TEXT, last_name TEXT, email TEXT DEFAULT '');
        CREATE TABLE accreditations (
            id INTEGER PRIMARY KEY, event_id INTEGER, person_id INTEGER, token TEXT,
            status TEXT, checked_in_at TEXT, checked_in_by TEXT DEFAULT '', access_count INTEGER DEFAULT 0
        );
        CREATE TABLE access_logs (
            id INTEGER PRIMARY KEY, accreditation_id INTEGER, event_id INTEGER, token TEXT,
            operator TEXT DEFAULT '', checkpoint TEXT DEFAULT '', result TEXT, reason TEXT,
            created_at TEXT, activity_id INTEGER, operator_id INTEGER, access_point TEXT DEFAULT '',
            access_context TEXT DEFAULT 'event_entry'
        );
        CREATE TABLE audit_logs (id INTEGER PRIMARY KEY, event_id INTEGER, actor TEXT, action TEXT, entity_type TEXT, entity_id INTEGER, payload TEXT, created_at TEXT);
        CREATE TABLE public_display_config (
            event_id INTEGER PRIMARY KEY, message TEXT, room_filter TEXT, refresh_seconds INTEGER
        );
        INSERT INTO organizations VALUES (1, 'BITORA');
        INSERT INTO events VALUES (18, 1, 'Production Event');
        INSERT INTO people VALUES (1, 'Test', 'Participant', 'test@example.com');
        INSERT INTO accreditations VALUES (1, 18, 1, 'BITORA:PROD:001', 'active', NULL, '', 0);
        INSERT INTO public_display_config VALUES (18, 'Welcome', 'MAIN_HALL', 10);
        """
    )
    migration = Path("backend/migrations/036_android_edge_devices.sql").read_text(encoding="utf-8")
    db.executescript(migration.replace("BIGSERIAL", "INTEGER"))
    domains = Path("backend/migrations/037_android_operational_domains.sql").read_text(encoding="utf-8")
    db.executescript(domains.replace("BIGSERIAL", "INTEGER"))

    service = AndroidEdgeService("https://bitora.example")
    code = "BTR-ABCD-1234"
    nonce = "nonce-with-enough-entropy"
    requested = service.register_pairing(db, {"pairingCode": code, "nonce": nonce, "deviceKind": "OPERATION", "requestedProfile": "ACCESS_FAST", "softwareVersion": "1.0"})
    assert requested["ok"] and requested["status"] == "PENDING"
    approved = service.approve(db, {"pairingCode": code, "eventId": 18})
    assert approved["ok"] and approved["status"] == "APPROVED"
    exchanged = service.exchange(db, {"pairingCode": code, "nonce": nonce})
    assert exchanged["ok"] and exchanged["credentialToken"]
    device = service.authenticate_device(db, exchanged["deviceId"], exchanged["credentialToken"])
    assert device is not None

    devices = {"ACCESS_FAST": (device, exchanged)}
    for profile, pairing_code in {
        "RECEPTION": "BTR-RECP-0001",
        "SERVICE": "BTR-SRVC-0001",
        "LEAD_RETRIEVAL": "BTR-LEAD-0001",
        "LOGISTICS": "BTR-LOGI-0001",
    }.items():
        profile_nonce = f"nonce-for-{profile}-device"
        assert service.register_pairing(db, {"pairingCode": pairing_code, "nonce": profile_nonce, "deviceKind": "OPERATION", "requestedProfile": profile})["ok"]
        assert service.approve(db, {"pairingCode": pairing_code, "eventId": 18, "profile": profile})["ok"]
        identity = service.exchange(db, {"pairingCode": pairing_code, "nonce": profile_nonce})
        devices[profile] = (service.authenticate_device(db, identity["deviceId"], identity["credentialToken"]), identity)

    service.configure_resource(db, {"kind": "SERVICE", "eventId": 18, "accreditationId": 1, "enabled": True, "quantity": 1})
    service.configure_resource(db, {"kind": "LEAD", "eventId": 18, "accreditationId": 1, "enabled": True})
    resources = service.configure_resource(db, {"kind": "VEHICLE", "eventId": 18, "displayLabel": "Vehicle 01", "enabled": True})
    vehicle_token = resources["vehicles"][0]["permit_token"]

    envelope = service.dataset(db, device)
    checksum = hashlib.sha256(envelope["payloadJson"].encode()).hexdigest()
    assert checksum == envelope["checksum"]
    signing_key = hashlib.sha256(exchanged["credentialToken"].encode()).hexdigest().encode()
    signed = f"{envelope['organizationId']}|{envelope['eventId']}|{envelope['revision']}|{checksum}|{envelope['expiresAtEpochSeconds']}"
    assert hmac.new(signing_key, signed.encode(), hashlib.sha256).hexdigest() == envelope["signature"]
    payload = json.loads(envelope["payloadJson"])
    assert payload["credentials"][0]["token"] == "BITORA:PROD:001"
    assert payload["participants"] == []
    assert json.loads(service.dataset(db, devices["SERVICE"][0])["payloadJson"])["service_entitlements"][0]["available"] == 1
    assert json.loads(service.dataset(db, devices["LEAD_RETRIEVAL"][0])["payloadJson"])["lead_participants"][0]["lead_consent"] is True
    assert json.loads(service.dataset(db, devices["LOGISTICS"][0])["payloadJson"])["vehicle_permits"][0]["token"] == vehicle_token

    heartbeat = service.heartbeat(db, device, {"datasetRevision": envelope["revision"], "telemetry": {"queuePending": 0}})
    assert heartbeat["ok"]
    credential_ref = hashlib.sha256("BITORA:PROD:001".encode()).hexdigest()
    def common(profile: str) -> dict:
        return {"event_id": 18, "device_id": devices[profile][1]["deviceId"], "decision": "ALLOW", "device_timestamp": "2026-10-24T12:00:00+00:00"}

    operations = {
        "ACCESS_FAST": {"operationId": "op-access", "idempotencyKey": "idem-access", "operationType": "ACCESS_ATTEMPT", "payload": {**common("ACCESS_FAST"), "token_hash": credential_ref, "door": "main", "zone": "general", "direction": "ENTRY", "reason_code": "ACCESS_ALLOWED"}},
        "RECEPTION": {"operationId": "op-checkin", "idempotencyKey": "idem-checkin", "operationType": "PARTICIPANT_CHECK_IN", "payload": {**common("RECEPTION"), "credential_ref": credential_ref, "reason_code": "CHECKED_IN"}},
        "SERVICE": {"operationId": "op-service", "idempotencyKey": "idem-service", "operationType": "ENTITLEMENT_CONSUMPTION", "payload": {**common("SERVICE"), "credential_ref": credential_ref, "entitlement_type": "COFFEE", "service_point": "coffee-main", "quantity": 1}},
        "LEAD_RETRIEVAL": {"operationId": "op-lead", "idempotencyKey": "idem-lead", "operationType": "LEAD_CAPTURE", "payload": {**common("LEAD_RETRIEVAL"), "participant_ref": credential_ref, "consent_verified": True}},
        "LOGISTICS": {"operationId": "op-vehicle", "idempotencyKey": "idem-vehicle", "operationType": "VEHICLE_ACCESS", "payload": {**common("LOGISTICS"), "vehicle_ref": hashlib.sha256(vehicle_token.encode()).hexdigest(), "checkpoint": "logistics-main"}},
    }
    results = [service.sync(db, devices[profile][0], {"operations": [operation]})["results"][0] for profile, operation in operations.items()]
    second = service.sync(db, device, {"operations": [operations["ACCESS_FAST"]]})
    assert all(item["status"] == "ACKNOWLEDGED" for item in results)
    assert second["results"][0]["status"] == "DUPLICATE"
    assert db.execute("SELECT checked_in_at FROM accreditations WHERE id = 1").fetchone()["checked_in_at"]
    assert db.execute("SELECT COUNT(*) AS c FROM access_logs").fetchone()["c"] == 2
    assert db.execute("SELECT COUNT(*) AS c FROM android_service_consumptions").fetchone()["c"] == 1
    assert db.execute("SELECT COUNT(*) AS c FROM android_lead_captures").fetchone()["c"] == 1
    assert db.execute("SELECT COUNT(*) AS c FROM android_vehicle_access WHERE decision = 'ALLOW'").fetchone()["c"] == 1
    assert service.resources(db, 18)["counts"] == {"serviceConsumptions": 1, "leadCaptures": 1, "vehicleAccesses": 1}
    for profile_device, _identity in devices.values():
        service.heartbeat(db, profile_device, {"datasetRevision": envelope["revision"], "telemetry": {"queuePending": 0}})
    assert service.telemetry(db)["status"] == "HEALTHY"
    for _profile_device, identity in devices.values():
        service.revoke(db, {"deviceId": identity["deviceId"]})
    assert service.authenticate_device(db, exchanged["deviceId"], exchanged["credentialToken"]) is None
    assert service.telemetry(db)["status"] == "EMPTY"
    print("PASS android production edge pairing, dataset, heartbeat, sync and revoke")


if __name__ == "__main__":
    main()
