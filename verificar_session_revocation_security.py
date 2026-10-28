from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from backend.security.sessions import SessionStore


ROOT = Path(__file__).resolve().parent
SERVER = ROOT / "server.py"


def verify_store_revocation() -> None:
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute(
        """CREATE TABLE auth_sessions (
            token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL,
            csrf_hash TEXT NOT NULL, data_json TEXT NOT NULL,
            created_at TEXT NOT NULL, expires_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL, revoked_at TEXT
        )"""
    )
    store = SessionStore(db, clock=lambda: datetime(2026, 10, 27, tzinfo=timezone.utc))
    store.create("token-a", 7, "csrf-a", {"name": "Operator", "role": "Operador"})
    store.create("token-b", 7, "csrf-b", {"name": "Operator", "role": "Operador"})
    store.create("token-other", 8, "csrf-other", {"name": "Other", "role": "Viewer"})
    assert store.revoke_user(7) == 2
    assert store.get("token-a") is None and store.get("token-b") is None
    assert store.get("token-other") is not None


def verify_server_contract() -> None:
    source = SERVER.read_text(encoding="utf-8")
    required = (
        'SELECT * FROM users WHERE id = ? AND active = 1',
        "if stored_role != current_role:",
        '"reauthentication_required": True',
        "SessionStore(db).revoke_user(int(user[\"id\"]))",
        "SessionStore(db).revoke_user(user_id)",
        "if not active:\n                        SessionStore(db).revoke_user(user_id)",
    )
    missing = [item for item in required if item not in source]
    assert not missing, f"faltan controles de revocacion: {missing}"

    reset_start = source.index('if path == "/api/users/password-reset":')
    status_start = source.index('if path == "/api/users/status":')
    delete_start = source.index('if path == "/api/users/delete":')
    bootstrap_start = source.index('if path == "/api/admin/bootstrap-reset":')
    demo_start = source.index('if path == "/api/admin/demo-full/prepare":')
    assert 'SessionStore(db).revoke_user(int(user["id"]))' in source[bootstrap_start:demo_start]
    assert "revoke_user(user_id)" in source[reset_start:status_start]
    assert "revoke_user(user_id)" in source[status_start:delete_start]


if __name__ == "__main__":
    verify_store_revocation()
    verify_server_contract()
    print("OK - sesiones revocadas ante password, estado y rol; identidad revalidada")
