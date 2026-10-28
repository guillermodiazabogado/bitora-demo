from __future__ import annotations

import hashlib
import hmac
import json
import logging
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Protocol


class EdgeClientError(RuntimeError):
    pass


class DatasetVerificationError(EdgeClientError):
    pass


@dataclass(frozen=True)
class EdgeScope:
    organization_id: int
    event_id: int
    device_id: int

    def validate(self) -> None:
        if min(self.organization_id, self.event_id, self.device_id) <= 0:
            raise EdgeClientError("organization_id, event_id y device_id son obligatorios")


class EdgeTransport(Protocol):
    def heartbeat(self, *, scope: EdgeScope, secret: str, payload: Mapping[str, Any]) -> Mapping[str, Any]: ...

    def sync(self, *, scope: EdgeScope, secret: str, operations: list[dict[str, Any]]) -> Mapping[str, Any]: ...


class _SecretRedactionFilter(logging.Filter):
    def __init__(self, secrets: set[str]) -> None:
        super().__init__()
        self.secrets = secrets

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        for secret in tuple(self.secrets):
            if secret:
                message = message.replace(secret, "[REDACTED]")
        record.msg = message
        record.args = ()
        return True


class EdgeClient:
    """Durable, transport-neutral reference client for the V5.8 device API."""

    def __init__(
        self,
        database_path: str | Path,
        *,
        scope: EdgeScope,
        device_secret: str,
        signing_keys: Mapping[str, str],
        transport: EdgeTransport | None = None,
        logger: logging.Logger | None = None,
        clock=time.time,
    ) -> None:
        scope.validate()
        if not str(device_secret or ""):
            raise EdgeClientError("device_secret es obligatorio")
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.scope = scope
        self._secret = str(device_secret)
        self.signing_keys = {str(key): str(value) for key, value in signing_keys.items() if key and value}
        self.transport = transport
        self.clock = clock
        self._lock = threading.RLock()
        self.logger = logger or logging.getLogger(f"bitora.edge.reference.{scope.device_id}")
        self._redaction_filter = _SecretRedactionFilter({self._secret, *self.signing_keys.values()})
        self.logger.addFilter(self._redaction_filter)
        self._initialize()

    def close(self) -> None:
        self.logger.removeFilter(self._redaction_filter)

    def activate_dataset(self, dataset: Mapping[str, Any]) -> dict[str, Any]:
        verification = self.verify_dataset(dataset, self.signing_keys)
        if not verification["ok"]:
            raise DatasetVerificationError(str(verification["status"]))
        revision = str(dataset.get("revision") or "").strip()
        if not revision:
            raise DatasetVerificationError("REVISION_MISSING")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("UPDATE datasets SET status = 'RETIRED' WHERE status = 'ACTIVE'")
            db.execute(
                """
                INSERT INTO datasets(revision, payload_json, checksum, metadata_json, status, activated_at)
                VALUES (?, ?, ?, ?, 'ACTIVE', ?)
                ON CONFLICT(revision) DO UPDATE SET payload_json=excluded.payload_json,
                    checksum=excluded.checksum, metadata_json=excluded.metadata_json,
                    status='ACTIVE', activated_at=excluded.activated_at
                """,
                (
                    revision,
                    str(dataset.get("payload_json") or "{}"),
                    str(dataset.get("checksum") or ""),
                    str(dataset.get("metadata_json") or "{}"),
                    self._now_iso(),
                ),
            )
            db.execute("INSERT INTO state(key,value) VALUES('dataset_revision',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (revision,))
            db.commit()
        return {"ok": True, "revision": revision, "verification": verification}

    @staticmethod
    def verify_dataset(dataset: Mapping[str, Any], signing_keys: Mapping[str, str], *, now: datetime | None = None) -> dict[str, Any]:
        payload_json = str(dataset.get("payload_json") or "{}")
        expected_checksum = str(dataset.get("checksum") or "")
        actual_checksum = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
        if not expected_checksum or not hmac.compare_digest(actual_checksum, expected_checksum):
            return {"ok": False, "status": "CHECKSUM_MISMATCH", "checksum": actual_checksum}
        try:
            metadata = json.loads(str(dataset.get("metadata_json") or "{}"))
        except json.JSONDecodeError:
            return {"ok": False, "status": "METADATA_INVALID", "checksum": actual_checksum}
        signature = metadata.get("signature") or {}
        key_id = str(signature.get("key_id") or "")
        value = str(signature.get("signature") or "")
        if signature.get("algorithm", "HMAC-SHA256") != "HMAC-SHA256" or not key_id or not value:
            return {"ok": False, "status": "MISSING_SIGNATURE", "checksum": actual_checksum, "key_id": key_id}
        if str(signature.get("status") or "ACTIVE") != "ACTIVE":
            return {"ok": False, "status": "KEY_INACTIVE", "checksum": actual_checksum, "key_id": key_id}
        expires_at = str(signature.get("expires_at") or "")
        if expires_at:
            try:
                expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                reference = now or datetime.now(timezone.utc)
                if expiry.tzinfo is None:
                    expiry = expiry.replace(tzinfo=timezone.utc)
                if reference.tzinfo is None:
                    reference = reference.replace(tzinfo=timezone.utc)
                if expiry <= reference:
                    return {"ok": False, "status": "KEY_EXPIRED", "checksum": actual_checksum, "key_id": key_id}
            except ValueError:
                return {"ok": False, "status": "KEY_EXPIRY_INVALID", "checksum": actual_checksum, "key_id": key_id}
        key = signing_keys.get(key_id)
        if not key:
            return {"ok": False, "status": "UNKNOWN_KEY", "checksum": actual_checksum, "key_id": key_id}
        expected = hmac.new(str(key).encode("utf-8"), payload_json.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, value):
            return {"ok": False, "status": "SIGNATURE_MISMATCH", "checksum": actual_checksum, "key_id": key_id}
        return {"ok": True, "status": "VALID", "checksum": actual_checksum, "key_id": key_id}

    def enqueue(
        self,
        operation_type: str,
        payload: Mapping[str, Any],
        *,
        local_decision: Mapping[str, Any] | None = None,
        idempotency_key: str,
        correlation_id: str = "",
        occurred_at: str = "",
    ) -> dict[str, Any]:
        idem = str(idempotency_key or "").strip()
        if not idem:
            raise EdgeClientError("idempotency_key es obligatorio")
        with self._lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("SELECT * FROM operations WHERE idempotency_key = ?", (idem,)).fetchone()
            if existing:
                db.commit()
                result = self._operation(existing)
                result["duplicate"] = True
                return result
            sequence = int(db.execute("SELECT value FROM state WHERE key='sequence'").fetchone()["value"]) + 1
            operation_id = uuid.uuid4().hex
            now = self._now_iso()
            db.execute("UPDATE state SET value=? WHERE key='sequence'", (str(sequence),))
            db.execute(
                """
                INSERT INTO operations(operation_id,idempotency_key,operation_type,payload_json,
                    local_decision_json,dataset_revision,sequence,correlation_id,occurred_at,
                    status,attempts,next_attempt_at,last_error,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,'PENDING',0,0,'',?,?)
                """,
                (
                    operation_id,
                    idem,
                    str(operation_type).strip().upper(),
                    self._json(payload),
                    self._json(local_decision or {}),
                    self.dataset_revision,
                    sequence,
                    str(correlation_id or "")[:160],
                    occurred_at or now,
                    now,
                    now,
                ),
            )
            row = db.execute("SELECT * FROM operations WHERE operation_id=?", (operation_id,)).fetchone()
            db.commit()
            return self._operation(row)

    @property
    def dataset_revision(self) -> str:
        with self._connect() as db:
            row = db.execute("SELECT value FROM state WHERE key='dataset_revision'").fetchone()
            return str(row["value"] if row else "")

    def pending(self, *, limit: int = 100, now: float | None = None) -> list[dict[str, Any]]:
        timestamp = self.clock() if now is None else now
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM operations WHERE status IN ('PENDING','RETRY') AND next_attempt_at <= ? ORDER BY sequence LIMIT ?",
                (float(timestamp), max(1, min(int(limit), 250))),
            ).fetchall()
            return [self._operation(row) for row in rows]

    def sync(self, *, limit: int = 100) -> dict[str, Any]:
        if self.transport is None:
            raise EdgeClientError("transport no configurado")
        operations = self.pending(limit=limit)
        if not operations:
            return {"ok": True, "sent": 0, "acknowledged": 0, "pending": self.queue_depth}
        try:
            response = self.transport.sync(scope=self.scope, secret=self._secret, operations=operations)
        except Exception as exc:
            self._retry([item["operation_id"] for item in operations], type(exc).__name__)
            self.logger.warning("sync retry device_secret=%s error=%s", self._secret, type(exc).__name__)
            return {"ok": False, "sent": len(operations), "acknowledged": 0, "pending": self.queue_depth}
        sent_operation_ids = {str(item["operation_id"]) for item in operations}
        # A transport response is untrusted input.  Only acknowledgements for
        # this exact batch may change the durable queue or its counters.
        acknowledged = {
            str(item)
            for item in response.get("acknowledged_operation_ids", [])
            if str(item) in sent_operation_ids
        }
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            for item in operations:
                if item["operation_id"] in acknowledged:
                    db.execute("UPDATE operations SET status='ACKED', updated_at=?, last_error='' WHERE operation_id=?", (self._now_iso(), item["operation_id"]))
                else:
                    self._retry_one(db, item["operation_id"], "NOT_ACKNOWLEDGED")
            db.commit()
        complete = len(acknowledged) == len(operations)
        return {
            "ok": bool(response.get("ok")) and complete,
            "sent": len(operations),
            "acknowledged": len(acknowledged),
            "pending": self.queue_depth,
        }

    def heartbeat(self, *, software_version: str = "reference", sync_status: str = "READY") -> Mapping[str, Any]:
        if self.transport is None:
            raise EdgeClientError("transport no configurado")
        return self.transport.heartbeat(
            scope=self.scope,
            secret=self._secret,
            payload={
                "dataset_revision": self.dataset_revision,
                "queue_depth": self.queue_depth,
                "sync_status": sync_status,
                "software_version": software_version,
                "device_timestamp": self._now_iso(),
            },
        )

    @property
    def queue_depth(self) -> int:
        with self._connect() as db:
            return int(db.execute("SELECT COUNT(*) AS c FROM operations WHERE status <> 'ACKED'").fetchone()["c"])

    @property
    def last_sequence(self) -> int:
        with self._connect() as db:
            return int(db.execute("SELECT value FROM state WHERE key='sequence'").fetchone()["value"])

    def _retry(self, operation_ids: list[str], error: str) -> None:
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            for operation_id in operation_ids:
                self._retry_one(db, operation_id, error)
            db.commit()

    def _retry_one(self, db: sqlite3.Connection, operation_id: str, error: str) -> None:
        row = db.execute("SELECT attempts FROM operations WHERE operation_id=?", (operation_id,)).fetchone()
        attempts = int(row["attempts"] if row else 0) + 1
        delay = min(300.0, 0.5 * (2 ** min(attempts - 1, 10)))
        db.execute(
            "UPDATE operations SET status='RETRY',attempts=?,next_attempt_at=?,last_error=?,updated_at=? WHERE operation_id=?",
            (attempts, self.clock() + delay, str(error)[:160], self._now_iso(), operation_id),
        )

    def _initialize(self) -> None:
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS state(key TEXT PRIMARY KEY, value TEXT NOT NULL);
                INSERT OR IGNORE INTO state(key,value) VALUES('sequence','0');
                INSERT OR IGNORE INTO state(key,value) VALUES('dataset_revision','');
                CREATE TABLE IF NOT EXISTS datasets(
                    revision TEXT PRIMARY KEY, payload_json TEXT NOT NULL, checksum TEXT NOT NULL,
                    metadata_json TEXT NOT NULL, status TEXT NOT NULL, activated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS operations(
                    operation_id TEXT PRIMARY KEY, idempotency_key TEXT NOT NULL UNIQUE,
                    operation_type TEXT NOT NULL, payload_json TEXT NOT NULL,
                    local_decision_json TEXT NOT NULL, dataset_revision TEXT NOT NULL,
                    sequence INTEGER NOT NULL UNIQUE, correlation_id TEXT NOT NULL,
                    occurred_at TEXT NOT NULL, status TEXT NOT NULL, attempts INTEGER NOT NULL,
                    next_attempt_at REAL NOT NULL, last_error TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_edge_operations_pending
                ON operations(status,next_attempt_at,sequence);
                """
            )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.database_path, timeout=30, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=FULL")
        db.execute("PRAGMA busy_timeout=30000")
        return db

    @staticmethod
    def _operation(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "operation_id": row["operation_id"],
            "idempotency_key": row["idempotency_key"],
            "operation_type": row["operation_type"],
            "payload": json.loads(row["payload_json"]),
            "local_decision": json.loads(row["local_decision_json"]),
            "dataset_revision": row["dataset_revision"],
            "device_sequence": int(row["sequence"]),
            "correlation_id": row["correlation_id"],
            "occurred_at": row["occurred_at"],
            "status": row["status"],
            "attempts": int(row["attempts"]),
        }

    @staticmethod
    def _json(value: Mapping[str, Any]) -> str:
        return json.dumps(dict(value), ensure_ascii=True, sort_keys=True, separators=(",", ":"))

    def _now_iso(self) -> str:
        return datetime.fromtimestamp(self.clock(), timezone.utc).isoformat(timespec="seconds")
