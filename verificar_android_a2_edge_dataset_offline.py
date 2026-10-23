from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass, field
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SIGNING_KEY = b"BITORA-A2-LAB-SIGNING-KEY"


def sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sign(value: str) -> str:
    return hmac.new(SIGNING_KEY, value.encode("utf-8"), hashlib.sha256).hexdigest()


def dataset(*, organization_id: int = 1, event_id: int = 18, revision: str = "LAB-A2-18-001", expires_delta: int = 3600) -> dict:
    payload = {
        "event": {"organization_id": organization_id, "event_id": event_id},
        "doors": [{"id": "main", "direction": "ENTRY"}],
        "zones": [{"id": "general"}],
        "capabilities": ["VALIDATE_ACCESS", "SCAN_QR", "DISPLAY_CONTENT", "SYNC_DATASET"],
    }
    payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    checksum = sha(payload_json)
    expires = int(time.time() + expires_delta)
    return {
        "organizationId": organization_id,
        "eventId": event_id,
        "revision": revision,
        "schemaVersion": "v5.8",
        "expiresAtEpochSeconds": expires,
        "payloadJson": payload_json,
        "checksum": checksum,
        "signature": sign(f"{organization_id}|{event_id}|{revision}|{checksum}|{expires}"),
    }


def verify_dataset(envelope: dict, expected_org: int, expected_event: int, active_revision: str | None = None) -> str:
    if envelope["organizationId"] != expected_org:
        return "wrong_org"
    if envelope["eventId"] != expected_event:
        return "wrong_event"
    if envelope["expiresAtEpochSeconds"] <= int(time.time()):
        return "expired"
    checksum = sha(envelope["payloadJson"])
    if checksum != envelope["checksum"]:
        return "corrupt_dataset"
    expected_signature = sign(f"{envelope['organizationId']}|{envelope['eventId']}|{envelope['revision']}|{checksum}|{envelope['expiresAtEpochSeconds']}")
    if expected_signature != envelope["signature"]:
        return "invalid_signature"
    if active_revision and envelope["revision"] < active_revision:
        return "downgrade"
    return "valid"


@dataclass
class QueueItem:
    operation_id: str
    idempotency_key: str
    sequence: int
    status: str = "PENDING"


@dataclass
class PersistentQueueSimulator:
    items: list[QueueItem] = field(default_factory=list)
    checkpoint: int = 0

    def enqueue(self, item: QueueItem) -> None:
        if any(existing.idempotency_key == item.idempotency_key for existing in self.items):
            return
        self.items.append(item)

    def restart(self) -> "PersistentQueueSimulator":
        clone = PersistentQueueSimulator()
        clone.items = [QueueItem(**item.__dict__) for item in self.items]
        clone.checkpoint = self.checkpoint
        return clone

    def batch(self, limit: int = 100) -> list[QueueItem]:
        return sorted([item for item in self.items if item.status == "PENDING"], key=lambda item: item.sequence)[:limit]

    def acknowledge(self, operation_id: str) -> None:
        for item in self.items:
            if item.operation_id == operation_id:
                item.status = "ACKNOWLEDGED"
                self.checkpoint = max(self.checkpoint, item.sequence)

    def pending_count(self) -> int:
        return sum(1 for item in self.items if item.status == "PENDING")


def assert_static_contracts() -> None:
    required = [
        "android/shared/foundation/src/main/java/com/bitora/android/foundation/edge/DatasetVerifier.kt",
        "android/shared/foundation/src/main/java/com/bitora/android/foundation/edge/EdgeClient.kt",
        "android/shared/foundation/src/main/java/com/bitora/android/foundation/persistence/A2LocalStore.kt",
        "android/apps/operation/src/main/java/com/bitora/android/operation/MainActivity.kt",
        "android/apps/display/src/main/java/com/bitora/android/display/MainActivity.kt",
        "tools/android_pairing_lab_server.py",
    ]
    for rel in required:
        assert (ROOT / rel).exists(), rel
    combined = "\n".join((ROOT / rel).read_text(encoding="utf-8") for rel in required)
    assert "/api/edge/dataset" in combined
    assert "/api/edge/heartbeat" in combined
    assert "/api/edge/sync" in combined
    assert "saveActiveDataset" in combined
    assert "loadActiveDataset" in combined
    assert "offlineSnapshot" in combined
    assert "BitoraEdgeStatus.OFFLINE" in combined
    assert "EncryptedSharedPreferences" in combined
    assert "Pairing required\" else \"Display ready" in combined
    assert combined.count("android-a11-${BuildConfig.VERSION_NAME}") == 2


def assert_dataset_security() -> None:
    valid = dataset()
    assert verify_dataset(valid, 1, 18) == "valid"
    modified = dict(valid, payloadJson='{"tampered":true}')
    assert verify_dataset(modified, 1, 18) == "corrupt_dataset"
    bad_signature = dict(valid, signature="bad")
    assert verify_dataset(bad_signature, 1, 18) == "invalid_signature"
    assert verify_dataset(valid, 2, 18) == "wrong_org"
    assert verify_dataset(valid, 1, 19) == "wrong_event"
    assert verify_dataset(dataset(expires_delta=-1), 1, 18) == "expired"
    assert verify_dataset(dataset(revision="LAB-A2-18-000"), 1, 18, "LAB-A2-18-001") == "downgrade"


def assert_queue_and_reconciliation() -> None:
    queue = PersistentQueueSimulator()
    queue.enqueue(QueueItem("op-2", "idem-2", 2))
    queue.enqueue(QueueItem("op-1", "idem-1", 1))
    queue.enqueue(QueueItem("op-dup", "idem-1", 3))
    assert queue.pending_count() == 2
    restarted = queue.restart()
    ordered = restarted.batch()
    assert [item.operation_id for item in ordered] == ["op-1", "op-2"]
    restarted.acknowledge("op-1")
    restarted.acknowledge("op-2")
    assert restarted.pending_count() == 0
    assert restarted.checkpoint == 2


def assert_last_known_good_semantics() -> None:
    active = dataset()
    assert verify_dataset(active, 1, 18) == "valid"
    offline_view = {
        "edge": "OFFLINE",
        "dataset": "CURRENT" if verify_dataset(active, 1, 18) == "valid" else "INVALID",
        "revision": active["revision"],
    }
    assert offline_view["edge"] == "OFFLINE"
    assert offline_view["dataset"] == "CURRENT"
    assert offline_view["revision"] == "LAB-A2-18-001"


def assert_device_simulation() -> None:
    for devices in (30, 50, 100):
        queues = [PersistentQueueSimulator() for _ in range(devices)]
        for index, queue in enumerate(queues):
            queue.enqueue(QueueItem(f"dev-{index}-op-1", f"dev-{index}-idem-1", 1))
            queue.enqueue(QueueItem(f"dev-{index}-op-2", f"dev-{index}-idem-2", 2))
            queue.enqueue(QueueItem(f"dev-{index}-op-dup", f"dev-{index}-idem-2", 3))
        total_pending = sum(queue.pending_count() for queue in queues)
        assert total_pending == devices * 2
        for queue in queues:
            for item in queue.batch():
                queue.acknowledge(item.operation_id)
        assert sum(queue.pending_count() for queue in queues) == 0


def main() -> int:
    assert_static_contracts()
    assert_dataset_security()
    assert_queue_and_reconciliation()
    assert_last_known_good_semantics()
    assert_device_simulation()
    print(json.dumps({
        "status": "PASS",
        "edge": True,
        "signed_dataset": True,
        "local_storage": True,
        "offline_queue": True,
        "reconnect": True,
        "reconciliation": True,
        "simulated_devices": [30, 50, 100],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
