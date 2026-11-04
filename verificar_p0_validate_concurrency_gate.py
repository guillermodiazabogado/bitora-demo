from __future__ import annotations

import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import server


class ValidateConcurrencyGateTest(unittest.TestCase):
    def test_configuration_defaults_and_stays_bounded(self) -> None:
        with patch.dict(server.os.environ, {}, clear=False):
            server.os.environ.pop("QR_POSTGRES_ACCESS_CONCURRENCY", None)
            self.assertEqual(server.postgres_access_concurrency_limit(None), 1)
        self.assertEqual(server.postgres_access_concurrency_limit("invalid"), 1)
        self.assertEqual(server.postgres_access_concurrency_limit("0"), 1)
        self.assertEqual(server.postgres_access_concurrency_limit("8"), 8)
        self.assertEqual(server.postgres_access_concurrency_limit("999"), 32)

    def test_sqlite_keeps_process_database_lock(self) -> None:
        with patch.object(server, "DB_CONFIG", SimpleNamespace(engine="sqlite")):
            self.assertIs(server.access_validation_concurrency_gate(), server.DB_LOCK)

    def test_postgres_uses_configured_bounded_gate(self) -> None:
        gate = threading.BoundedSemaphore(2)
        with (
            patch.object(server, "DB_CONFIG", SimpleNamespace(engine="postgres")),
            patch.object(server, "QR_POSTGRES_ACCESS_GATE", gate),
        ):
            selected = server.access_validation_concurrency_gate()
            self.assertIs(selected, gate)
            self.assertTrue(selected.acquire(blocking=False))
            self.assertTrue(selected.acquire(blocking=False))
            self.assertFalse(selected.acquire(blocking=False))
            selected.release()
            self.assertTrue(selected.acquire(blocking=False))
            selected.release()
            selected.release()


if __name__ == "__main__":
    unittest.main()
