from __future__ import annotations


class EventLifecycleError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class EventLifecycleService:
    """Small transactional state machine for the formal end of an event."""

    CLOSED_STATUS = "closed"
    CLOSABLE_STATUSES = {"draft", "published", "active"}

    def __init__(self, audit_service, now) -> None:
        self.audit_service = audit_service
        self.now = now

    def close_event(
        self,
        db,
        *,
        event_id: int,
        actor: str,
        reason: str,
        confirmation: str,
    ) -> dict:
        row = db.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
        if not row:
            raise EventLifecycleError("EVENT_NOT_FOUND", "Evento inexistente", 404)

        status = str(row["status"] or "").strip().lower()
        if status == self.CLOSED_STATUS:
            return {"ok": True, "idempotent": True, "item": self._payload(row)}
        if status not in self.CLOSABLE_STATUSES:
            raise EventLifecycleError("EVENT_NOT_CLOSABLE", "El estado actual no permite finalizar el evento", 409)
        if str(confirmation or "").strip().upper() != "FINALIZAR":
            raise EventLifecycleError("EVENT_CLOSE_CONFIRMATION_REQUIRED", "Se requiere confirmacion explicita", 400)

        actor = str(actor or "").strip()
        if not actor:
            raise EventLifecycleError("EVENT_CLOSE_ACTOR_REQUIRED", "No se pudo identificar al responsable", 400)
        reason = str(reason or "").strip()[:500]
        now = self.now()
        db.execute(
            """
            UPDATE events
            SET status = ?, closed_at = ?, closed_by = ?, closure_reason = ?
            WHERE id = ? AND status = ?
            """,
            (self.CLOSED_STATUS, now, actor, reason, event_id, row["status"]),
        )
        updated = db.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
        if not updated or str(updated["status"]).lower() != self.CLOSED_STATUS:
            raise EventLifecycleError("EVENT_CLOSE_CONFLICT", "El evento cambio durante la finalizacion", 409)

        counts = self.closure_snapshot(db, event_id)
        self.audit_service.record(
            db,
            actor,
            "event.closed",
            "event",
            event_id,
            {"event_id": event_id, "previous_status": status, "reason": reason, "snapshot": counts},
        )
        return {"ok": True, "idempotent": False, "item": self._payload(updated), "snapshot": counts}

    def closure_snapshot(self, db, event_id: int) -> dict:
        def count(sql: str) -> int:
            return int(db.execute(sql, (event_id,)).fetchone()["c"] or 0)

        return {
            "participants": count("SELECT COUNT(*) AS c FROM accreditations WHERE event_id = ? AND status <> 'cancelled'"),
            "checked_in": count("SELECT COUNT(*) AS c FROM accreditations WHERE event_id = ? AND checked_in_at IS NOT NULL AND status <> 'cancelled'"),
            "activities": count("SELECT COUNT(*) AS c FROM activities WHERE event_id = ? AND status <> 'cancelled'"),
            "attendance_records": count("SELECT COUNT(*) AS c FROM attendance_records WHERE event_id = ? AND status = 'VALID'"),
            "certificates": count("SELECT COUNT(*) AS c FROM certificate_issuances WHERE event_id = ? AND status = 'ISSUED'"),
        }

    @staticmethod
    def _payload(row) -> dict:
        return {
            "id": int(row["id"]),
            "status": str(row["status"]),
            "closed_at": row["closed_at"],
            "closed_by": row["closed_by"],
            "closure_reason": row["closure_reason"],
        }


def event_is_closed(db, event_id: int) -> bool:
    row = db.execute("SELECT status FROM events WHERE id = ?", (event_id,)).fetchone()
    return bool(row and str(row["status"] or "").strip().lower() == EventLifecycleService.CLOSED_STATUS)
