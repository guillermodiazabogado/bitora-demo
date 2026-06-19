from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import server
from qa2_utils import Harness, request


class FakeMetaHandler(BaseHTTPRequestHandler):
    sent: list[dict] = []

    def log_message(self, format, *args):
        return

    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))).decode("utf-8"))
        self.__class__.sent.append(payload)
        body = json.dumps({"messages": [{"id": f"wamid-live-{len(self.__class__.sent)}"}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def wait_until_processed(event_id: int, expected: int, timeout: float = 15) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with server.connect() as db:
            processed = int(
                db.execute(
                    """
                    SELECT COUNT(*) AS c
                    FROM communication_queue
                    WHERE event_id = ? AND channel = 'whatsapp' AND status = 'enviado'
                    """,
                    (event_id,),
                ).fetchone()["c"]
                or 0
            )
        if processed >= expected:
            return
        time.sleep(0.1)
    raise AssertionError(f"WhatsApp procesados: {processed}/{expected}")


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="bitora-live10-"))
    meta = ThreadingHTTPServer(("127.0.0.1", 0), FakeMetaHandler)
    threading.Thread(target=meta.serve_forever, daemon=True).start()
    old_db = server.DB_PATH
    old_env = {key: os.environ.get(key) for key in (
        "WHATSAPP_PROVIDER",
        "WHATSAPP_ENABLED",
        "WHATSAPP_ACCESS_TOKEN",
        "WHATSAPP_PHONE_NUMBER_ID",
        "WHATSAPP_META_API_URL",
        "WHATSAPP_REGISTRATION_TEMPLATE",
    )}
    harness = Harness("bitora-demo-live10-")
    worker = None
    try:
        os.environ.update({
            "WHATSAPP_PROVIDER": "meta",
            "WHATSAPP_ENABLED": "true",
            "WHATSAPP_ACCESS_TOKEN": "test-token",
            "WHATSAPP_PHONE_NUMBER_ID": "123456",
            "WHATSAPP_META_API_URL": f"http://127.0.0.1:{meta.server_address[1]}",
            "WHATSAPP_REGISTRATION_TEMPLATE": "",
        })
        server.DB_PATH = tmp / "live10.sqlite3"
        harness.start()
        worker = server.start_job_worker()

        status, demo = request(
            harness.base,
            "POST",
            "/api/demo-live-10",
            {"actor": "Admin", "confirm": "LIVE10", "name": "Demo 10 QA"},
        )
        assert status == 201 and demo["capacity"] == 10
        event_id = int(demo["event_id"])

        tokens = []
        for index in range(10):
            status, registration = request(
                harness.base,
                "POST",
                "/api/register",
                {
                    "event_id": event_id,
                    "actor": "public",
                    "first_name": f"Persona{index + 1}",
                    "last_name": "Demo",
                    "email": f"persona{index + 1}@demo.test",
                    "phone": f"+549299555{index + 1:04d}",
                    "type": "General",
                    "acepta_whatsapp": True,
                    "canal_preferido": "whatsapp",
                    "source": "landing",
                    "device_type": "mobile",
                },
            )
            assert status == 201
            assert registration["communications"]["whatsapp"]["status"] == "pending"
            tokens.append(registration["token"])

        wait_until_processed(event_id, 10)
        assert len(FakeMetaHandler.sent) == 10
        assert all("portal" in item["text"]["body"].lower() for item in FakeMetaHandler.sent)

        status, overflow = request(
            harness.base,
            "POST",
            "/api/register",
            {
                "event_id": event_id,
                "actor": "public",
                "first_name": "Persona11",
                "last_name": "Demo",
                "email": "persona11@demo.test",
                "phone": "+5492995550011",
                "type": "General",
                "acepta_whatsapp": True,
            },
        )
        assert status == 409 and "Cupo completo" in overflow["error"]

        status, portal = request(harness.base, "GET", f"/api/portal?token={tokens[0]}")
        assert status == 200 and portal["event_name"] == "Demo 10 QA"

        status, no_consent_demo = request(
            harness.base,
            "POST",
            "/api/demo-live-10",
            {"actor": "Admin", "confirm": "LIVE10", "name": "Demo sin consentimiento"},
        )
        assert status == 201
        status, no_consent = request(
            harness.base,
            "POST",
            "/api/register",
            {
                "event_id": no_consent_demo["event_id"],
                "actor": "public",
                "first_name": "Sin",
                "last_name": "Consentimiento",
                "email": "sin-consentimiento@demo.test",
                "phone": "+5492995559999",
                "type": "General",
                "acepta_whatsapp": False,
            },
        )
        assert status == 201
        assert no_consent["communications"]["whatsapp"]["status"] == "skipped"
        assert len(FakeMetaHandler.sent) == 10

        with server.connect() as db:
            counts = dict(
                db.execute(
                    """
                    SELECT
                      (SELECT COUNT(*) FROM accreditations WHERE event_id = ?) AS participants,
                      (SELECT COUNT(*) FROM communication_queue WHERE event_id = ? AND status = 'enviado') AS whatsapp_sent,
                      (SELECT COUNT(*) FROM audit_logs WHERE action = 'demo.live10_created' AND entity_id = ?) AS demo_audit
                    """,
                    (event_id, event_id, event_id),
                ).fetchone()
            )
        assert counts == {"participants": 10, "whatsapp_sent": 10, "demo_audit": 1}
        print("OK: demo en vivo 10, cupo, inscripcion, portal, QR y WhatsApp automatico")
    finally:
        if worker:
            worker.stop()
        harness.cleanup()
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
