from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import server


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="bitora-v67-simulator-"))
    old_db = server.DB_PATH
    try:
        server.DB_PATH = tmp / "simulator.sqlite3"
        server.init_db()
        server.seed_if_empty()
        with server.connect() as db:
            event_id = db.execute(
                "INSERT INTO events (name, description, status, created_at) VALUES ('Demo Simulador', 'evento demo', 'published', ?)",
                (server.now_iso(),),
            ).lastrowid
            for index in range(10):
                person_id = db.execute(
                    "INSERT INTO people (first_name, last_name, email, created_at) VALUES (?, 'Demo', ?, ?)",
                    (f"P{index}", f"p{index}@demo.test", server.now_iso()),
                ).lastrowid
                db.execute(
                    "INSERT INTO accreditations (event_id, person_id, token, type, status, created_at) VALUES (?, ?, ?, 'General', 'confirmed', ?)",
                    (event_id, person_id, f"SIM-{index}", server.now_iso()),
                )
            db.execute(
                """
                INSERT INTO simulator_state (
                    event_id, status, mode, scenario, participants_active, accesses_per_minute,
                    rejections_per_minute, active_terminals, updated_at
                ) VALUES (?, 'running', 'high', 'congress', 10, 120, 24, 5, ?)
                """,
                (event_id, server.now_iso()),
            )
        server.simulator_step()
        with server.connect() as db:
            granted = db.execute("SELECT COUNT(*) AS c FROM access_logs WHERE event_id = ? AND result = 'granted'", (event_id,)).fetchone()["c"]
            rejected = db.execute("SELECT COUNT(*) AS c FROM access_logs WHERE event_id = ? AND result = 'rejected'", (event_id,)).fetchone()["c"]
            communications = db.execute("SELECT COUNT(*) AS c FROM communication_logs WHERE event_id = ?", (event_id,)).fetchone()["c"]
        assert granted > 0 and rejected > 0 and communications == 0
        print("OK: V6.7 simulador genera actividad aislada sin comunicaciones reales")
    finally:
        server.DB_PATH = old_db
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
