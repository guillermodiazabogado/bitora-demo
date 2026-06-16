from __future__ import annotations

import sqlite3
from typing import Any


class SQLiteRepository:
    """Data-access boundary for the current SQLite implementation.

    Services should depend on this repository shape instead of embedding SQL in
    HTTP handlers. A PostgreSQL repository can later provide the same methods.
    """

    def accreditation_for_access(self, db: sqlite3.Connection, token: str):
        return db.execute(
            """
            SELECT a.*, COALESCE(t.access_enabled, 1) AS type_access_enabled
            FROM accreditations a
            LEFT JOIN accreditation_types t ON t.event_id = a.event_id AND t.name = a.type
            WHERE a.token = ?
            """,
            (token,),
        ).fetchone()

    def activity_for_access(self, db: sqlite3.Connection, activity_id: int, event_id: int):
        return db.execute(
            """
            SELECT a.*, e.activity_access_open_minutes_before AS event_access_open_minutes_before
            FROM activities a
            JOIN events e ON e.id = a.event_id
            WHERE a.id = ? AND a.event_id = ? AND a.status <> 'cancelled'
            """,
            (activity_id, event_id),
        ).fetchone()

    def confirmed_reservation(self, db: sqlite3.Connection, activity_id: int, accreditation_id: int):
        return db.execute(
            """
            SELECT * FROM reservations
            WHERE activity_id = ? AND accreditation_id = ? AND status = 'confirmed'
            """,
            (activity_id, accreditation_id),
        ).fetchone()

    def granted_activity_access(self, db: sqlite3.Connection, activity_id: int, accreditation_id: int):
        return db.execute(
            """
            SELECT *
            FROM access_logs
            WHERE activity_id = ?
              AND accreditation_id = ?
              AND access_context = 'activity_entry'
              AND result = 'granted'
            ORDER BY id
            LIMIT 1
            """,
            (activity_id, accreditation_id),
        ).fetchone()

    def increment_activity_access(self, db: sqlite3.Connection, accreditation_id: int) -> None:
        db.execute(
            "UPDATE accreditations SET access_count = access_count + 1 WHERE id = ?",
            (accreditation_id,),
        )

    def mark_general_access(self, db: sqlite3.Connection, accreditation_id: int, operator: str, checked_in_at: str) -> None:
        db.execute(
            """
            UPDATE accreditations
            SET checked_in_at = COALESCE(checked_in_at, ?),
                checked_in_by = ?,
                access_count = access_count + 1
            WHERE id = ?
            """,
            (checked_in_at, operator, accreditation_id),
        )

    def add_access_log(
        self,
        db: sqlite3.Connection,
        *,
        token: str,
        operator: str,
        checkpoint: str,
        result: str,
        reason: str,
        created_at: str,
        accreditation_id: int | None = None,
        event_id: int | None = None,
        activity_id: int | None = None,
        access_context: str = "event_entry",
        access_point: str = "",
        operator_id: int | None = None,
    ) -> None:
        db.execute(
            """
            INSERT INTO access_logs (
                accreditation_id, event_id, activity_id, token, operator, operator_id,
                checkpoint, access_point, access_context, result, reason, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                accreditation_id,
                event_id,
                activity_id,
                token,
                operator,
                operator_id,
                checkpoint,
                access_point or checkpoint,
                access_context,
                result,
                reason,
                created_at,
            ),
        )

    def insert_audit(
        self,
        db: sqlite3.Connection,
        *,
        actor: str,
        action: str,
        entity_type: str,
        entity_id: int | None,
        payload_json: str,
        created_at: str,
    ) -> None:
        db.execute(
            """
            INSERT INTO audit_logs (actor, action, entity_type, entity_id, payload, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (actor, action, entity_type, entity_id, payload_json, created_at),
        )

    def accreditation_for_reservation(self, db: sqlite3.Connection, event_id: int, accreditation_id: int):
        return db.execute(
            "SELECT * FROM accreditations WHERE id = ? AND event_id = ? AND status = 'active'",
            (accreditation_id, event_id),
        ).fetchone()

    def activity_for_reservation(self, db: sqlite3.Connection, event_id: int, activity_id: int):
        return db.execute(
            "SELECT * FROM activities WHERE id = ? AND event_id = ? AND status <> 'cancelled'",
            (activity_id, event_id),
        ).fetchone()

    def reservation_for_pair(self, db: sqlite3.Connection, activity_id: int, accreditation_id: int):
        return db.execute(
            "SELECT * FROM reservations WHERE activity_id = ? AND accreditation_id = ?",
            (activity_id, accreditation_id),
        ).fetchone()

    def insert_reservation(
        self,
        db: sqlite3.Connection,
        *,
        event_id: int,
        activity_id: int,
        bag_id: int | None,
        accreditation_id: int,
        status: str,
        created_at: str,
    ) -> int:
        cur = db.execute(
            """
            INSERT INTO reservations (event_id, activity_id, bag_id, accreditation_id, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (event_id, activity_id, bag_id, accreditation_id, status, created_at),
        )
        return int(cur.lastrowid)

    def waitlisted_reservation(self, db: sqlite3.Connection, event_id: int, activity_id: int):
        return db.execute(
            """
            SELECT *
            FROM reservations
            WHERE event_id = ? AND activity_id = ? AND status = 'waitlisted'
            ORDER BY id
            LIMIT 1
            """,
            (event_id, activity_id),
        ).fetchone()

    def promote_reservation(self, db: sqlite3.Connection, reservation_id: int, bag_id: int) -> None:
        db.execute("UPDATE reservations SET status = 'confirmed', bag_id = ? WHERE id = ?", (bag_id, reservation_id))

    def scalar(self, db: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> Any:
        row = db.execute(sql, params).fetchone()
        return row[0] if row else None
