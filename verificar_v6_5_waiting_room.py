from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import server


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="bitora-v65-waiting-"))
    old_db = server.DB_PATH
    try:
        server.DB_PATH = tmp / "waiting.sqlite3"
        server.init_db()
        server.seed_if_empty()
        with server.connect() as db:
            event_id = db.execute(
                "INSERT INTO events (name, description, status, created_at) VALUES ('Demo Espera', 'demo', 'published', ?)",
                (server.now_iso(),),
            ).lastrowid
            open_status = server.waiting_room_payload(db, event_id, "visitor-open")
            assert open_status["enabled"] is False
            db.execute(
                "UPDATE events SET waiting_room_enabled = 1, users_allowed_per_minute = 1, turn_duration_minutes = 10 WHERE id = ?",
                (event_id,),
            )
            first = server.waiting_room_payload(db, event_id, "visitor-1")
            second = server.waiting_room_payload(db, event_id, "visitor-2")
            assert first["status"] == "admitted" and first["access_token"]
            assert second["status"] == "waiting" and second["position"] >= 1
            counts = server.diagnostics_service()._waiting_room_status(db)
            assert counts["admitted"] == 1 and counts["waiting"] == 1
        public_js = (Path("frontend") / "public.js").read_text(encoding="utf-8")
        assert "waiting_room_token" in public_js and "checkWaitingRoom" in public_js
        print("OK: V6.5 sala desactivada, espera, admision, token y diagnostico")
    finally:
        server.DB_PATH = old_db
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
