from __future__ import annotations

import sqlite3

from backend.repositories import SQLiteRepository


class TracedConnection:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection
        self.statements: list[str] = []

    def execute(self, sql: str, params=()):
        self.statements.append(" ".join(sql.split()))
        return self.connection.execute(sql, params)


def main() -> int:
    raw = sqlite3.connect(":memory:")
    raw.row_factory = sqlite3.Row
    raw.execute(
        """
        CREATE TABLE audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER,
            actor TEXT NOT NULL,
            action TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id INTEGER,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    traced = TracedConnection(raw)
    SQLiteRepository().insert_audit(
        traced,
        event_id=42,
        actor="Operador",
        action="access.validated",
        entity_type="accreditation",
        entity_id=7,
        payload_json='{"event_id": 42}',
        created_at="2026-11-04T00:00:00",
    )
    row = raw.execute("SELECT * FROM audit_logs").fetchone()
    assert row is not None
    assert row["event_id"] == 42
    assert row["action"] == "access.validated"
    assert len(traced.statements) == 1
    assert traced.statements[0].startswith("INSERT INTO audit_logs (event_id,")
    assert all("PRAGMA" not in statement.upper() for statement in traced.statements)
    print("P0_AUDIT_SCHEMA_CONTRACT_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
