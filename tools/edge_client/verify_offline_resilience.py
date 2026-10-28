from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tools.edge_client import DatasetVerificationError, EdgeClient, EdgeScope


KEY_ID = "field-readiness-key"
SIGNING_KEY = "field-readiness-signing-secret"
DEVICE_SECRET = "field-readiness-device-secret"


class MutableClock:
    def __init__(self, value: float = 100_000.0) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


def signed_dataset(payload: dict, *, signature_overrides: dict | None = None) -> dict:
    payload_json = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    checksum = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
    signature = {
        "algorithm": "HMAC-SHA256",
        "key_id": KEY_ID,
        "status": "ACTIVE",
        "signature": hmac.new(SIGNING_KEY.encode(), payload_json.encode(), hashlib.sha256).hexdigest(),
    }
    signature.update(signature_overrides or {})
    return {
        "revision": f"field-{checksum[:20]}",
        "payload_json": payload_json,
        "checksum": checksum,
        "metadata_json": json.dumps({"signature": signature}, sort_keys=True),
    }


class ControlledTransport:
    def __init__(self) -> None:
        self.online = False
        self.revoked = False
        self.partial_ack = False
        self.inject_unknown_ack = False
        self.calls: list[list[int]] = []
        self.received_idempotency: set[str] = set()

    def heartbeat(self, *, scope, secret, payload):
        self._authorize(scope, secret)
        if not self.online:
            raise ConnectionError("offline")
        return {"ok": True, "queue_depth": payload["queue_depth"]}

    def sync(self, *, scope, secret, operations):
        self._authorize(scope, secret)
        if not self.online:
            raise ConnectionError("offline")
        sequences = [int(item["device_sequence"]) for item in operations]
        assert sequences == sorted(sequences), "el transporte recibio operaciones fuera de orden"
        self.calls.append(sequences)
        accepted = operations
        if self.partial_ack:
            accepted = operations[::2]
            self.partial_ack = False
        for operation in accepted:
            self.received_idempotency.add(operation["idempotency_key"])
        acknowledged = [item["operation_id"] for item in accepted]
        if self.inject_unknown_ack:
            acknowledged.extend(["unknown-operation", "unknown-operation"])
            self.inject_unknown_ack = False
        return {"ok": True, "acknowledged_operation_ids": acknowledged}

    def _authorize(self, scope, secret) -> None:
        assert scope == EdgeScope(organization_id=7, event_id=11, device_id=13)
        assert secret == DEVICE_SECRET
        if self.revoked:
            raise PermissionError("device revoked")


def expect_dataset_failure(client: EdgeClient, item: dict, status: str) -> None:
    try:
        client.activate_dataset(item)
    except DatasetVerificationError as exc:
        assert str(exc) == status, (str(exc), status)
    else:
        raise AssertionError(f"dataset invalido aceptado: {status}")


def database_counts(path: Path) -> dict[str, int]:
    with sqlite3.connect(path) as db:
        return {
            status: int(db.execute("SELECT COUNT(*) FROM operations WHERE status=?", (status,)).fetchone()[0])
            for status in ("PENDING", "RETRY", "ACKED")
        }


def verify_bounded_backoff() -> dict:
    tmp_parent = Path.cwd() / "tmp"
    tmp_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="bitora-edge-backoff-", dir=tmp_parent, ignore_cleanup_errors=True) as root:
        database = Path(root) / "edge.sqlite3"
        clock = MutableClock()
        transport = ControlledTransport()
        client = EdgeClient(
            database,
            scope=EdgeScope(organization_id=7, event_id=11, device_id=13),
            device_secret=DEVICE_SECRET,
            signing_keys={KEY_ID: SIGNING_KEY},
            transport=transport,
            clock=clock,
        )
        client.enqueue("VALIDATE_ACCESS", {"direction": "ENTRY"}, idempotency_key="backoff-operation")
        observed: list[float] = []
        for attempt in range(1, 13):
            result = client.sync(limit=1)
            assert not result["ok"] and result["sent"] == 1
            with sqlite3.connect(database) as db:
                attempts, next_attempt_at = db.execute(
                    "SELECT attempts,next_attempt_at FROM operations WHERE idempotency_key='backoff-operation'"
                ).fetchone()
            expected = min(300.0, 0.5 * (2 ** min(attempt - 1, 10)))
            delay = float(next_attempt_at) - clock()
            assert attempts == attempt and abs(delay - expected) < 0.0001, (attempts, delay, expected)
            observed.append(delay)
            clock.advance(expected)
        client.close()
        assert observed[-2:] == [300.0, 300.0]
        return {"attempts": len(observed), "delays_seconds": observed, "maximum_seconds": max(observed)}


def verify_dataset_matrix(client: EdgeClient) -> None:
    for credential_count in (0, 500, 3_000, 10_000):
        item = signed_dataset(
            {
                "event_id": 11,
                "credentials": [{"id": index, "state": "OUTSIDE"} for index in range(credential_count)],
            }
        )
        result = client.activate_dataset(item)
        assert result["ok"] and result["revision"] == item["revision"]

    valid = signed_dataset({"event_id": 11, "credentials": [1]})
    corrupt = dict(valid)
    corrupt["payload_json"] += " "
    expect_dataset_failure(client, corrupt, "CHECKSUM_MISMATCH")

    bad_signature = signed_dataset({"event_id": 11}, signature_overrides={"signature": "0" * 64})
    expect_dataset_failure(client, bad_signature, "SIGNATURE_MISMATCH")
    expect_dataset_failure(client, signed_dataset({"event_id": 11}, signature_overrides={"status": "REVOKED"}), "KEY_INACTIVE")
    expect_dataset_failure(client, signed_dataset({"event_id": 11}, signature_overrides={"key_id": "unknown"}), "UNKNOWN_KEY")
    expect_dataset_failure(client, signed_dataset({"event_id": 11}, signature_overrides={"expires_at": "invalid"}), "KEY_EXPIRY_INVALID")
    expired = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    expect_dataset_failure(client, signed_dataset({"event_id": 11}, signature_overrides={"expires_at": expired}), "KEY_EXPIRED")


def enqueue_concurrently(client: EdgeClient, count: int) -> None:
    def enqueue(index: int) -> None:
        created = client.enqueue(
            "VALIDATE_ACCESS",
            {"token_hash": f"field-hash-{index}", "direction": "ENTRY" if index % 2 == 0 else "EXIT"},
            local_decision={"decision": "ALLOW", "reason_code": "VALID"},
            idempotency_key=f"field-operation-{index}",
            correlation_id=f"field-correlation-{index}",
        )
        assert created["idempotency_key"] == f"field-operation-{index}"

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(enqueue, range(count)))


def verify_profile(operation_count: int) -> dict:
    tmp_parent = Path.cwd() / "tmp"
    tmp_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f"bitora-edge-{operation_count}-", dir=tmp_parent, ignore_cleanup_errors=True) as root:
        database = Path(root) / "edge.sqlite3"
        clock = MutableClock()
        transport = ControlledTransport()
        scope = EdgeScope(organization_id=7, event_id=11, device_id=13)
        client = EdgeClient(
            database,
            scope=scope,
            device_secret=DEVICE_SECRET,
            signing_keys={KEY_ID: SIGNING_KEY},
            transport=transport,
            clock=clock,
        )
        verify_dataset_matrix(client)
        enqueue_concurrently(client, operation_count)
        assert client.queue_depth == operation_count
        assert client.last_sequence == operation_count
        assert database_counts(database) == {"PENDING": operation_count, "RETRY": 0, "ACKED": 0}

        # Local idempotency must not allocate a new sequence or overwrite payload.
        duplicate = client.enqueue("VALIDATE_ACCESS", {"ignored": True}, idempotency_key="field-operation-0")
        assert duplicate["duplicate"] and client.last_sequence == operation_count

        first_batch = min(operation_count, 250)
        failed_sent = 0
        for _ in range((operation_count + 249) // 250):
            failed = client.sync(limit=250)
            assert not failed["ok"]
            failed_sent += failed["sent"]
        assert failed_sent == operation_count
        assert client.pending(limit=250) == [], "backoff no fue respetado"
        clock.advance(0.49)
        assert client.pending(limit=250) == [], "reintento prematuro"
        clock.advance(0.01)

        # A revoked device retains its durable queue but cannot synchronize.
        transport.online = True
        transport.revoked = True
        revoked = client.sync(limit=250)
        assert not revoked["ok"] and revoked["acknowledged"] == 0
        client.close()

        # Simulate process restart while offline/revoked. Queue, attempts, dataset
        # and monotonic sequence must survive the new client object.
        restarted = EdgeClient(
            database,
            scope=scope,
            device_secret=DEVICE_SECRET,
            signing_keys={KEY_ID: SIGNING_KEY},
            transport=transport,
            clock=clock,
        )
        assert restarted.queue_depth == operation_count
        assert restarted.last_sequence == operation_count
        assert restarted.dataset_revision.startswith("field-")

        clock.advance(1.0)
        transport.revoked = False
        transport.partial_ack = True
        transport.inject_unknown_ack = True
        partial = restarted.sync(limit=250)
        # Unknown acknowledgements are ignored and a partial batch is not PASS.
        expected_partial = (first_batch + 1) // 2
        assert not partial["ok"]
        assert partial["acknowledged"] == expected_partial

        # Drain every deferred/retried operation. Advancing the deterministic
        # clock exercises bounded backoff without sleeping in wall-clock time.
        for _ in range(100):
            if restarted.queue_depth == 0:
                break
            clock.advance(300.0)
            restarted.sync(limit=250)
        assert restarted.queue_depth == 0
        counts = database_counts(database)
        assert counts == {"PENDING": 0, "RETRY": 0, "ACKED": operation_count}, counts
        assert len(transport.received_idempotency) == operation_count
        assert all(call == sorted(call) for call in transport.calls)
        heartbeat = restarted.heartbeat(sync_status="ONLINE")
        assert heartbeat == {"ok": True, "queue_depth": 0}
        restarted.close()

        return {
            "operations_created": operation_count,
            "operations_persisted": sum(counts.values()),
            "operations_synchronized": counts["ACKED"],
            "operations_pending": counts["PENDING"] + counts["RETRY"],
            "operations_lost": operation_count - sum(counts.values()),
            "duplicates_created": 0,
            "sync_calls": len(transport.calls),
        }


def main() -> None:
    results = [verify_profile(count) for count in (100, 500, 2_000)]
    assert all(item["operations_lost"] == 0 for item in results)
    assert all(item["operations_created"] == item["operations_synchronized"] for item in results)
    print(json.dumps({"ok": True, "backoff": verify_bounded_backoff(), "profiles": results}, sort_keys=True))


if __name__ == "__main__":
    main()
