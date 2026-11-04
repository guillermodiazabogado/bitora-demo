from __future__ import annotations

import unittest

import server


class FakeCursor:
    def __init__(self, row=None) -> None:
        self.row = row

    def fetchone(self):
        return self.row


class ScopeDatabase:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple]] = []

    def execute(self, sql: str, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))
        return FakeCursor({"accreditation_id": 7, "event_id": 3, "organization_id": 2, "entity_id": 41})


class PostgresLockDatabase:
    engine = "postgres"

    def __init__(self) -> None:
        self.lock_keys: list[int] = []

    def execute(self, sql: str, params=()):
        if "pg_advisory_xact_lock" not in sql:
            raise AssertionError(sql)
        self.lock_keys.append(int(params[0]))
        return FakeCursor()


class AccessLockIdentityTest(unittest.TestCase):
    def test_scope_resolves_entity_in_the_existing_lookup(self) -> None:
        db = ScopeDatabase()

        scope = server.access_event_scope(db, "TOKEN-1")

        self.assertEqual(scope["entity_id"], 41)
        self.assertEqual(len(db.calls), 1)
        self.assertIn("LEFT JOIN enterprise_credentials ec", db.calls[0][0])
        self.assertIn("ec.credential_type = 'QR_TOKEN'", db.calls[0][0])

    def test_same_entity_uses_same_postgres_advisory_lock(self) -> None:
        db = PostgresLockDatabase()
        common = {"organization_id": 2, "event_id": 3, "entity_id": 41}

        first = server.acquire_access_transaction_lock(db, {**common, "accreditation_id": 7})
        second = server.acquire_access_transaction_lock(db, {**common, "accreditation_id": 8})

        self.assertEqual(first, second)
        self.assertEqual(db.lock_keys, [first, second])

    def test_missing_entity_falls_back_to_accreditation(self) -> None:
        db = PostgresLockDatabase()
        common = {"organization_id": 2, "event_id": 3, "entity_id": None}

        first = server.acquire_access_transaction_lock(db, {**common, "accreditation_id": 7})
        second = server.acquire_access_transaction_lock(db, {**common, "accreditation_id": 8})

        self.assertNotEqual(first, second)


if __name__ == "__main__":
    unittest.main()
