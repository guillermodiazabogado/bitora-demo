from __future__ import annotations

from .sqlite import SQLiteRepository


class PostgresRepository(SQLiteRepository):
    """PostgreSQL repository with row locks around critical decisions."""

    def accreditation_for_access(self, db, token: str):
        return db.execute(
            """
            SELECT a.*, COALESCE(t.access_enabled, 1) AS type_access_enabled
            FROM accreditations a
            LEFT JOIN accreditation_types t ON t.event_id = a.event_id AND t.name = a.type
            WHERE a.token = ?
            FOR UPDATE OF a
            """,
            (token,),
        ).fetchone()

    def activity_for_reservation(self, db, event_id: int, activity_id: int):
        return db.execute(
            """
            SELECT * FROM activities
            WHERE id = ? AND event_id = ? AND status <> 'cancelled'
            FOR UPDATE
            """,
            (activity_id, event_id),
        ).fetchone()

    def waitlisted_reservation(self, db, event_id: int, activity_id: int):
        return db.execute(
            """
            SELECT *
            FROM reservations
            WHERE event_id = ? AND activity_id = ? AND status = 'waitlisted'
            ORDER BY id
            LIMIT 1
            FOR UPDATE SKIP LOCKED
            """,
            (event_id, activity_id),
        ).fetchone()
