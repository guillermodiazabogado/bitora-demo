from __future__ import annotations

import sqlite3

import server


class RecordingPostgresConnection:
    engine = "postgres"

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[int, ...]]] = []

    def execute(self, sql: str, params=()):
        self.calls.append((sql, tuple(params)))
        return self


def main() -> None:
    scope = {"organization_id": 7, "event_id": 19, "accreditation_id": 23}
    first = RecordingPostgresConnection()
    second = RecordingPostgresConnection()
    first_key = server.acquire_access_transaction_lock(first, scope)
    second_key = server.acquire_access_transaction_lock(second, dict(scope))
    if first_key != second_key or first_key is None:
        raise AssertionError("the lock key must be stable for the same accreditation scope")
    if first.calls != [("SELECT pg_advisory_xact_lock(?)", (first_key,))]:
        raise AssertionError(first.calls)

    distinct = RecordingPostgresConnection()
    distinct_key = server.acquire_access_transaction_lock(
        distinct,
        {**scope, "accreditation_id": 24},
    )
    if distinct_key == first_key:
        raise AssertionError("different accreditations must not share the critical section")

    sqlite_db = sqlite3.connect(":memory:")
    try:
        if server.acquire_access_transaction_lock(sqlite_db, scope) is not None:
            raise AssertionError("SQLite must continue using its existing process lock")
    finally:
        sqlite_db.close()
    print("P1 PostgreSQL distributed access lock: OK")


if __name__ == "__main__":
    main()
