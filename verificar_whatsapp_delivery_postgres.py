from __future__ import annotations

import json
import multiprocessing
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

os.environ.setdefault("QR_REQUIRE_LOGIN", "0")
os.environ["QR_DB_ENGINE"] = "postgres"
os.environ["DATABASE_ENGINE"] = "postgres"
os.environ["WHATSAPP_ENABLED"] = "true"
os.environ["WHATSAPP_PROVIDER"] = "meta"
os.environ["WHATSAPP_ACCESS_TOKEN"] = "synthetic-token"
os.environ["WHATSAPP_PHONE_NUMBER_ID"] = "synthetic-phone-id"
os.environ["WHATSAPP_BUSINESS_ACCOUNT_ID"] = "synthetic-waba"
os.environ["WHATSAPP_VERIFY_TOKEN"] = "synthetic-verify"
os.environ["WHATSAPP_APP_SECRET"] = "synthetic-secret"
os.environ["WHATSAPP_SAFE_MODE"] = "false"

import server


class MetaStubHandler(BaseHTTPRequestHandler):
    calls = 0
    lock = threading.Lock()

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        assert payload.get("biz_opaque_callback_data", "").startswith("bitora-wa:")
        with self.lock:
            type(self).calls += 1
        time.sleep(0.25)
        body = json.dumps({"messages": [{"id": "wamid.postgres.synthetic"}]}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:
        del format, args


def process_queue(queue_id: int, start, results) -> None:
    # A real replica owns its own pool.  Forked QA workers must discard the
    # parent's pool handle before opening independent PostgreSQL connections.
    import backend.database as database

    database._POSTGRES_POOL = None
    start.wait(timeout=5)
    results.put(server.process_whatsapp_queue_item(queue_id))


def main() -> None:
    if not os.environ.get("QR_POSTGRES_DSN"):
        raise SystemExit("QR_POSTGRES_DSN is required")
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), MetaStubHandler)
    os.environ["WHATSAPP_META_API_URL"] = f"http://127.0.0.1:{httpd.server_port}"
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        server.init_db()
        with server.connect() as db:
            organization_id = server.bootstrap_default_organization(db)
            db.execute(
                "UPDATE organizations SET safe_mode_whatsapp = 0, force_whatsapp_recipient = '' WHERE id = ?",
                (organization_id,),
            )
            event_id = server.insert_event_from_config(
                db,
                {"name": "WhatsApp PostgreSQL Safety", "organization_id": organization_id},
                "QA",
            )
            person_id = int(
                db.execute(
                    "INSERT INTO people (first_name,last_name,email,phone,created_at) VALUES ('QA','Postgres','qa-postgres@example.test','5491100000000',?) RETURNING id",
                    (server.now_iso(),),
                ).fetchone()["id"]
            )
            accreditation_id = int(
                db.execute(
                    "INSERT INTO accreditations (event_id,person_id,type,token,status,created_at) VALUES (?,?, 'General','EVT-WA-PG','confirmed',?) RETURNING id",
                    (event_id, person_id, server.now_iso()),
                ).fetchone()["id"]
            )
            queue_id = int(
                db.execute(
                    """
                    INSERT INTO communication_queue (
                        event_id,person_id,accreditation_id,channel,audience,template_code,
                        subject,content,recipient,status,attempts,max_attempts,provider,
                        provider_message_id,last_error,idempotency_key,created_by,created_at
                    ) VALUES (?,?,?,'whatsapp','registration','manual','Safety','Synthetic',?,'pendiente',0,3,'meta','','',?,'QA',?)
                    RETURNING id
                    """,
                    (event_id, person_id, accreditation_id, "5491100000000", f"wa-pg-{server.secrets.token_hex(8)}", server.now_iso()),
                ).fetchone()["id"]
            )

        context = multiprocessing.get_context("fork")
        start = context.Event()
        results = context.Queue()
        workers = [context.Process(target=process_queue, args=(queue_id, start, results)) for _ in range(2)]
        for worker in workers:
            worker.start()
        start.set()
        for worker in workers:
            worker.join(timeout=10)
            assert worker.exitcode == 0, f"worker exit={worker.exitcode}"
        outcomes = [results.get(timeout=2) for _ in workers]

        with server.connect() as db:
            row = db.execute(
                "SELECT status,attempts,provider_message_id FROM communication_queue WHERE id = ?",
                (queue_id,),
            ).fetchone()
        assert MetaStubHandler.calls == 1, f"Meta calls={MetaStubHandler.calls}"
        assert row["status"] == "enviado", dict(row)
        assert int(row["attempts"]) == 1, dict(row)
        assert row["provider_message_id"] == "wamid.postgres.synthetic", dict(row)
        assert any(outcome.get("duplicate_prevented") for outcome in outcomes), outcomes
        print("PASS: PostgreSQL multiinstancia reclamo atomico y una sola llamada Meta")
    finally:
        httpd.shutdown()
        httpd.server_close()


if __name__ == "__main__":
    main()
