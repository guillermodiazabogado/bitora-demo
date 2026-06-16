from __future__ import annotations

from collections.abc import Callable

from backend.repositories import SQLiteRepository
from backend.services.capacity_buckets import CapacityBucketService


class ReservationService:
    def __init__(
        self,
        repository: SQLiteRepository | None = None,
        capacity_service: CapacityBucketService | None = None,
        now: Callable[[], str] | None = None,
    ) -> None:
        self.repository = repository or SQLiteRepository()
        self.capacity_service = capacity_service or CapacityBucketService(repository=self.repository, now=now)
        self.now = now

    def create(
        self,
        db,
        event_id: int,
        activity_id: int,
        accreditation_id: int,
        source: str = "reception",
        overlap_validator: Callable[[object, int, int, int], str | None] | None = None,
    ) -> dict:
        acc = self.repository.accreditation_for_reservation(db, event_id, accreditation_id)
        if not acc:
            return {"ok": False, "error": "Acreditacion no valida", "status_code": 404}
        event = db.execute("SELECT activities_enabled, waitlist_enabled FROM events WHERE id = ?", (event_id,)).fetchone()
        if event and not int(event["activities_enabled"] or 0):
            return {"ok": False, "error": "Este evento no utiliza inscripciones a actividades", "status_code": 409}
        activity = self.repository.activity_for_reservation(db, event_id, activity_id)
        if not activity:
            return {"ok": False, "error": "Actividad no valida", "status_code": 404}
        existing = self.repository.reservation_for_pair(db, activity_id, accreditation_id)
        if existing:
            return {"ok": True, "id": existing["id"], "status": existing["status"], "existing": True}
        if overlap_validator:
            overlap = overlap_validator(db, accreditation_id, activity_id)
            if overlap:
                return {
                    "ok": False,
                    "code": "schedule_overlap",
                    "error": overlap,
                    "status_code": 409,
                    "activity_id": activity_id,
                    "title": activity["title"],
                }
        bag = self.capacity_service.pick_bucket(db, event_id, activity_id, source)
        if not bag and event and not int(event["waitlist_enabled"] or 0):
            return {"ok": False, "error": "Cupo completo", "status_code": 409}
        status = "confirmed" if bag else "waitlisted"
        reservation_id = self.repository.insert_reservation(
            db,
            event_id=event_id,
            activity_id=activity_id,
            bag_id=bag["id"] if bag else None,
            accreditation_id=accreditation_id,
            status=status,
            created_at=self._now(),
        )
        return {"ok": True, "id": reservation_id, "status": status, "activity_id": activity_id, "title": activity["title"]}

    def activity_has_capacity(self, db, activity_id: int) -> bool:
        activity = db.execute("SELECT * FROM activities WHERE id = ?", (activity_id,)).fetchone()
        if not activity:
            return False
        return self.capacity_service.pick_bucket(db, activity["event_id"], activity_id, "reception") is not None

    def promote_next_waitlisted(self, db, event_id: int, activity_id: int) -> dict | None:
        bag = self.capacity_service.pick_bucket(db, event_id, activity_id, "reception")
        if not bag:
            return None
        row = self.repository.waitlisted_reservation(db, event_id, activity_id)
        if not row:
            return None
        self.repository.promote_reservation(db, row["id"], bag["id"])
        promoted = dict(row)
        promoted["bag_id"] = bag["id"]
        return promoted

    def _now(self) -> str:
        if not self.now:
            raise RuntimeError("ReservationService requires a now provider")
        return self.now()
