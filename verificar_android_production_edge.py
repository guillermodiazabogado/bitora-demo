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
        CREATE TABLE people (id INTEGER PRIMARY KEY, first_name TEXT, last_name TEXT);
        CREATE TABLE accreditations (
            id INTEGER PRIMARY KEY, event_id INTEGER, person_id INTEGER, token TEXT,
            status TEXT, checked_in_at TEXT
        );
        CREATE TABLE public_display_config (
            event_id INTEGER PRIMARY KEY, message TEXT, room_filter TEXT, refresh_seconds INTEGER
        );
        INSERT INTO organizations VALUES (1, 'BITORA');
        INSERT INTO events VALUES (18, 1, 'Production Event');
        INSERT INTO people VALUES (1, 'Test', 'Participant');
        INSERT INTO accreditations VALUES (1, 18, 1, 'BITORA:PROD:001', 'active', NULL);
        INSERT INTO public_display_config VALUES (18, 'Welcome', 'MAIN_HALL', 10);
        """
    )
    migration = Path("backend/migrations/036_android_edge_devices.sql").read_text(encoding="utf-8")
    db.executescript(migration.replace("BIGSERIAL", "INTEGER"))

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

    envelope = service.dataset(db, device)
    checksum = hashlib.sha256(envelope["payloadJson"].encode()).hexdigest()
    assert checksum == envelope["checksum"]
    signing_key = hashlib.sha256(exchanged["credentialToken"].encode()).hexdigest().encode()
    signed = f"{envelope['organizationId']}|{envelope['eventId']}|{envelope['revision']}|{checksum}|{envelope['expiresAtEpochSeconds']}"
    assert hmac.new(signing_key, signed.encode(), hashlib.sha256).hexdigest() == envelope["signature"]
    assert json.loads(envelope["payloadJson"])["participants"][0]["token"] == "BITORA:PROD:001"

    heartbeat = service.heartbeat(db, device, {"datasetRevision": envelope["revision"], "telemetry": {"queuePending": 0}})
    assert heartbeat["ok"]
    operation = {"operationId": "op-1", "idempotencyKey": "idem-1", "operationType": "ACCESS_ATTEMPT", "payload": {"decision": "ALLOW"}}
    first = service.sync(db, device, {"operations": [operation]})
    second = service.sync(db, device, {"operations": [operation]})
    assert first["results"][0]["status"] == "ACKNOWLEDGED"
    assert second["results"][0]["status"] == "DUPLICATE"
    assert service.telemetry(db)["status"] == "HEALTHY"
    service.revoke(db, {"deviceId": exchanged["deviceId"]})
    assert service.authenticate_device(db, exchanged["deviceId"], exchanged["credentialToken"]) is None
    assert service.telemetry(db)["status"] == "EMPTY"
    print("PASS android production edge pairing, dataset, heartbeat, sync and revoke")


if __name__ == "__main__":
    main()
