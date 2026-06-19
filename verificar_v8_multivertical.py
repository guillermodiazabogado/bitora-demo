from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import server
from backend.verticals import normalize_project_type, registered_verticals, vertical_config


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="bitora-v8-multivertical-"))
    old_db = server.DB_PATH
    try:
        server.DB_PATH = tmp / "multivertical.sqlite3"
        server.init_db()
        server.seed_if_empty()
        with server.connect() as db:
            legacy_id = db.execute(
                "INSERT INTO events (name, status, project_type, created_at) VALUES ('Legacy', 'draft', '', ?)",
                (server.now_iso(),),
            ).lastrowid
        server.init_db()
        with server.connect() as db:
            legacy = db.execute("SELECT project_type FROM events WHERE id = ?", (legacy_id,)).fetchone()
            assert legacy["project_type"] == "conference"

            conference_id = server.insert_event_from_config(
                db,
                {"name": "Conference QA", "project_type": "conference"},
                "Admin",
                status="published",
            )
            ticketing_id = server.insert_event_from_config(
                db,
                {"name": "Ticketing QA", "project_type": "ticketing"},
                "Admin",
                status="published",
            )
            conference = db.execute("SELECT * FROM events WHERE id = ?", (conference_id,)).fetchone()
            ticketing = db.execute("SELECT * FROM events WHERE id = ?", (ticketing_id,)).fetchone()
            assert conference["project_type"] == "conference"
            assert ticketing["project_type"] == "ticketing"

            conference_config = vertical_config(conference["project_type"])
            ticketing_config = vertical_config(ticketing["project_type"])
            assert conference_config["modules"]["agenda"] is True
            assert conference_config["modules"]["attendance"] is True
            assert conference_config["modules"]["certificates"] is True
            assert ticketing_config["modules"]["ticketing"] is True
            assert ticketing_config["modules"]["seats"] is False
            assert ticketing_config["modules"]["functions"] is False
            assert ticketing_config["status"] == "building"
            assert normalize_project_type("desconocido") == "conference"
            assert {item["key"] for item in registered_verticals()} == {"conference", "ticketing"}

            visual = server.DATA_VISUALIZATION.collect(db, ticketing_id, force=True)
            assert visual["project_type"] == "ticketing"
            assert visual["vertical"]["modules"]["ticketing"] is True
            assert "ticketing_placeholder" in visual["widgets"]

        html = Path("frontend/index.html").read_text(encoding="utf-8")
        app = Path("frontend/app.js").read_text(encoding="utf-8")
        noc = Path("frontend/noc.js").read_text(encoding="utf-8")
        migration = Path("backend/migrations/008_multivertical.sql").read_text(encoding="utf-8")
        assert 'name="project_type"' in html
        assert "Ticketing Mode" in html and "Funcionalidades en construccion" in html
        assert "currentProjectModules" in app
        assert "engine.vertical" in noc
        assert "ADD COLUMN IF NOT EXISTS project_type" in migration
        assert "QRService" in Path("backend/services/qr.py").read_text(encoding="utf-8")
        assert "JobQueueService" in Path("backend/services/jobs.py").read_text(encoding="utf-8")
        print("OK: V8.0 multi vertical mantiene Conference y prepara Ticketing sin funciones")
    finally:
        server.DB_PATH = old_db
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
