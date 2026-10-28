"""Isolated verifier for persistent and in-memory authentication sessions."""

from __future__ import annotations

import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.security.sessions import MemorySessionStore, SessionStore


class MutableClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.value

    def advance(self, seconds: int) -> None:
        self.value += timedelta(seconds=seconds)


def exercise(store, raw_rows=None) -> None:
    token = "bearer-secret-value-not-for-storage"
    csrf = "csrf-secret-value-not-for-storage"
    created = store.create(token, 7, csrf, {"role": "admin"}, ttl_seconds=60)
    assert created.user_id == 7 and created.data == {"role": "admin"}
    assert store.get(token) is not None
    assert store.verify_csrf(token, csrf)
    assert not store.verify_csrf(token, "wrong-csrf")
    if raw_rows is not None:
        stored = repr(raw_rows())
        assert token not in stored and csrf not in stored
    updated = store.update(token, data={"role": "operator"}, csrf_token="rotated")
    assert updated and updated.data["role"] == "operator"
    assert not store.verify_csrf(token, csrf) and store.verify_csrf(token, "rotated")
    active = store.active_payloads()
    assert len(active) == 1 and active[0]["id"] == 7 and token not in repr(active)
    assert store.revoke(token) and not store.revoke(token)
    assert store.get(token) is None
    assert store.cleanup() == 1


def main() -> None:
    migration = Path("backend/migrations/049_persistent_auth_sessions.sql").read_text(encoding="utf-8")
    clock = MutableClock()
    with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
        path = Path(directory) / "sessions.sqlite3"
        connection = sqlite3.connect(path)
        connection.row_factory = sqlite3.Row
        connection.executescript(migration)
        store = SessionStore(connection, clock=clock)
        exercise(store, lambda: [tuple(row) for row in connection.execute("SELECT * FROM auth_sessions")])

        store.create("expiring", 8, "csrf-2", ttl_seconds=5)
        store.create("user-revoke", 9, "csrf-4", ttl_seconds=30)
        assert store.revoke_user(9) == 1 and store.get("user-revoke") is None
        clock.advance(6)
        assert store.get("expiring") is None
        connection.close()

        reopened = sqlite3.connect(path)
        reopened.row_factory = sqlite3.Row
        restarted = SessionStore(reopened, clock=clock)
        assert restarted.cleanup() == 2
        reopened.close()

    memory_clock = MutableClock()
    memory = MemorySessionStore(clock=memory_clock)
    exercise(memory, lambda: list(memory._rows.values()))
    memory.create("expiring-memory", 9, "csrf-3", ttl_seconds=1)
    memory_clock.advance(2)
    assert memory.get("expiring-memory") is None and memory.cleanup() == 1
    print("OK: persistent sessions, restart, expiry, revocation, CSRF rotation and secret redaction")


if __name__ == "__main__":
    main()
