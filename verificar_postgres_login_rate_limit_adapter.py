from __future__ import annotations

from backend.database import PostgresConnection, _ID_TABLES


class FakeCursor:
    rowcount = 1

    def fetchone(self):
        raise AssertionError("The login rate-limit upsert must not fetch a generated id")

    def fetchall(self):
        return []


class FakeRaw:
    def __init__(self) -> None:
        self.executed_sql = ""
        self.executed_params = ()

    def execute(self, sql, params=()):
        self.executed_sql = sql
        self.executed_params = params
        return FakeCursor()


def main() -> None:
    if "auth_login_rate_limits" in _ID_TABLES:
        raise AssertionError("Composite/text-key table must not request RETURNING id")

    raw = FakeRaw()
    connection = PostgresConnection(raw, pool=None)
    cursor = connection.execute(
        """
        INSERT INTO auth_login_rate_limits (
            request_fingerprint, window_started_at, attempts, blocked_until,
            last_attempt_at, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(request_fingerprint) DO UPDATE SET
            attempts = excluded.attempts,
            updated_at = excluded.updated_at
        """,
        ("fingerprint", "now", 1, None, "now", "now", "now"),
    )

    if "RETURNING id" in raw.executed_sql:
        raise AssertionError(raw.executed_sql)
    if "%s" not in raw.executed_sql or cursor.lastrowid is not None:
        raise AssertionError((raw.executed_sql, cursor.lastrowid))
    print("PostgreSQL login rate-limit adapter contract: OK")


if __name__ == "__main__":
    main()
