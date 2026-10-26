"""Registration confirmations must not depend on the operator's origin."""
import os
import gc
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch

import server
from verificar_v6_1_email_real import req


def main():
    with tempfile.TemporaryDirectory(prefix="bitora-registration-") as directory:
        with patch.dict(os.environ, {"EMAIL_PROVIDER": "demo", "WHATSAPP_PROVIDER": "demo"}):
            server.DB_PATH = Path(directory) / "test.sqlite3"
            server.BACKUP_DIR = Path(directory) / "backups"
            server.AppHandler.log_message = lambda *args: None
            server.init_db()
            server.seed_if_empty()
            app = server.OperationalHTTPServer(("127.0.0.1", 0), server.AppHandler)
            threading.Thread(target=app.serve_forever, daemon=True).start()
            try:
                base = f"http://127.0.0.1:{app.server_address[1]}"
                event = req(base, "POST", "/api/events", {
                    "actor": "Admin", "name": "Confirmations", "status": "published",
                    "starts_at": "2026-11-01T09:00",
                }, 201)["id"]
                payload = {"event_id": event, "first_name": "First", "last_name": "Person",
                           "email": "first@example.test", "type": "General", "acepta_email": True}
                req(base, "POST", "/api/register", dict(payload, actor="Admin"), 201)
                req(base, "POST", "/api/register", dict(payload, actor="public"), 200)
                req(base, "POST", "/api/register", dict(payload, actor="public",
                    first_name="Second", email="second@example.test"), 201)
                req(base, "POST", "/api/register", dict(payload, actor="Admin",
                    email="no-consent@example.test", acepta_email=False), 201)
                with server.connect() as db:
                    rows = db.execute("SELECT recipient,content,accreditation_id FROM communication_queue WHERE event_id=? AND channel='email'", (event,)).fetchall()
                    assert len(rows) == 2, [dict(r) for r in rows]
                    assert {r["recipient"] for r in rows} == {"first@example.test", "second@example.test"}
                    for row in rows:
                        accreditation = db.execute("SELECT token FROM accreditations WHERE id=?", (row["accreditation_id"],)).fetchone()
                        assert accreditation["token"] in row["content"]
                    # A legacy registration without a confirmation is repaired once on repeat.
                    db.execute("DELETE FROM communication_queue WHERE event_id=? AND recipient=?", (event, "first@example.test"))
                db.close()
                req(base, "POST", "/api/register", dict(payload, actor="Admin"), 200)
                req(base, "POST", "/api/register", dict(payload, actor="Admin"), 200)
                with server.connect() as db:
                    assert db.execute("SELECT COUNT(*) AS n FROM communication_queue WHERE event_id=? AND recipient=?", (event, "first@example.test")).fetchone()["n"] == 1
                db.close()
                print("PASS: admin/public confirmation, consent, recipient-specific portal, duplicate prevention and legacy repair")
            finally:
                app.shutdown()
                app.server_close()
                gc.collect()


if __name__ == "__main__":
    main()
