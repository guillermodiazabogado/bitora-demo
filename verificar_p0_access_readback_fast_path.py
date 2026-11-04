from __future__ import annotations

import unittest

from backend.services.access_state_engine import (
    AccessStateContext,
    AccessStateDecision,
    AccessStateEngine,
    DENY,
)


class FakeCursor:
    def __init__(self, *, lastrowid: int = 0, row: dict | None = None) -> None:
        self.lastrowid = lastrowid
        self._row = row

    def fetchone(self):
        return self._row


class RecordingDatabase:
    def __init__(self) -> None:
        self.statements: list[str] = []

    def execute(self, sql: str, params=()):
        normalized = " ".join(sql.split())
        self.statements.append(normalized)
        if normalized.startswith("INSERT INTO enterprise_access_events"):
            return FakeCursor(lastrowid=101)
        if normalized.startswith("SELECT * FROM enterprise_access_events WHERE id"):
            return FakeCursor(row={"id": 101, "decision": "DENY", "reason_code": "RULE_DENIED"})
        if normalized.startswith("INSERT INTO enterprise_access_comparisons"):
            return FakeCursor(lastrowid=202)
        if normalized.startswith("SELECT * FROM enterprise_access_comparisons WHERE id"):
            return FakeCursor(row={"id": 202, "comparison": "MATCH_DENY", "classification": "MATCH"})
        raise AssertionError(f"SQL inesperado: {normalized}")


class AccessReadbackFastPathTest(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = AccessStateEngine(now=lambda: "2026-11-04T12:00:00")
        self.context = AccessStateContext(organization_id=1, event_id=2, token="EVT-TEST")
        self.decision = AccessStateDecision(decision=DENY, reason_code="RULE_DENIED")

    def test_default_access_event_preserves_readback(self) -> None:
        db = RecordingDatabase()

        result = self.engine.record_access_event(db, self.context, self.decision)

        self.assertEqual(result["decision"], "DENY")
        self.assertTrue(any("SELECT * FROM enterprise_access_events WHERE id" in sql for sql in db.statements))

    def test_access_event_fast_path_returns_id_without_readback(self) -> None:
        db = RecordingDatabase()

        result = self.engine.record_access_event(db, self.context, self.decision, read_back=False)

        self.assertEqual(result, {"id": 101})
        self.assertFalse(any("SELECT * FROM enterprise_access_events WHERE id" in sql for sql in db.statements))

    def test_default_comparison_preserves_readback(self) -> None:
        db = RecordingDatabase()

        result = self.engine.record_comparison(db, self.context, self.decision, {"result": "rejected", "reason": "denied"})

        self.assertEqual(result["comparison"], "MATCH_DENY")
        self.assertTrue(any("SELECT * FROM enterprise_access_comparisons WHERE id" in sql for sql in db.statements))

    def test_comparison_fast_path_returns_identity_without_readback(self) -> None:
        db = RecordingDatabase()

        result = self.engine.record_comparison(
            db,
            self.context,
            self.decision,
            {"result": "rejected", "reason": "denied"},
            read_back=False,
        )

        self.assertEqual(result, {"id": 202, "comparison": "MATCH_DENY", "classification": "MATCH"})
        self.assertFalse(any("SELECT * FROM enterprise_access_comparisons WHERE id" in sql for sql in db.statements))


if __name__ == "__main__":
    unittest.main()
