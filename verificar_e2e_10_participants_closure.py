from __future__ import annotations

from datetime import datetime, timedelta

from backend.services.access_validation import AccessValidationService


class FakeRepository:
    def __init__(self, checked_in: bool) -> None:
        self.checked_in = checked_in
        self.logs: list[dict] = []
        self.incremented = False

    def accreditation_for_access(self, db, token: str) -> dict:
        return {
            "id": 10,
            "event_id": 7,
            "status": "active",
            "type_access_enabled": 1,
            "checked_in_at": "2026-08-10T20:00:00" if self.checked_in else "",
            "max_reentries": 0,
            "access_count": 0,
        }

    def activity_for_access(self, db, activity_id: int, event_id: int) -> dict:
        return {
            "id": activity_id,
            "event_id": event_id,
            "reservation_mode": "free",
            "starts_at": (datetime.now() - timedelta(minutes=5)).isoformat(timespec="seconds"),
            "access_open_minutes_before": 10,
            "event_access_open_minutes_before": 10,
        }

    def confirmed_reservation(self, db, activity_id: int, accreditation_id: int):
        return None

    def granted_activity_access(self, db, activity_id: int, accreditation_id: int):
        return None

    def increment_activity_access(self, db, accreditation_id: int) -> None:
        self.incremented = True

    def mark_general_access(self, db, accreditation_id: int, operator: str, now: str) -> None:
        self.checked_in = True

    def add_access_log(self, db, **payload) -> None:
        self.logs.append(payload)


class FakeAudit:
    def record(self, db, actor: str, action: str, entity_type: str, entity_id: int, payload: dict) -> None:
        return None


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    pending_repo = FakeRepository(checked_in=False)
    service = AccessValidationService(repository=pending_repo, audit_service=FakeAudit(), now=lambda: datetime.now().isoformat(timespec="seconds"))
    pending = service.validate(None, "EVT-VALIDO", "acceso-e2e", "Acceso principal E2E", activity_id=44)
    check(pending["result"] == "rejected", "QR valido no acreditado debe ser bloqueado")
    check("pendiente de acreditacion" in pending["reason"].lower(), "Mensaje de bloqueo no explica acreditacion pendiente")
    check(not pending_repo.incremented, "No debe registrar acceso de actividad sin acreditacion previa")

    checked_repo = FakeRepository(checked_in=True)
    service = AccessValidationService(repository=checked_repo, audit_service=FakeAudit(), now=lambda: datetime.now().isoformat(timespec="seconds"))
    granted = service.validate(None, "EVT-VALIDO", "acceso-e2e", "Acceso principal E2E", activity_id=44)
    check(granted["result"] == "granted", "QR acreditado debe permitir acceso a actividad valida")
    check(checked_repo.incremented, "Debe registrar acceso de actividad acreditada")

    print("OK: cierre E2E 10 participantes - regla acreditacion antes de acceso")


if __name__ == "__main__":
    main()
