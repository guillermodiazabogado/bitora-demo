from __future__ import annotations

import hashlib
import hmac
import io
import json
import logging
import tempfile
from pathlib import Path

from tools.edge_client import DatasetVerificationError, EdgeClient, EdgeScope


KEY_ID = "verification-key"
SIGNING_KEY = "verification-signing-secret"
DEVICE_SECRET = "device-secret-must-never-appear"


def dataset(payload: dict) -> dict:
    payload_json = json.dumps(payload, ensure_ascii=True, sort_keys=True)
    checksum = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
    signature = hmac.new(SIGNING_KEY.encode("utf-8"), payload_json.encode("utf-8"), hashlib.sha256).hexdigest()
    return {
        "revision": f"v58-test-{checksum[:16]}",
        "payload_json": payload_json,
        "checksum": checksum,
        "metadata_json": json.dumps({"signature": {"algorithm": "HMAC-SHA256", "key_id": KEY_ID, "status": "ACTIVE", "signature": signature}}, sort_keys=True),
    }


class ReconnectingTransport:
    def __init__(self) -> None:
        self.online = False
        self.seen_idempotency: set[str] = set()
        self.heartbeat_payload = None

    def heartbeat(self, *, scope, secret, payload):
        assert secret == DEVICE_SECRET and scope.device_id == 3
        self.heartbeat_payload = dict(payload)
        return {"ok": True}

    def sync(self, *, scope, secret, operations):
        assert secret == DEVICE_SECRET and scope.event_id == 2
        if not self.online:
            raise ConnectionError("offline")
        acknowledged = []
        for operation in operations:
            self.seen_idempotency.add(operation["idempotency_key"])
            acknowledged.append(operation["operation_id"])
        return {"ok": True, "acknowledged_operation_ids": acknowledged}


def main() -> None:
    temp_parent = Path.cwd() / "tmp"
    temp_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="bitora-edge-reference-", dir=temp_parent, ignore_cleanup_errors=True) as root:
        database = Path(root) / "edge.sqlite3"
        transport = ReconnectingTransport()
        stream = io.StringIO()
        logger = logging.getLogger("bitora.edge.reference.verifier")
        logger.handlers.clear()
        logger.setLevel(logging.INFO)
        logger.addHandler(logging.StreamHandler(stream))
        scope = EdgeScope(organization_id=1, event_id=2, device_id=3)

        client = EdgeClient(database, scope=scope, device_secret=DEVICE_SECRET, signing_keys={KEY_ID: SIGNING_KEY}, transport=transport, logger=logger, clock=lambda: 10_000.0)
        active = client.activate_dataset(dataset({"event_id": 2, "credentials": [], "entitlements": []}))
        assert active["ok"] and client.dataset_revision.startswith("v58-test-")

        corrupt = dataset({"event_id": 2, "credentials": [1]})
        corrupt["payload_json"] += " "
        try:
            client.activate_dataset(corrupt)
        except DatasetVerificationError as exc:
            assert str(exc) == "CHECKSUM_MISMATCH"
        else:
            raise AssertionError("dataset corrupto aceptado")

        bad_signature = dataset({"event_id": 2, "credentials": [2]})
        signature_metadata = json.loads(bad_signature["metadata_json"])
        signature_metadata["signature"]["signature"] = "0" * 64
        bad_signature["metadata_json"] = json.dumps(signature_metadata, sort_keys=True)
        try:
            client.activate_dataset(bad_signature)
        except DatasetVerificationError as exc:
            assert str(exc) == "SIGNATURE_MISMATCH"
        else:
            raise AssertionError("firma de dataset invalida aceptada")

        for index in range(100):
            operation = client.enqueue(
                "VALIDATE_ACCESS",
                {"token_hash": f"hash-{index}", "direction": "ENTRY"},
                local_decision={"decision": "ALLOW", "reason_code": "VALID"},
                idempotency_key=f"offline-{index}",
            )
            assert operation["device_sequence"] == index + 1
        duplicate = client.enqueue("VALIDATE_ACCESS", {"ignored": True}, idempotency_key="offline-50")
        assert duplicate["duplicate"] and client.queue_depth == 100 and client.last_sequence == 100

        failed = client.sync(limit=100)
        assert not failed["ok"] and client.queue_depth == 100
        assert DEVICE_SECRET not in stream.getvalue() and SIGNING_KEY not in stream.getvalue()
        client.close()

        # A new process/client object observes the same monotonic sequence and queue.
        restarted = EdgeClient(database, scope=scope, device_secret=DEVICE_SECRET, signing_keys={KEY_ID: SIGNING_KEY}, transport=transport, logger=logger, clock=lambda: 20_000.0)
        assert restarted.queue_depth == 100 and restarted.last_sequence == 100
        transport.online = True
        synced = restarted.sync(limit=100)
        assert synced == {"ok": True, "sent": 100, "acknowledged": 100, "pending": 0}
        assert len(transport.seen_idempotency) == 100
        heartbeat = restarted.heartbeat()
        assert heartbeat["ok"] and transport.heartbeat_payload["queue_depth"] == 0
        assert transport.heartbeat_payload["dataset_revision"] == restarted.dataset_revision
        assert DEVICE_SECRET not in stream.getvalue() and SIGNING_KEY not in stream.getvalue()
        restarted.close()

    print("OK: Edge reference client durable queue, restart, reconnect, idempotency, dataset verification and secret redaction")


if __name__ == "__main__":
    main()
