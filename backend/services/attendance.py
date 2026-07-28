from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from datetime import datetime, timezone

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
