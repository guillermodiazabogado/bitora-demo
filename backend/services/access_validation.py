from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
import re
from urllib.parse import parse_qs, urlparse

from backend.repositories import SQLiteRepository
from backend.services.audit import AuditService


class AccessValidationService:
    """Authoritative QR validation service.

    Frontend code never validates QR locally. This service owns the access
    decision and writes access logs inside the same transaction used by the API.
    """

    def __init__(
        self,
        repository: SQLiteRepository | None = None,
        audit_service: AuditService | None = None,
        now: Callable[[], str] | None = None,
    ) -> None:
        self.repository = repository or SQLiteRepository()
        self.now = now
        self.audit_service = audit_service or AuditService(repository=self.repository, now=now)

    def validate(self, db, token: str, operator: str, checkpoint: str, activity_id: int | None = None) -> dict:
        token = self._normalize_token(token)
        operator = operator.strip() or "operador"
        checkpoint = checkpoint.strip() or "Acceso principal"
        activity_id = int(activity_id or 0)

        acc = self.repository.accreditation_for_access(db, token)
        if not acc:
            self.repository.add_access_log(
                db,
                token=token,
                operator=operator,
                checkpoint=checkpoint,
                result="rejected",
                reason="QR inexistente",
                created_at=self._now(),
            )
            return {"result": "rejected", "reason": "QR inexistente", "color": "red", "status_code": 404}

        result = "granted"
        reason = "Acceso concedido"
        color = "green"
        if acc["status"] != "active":
            status_label = "cancelada" if acc["status"] == "cancelled" else acc["status"]
            result, reason, color = "rejected", f"Acreditacion {status_label}", "red"
        elif not int(acc["type_access_enabled"]):
            result, reason, color = "rejected", "Tipo de acreditacion no habilitado", "red"
        elif activity_id:
            activity = self.repository.activity_for_access(db, activity_id, acc["event_id"])
            if not activity:
                result, reason, color = "rejected", "Actividad incorrecta", "red"
            elif activity["reservation_mode"] in ("required", "invited"):
                reservation = self.repository.confirmed_reservation(db, activity_id, acc["id"])
                if not reservation:
                    result, reason, color = "rejected", "Sin reserva confirmada", "red"
            if result == "granted":
                duplicate = self.repository.granted_activity_access(db, activity_id, acc["id"])
                if duplicate:
                    try:
                        duplicated_at = datetime.fromisoformat(str(duplicate["created_at"])).astimezone().strftime("%H:%M")
                    except ValueError:
                        duplicated_at = str(duplicate["created_at"])[11:16]
                    result, reason, color = "rejected", f"Ya ingreso a esta actividad a las {duplicated_at}.", "yellow"
            if result == "granted":
                open_at, _open_minutes = self._activity_open_at(activity)
                if self._local_now() < open_at:
                    result = "rejected"
                    reason = f"Acceso aun no habilitado. Se habilita a las {open_at.strftime('%H:%M')}."
                    color = "yellow"
        elif acc["checked_in_at"] and int(acc["max_reentries"] or 0) == 0:
            result, reason, color = "rejected", "QR ya utilizado", "red"
        elif acc["checked_in_at"] and int(acc["max_reentries"] or 0) <= int(acc["access_count"] or 0):
            result, reason, color = "rejected", "Reingresos agotados", "red"

        if result == "granted":
            if activity_id:
                self.repository.increment_activity_access(db, acc["id"])
            else:
                self.repository.mark_general_access(db, acc["id"], operator, self._now())

        self.repository.add_access_log(
            db,
            accreditation_id=acc["id"],
            event_id=acc["event_id"],
            activity_id=activity_id or None,
            token=token,
            operator=operator,
            checkpoint=checkpoint,
            access_context="activity_entry" if activity_id else "event_entry",
            access_point=checkpoint,
            result=result,
            reason=reason,
            created_at=self._now(),
        )
        self.audit_service.record(
            db,
            operator,
            "access.validated",
            "accreditation",
            acc["id"],
            {"event_id": acc["event_id"], "result": result, "reason": reason, "checkpoint": checkpoint, "activity_id": activity_id},
        )
        return {"result": result, "reason": reason, "color": color, "status_code": 200}

    def _activity_open_at(self, activity) -> tuple[datetime, int]:
        raw_activity_minutes = activity["access_open_minutes_before"]
        raw_event_minutes = activity["event_access_open_minutes_before"]
        minutes = raw_activity_minutes if raw_activity_minutes is not None and str(raw_activity_minutes) != "" else raw_event_minutes
        minutes = max(0, int(minutes if minutes is not None else 10))
        return datetime.fromisoformat(activity["starts_at"]) - timedelta(minutes=minutes), minutes

    def _local_now(self) -> datetime:
        current = datetime.fromisoformat(self._now())
        if current.tzinfo:
            return current.astimezone().replace(tzinfo=None)
        return current

    def _now(self) -> str:
        if not self.now:
            raise RuntimeError("AccessValidationService requires a now provider")
        return self.now()

    def _normalize_token(self, token: str) -> str:
        raw = str(token or "").strip()
        match = re.search(r"EVT-[A-Z0-9]+", raw, re.IGNORECASE)
        if match:
            return match.group(0).upper()
        parsed = urlparse(raw)
        if parsed.query:
            candidate = parse_qs(parsed.query).get("token", [""])[0]
            match = re.search(r"EVT-[A-Z0-9]+", candidate, re.IGNORECASE)
            if match:
                return match.group(0).upper()
        return raw.upper()
