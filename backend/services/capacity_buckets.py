from __future__ import annotations

from collections.abc import Callable

from backend.repositories import SQLiteRepository


class CapacityBucketService:
    def __init__(self, repository: SQLiteRepository | None = None, now: Callable[[], str] | None = None) -> None:
        self.repository = repository or SQLiteRepository()
        self.now = now

    def ensure_for_event(self, db, event_id: int | None = None, activity_id: int | None = None) -> None:
        params: list[object] = []
        where = "1 = 1"
        if event_id:
            where += " AND event_id = ?"
            params.append(event_id)
        if activity_id:
            where += " AND id = ?"
            params.append(activity_id)
        activities = db.execute(f"SELECT * FROM activities WHERE {where}", params).fetchall()
        for activity in activities:
            existing = db.execute("SELECT COUNT(*) AS c FROM capacity_bags WHERE activity_id = ?", (activity["id"],)).fetchone()["c"]
            if existing:
                continue
            capacity = int(activity["capacity"] or 0)
            db.execute(
                """
                INSERT OR IGNORE INTO capacity_bags (
                    event_id, activity_id, name, code, assigned_capacity, priority,
                    public_visible, public_registration, reception_enabled, release_enabled, status, created_at
                )
                VALUES (?, ?, 'Online', 'online', ?, 10, 1, 1, 1, 1, 'active', ?)
                """,
                (activity["event_id"], activity["id"], max(capacity, 0), self._now()),
            )
            for priority, name, code in [
                (20, "Mostrador", "mostrador"),
                (30, "Empresas", "empresas"),
                (40, "Invitaciones", "invitaciones"),
                (50, "Sponsors", "sponsors"),
                (60, "Prensa", "prensa"),
                (70, "Protocolo", "protocolo"),
                (80, "Staff", "staff"),
                (90, "Backup operativo", "backup_operativo"),
            ]:
                db.execute(
                    """
                    INSERT OR IGNORE INTO capacity_bags (
                        event_id, activity_id, name, code, assigned_capacity, priority,
                        public_visible, public_registration, reception_enabled, release_enabled, status, created_at
                    )
                    VALUES (?, ?, ?, ?, 0, ?, 0, 0, 1, 1, 'active', ?)
                    """,
                    (activity["event_id"], activity["id"], name, code, priority, self._now()),
                )

    def bag_usage(self, db, bag_id: int) -> int:
        return int(
            self.repository.scalar(
                db,
                "SELECT COUNT(*) AS c FROM reservations WHERE bag_id = ? AND status = 'confirmed'",
                (bag_id,),
            )
            or 0
        )

    def public_availability(self, db, activity_id: int) -> dict:
        self.ensure_for_event(db, activity_id=activity_id)
        capacity = int(
            self.repository.scalar(
                db,
                """
                SELECT SUM(assigned_capacity) AS capacity
                FROM capacity_bags
                WHERE activity_id = ? AND public_visible = 1 AND status = 'active'
                """,
                (activity_id,),
            )
            or 0
        )
        used = int(
            self.repository.scalar(
                db,
                """
                SELECT COUNT(*) AS c
                FROM reservations r
                JOIN capacity_bags b ON b.id = r.bag_id
                WHERE r.activity_id = ? AND r.status = 'confirmed'
                  AND b.public_visible = 1 AND b.status = 'active'
                """,
                (activity_id,),
            )
            or 0
        )
        remaining = max(capacity - used, 0)
        if capacity == 0 or remaining == 0:
            label, color = "Completa", "red"
        elif remaining / capacity <= 0.2:
            label, color = f"Ultimos lugares ({remaining})", "yellow"
        else:
            label, color = f"Quedan {remaining} lugares", "green"
        return {"capacity": capacity, "used": used, "remaining": remaining, "label": label, "color": color}

    def pick_bucket(self, db, event_id: int, activity_id: int, source: str):
        self.ensure_for_event(db, event_id=event_id, activity_id=activity_id)
        activity = db.execute("SELECT capacity FROM activities WHERE id = ?", (activity_id,)).fetchone()
        physical_capacity = int(activity["capacity"] or 0) if activity else 0
        source_filter = "public_registration = 1" if source == "public" else "reception_enabled = 1"
        rows = db.execute(
            f"""
            SELECT *
            FROM capacity_bags
            WHERE event_id = ? AND activity_id = ? AND status = 'active' AND {source_filter}
            ORDER BY priority, id
            """,
            (event_id, activity_id),
        ).fetchall()
        for row in rows:
            assigned = int(row["assigned_capacity"] or 0)
            if (assigned == 0 and physical_capacity == 0) or (assigned > 0 and self.bag_usage(db, row["id"]) < assigned):
                return row
        return None

    def _now(self) -> str:
        if not self.now:
            raise RuntimeError("CapacityBucketService requires a now provider")
        return self.now()
