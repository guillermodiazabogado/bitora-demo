from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

from backend.services.audit import AuditService


ATTENDANCE_V4_STATUSES = {"PRESENT", "ABSENT", "PARTIAL", "INVALIDATED"}
ATTENDANCE_V4_TYPES = {"EVENT", "ACTIVITY", "ENTRY", "EXIT"}
ATTENDANCE_V4_SOURCES = {"MANUAL", "QR", "ACCESS_CONTROL"}
ATTENDANCE_V4_EVENT_TYPES = {
    "AttendanceRecorded",
    "AttendanceCorrected",
    "AttendanceInvalidated",
    "AttendanceEntryRecorded",
    "AttendanceExitRecorded",
    "AttendanceIdempotencyReplayed",
}
ATTENDANCE_V4_2_SCOPE_TYPES = {"EVENT", "ACTIVITY"}
ATTENDANCE_V4_2_RULE_STATUS = {"DRAFT", "PUBLISHED", "RETIRED"}
ATTENDANCE_V4_2_CLOSURE_STATUS = {"CLOSING", "CLOSED", "REOPENED", "SUPERSEDED", "FAILED"}
ATTENDANCE_V4_2_ELIGIBILITY_RESULTS = {"ELIGIBLE", "NOT_ELIGIBLE", "INSUFFICIENT_DATA", "MANUALLY_APPROVED", "MANUALLY_REJECTED"}
ATTENDANCE_EVALUATION_ALGORITHM_VERSION = "attendance_evaluation_algorithm_v1"


class AttendanceDomainError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class AttendanceService:
    """Owns activity attendance and certificate eligibility rules."""

    def __init__(self, audit_service: AuditService, now: Callable[[], str]) -> None:
        self.audit_service = audit_service
        self.now = now

    def record_attendance(
        self,
        db,
        *,
        organization_id: int,
        event_id: int,
        actor: str,
        participant_id: int | None = None,
        accreditation_id: int | None = None,
        activity_id: int | None = None,
        attendance_type: str = "EVENT",
        status: str = "PRESENT",
        source: str = "MANUAL",
        occurred_at: str | None = None,
        idempotency_key: str = "",
        correlation_id: str = "",
        metadata: dict | None = None,
    ) -> dict:
        attendance_type = self._normalize_choice(attendance_type, ATTENDANCE_V4_TYPES, "ATTENDANCE_INVALID_TYPE")
        status = self._normalize_choice(status, ATTENDANCE_V4_STATUSES - {"INVALIDATED"}, "ATTENDANCE_INVALID_TRANSITION")
        source = self._normalize_choice(source, ATTENDANCE_V4_SOURCES, "ATTENDANCE_INVALID_SOURCE")
        key = self._validate_idempotency_key(idempotency_key)
        metadata = self._sanitize_metadata(metadata or {})
        occurred_at_was_supplied = bool(str(occurred_at or "").strip())
        occurred_at = self._validate_timestamp(occurred_at or self.now())
        organization_id, event_id, participant_id, accreditation_id, activity_id = self._validate_context(
            db,
            organization_id=organization_id,
            event_id=event_id,
            participant_id=participant_id,
            accreditation_id=accreditation_id,
            activity_id=activity_id,
            activity_required=attendance_type in {"ACTIVITY", "ENTRY", "EXIT"},
        )
        request_hash = self._request_hash(
            {
                "organization_id": organization_id,
                "event_id": event_id,
                "participant_id": participant_id,
                "accreditation_id": accreditation_id,
                "activity_id": activity_id,
                "attendance_type": attendance_type,
                "status": status,
                "source": source,
                "occurred_at": occurred_at if occurred_at_was_supplied else "",
                "metadata": metadata,
            }
        )
        existing = db.execute(
            "SELECT * FROM attendance_records WHERE organization_id = ? AND idempotency_key = ?",
            (organization_id, key),
        ).fetchone()
        if existing:
            if str(existing["request_hash"]) != request_hash:
                raise AttendanceDomainError("ATTENDANCE_IDEMPOTENCY_CONFLICT", "La clave de idempotencia ya fue usada con otro payload", 409)
            self._append_event(db, existing, "AttendanceIdempotencyReplayed", actor, key, correlation_id, {"replayed": True})
            self.audit_service.record(
                db,
                actor,
                "attendance.idempotency_replayed",
                "attendance_record",
                int(existing["id"]),
                {"organization_id": organization_id, "event_id": event_id, "participant_id": participant_id, "activity_id": activity_id, "correlation_id": correlation_id},
            )
            return {"ok": True, "idempotent": True, "item": self._row_payload(existing)}

        now = self.now()
        cur = db.execute(
            """
            INSERT INTO attendance_records (
                organization_id, event_id, participant_id, accreditation_id, activity_id,
                attendance_type, status, source, occurred_at, recorded_at, recorded_by,
                idempotency_key, request_hash, correlation_id, metadata_json,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                organization_id,
                event_id,
                participant_id,
                accreditation_id,
                activity_id,
                attendance_type,
                status,
                source,
                occurred_at,
                now,
                actor,
                key,
                request_hash,
                correlation_id,
                json.dumps(metadata, ensure_ascii=True, sort_keys=True),
                now,
                now,
            ),
        )
        record = db.execute("SELECT * FROM attendance_records WHERE id = ?", (int(cur.lastrowid),)).fetchone()
        event_type = "AttendanceEntryRecorded" if attendance_type == "ENTRY" else "AttendanceExitRecorded" if attendance_type == "EXIT" else "AttendanceRecorded"
        self._append_event(db, record, event_type, actor, key, correlation_id, {"status": status, "source": source})
        self.audit_service.record(
            db,
            actor,
            "attendance.created",
            "attendance_record",
            int(record["id"]),
            {"organization_id": organization_id, "event_id": event_id, "participant_id": participant_id, "activity_id": activity_id, "status": status, "source": source, "correlation_id": correlation_id},
        )
        return {"ok": True, "idempotent": False, "item": self._row_payload(record)}

    def record_entry_v4(self, db, **kwargs) -> dict:
        return self.record_attendance(db, attendance_type="ENTRY", status="PRESENT", source=kwargs.pop("source", "ACCESS_CONTROL"), **kwargs)

    def record_exit_v4(self, db, **kwargs) -> dict:
        return self.record_attendance(db, attendance_type="EXIT", status="PARTIAL", source=kwargs.pop("source", "ACCESS_CONTROL"), **kwargs)

    def correct_attendance(self, db, *, attendance_id: int, organization_id: int, event_id: int, actor: str, status: str, reason: str, metadata: dict | None = None, correlation_id: str = "") -> dict:
        if not reason.strip():
            raise AttendanceDomainError("ATTENDANCE_REASON_REQUIRED", "El motivo es obligatorio", 400)
        status = self._normalize_choice(status, ATTENDANCE_V4_STATUSES - {"INVALIDATED"}, "ATTENDANCE_INVALID_TRANSITION")
        record = self._get_owned_record(db, attendance_id, organization_id, event_id)
        if str(record["status"]) == "INVALIDATED":
            raise AttendanceDomainError("ATTENDANCE_INVALID_TRANSITION", "Un registro invalidado no se corrige directamente", 409)
        metadata = self._sanitize_metadata(metadata or self._json(record["metadata_json"]))
        now = self.now()
        previous_metadata = str(record["metadata_json"] or "{}")
        new_metadata = json.dumps(metadata, ensure_ascii=True, sort_keys=True)
        db.execute(
            """
            INSERT INTO attendance_corrections (
                attendance_id, organization_id, event_id, previous_status, new_status,
                previous_metadata_json, new_metadata_json, reason, corrected_by, corrected_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (attendance_id, organization_id, event_id, record["status"], status, previous_metadata, new_metadata, reason.strip(), actor, now),
        )
        db.execute(
            """
            UPDATE attendance_records
            SET status = ?, metadata_json = ?, updated_at = ?
            WHERE id = ?
            """,
            (status, new_metadata, now, attendance_id),
        )
        updated = db.execute("SELECT * FROM attendance_records WHERE id = ?", (attendance_id,)).fetchone()
        self._append_event(db, updated, "AttendanceCorrected", actor, "", correlation_id, {"previous_status": record["status"], "new_status": status, "reason": reason.strip()})
        self.audit_service.record(db, actor, "attendance.corrected", "attendance_record", attendance_id, {"organization_id": organization_id, "event_id": event_id, "previous_status": record["status"], "new_status": status, "reason": reason.strip(), "correlation_id": correlation_id})
        return {"ok": True, "item": self._row_payload(updated)}

    def invalidate_attendance(self, db, *, attendance_id: int, organization_id: int, event_id: int, actor: str, reason: str, correlation_id: str = "") -> dict:
        if not reason.strip():
            raise AttendanceDomainError("ATTENDANCE_REASON_REQUIRED", "El motivo es obligatorio", 400)
        record = self._get_owned_record(db, attendance_id, organization_id, event_id)
        if str(record["status"]) == "INVALIDATED":
            return {"ok": True, "idempotent": True, "item": self._row_payload(record)}
        now = self.now()
        db.execute(
            """
            UPDATE attendance_records
            SET status = 'INVALIDATED', invalidated_at = ?, invalidated_by = ?,
                invalidation_reason = ?, updated_at = ?
            WHERE id = ?
            """,
            (now, actor, reason.strip(), now, attendance_id),
        )
        updated = db.execute("SELECT * FROM attendance_records WHERE id = ?", (attendance_id,)).fetchone()
        self._append_event(db, updated, "AttendanceInvalidated", actor, "", correlation_id, {"reason": reason.strip()})
        self.audit_service.record(db, actor, "attendance.invalidated", "attendance_record", attendance_id, {"organization_id": organization_id, "event_id": event_id, "reason": reason.strip(), "correlation_id": correlation_id})
        return {"ok": True, "idempotent": False, "item": self._row_payload(updated)}

    def get_attendance(self, db, *, organization_id: int, event_id: int, attendance_id: int) -> dict:
        return self._row_payload(self._get_owned_record(db, attendance_id, organization_id, event_id))

    def list_attendance(self, db, *, organization_id: int, event_id: int, filters: dict | None = None, limit: int = 50, offset: int = 0) -> dict:
        filters = filters or {}
        where = ["organization_id = ?", "event_id = ?"]
        params: list[object] = [organization_id, event_id]
        for column in ("participant_id", "activity_id"):
            if filters.get(column):
                where.append(f"{column} = ?")
                params.append(int(filters[column]))
        for column in ("status", "source"):
            if filters.get(column):
                where.append(f"{column} = ?")
                params.append(str(filters[column]).upper())
        if filters.get("from"):
            where.append("occurred_at >= ?")
            params.append(str(filters["from"]))
        if filters.get("to"):
            where.append("occurred_at <= ?")
            params.append(str(filters["to"]))
        limit = max(1, min(200, int(limit or 50)))
        offset = max(0, int(offset or 0))
        rows = db.execute(
            f"SELECT * FROM attendance_records WHERE {' AND '.join(where)} ORDER BY occurred_at DESC, id DESC LIMIT ? OFFSET ?",
            tuple(params + [limit, offset]),
        ).fetchall()
        return {"items": [self._row_payload(row) for row in rows], "limit": limit, "offset": offset}

    def get_participant_attendance_history(self, db, *, organization_id: int, event_id: int, participant_id: int) -> dict:
        rows = db.execute(
            """
            SELECT * FROM attendance_records
            WHERE organization_id = ? AND event_id = ? AND participant_id = ?
            ORDER BY occurred_at DESC, id DESC
            """,
            (organization_id, event_id, participant_id),
        ).fetchall()
        return {"items": [self._row_payload(row) for row in rows]}

    def list_attendance_events(self, db, *, organization_id: int, event_id: int, attendance_id: int) -> dict:
        self._get_owned_record(db, attendance_id, organization_id, event_id)
        rows = db.execute(
            """
            SELECT * FROM attendance_events
            WHERE organization_id = ? AND event_id = ? AND attendance_id = ?
            ORDER BY id
            """,
            (organization_id, event_id, attendance_id),
        ).fetchall()
        return {"items": [dict(row) for row in rows]}

    def create_rule_set(
        self,
        db,
        *,
        organization_id: int,
        event_id: int,
        actor: str,
        name: str,
        scope_type: str = "EVENT",
        activity_id: int | None = None,
    ) -> dict:
        scope_type, activity_id = self._validate_scope(db, organization_id, event_id, scope_type, activity_id)
        name = str(name or "").strip()
        if not name or len(name) > 120:
            raise AttendanceDomainError("ATTENDANCE_RULE_CONFIGURATION_INVALID", "Nombre de regla invalido", 400)
        now = self.now()
        cur = db.execute(
            """
            INSERT INTO attendance_rule_sets (
                organization_id, event_id, activity_id, name, scope_type, status,
                created_by, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, 'DRAFT', ?, ?, ?)
            """,
            (organization_id, event_id, activity_id, name, scope_type, actor, now, now),
        )
        rule_set = db.execute("SELECT * FROM attendance_rule_sets WHERE id = ?", (int(cur.lastrowid),)).fetchone()
        self.audit_service.record(db, actor, "attendance.rules.created", "attendance_rule_set", int(rule_set["id"]), {"organization_id": organization_id, "event_id": event_id, "activity_id": activity_id, "scope_type": scope_type})
        return {"ok": True, "item": self._rule_set_payload(rule_set)}

    def create_rule_set_version(
        self,
        db,
        *,
        organization_id: int,
        event_id: int,
        rule_set_id: int,
        actor: str,
        configuration: dict,
    ) -> dict:
        rule_set = self._get_rule_set(db, rule_set_id, organization_id, event_id)
        if str(rule_set["status"]) not in {"DRAFT", "PUBLISHED"}:
            raise AttendanceDomainError("ATTENDANCE_RULE_CONFIGURATION_INVALID", "Rule set no admite nuevas versiones", 409)
        normalized = self._normalize_rule_configuration(configuration, str(rule_set["scope_type"]))
        config_hash = self._stable_hash(normalized)
        existing = db.execute(
            "SELECT * FROM attendance_rule_set_versions WHERE rule_set_id = ? AND configuration_hash = ?",
            (rule_set_id, config_hash),
        ).fetchone()
        if existing:
            return {"ok": True, "idempotent": True, "item": self._rule_version_payload(existing)}
        version_number = int(
            db.execute("SELECT COALESCE(MAX(version_number), 0) AS n FROM attendance_rule_set_versions WHERE rule_set_id = ?", (rule_set_id,)).fetchone()["n"]
            or 0
        ) + 1
        now = self.now()
        cur = db.execute(
            """
            INSERT INTO attendance_rule_set_versions (
                rule_set_id, organization_id, event_id, activity_id, version_number,
                configuration_json, configuration_hash, status, created_by, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 'DRAFT', ?, ?)
            """,
            (
                rule_set_id,
                organization_id,
                event_id,
                rule_set["activity_id"],
                version_number,
                json.dumps(normalized, ensure_ascii=True, sort_keys=True, separators=(",", ":")),
                config_hash,
                actor,
                now,
            ),
        )
        row = db.execute("SELECT * FROM attendance_rule_set_versions WHERE id = ?", (int(cur.lastrowid),)).fetchone()
        self.audit_service.record(db, actor, "attendance.rules.version_created", "attendance_rule_set_version", int(row["id"]), {"organization_id": organization_id, "event_id": event_id, "rule_set_id": rule_set_id, "configuration_hash": config_hash})
        return {"ok": True, "item": self._rule_version_payload(row)}

    def publish_rule_set_version(
        self,
        db,
        *,
        organization_id: int,
        event_id: int,
        rule_set_id: int,
        version_id: int,
        actor: str,
        idempotency_key: str,
        correlation_id: str = "",
    ) -> dict:
        key = self._validate_idempotency_key(idempotency_key)
        rule_set = self._get_rule_set(db, rule_set_id, organization_id, event_id)
        version = self._get_rule_version(db, version_id, rule_set_id, organization_id, event_id)
        request_hash = self._request_hash({"operation": "publish_rule_version", "rule_set_id": rule_set_id, "version_id": version_id})
        existing = self._idempotency_lookup(db, organization_id, key, request_hash, "attendance_rule_set_versions")
        if existing:
            return {"ok": True, "idempotent": True, "item": self._rule_version_payload(version)}
        if str(version["status"]) == "PUBLISHED":
            return {"ok": True, "idempotent": True, "item": self._rule_version_payload(version)}
        now = self.now()
        db.execute("UPDATE attendance_rule_set_versions SET status = 'PUBLISHED', published_at = ?, published_by = ?, idempotency_key = ?, request_hash = ? WHERE id = ?", (now, actor, key, request_hash, version_id))
        db.execute("UPDATE attendance_rule_sets SET status = 'PUBLISHED', current_version_id = ?, updated_at = ? WHERE id = ?", (version_id, now, rule_set_id))
        updated = db.execute("SELECT * FROM attendance_rule_set_versions WHERE id = ?", (version_id,)).fetchone()
        self.audit_service.record(db, actor, "attendance.rules.published", "attendance_rule_set_version", version_id, {"organization_id": organization_id, "event_id": event_id, "rule_set_id": int(rule_set["id"]), "configuration_hash": updated["configuration_hash"], "idempotency_key": key, "correlation_id": correlation_id})
        return {"ok": True, "item": self._rule_version_payload(updated)}

    def close_attendance(
        self,
        db,
        *,
        organization_id: int,
        event_id: int,
        actor: str,
        rule_set_version_id: int,
        scope_type: str = "EVENT",
        activity_id: int | None = None,
        reason: str = "",
        cutoff_at: str | None = None,
        idempotency_key: str = "",
        correlation_id: str = "",
    ) -> dict:
        scope_type, activity_id = self._validate_scope(db, organization_id, event_id, scope_type, activity_id)
        key = self._validate_idempotency_key(idempotency_key)
        cutoff_at = self._validate_timestamp(cutoff_at or self.now())
        version = self._get_published_rule_version(db, rule_set_version_id, organization_id, event_id, scope_type, activity_id)
        request_hash = self._request_hash({"operation": "close_attendance", "event_id": event_id, "activity_id": activity_id, "scope_type": scope_type, "rule_set_version_id": rule_set_version_id, "cutoff_at": cutoff_at})
        existing = self._idempotency_lookup(db, organization_id, key, request_hash, "attendance_closures")
        if existing:
            closure = db.execute("SELECT * FROM attendance_closures WHERE id = ?", (int(existing["id"]),)).fetchone()
            return {"ok": True, "idempotent": True, "item": self._closure_payload(closure)}
        open_conflict = db.execute(
            """
            SELECT id FROM attendance_closures
            WHERE organization_id = ? AND event_id = ? AND scope_type = ?
              AND COALESCE(activity_id, 0) = COALESCE(?, 0)
              AND status IN ('CLOSING', 'CLOSED')
            ORDER BY id DESC LIMIT 1
            """,
            (organization_id, event_id, scope_type, activity_id),
        ).fetchone()
        if open_conflict:
            raise AttendanceDomainError("ATTENDANCE_CLOSURE_ALREADY_EXISTS", "Ya existe un cierre activo para este alcance", 409)
        superseded = db.execute(
            """
            SELECT id FROM attendance_closures
            WHERE organization_id = ? AND event_id = ? AND scope_type = ?
              AND COALESCE(activity_id, 0) = COALESCE(?, 0)
              AND status = 'REOPENED'
            ORDER BY id DESC LIMIT 1
            """,
            (organization_id, event_id, scope_type, activity_id),
        ).fetchone()
        supersedes_closure_id = int(superseded["id"]) if superseded else None
        now = self.now()
        cur = db.execute(
            """
            INSERT INTO attendance_closures (
                organization_id, event_id, activity_id, scope_type, rule_set_version_id,
                status, closed_by, closure_reason, cutoff_at, algorithm_version,
                supersedes_closure_id, idempotency_key, request_hash, correlation_id, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, 'CLOSING', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (organization_id, event_id, activity_id, scope_type, rule_set_version_id, actor, str(reason or "").strip(), cutoff_at, ATTENDANCE_EVALUATION_ALGORITHM_VERSION, supersedes_closure_id, key, request_hash, correlation_id, now, now),
        )
        closure_id = int(cur.lastrowid)
        self.audit_service.record(db, actor, "attendance.closure.started", "attendance_closure", closure_id, {"organization_id": organization_id, "event_id": event_id, "activity_id": activity_id, "rule_set_version_id": rule_set_version_id, "correlation_id": correlation_id})
        try:
            snapshot = self._build_closure_snapshot(db, organization_id, event_id, activity_id, scope_type, version, cutoff_at, actor)
            snapshot_hash = self._stable_hash(snapshot)
            for evaluation in snapshot["evaluations"]:
                self._insert_evaluation(db, closure_id, organization_id, event_id, activity_id, evaluation, actor)
            completed_at = self.now()
            db.execute(
                """
                UPDATE attendance_closures
                SET status = 'CLOSED', closed_at = ?, snapshot_json = ?, snapshot_hash = ?, updated_at = ?
                WHERE id = ?
                """,
                (completed_at, json.dumps(snapshot, ensure_ascii=True, sort_keys=True, separators=(",", ":")), snapshot_hash, completed_at, closure_id),
            )
            if supersedes_closure_id:
                db.execute("UPDATE attendance_closures SET status = 'SUPERSEDED', updated_at = ? WHERE id = ?", (completed_at, supersedes_closure_id))
            closure = db.execute("SELECT * FROM attendance_closures WHERE id = ?", (closure_id,)).fetchone()
            self.audit_service.record(db, actor, "attendance.snapshot.created", "attendance_closure", closure_id, {"organization_id": organization_id, "event_id": event_id, "snapshot_hash": snapshot_hash})
            self.audit_service.record(db, actor, "attendance.closure.completed", "attendance_closure", closure_id, {"organization_id": organization_id, "event_id": event_id, "evaluations": len(snapshot["evaluations"]), "snapshot_hash": snapshot_hash})
            return {"ok": True, "item": self._closure_payload(closure)}
        except Exception:
            db.execute("UPDATE attendance_closures SET status = 'FAILED', updated_at = ? WHERE id = ?", (self.now(), closure_id))
            self.audit_service.record(db, actor, "attendance.closure.failed", "attendance_closure", closure_id, {"organization_id": organization_id, "event_id": event_id})
            raise

    def reopen_closure(
        self,
        db,
        *,
        organization_id: int,
        event_id: int,
        closure_id: int,
        actor: str,
        reason: str,
        idempotency_key: str,
        correlation_id: str = "",
    ) -> dict:
        reason = str(reason or "").strip()
        if not reason:
            raise AttendanceDomainError("ATTENDANCE_REASON_REQUIRED", "El motivo es obligatorio", 400)
        key = self._validate_idempotency_key(idempotency_key)
        closure = self._get_closure(db, closure_id, organization_id, event_id)
        if str(closure["status"]) not in {"CLOSED"}:
            raise AttendanceDomainError("ATTENDANCE_CLOSURE_NOT_REOPENABLE", "El cierre no puede reabrirse", 409)
        request_hash = self._request_hash({"operation": "reopen_closure", "closure_id": closure_id, "reason": reason})
        existing = self._idempotency_lookup(db, organization_id, key, request_hash, "attendance_reopenings")
        if existing:
            return {"ok": True, "idempotent": True, "item": self._closure_payload(db.execute("SELECT * FROM attendance_closures WHERE id = ?", (closure_id,)).fetchone())}
        now = self.now()
        db.execute("UPDATE attendance_closures SET status = 'REOPENED', reopened_at = ?, reopened_by = ?, reopening_reason = ?, updated_at = ? WHERE id = ?", (now, actor, reason, now, closure_id))
        db.execute(
            """
            INSERT INTO attendance_reopenings (
                organization_id, event_id, closure_id, reason, idempotency_key,
                request_hash, correlation_id, reopened_by, reopened_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (organization_id, event_id, closure_id, reason, key, request_hash, correlation_id, actor, now),
        )
        updated = db.execute("SELECT * FROM attendance_closures WHERE id = ?", (closure_id,)).fetchone()
        self.audit_service.record(db, actor, "attendance.closure.reopened", "attendance_closure", closure_id, {"organization_id": organization_id, "event_id": event_id, "reason": reason, "correlation_id": correlation_id})
        return {"ok": True, "item": self._closure_payload(updated)}

    def override_eligibility(
        self,
        db,
        *,
        organization_id: int,
        event_id: int,
        participant_id: int,
        actor: str,
        manual_result: str,
        reason: str,
        evidence: dict | None = None,
        closure_id: int | None = None,
        idempotency_key: str = "",
        correlation_id: str = "",
    ) -> dict:
        reason = str(reason or "").strip()
        if not reason:
            raise AttendanceDomainError("ATTENDANCE_REASON_REQUIRED", "El motivo es obligatorio", 400)
        manual_result = self._normalize_choice(manual_result, {"MANUALLY_APPROVED", "MANUALLY_REJECTED"}, "ATTENDANCE_ELIGIBILITY_OVERRIDE_DENIED")
        key = self._validate_idempotency_key(idempotency_key)
        query = """
            SELECT ev.*, d.effective_result, d.id AS decision_id
            FROM attendance_evaluations ev
            JOIN attendance_eligibility_decisions d ON d.evaluation_id = ev.id
            JOIN attendance_closures c ON c.id = ev.closure_id
            WHERE ev.organization_id = ? AND ev.event_id = ? AND ev.participant_id = ?
              AND c.status = 'CLOSED'
        """
        params: list[object] = [organization_id, event_id, participant_id]
        if closure_id:
            query += " AND ev.closure_id = ?"
            params.append(int(closure_id))
        query += " ORDER BY ev.closure_id DESC, ev.id DESC LIMIT 1"
        evaluation = db.execute(query, tuple(params)).fetchone()
        if not evaluation:
            raise AttendanceDomainError("ATTENDANCE_EVALUATION_INSUFFICIENT_DATA", "No existe evaluacion cerrada para este participante", 404)
        request_hash = self._request_hash({"operation": "override_eligibility", "evaluation_id": int(evaluation["id"]), "manual_result": manual_result, "reason": reason})
        existing = self._idempotency_lookup(db, organization_id, key, request_hash, "attendance_overrides")
        if existing:
            decision = db.execute("SELECT * FROM attendance_eligibility_decisions WHERE evaluation_id = ?", (int(evaluation["id"]),)).fetchone()
            return {"ok": True, "idempotent": True, "item": self._decision_payload(decision)}
        now = self.now()
        clean_evidence = self._sanitize_metadata(evidence or {})
        cur = db.execute(
            """
            INSERT INTO attendance_overrides (
                organization_id, event_id, closure_id, evaluation_id, participant_id,
                previous_effective_result, manual_result, reason, evidence_json,
                idempotency_key, request_hash, correlation_id, created_by, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (organization_id, event_id, int(evaluation["closure_id"]), int(evaluation["id"]), participant_id, evaluation["effective_result"], manual_result, reason, json.dumps(clean_evidence, ensure_ascii=True, sort_keys=True), key, request_hash, correlation_id, actor, now),
        )
        override_id = int(cur.lastrowid)
        db.execute(
            """
            UPDATE attendance_eligibility_decisions
            SET effective_result = ?, override_id = ?, status = ?, decided_at = ?, decided_by = ?
            WHERE evaluation_id = ?
            """,
            (manual_result, override_id, manual_result, now, actor, int(evaluation["id"])),
        )
        decision = db.execute("SELECT * FROM attendance_eligibility_decisions WHERE evaluation_id = ?", (int(evaluation["id"]),)).fetchone()
        self.audit_service.record(db, actor, "attendance.eligibility.overridden", "attendance_eligibility_decision", int(decision["id"]), {"organization_id": organization_id, "event_id": event_id, "participant_id": participant_id, "closure_id": int(evaluation["closure_id"]), "manual_result": manual_result, "reason": reason, "correlation_id": correlation_id})
        return {"ok": True, "item": self._decision_payload(decision)}

    def list_rule_sets(self, db, *, organization_id: int, event_id: int) -> dict:
        rows = db.execute("SELECT * FROM attendance_rule_sets WHERE organization_id = ? AND event_id = ? ORDER BY id", (organization_id, event_id)).fetchall()
        return {"items": [self._rule_set_payload(row) for row in rows]}

    def list_closures(self, db, *, organization_id: int, event_id: int) -> dict:
        rows = db.execute("SELECT * FROM attendance_closures WHERE organization_id = ? AND event_id = ? ORDER BY id DESC", (organization_id, event_id)).fetchall()
        return {"items": [self._closure_payload(row) for row in rows]}

    def get_closure(self, db, *, organization_id: int, event_id: int, closure_id: int) -> dict:
        return self._closure_payload(self._get_closure(db, closure_id, organization_id, event_id))

    def list_closure_evaluations(self, db, *, organization_id: int, event_id: int, closure_id: int) -> dict:
        self._get_closure(db, closure_id, organization_id, event_id)
        rows = db.execute("SELECT * FROM attendance_evaluations WHERE closure_id = ? AND organization_id = ? AND event_id = ? ORDER BY participant_id", (closure_id, organization_id, event_id)).fetchall()
        return {"items": [self._evaluation_payload(row) for row in rows]}

    def participant_eligibility(self, db, *, organization_id: int, event_id: int, participant_id: int) -> dict:
        rows = db.execute(
            """
            SELECT d.*
            FROM attendance_eligibility_decisions d
            JOIN attendance_closures c ON c.id = d.closure_id
            WHERE d.organization_id = ? AND d.event_id = ? AND d.participant_id = ? AND c.status = 'CLOSED'
            ORDER BY d.closure_id DESC, d.id DESC
            """,
            (organization_id, event_id, participant_id),
        ).fetchall()
        return {"items": [self._decision_payload(row) for row in rows]}

    def register_entry(self, db, token: str, activity_id: int, operator: str) -> dict:
        context = self._context(db, token, activity_id)
        if not context:
            return {"ok": False, "error": "Actividad o participante inexistente"}
        event, activity, accreditation, reservation = context
        if not int(event["controlar_asistencia"] or 0) or not int(activity["requiere_asistencia"] or 0):
            return {"ok": True, "ignored": True, "status": "No requerida", "eligibility_status": "Pendiente", "percentage": 0}
        current = db.execute(
            "SELECT * FROM activity_attendance WHERE activity_id = ? AND accreditation_id = ?",
            (activity_id, accreditation["id"]),
        ).fetchone()
        now = self.now()
        if current:
            if current["entry_at"]:
                return self._recalculate(db, current["id"], operator, "attendance.entry_repeated")
            db.execute(
                """
                UPDATE activity_attendance
                SET entry_at = ?, entry_operator = ?, updated_at = ?
                WHERE id = ?
                """,
                (now, operator, now, current["id"]),
            )
            attendance_id = int(current["id"])
        else:
            cur = db.execute(
                """
                INSERT INTO activity_attendance (
                    event_id, activity_id, accreditation_id, reservation_id,
                    entry_at, entry_operator, status, eligibility_status,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, 'presente', 'Pendiente', ?, ?)
                """,
                (
                    event["id"],
                    activity["id"],
                    accreditation["id"],
                    reservation["id"] if reservation else None,
                    now,
                    operator,
                    now,
                    now,
                ),
            )
            attendance_id = int(cur.lastrowid)
        result = self._recalculate(db, attendance_id, operator, "attendance.entry_registered")
        self.audit_service.record(
            db,
            operator,
            "attendance.entry_registered",
            "activity_attendance",
            attendance_id,
            {"event_id": event["id"], "activity_id": activity["id"], "accreditation_id": accreditation["id"]},
        )
        return result

    def register_exit(self, db, token: str, activity_id: int, operator: str) -> dict:
        context = self._context(db, token, activity_id)
        if not context:
            return {"ok": False, "error": "Actividad o participante inexistente"}
        event, activity, accreditation, _reservation = context
        if not int(event["controlar_asistencia"] or 0) or not int(activity["requiere_asistencia"] or 0):
            return {"ok": True, "ignored": True, "status": "No requerida", "eligibility_status": "Pendiente", "percentage": 0}
        row = db.execute(
            "SELECT * FROM activity_attendance WHERE activity_id = ? AND accreditation_id = ?",
            (activity_id, accreditation["id"]),
        ).fetchone()
        if not row or not row["entry_at"]:
            return {"ok": False, "error": "Primero debe registrarse el ingreso"}
        now = self.now()
        db.execute(
            """
            UPDATE activity_attendance
            SET exit_at = ?, exit_operator = ?, updated_at = ?
            WHERE id = ?
            """,
            (now, operator, now, row["id"]),
        )
        result = self._recalculate(db, int(row["id"]), operator, "attendance.exit_registered")
        self.audit_service.record(
            db,
            operator,
            "attendance.exit_registered",
            "activity_attendance",
            int(row["id"]),
            {"event_id": event["id"], "activity_id": activity["id"], "accreditation_id": accreditation["id"]},
        )
        return result

    def manual_update(self, db, attendance_id: int, operator: str, status: str, percentage: int | None, reason: str) -> dict:
        row = db.execute(
            """
            SELECT at.*, act.porcentaje_minimo_asistencia, act.habilita_certificado, e.generar_certificados
            FROM activity_attendance at
            JOIN activities act ON act.id = at.activity_id
            JOIN events e ON e.id = at.event_id
            WHERE at.id = ?
            """,
            (attendance_id,),
        ).fetchone()
        if not row:
            return {"ok": False, "error": "Asistencia inexistente"}
        status = self._normalize_status(status)
        now = self.now()
        pct = max(0, min(100, int(percentage if percentage is not None else row["attendance_percentage"] or 0)))
        certificate_enabled = int(row["habilita_certificado"] or 0) and int(row["generar_certificados"] or 0)
        eligibility = self._eligibility(status, pct, row["porcentaje_minimo_asistencia"], certificate_enabled)
        db.execute(
            """
            UPDATE activity_attendance
            SET status = ?, attendance_percentage = ?, eligibility_status = ?,
                corrected_by = ?, correction_reason = ?, updated_at = ?
            WHERE id = ?
            """,
            (status, pct, eligibility, operator, reason, now, attendance_id),
        )
        self._upsert_certificate(db, row["event_id"], row["activity_id"], row["accreditation_id"], pct, eligibility)
        action = "attendance.annulled" if status == "Anulada" else "attendance.manual_corrected"
        self.audit_service.record(
            db,
            operator,
            action,
            "activity_attendance",
            attendance_id,
            {"event_id": row["event_id"], "activity_id": row["activity_id"], "percentage": pct, "status": status, "reason": reason},
        )
        return {"ok": True, "id": attendance_id, "status": status, "percentage": pct, "eligibility_status": eligibility}

    def ensure_absences(self, db, event_id: int) -> None:
        rows = db.execute(
            """
            SELECT r.event_id, r.activity_id, r.accreditation_id, r.id AS reservation_id,
                   a.ends_at, a.porcentaje_minimo_asistencia, a.habilita_certificado,
                   e.generar_certificados
            FROM reservations r
            JOIN activities a ON a.id = r.activity_id
            JOIN events e ON e.id = r.event_id
            LEFT JOIN activity_attendance at ON at.activity_id = r.activity_id AND at.accreditation_id = r.accreditation_id
            WHERE r.event_id = ? AND r.status = 'confirmed' AND a.requiere_asistencia = 1 AND at.id IS NULL
            """,
            (event_id,),
        ).fetchall()
        now = self.now()
        for row in rows:
            finished = self._activity_finished(row["ends_at"])
            status = "Ausente" if finished else "Pendiente"
            certificate_enabled = int(row["habilita_certificado"] or 0) and int(row["generar_certificados"] or 0)
            eligibility = self._eligibility(status, 0, row["porcentaje_minimo_asistencia"], certificate_enabled)
            db.execute(
                """
                INSERT INTO activity_attendance (
                    event_id, activity_id, accreditation_id, reservation_id,
                    status, eligibility_status, attendance_percentage, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)
                """,
                (row["event_id"], row["activity_id"], row["accreditation_id"], row["reservation_id"], status, eligibility, now, now),
            )
            self._upsert_certificate(db, row["event_id"], row["activity_id"], row["accreditation_id"], 0, eligibility)

    def _recalculate(self, db, attendance_id: int, operator: str, action: str) -> dict:
        row = db.execute(
            """
            SELECT at.*, e.attendance_mode AS event_attendance_mode, e.generar_certificados,
                   a.starts_at, a.ends_at, a.porcentaje_minimo_asistencia, a.habilita_certificado, a.attendance_mode
            FROM activity_attendance at
            JOIN events e ON e.id = at.event_id
            JOIN activities a ON a.id = at.activity_id
            WHERE at.id = ?
            """,
            (attendance_id,),
        ).fetchone()
        mode = row["attendance_mode"] or row["event_attendance_mode"] or "entry_only"
        percentage = 0
        minutes = 0
        status = "Pendiente"
        if row["entry_at"]:
            if mode == "entry_exit" and row["exit_at"]:
                minutes = self._minutes_between(row["entry_at"], row["exit_at"])
                total = max(1, self._minutes_between(row["starts_at"], row["ends_at"]))
                percentage = max(0, min(100, round((minutes / total) * 100)))
                status = "Completa" if percentage >= int(row["porcentaje_minimo_asistencia"] or 80) else "Parcial"
            elif mode == "entry_exit":
                status = "Presente"
                percentage = 0
            else:
                total = max(1, self._minutes_between(row["starts_at"], row["ends_at"]))
                minutes = total
                percentage = 100
                status = "Completa"
        certificate_enabled = int(row["habilita_certificado"] or 0) and int(row["generar_certificados"] or 0)
        eligibility = self._eligibility(status, percentage, row["porcentaje_minimo_asistencia"], certificate_enabled)
        now = self.now()
        db.execute(
            """
            UPDATE activity_attendance
            SET attended_minutes = ?, attendance_percentage = ?, status = ?, eligibility_status = ?, updated_at = ?
            WHERE id = ?
            """,
            (minutes, percentage, status, eligibility, now, attendance_id),
        )
        self._upsert_certificate(db, row["event_id"], row["activity_id"], row["accreditation_id"], percentage, eligibility)
        return {"ok": True, "id": attendance_id, "status": status, "percentage": percentage, "eligibility_status": eligibility}

    def _context(self, db, token: str, activity_id: int):
        row = db.execute(
            """
            SELECT ac.*, e.id AS event_id
            FROM accreditations ac
            JOIN events e ON e.id = ac.event_id
            WHERE ac.token = ?
            """,
            (token.strip().upper(),),
        ).fetchone()
        if not row:
            return None
        activity = db.execute("SELECT * FROM activities WHERE id = ? AND event_id = ?", (activity_id, row["event_id"])).fetchone()
        event = db.execute("SELECT * FROM events WHERE id = ?", (row["event_id"],)).fetchone()
        if not activity or not event:
            return None
        reservation = db.execute(
            "SELECT * FROM reservations WHERE activity_id = ? AND accreditation_id = ? AND status = 'confirmed'",
            (activity_id, row["id"]),
        ).fetchone()
        return event, activity, row, reservation

    def _eligibility(self, status: str, percentage: int, minimum: int, enabled: int) -> str:
        if not int(enabled or 0) or status in {"Pendiente", "Presente"}:
            return "Pendiente"
        if status in {"Ausente", "Anulada"}:
            return "No elegible"
        return "Elegible" if int(percentage or 0) >= int(minimum or 80) else "No elegible"

    def _upsert_certificate(self, db, event_id: int, activity_id: int, accreditation_id: int, percentage: int, eligibility: str) -> None:
        now = self.now()
        db.execute(
            """
            INSERT INTO certificate_eligibility (
                event_id, activity_id, accreditation_id, porcentaje, elegible, estado, fecha_calculo
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(activity_id, accreditation_id)
            DO UPDATE SET porcentaje = excluded.porcentaje,
                          elegible = excluded.elegible,
                          estado = excluded.estado,
                          fecha_calculo = excluded.fecha_calculo
            """,
            (event_id, activity_id, accreditation_id, int(percentage or 0), 1 if eligibility == "Elegible" else 0, eligibility, now),
        )

    def _minutes_between(self, start: str, end: str) -> int:
        try:
            start_dt = datetime.fromisoformat(str(start).replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(str(end).replace("Z", "+00:00"))
            if start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=timezone.utc)
            if end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=timezone.utc)
            return max(0, round((end_dt - start_dt).total_seconds() / 60))
        except ValueError:
            return 0

    def _normalize_status(self, status: str) -> str:
        mapping = {
            "pendiente": "Pendiente",
            "presente": "Presente",
            "ausente": "Ausente",
            "parcial": "Parcial",
            "completa": "Completa",
            "anulada": "Anulada",
        }
        return mapping.get(status.strip().lower(), "Pendiente")

    def _activity_finished(self, ends_at: str) -> bool:
        try:
            end_dt = datetime.fromisoformat(str(ends_at).replace("Z", "+00:00"))
            if end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=timezone.utc)
            return end_dt < datetime.now(timezone.utc)
        except ValueError:
            return False

    def _validate_context(self, db, *, organization_id: int, event_id: int, participant_id: int | None, accreditation_id: int | None, activity_id: int | None, activity_required: bool):
        event = db.execute("SELECT id, organization_id FROM events WHERE id = ?", (event_id,)).fetchone()
        if not event or int(event["organization_id"] or 0) != int(organization_id):
            raise AttendanceDomainError("ATTENDANCE_CROSS_TENANT_REFERENCE", "Evento fuera de alcance", 403)
        activity_id = int(activity_id or 0) or None
        if activity_required and not activity_id:
            raise AttendanceDomainError("ATTENDANCE_ACTIVITY_REQUIRED", "La actividad es obligatoria para este tipo de asistencia", 400)
        if activity_id:
            activity = db.execute("SELECT id FROM activities WHERE id = ? AND event_id = ?", (activity_id, event_id)).fetchone()
            if not activity:
                raise AttendanceDomainError("ATTENDANCE_ACTIVITY_EVENT_MISMATCH", "Actividad fuera de alcance", 403)
        accreditation = None
        if accreditation_id:
            accreditation = db.execute("SELECT id, event_id, person_id FROM accreditations WHERE id = ?", (int(accreditation_id),)).fetchone()
        if not accreditation and participant_id:
            accreditation = db.execute(
                "SELECT id, event_id, person_id FROM accreditations WHERE event_id = ? AND person_id = ? ORDER BY id LIMIT 1",
                (event_id, int(participant_id)),
            ).fetchone()
        if not accreditation:
            raise AttendanceDomainError("ATTENDANCE_PARTICIPANT_EVENT_MISMATCH", "Participante fuera de alcance", 403)
        if int(accreditation["event_id"]) != int(event_id):
            raise AttendanceDomainError("ATTENDANCE_PARTICIPANT_EVENT_MISMATCH", "Participante fuera de alcance", 403)
        return int(organization_id), int(event_id), int(accreditation["person_id"]), int(accreditation["id"]), activity_id

    def _get_owned_record(self, db, attendance_id: int, organization_id: int, event_id: int):
        row = db.execute(
            "SELECT * FROM attendance_records WHERE id = ? AND organization_id = ? AND event_id = ?",
            (int(attendance_id), int(organization_id), int(event_id)),
        ).fetchone()
        if not row:
            raise AttendanceDomainError("ATTENDANCE_NOT_FOUND", "Asistencia inexistente", 404)
        return row

    def _append_event(self, db, record, event_type: str, actor: str, idempotency_key: str, correlation_id: str, payload: dict) -> None:
        if event_type not in ATTENDANCE_V4_EVENT_TYPES:
            raise AttendanceDomainError("ATTENDANCE_INVALID_EVENT", "Evento de dominio invalido", 400)
        db.execute(
            """
            INSERT INTO attendance_events (
                attendance_id, organization_id, event_id, participant_id, activity_id,
                event_type, status, source, occurred_at, actor, idempotency_key,
                correlation_id, payload_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(record["id"]),
                int(record["organization_id"]),
                int(record["event_id"]),
                int(record["participant_id"]),
                record["activity_id"],
                event_type,
                record["status"],
                record["source"],
                self.now(),
                actor,
                idempotency_key,
                correlation_id,
                json.dumps(self._sanitize_metadata(payload), ensure_ascii=True, sort_keys=True),
                self.now(),
            ),
        )

    def _row_payload(self, row) -> dict:
        data = dict(row)
        data["metadata"] = self._json(data.pop("metadata_json", "{}"))
        data.pop("request_hash", None)
        return data

    def _sanitize_metadata(self, metadata: dict) -> dict:
        if not isinstance(metadata, dict):
            raise AttendanceDomainError("ATTENDANCE_INVALID_METADATA", "Metadata invalida", 400)
        allowed = {"note", "checkpoint", "device", "reason", "source_ref"}
        clean = {}
        for key, value in metadata.items():
            key = str(key)
            if key not in allowed:
                continue
            text = str(value or "")[:240]
            if re.search(r"(?i)(token|secret|authorization|password)", key + text):
                continue
            clean[key] = text
        return clean

    def _validate_idempotency_key(self, key: str) -> str:
        key = str(key or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9._:-]{8,120}", key):
            raise AttendanceDomainError("ATTENDANCE_INVALID_IDEMPOTENCY_KEY", "Idempotency key invalida", 400)
        return key

    def _validate_timestamp(self, value: str) -> str:
        try:
            datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError as exc:
            raise AttendanceDomainError("ATTENDANCE_INVALID_TIMESTAMP", "Fecha invalida", 400) from exc
        return str(value)

    def _normalize_choice(self, value: str, allowed: set[str], code: str) -> str:
        text = str(value or "").strip().upper()
        if text not in allowed:
            raise AttendanceDomainError(code, "Valor no permitido", 400)
        return text

    def _request_hash(self, payload: dict) -> str:
        body = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(body.encode("utf-8")).hexdigest()

    def _json(self, value: str) -> dict:
        try:
            parsed = json.loads(value or "{}")
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}

    def _json_list(self, value: str) -> list:
        try:
            parsed = json.loads(value or "[]")
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return []

    def _validate_scope(self, db, organization_id: int, event_id: int, scope_type: str, activity_id: int | None):
        scope_type = self._normalize_choice(scope_type, ATTENDANCE_V4_2_SCOPE_TYPES, "ATTENDANCE_SCOPE_MISMATCH")
        event = db.execute("SELECT id, organization_id FROM events WHERE id = ?", (int(event_id),)).fetchone()
        if not event or int(event["organization_id"] or 0) != int(organization_id):
            raise AttendanceDomainError("ATTENDANCE_SCOPE_MISMATCH", "Evento fuera de alcance", 403)
        activity_id = int(activity_id or 0) or None
        if scope_type == "ACTIVITY":
            if not activity_id:
                raise AttendanceDomainError("ATTENDANCE_SCOPE_MISMATCH", "La actividad es obligatoria", 400)
            activity = db.execute("SELECT id FROM activities WHERE id = ? AND event_id = ?", (activity_id, int(event_id))).fetchone()
            if not activity:
                raise AttendanceDomainError("ATTENDANCE_SCOPE_MISMATCH", "Actividad fuera de alcance", 403)
        elif activity_id:
            raise AttendanceDomainError("ATTENDANCE_SCOPE_MISMATCH", "El cierre de evento no recibe actividad", 400)
        return scope_type, activity_id

    def _get_rule_set(self, db, rule_set_id: int, organization_id: int, event_id: int):
        row = db.execute(
            "SELECT * FROM attendance_rule_sets WHERE id = ? AND organization_id = ? AND event_id = ?",
            (int(rule_set_id), int(organization_id), int(event_id)),
        ).fetchone()
        if not row:
            raise AttendanceDomainError("ATTENDANCE_RULE_SET_NOT_FOUND", "Rule set inexistente", 404)
        return row

    def _get_rule_version(self, db, version_id: int, rule_set_id: int, organization_id: int, event_id: int):
        row = db.execute(
            """
            SELECT * FROM attendance_rule_set_versions
            WHERE id = ? AND rule_set_id = ? AND organization_id = ? AND event_id = ?
            """,
            (int(version_id), int(rule_set_id), int(organization_id), int(event_id)),
        ).fetchone()
        if not row:
            raise AttendanceDomainError("ATTENDANCE_RULE_SET_NOT_FOUND", "Version de reglas inexistente", 404)
        return row

    def _get_published_rule_version(self, db, version_id: int, organization_id: int, event_id: int, scope_type: str, activity_id: int | None):
        row = db.execute(
            """
            SELECT v.*, rs.scope_type
            FROM attendance_rule_set_versions v
            JOIN attendance_rule_sets rs ON rs.id = v.rule_set_id
            WHERE v.id = ? AND v.organization_id = ? AND v.event_id = ? AND v.status = 'PUBLISHED'
              AND rs.scope_type = ? AND COALESCE(rs.activity_id, 0) = COALESCE(?, 0)
            """,
            (int(version_id), int(organization_id), int(event_id), scope_type, activity_id),
        ).fetchone()
        if not row:
            raise AttendanceDomainError("ATTENDANCE_RULE_VERSION_NOT_PUBLISHED", "La version de reglas publicada no existe para este alcance", 409)
        return row

    def _get_closure(self, db, closure_id: int, organization_id: int, event_id: int):
        row = db.execute(
            "SELECT * FROM attendance_closures WHERE id = ? AND organization_id = ? AND event_id = ?",
            (int(closure_id), int(organization_id), int(event_id)),
        ).fetchone()
        if not row:
            raise AttendanceDomainError("ATTENDANCE_CLOSURE_NOT_FOUND", "Cierre inexistente", 404)
        return row

    def _idempotency_lookup(self, db, organization_id: int, key: str, request_hash: str, table: str):
        row = db.execute(f"SELECT * FROM {table} WHERE organization_id = ? AND idempotency_key = ?", (int(organization_id), key)).fetchone()
        if not row:
            return None
        if str(row["request_hash"]) != request_hash:
            raise AttendanceDomainError("ATTENDANCE_CLOSURE_IDEMPOTENCY_CONFLICT", "La clave de idempotencia ya fue usada con otro payload", 409)
        return row

    def _normalize_rule_configuration(self, config: dict, scope_type: str) -> dict:
        if not isinstance(config, dict):
            raise AttendanceDomainError("ATTENDANCE_RULE_CONFIGURATION_INVALID", "Configuracion invalida", 400)
        allowed = {
            "minimum_attendance_percentage",
            "minimum_attended_activities",
            "mandatory_activity_ids",
            "allow_partial_attendance",
            "require_event_presence",
            "require_all_mandatory_activities",
            "eligibility_mode",
            "allow_manual_override",
        }
        unknown = sorted(set(config) - allowed)
        if unknown:
            raise AttendanceDomainError("ATTENDANCE_RULE_CONFIGURATION_INVALID", "La configuracion contiene campos no permitidos", 400)
        try:
            minimum_percentage = Decimal(str(config.get("minimum_attendance_percentage", "80"))).quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError) as exc:
            raise AttendanceDomainError("ATTENDANCE_RULE_CONFIGURATION_INVALID", "Porcentaje minimo invalido", 400) from exc
        if minimum_percentage < 0 or minimum_percentage > 100:
            raise AttendanceDomainError("ATTENDANCE_RULE_CONFIGURATION_INVALID", "Porcentaje minimo fuera de rango", 400)
        minimum_attended = int(config.get("minimum_attended_activities", 0) or 0)
        if minimum_attended < 0:
            raise AttendanceDomainError("ATTENDANCE_RULE_CONFIGURATION_INVALID", "Minimo de actividades invalido", 400)
        mandatory_ids = []
        for value in config.get("mandatory_activity_ids", []) or []:
            try:
                activity_id = int(value)
            except (TypeError, ValueError) as exc:
                raise AttendanceDomainError("ATTENDANCE_RULE_CONFIGURATION_INVALID", "Actividad obligatoria invalida", 400) from exc
            if activity_id <= 0:
                raise AttendanceDomainError("ATTENDANCE_RULE_CONFIGURATION_INVALID", "Actividad obligatoria invalida", 400)
            mandatory_ids.append(activity_id)
        eligibility_mode = str(config.get("eligibility_mode", "ALL")).strip().upper()
        if eligibility_mode not in {"ALL", "ANY"}:
            raise AttendanceDomainError("ATTENDANCE_RULE_CONFIGURATION_INVALID", "Modo de elegibilidad invalido", 400)
        return {
            "schema": "attendance_rule_configuration_v1",
            "scope_type": scope_type,
            "minimum_attendance_percentage": str(minimum_percentage),
            "minimum_attended_activities": minimum_attended,
            "mandatory_activity_ids": sorted(set(mandatory_ids)),
            "allow_partial_attendance": bool(config.get("allow_partial_attendance", False)),
            "require_event_presence": bool(config.get("require_event_presence", scope_type == "EVENT")),
            "require_all_mandatory_activities": bool(config.get("require_all_mandatory_activities", True)),
            "eligibility_mode": eligibility_mode,
            "allow_manual_override": bool(config.get("allow_manual_override", True)),
        }

    def _build_closure_snapshot(self, db, organization_id: int, event_id: int, activity_id: int | None, scope_type: str, version, cutoff_at: str, actor: str) -> dict:
        config = self._json(version["configuration_json"])
        participants = db.execute(
            """
            SELECT ac.id AS accreditation_id, ac.person_id AS participant_id
            FROM accreditations ac
            WHERE ac.event_id = ?
            ORDER BY ac.person_id, ac.id
            """,
            (event_id,),
        ).fetchall()
        if scope_type == "ACTIVITY":
            required_units = [int(activity_id)]
        else:
            activities = db.execute("SELECT id FROM activities WHERE event_id = ? ORDER BY id", (event_id,)).fetchall()
            required_units = [int(row["id"]) for row in activities]
        mandatory_ids = [int(v) for v in config.get("mandatory_activity_ids", []) if int(v) in set(required_units)]
        evaluations = []
        for participant in participants:
            evaluations.append(
                self._evaluate_participant(
                    db,
                    organization_id=organization_id,
                    event_id=event_id,
                    activity_id=activity_id,
                    scope_type=scope_type,
                    participant_id=int(participant["participant_id"]),
                    accreditation_id=int(participant["accreditation_id"]),
                    required_units=required_units,
                    mandatory_activity_ids=mandatory_ids,
                    config=config,
                    cutoff_at=cutoff_at,
                )
            )
        return {
            "schema": "attendance_closure_snapshot_v1",
            "algorithm_version": ATTENDANCE_EVALUATION_ALGORITHM_VERSION,
            "organization_id": organization_id,
            "event_id": event_id,
            "activity_id": activity_id,
            "scope_type": scope_type,
            "rule_set_version_id": int(version["id"]),
            "rule_configuration_hash": version["configuration_hash"],
            "cutoff_at": cutoff_at,
            "created_by": actor,
            "evaluations": evaluations,
        }

    def _evaluate_participant(self, db, *, organization_id: int, event_id: int, activity_id: int | None, scope_type: str, participant_id: int, accreditation_id: int, required_units: list[int], mandatory_activity_ids: list[int], config: dict, cutoff_at: str) -> dict:
        params: list[object] = [organization_id, event_id, participant_id, cutoff_at]
        where = [
            "organization_id = ?",
            "event_id = ?",
            "participant_id = ?",
            "occurred_at <= ?",
            "status <> 'INVALIDATED'",
        ]
        if scope_type == "ACTIVITY":
            where.append("activity_id = ?")
            params.append(activity_id)
        rows = db.execute(
            f"SELECT * FROM attendance_records WHERE {' AND '.join(where)} ORDER BY activity_id, occurred_at, id",
            tuple(params),
        ).fetchall()
        attended_units: set[int] = set()
        event_presence = False
        items = []
        for row in rows:
            status = str(row["status"])
            row_activity = int(row["activity_id"] or 0)
            if status == "PRESENT" or (status == "PARTIAL" and bool(config.get("allow_partial_attendance"))):
                if row_activity:
                    attended_units.add(row_activity)
                if str(row["attendance_type"]) == "EVENT" or not row_activity:
                    event_presence = True
            items.append(
                {
                    "attendance_record_id": int(row["id"]),
                    "activity_id": row_activity or None,
                    "unit_key": f"activity:{row_activity}" if row_activity else "event",
                    "status": status,
                    "weight": "1.00" if status == "PRESENT" else "0.50" if status == "PARTIAL" and bool(config.get("allow_partial_attendance")) else "0.00",
                }
            )
        required_count = len(required_units) if required_units else (1 if bool(config.get("require_event_presence")) else 0)
        attended_count = len(attended_units & set(required_units)) if required_units else (1 if event_presence else 0)
        percentage = Decimal("0.00")
        if required_count:
            percentage = ((Decimal(attended_count) / Decimal(required_count)) * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        failures: list[str] = []
        if required_count == 0:
            failures.append("INSUFFICIENT_REQUIRED_UNITS")
        minimum_percentage = Decimal(str(config.get("minimum_attendance_percentage", "80")))
        if required_count and percentage < minimum_percentage:
            failures.append("MINIMUM_PERCENTAGE_NOT_MET")
        minimum_attended = int(config.get("minimum_attended_activities", 0) or 0)
        if attended_count < minimum_attended:
            failures.append("MINIMUM_ATTENDED_ACTIVITIES_NOT_MET")
        if bool(config.get("require_event_presence")) and not (event_presence or attended_count > 0):
            failures.append("EVENT_PRESENCE_REQUIRED")
        missing_mandatory = sorted(set(mandatory_activity_ids) - attended_units)
        if bool(config.get("require_all_mandatory_activities")) and missing_mandatory:
            failures.append("MANDATORY_ACTIVITIES_MISSING")
        if required_count == 0:
            result_status = "INSUFFICIENT_DATA"
        else:
            result_status = "ELIGIBLE" if not failures else "NOT_ELIGIBLE"
        return {
            "participant_id": participant_id,
            "accreditation_id": accreditation_id,
            "result_status": result_status,
            "attendance_percentage": str(percentage),
            "attended_count": attended_count,
            "required_count": required_count,
            "duration_minutes": 0,
            "eligible": result_status == "ELIGIBLE",
            "failure_reasons": failures,
            "calculation_details": {
                "required_units": required_units,
                "attended_units": sorted(attended_units),
                "mandatory_activity_ids": mandatory_activity_ids,
                "missing_mandatory_activity_ids": missing_mandatory,
                "records_considered": [item["attendance_record_id"] for item in items],
            },
            "items": items,
        }

    def _insert_evaluation(self, db, closure_id: int, organization_id: int, event_id: int, activity_id: int | None, evaluation: dict, actor: str) -> None:
        now = self.now()
        cur = db.execute(
            """
            INSERT INTO attendance_evaluations (
                closure_id, organization_id, event_id, activity_id, participant_id,
                accreditation_id, result_status, attendance_percentage, attended_count,
                required_count, duration_minutes, eligible, failure_reasons_json,
                calculation_details_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                closure_id,
                organization_id,
                event_id,
                activity_id,
                evaluation["participant_id"],
                evaluation["accreditation_id"],
                evaluation["result_status"],
                evaluation["attendance_percentage"],
                evaluation["attended_count"],
                evaluation["required_count"],
                evaluation["duration_minutes"],
                1 if evaluation["eligible"] else 0,
                json.dumps(evaluation["failure_reasons"], ensure_ascii=True, sort_keys=True),
                json.dumps(evaluation["calculation_details"], ensure_ascii=True, sort_keys=True),
                now,
            ),
        )
        evaluation_id = int(cur.lastrowid)
        for item in evaluation.get("items", []):
            db.execute(
                """
                INSERT INTO attendance_evaluation_items (
                    evaluation_id, organization_id, event_id, activity_id, attendance_record_id,
                    unit_key, status, weight, details_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (evaluation_id, organization_id, event_id, item.get("activity_id"), item.get("attendance_record_id"), item["unit_key"], item["status"], item["weight"], "{}", now),
            )
        db.execute(
            """
            INSERT INTO attendance_eligibility_decisions (
                closure_id, evaluation_id, organization_id, event_id, participant_id,
                automatic_result, effective_result, status, reasons_json, decided_at,
                decided_by, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (closure_id, evaluation_id, organization_id, event_id, evaluation["participant_id"], evaluation["result_status"], evaluation["result_status"], evaluation["result_status"], json.dumps(evaluation["failure_reasons"], ensure_ascii=True, sort_keys=True), now, "system", now),
        )
        self.audit_service.record(db, actor, "attendance.evaluation.generated", "attendance_evaluation", evaluation_id, {"organization_id": organization_id, "event_id": event_id, "closure_id": closure_id, "participant_id": evaluation["participant_id"], "result_status": evaluation["result_status"]})

    def _stable_hash(self, payload: dict) -> str:
        body = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(body.encode("utf-8")).hexdigest()

    def _rule_set_payload(self, row) -> dict:
        return dict(row)

    def _rule_version_payload(self, row) -> dict:
        data = dict(row)
        data["configuration"] = self._json(data.pop("configuration_json", "{}"))
        return data

    def _closure_payload(self, row) -> dict:
        data = dict(row)
        data["snapshot"] = self._json(data.pop("snapshot_json", "{}"))
        return data

    def _evaluation_payload(self, row) -> dict:
        data = dict(row)
        data["eligible"] = bool(data.get("eligible"))
        data["failure_reasons"] = self._json_list(data.pop("failure_reasons_json", "[]"))
        data["calculation_details"] = self._json(data.pop("calculation_details_json", "{}"))
        return data

    def _decision_payload(self, row) -> dict:
        data = dict(row)
        data["reasons"] = self._json_list(data.pop("reasons_json", "[]"))
        return data
