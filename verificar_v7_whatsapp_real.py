from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import server
from backend.services.whatsapp import create_whatsapp_provider


class FakeMetaHandler(BaseHTTPRequestHandler):
    sent: list[dict] = []

    def log_message(self, format, *args):
        return

    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))).decode("utf-8"))
        self.__class__.sent.append(payload)
        body = json.dumps({"messages": [{"id": f"wamid-{len(self.__class__.sent)}"}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        body = json.dumps({"display_phone_number": "+54 9 299 0000000", "verified_name": "BITORA"}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    keys = ("WHATSAPP_PROVIDER", "WHATSAPP_ENABLED", "WHATSAPP_ACCESS_TOKEN", "WHATSAPP_PHONE_NUMBER_ID", "WHATSAPP_BUSINESS_ACCOUNT_ID", "WHATSAPP_META_API_URL")
    old_env = {key: os.environ.get(key) for key in keys}
    tmp = Path(tempfile.mkdtemp(prefix="bitora-v7-whatsapp-"))
    meta = ThreadingHTTPServer(("127.0.0.1", 0), FakeMetaHandler)
    threading.Thread(target=meta.serve_forever, daemon=True).start()
    old_db = server.DB_PATH
    try:
        os.environ.update({
            "WHATSAPP_PROVIDER": "meta",
            "WHATSAPP_ENABLED": "true",
            "WHATSAPP_ACCESS_TOKEN": "test-token",
            "WHATSAPP_PHONE_NUMBER_ID": "123456",
            "WHATSAPP_BUSINESS_ACCOUNT_ID": "business-1",
            "WHATSAPP_META_API_URL": f"http://127.0.0.1:{meta.server_address[1]}",
        })
        server.DB_PATH = tmp / "whatsapp.sqlite3"
        server.init_db()
        server.seed_if_empty()
        provider = create_whatsapp_provider()
        assert provider.ready and provider.get_status()["status"] == "connected"
        sent = provider.send_message(to="+54 9 299 1234567", message="Hola BITORA")
        assert sent.ok and sent.message_id == "wamid-1"
        template = provider.send_template(to="5492991234567", template="confirmacion_inscripcion", variables=["Ana", "Evento"])
        assert template.ok and FakeMetaHandler.sent[-1]["type"] == "template"
        media = provider.send_media(to="5492991234567", media_url="https://example.test/qr.png", caption="Tu QR")
        assert media.ok and FakeMetaHandler.sent[-1]["type"] == "image"
        with server.connect() as db:
            event_id = db.execute("INSERT INTO events (name, status, created_at) VALUES ('Demo WhatsApp', 'published', ?)", (server.now_iso(),)).lastrowid
            person_id = db.execute("INSERT INTO people (first_name, last_name, email, phone, created_at) VALUES ('Ana', 'Meta', 'ana@meta.test', '+5492991234567', ?)", (server.now_iso(),)).lastrowid
            accreditation_id = db.execute("INSERT INTO accreditations (event_id, person_id, token, type, status, created_at) VALUES (?, ?, 'WA-TEST', 'General', 'active', ?)", (event_id, person_id, server.now_iso())).lastrowid
            db.execute("INSERT INTO participant_communication_preferences (person_id, phone, acepta_whatsapp, canal_preferido, updated_at) VALUES (?, '+5492991234567', 1, 'whatsapp', ?)", (person_id, server.now_iso()))
            queue_id = db.execute(
                """
                INSERT INTO communication_queue (event_id, person_id, accreditation_id, channel, audience, template_code, subject, content, recipient, status, attempts, max_attempts, provider, created_by, created_at)
                VALUES (?, ?, ?, 'whatsapp', 'all', 'manual', 'Aviso', 'Mensaje real', '+5492991234567', 'pendiente', 0, 3, 'meta', 'Admin', ?)
                """,
                (event_id, person_id, accreditation_id, server.now_iso()),
            ).lastrowid
        result = server.process_whatsapp_queue_item(queue_id)
        assert result["ok"] and result["status"] == "enviado"
        with server.connect() as db:
            webhook = server.apply_whatsapp_webhook(db, {"entry": [{"changes": [{"value": {"statuses": [{"id": result["message_id"], "status": "delivered"}, {"id": result["message_id"], "status": "read"}]}}]}]})
            row = db.execute("SELECT status FROM communication_queue WHERE id = ?", (queue_id,)).fetchone()
            audit = db.execute("SELECT COUNT(*) AS c FROM audit_logs WHERE action LIKE 'communications.whatsapp%'").fetchone()["c"]
        assert webhook["ok"] and row["status"] == "leido" and audit >= 2
        print("OK: V7 Meta Cloud API, texto, plantilla, QR/media, webhook, estados, historial y auditoria")
    finally:
        server.DB_PATH = old_db
        meta.shutdown()
        meta.server_close()
        for key, value in old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
