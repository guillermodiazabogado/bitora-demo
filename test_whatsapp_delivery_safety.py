from __future__ import annotations

import os
import tempfile
import threading
import unittest
import urllib.error
from io import BytesIO
from unittest.mock import patch

os.environ.setdefault("QR_REQUIRE_LOGIN", "0")
os.environ["QR_DB_ENGINE"] = "sqlite"
os.environ["DATABASE_ENGINE"] = "sqlite"
os.environ["WHATSAPP_SAFE_MODE"] = "false"

import server
from backend.services.whatsapp import (
    MetaCloudWhatsAppProvider,
    MetaRequestError,
    WhatsAppSendResult,
    verify_meta_signature,
)


class FakeWhatsAppProvider:
    name = "meta"

    def __init__(self, results: list[WhatsAppSendResult] | None = None, *, block: bool = False) -> None:
        self.results = list(results or [WhatsAppSendResult(ok=True, message_id="wamid.synthetic", status="enviado")])
        self.block = block
        self.calls = 0
        self.entered = threading.Event()
        self.release = threading.Event()

    @property
    def ready(self) -> bool:
        return True

    def validate_configuration(self) -> dict:
        return {"ok": True, "errors": []}

    def send_message(self, *, to: str, message: str, correlation_id: str = "") -> WhatsAppSendResult:
        del to, message
        self.calls += 1
        self.last_correlation_id = correlation_id
        self.entered.set()
        if self.block:
            self.release.wait(timeout=5)
        return self.results.pop(0) if self.results else WhatsAppSendResult(ok=True, message_id="wamid.synthetic", status="enviado")

    def send_template(self, **kwargs) -> WhatsAppSendResult:
        return self.send_message(to=kwargs["to"], message=kwargs["template"], correlation_id=kwargs.get("correlation_id", ""))

    def normalize_webhook(self, payload: dict) -> list[dict]:
        from backend.services.whatsapp import normalize_meta_webhook

        return normalize_meta_webhook(payload)


class WhatsAppDeliverySafetyTest(unittest.TestCase):
    def setUp(self) -> None:
        descriptor, path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(descriptor)
        self.path = path
        self.original_path = server.DB_PATH
        server.DB_PATH = server.Path(path)
        server.init_db()
        with server.connect() as db:
            organization_id = server.bootstrap_default_organization(db)
            db.execute(
                "UPDATE organizations SET safe_mode_whatsapp = 0, force_whatsapp_recipient = '' WHERE id = ?",
                (organization_id,),
            )
            self.event_id = server.insert_event_from_config(
                db,
                {"name": "WhatsApp Safety", "organization_id": organization_id},
                "QA",
            )
            self.person_id = int(
                db.execute(
                    "INSERT INTO people (first_name,last_name,email,phone,created_at) VALUES ('QA','WhatsApp','qa@example.test','5491100000000',?)",
                    (server.now_iso(),),
                ).lastrowid
            )
            self.accreditation_id = int(
                db.execute(
                    "INSERT INTO accreditations (event_id,person_id,type,token,status,created_at) VALUES (?,?, 'General','EVT-WA-SAFETY','confirmed',?)",
                    (self.event_id, self.person_id, server.now_iso()),
                ).lastrowid
            )

    def tearDown(self) -> None:
        server.DB_PATH = self.original_path
        try:
            os.remove(self.path)
        except OSError:
            pass

    def queue(self, *, status: str = "pendiente", processed_at: str | None = None) -> int:
        with server.connect() as db:
            return int(
                db.execute(
                    """
                    INSERT INTO communication_queue (
                        event_id,person_id,accreditation_id,channel,audience,template_code,
                        subject,content,recipient,status,attempts,max_attempts,provider,
                        provider_message_id,last_error,processed_at,idempotency_key,created_by,created_at
                    ) VALUES (?,?,?,'whatsapp','registration','manual','Safety','Synthetic',?, ?,0,3,'meta','','',?,?,'QA',?)
                    """,
                    (
                        self.event_id,
                        self.person_id,
                        self.accreditation_id,
                        "5491100000000",
                        status,
                        processed_at,
                        f"wa-safety-{server.secrets.token_hex(8)}",
                        server.now_iso(),
                    ),
                ).lastrowid
            )

    @staticmethod
    def status_payload(message_id: str, status: str, timestamp: str, correlation_id: str = "") -> dict:
        item = {
            "id": message_id,
            "status": status,
            "timestamp": timestamp,
            "recipient_id": "5491100000000",
        }
        if correlation_id:
            item["biz_opaque_callback_data"] = correlation_id
        if status == "failed":
            item["errors"] = [{"code": 131000, "title": "Synthetic failure"}]
        return {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "metadata": {"phone_number_id": "synthetic-phone-id"},
                                "statuses": [item],
                            }
                        }
                    ]
                }
            ]
        }

    def test_two_workers_send_one_message(self) -> None:
        queue_id = self.queue()
        provider = FakeWhatsAppProvider(block=True)
        results: list[dict] = []
        with patch.object(server, "create_whatsapp_provider", return_value=provider):
            first = threading.Thread(target=lambda: results.append(server.process_whatsapp_queue_item(queue_id)))
            first.start()
            self.assertTrue(provider.entered.wait(timeout=3))
            second = threading.Thread(target=lambda: results.append(server.process_whatsapp_queue_item(queue_id)))
            second.start()
            second.join(timeout=3)
            provider.release.set()
            first.join(timeout=3)
        self.assertEqual(provider.calls, 1)
        self.assertTrue(any(result.get("duplicate_prevented") for result in results))
        with server.connect() as db:
            row = db.execute("SELECT status,attempts,provider_message_id FROM communication_queue WHERE id = ?", (queue_id,)).fetchone()
            self.assertEqual(row["status"], "enviado")
            self.assertEqual(int(row["attempts"]), 1)
            self.assertTrue(row["provider_message_id"])

    def test_ambiguous_result_is_not_retried(self) -> None:
        queue_id = self.queue()
        provider = FakeWhatsAppProvider(
            [WhatsAppSendResult(ok=False, status="desconocido", error="timeout", ambiguous=True, error_code="timeout_unknown")]
        )
        with patch.object(server, "create_whatsapp_provider", return_value=provider):
            first = server.process_whatsapp_queue_item(queue_id)
            second = server.process_whatsapp_queue_item(queue_id)
        self.assertTrue(first["ambiguous"])
        self.assertEqual(first["status"], "desconocido")
        self.assertEqual(second["status"], "desconocido")
        self.assertEqual(provider.calls, 1)

    def test_retryable_rejection_uses_job_retry_path(self) -> None:
        queue_id = self.queue()
        provider = FakeWhatsAppProvider(
            [
                WhatsAppSendResult(ok=False, status="pendiente", error="busy", retryable=True, error_code="http_503"),
                WhatsAppSendResult(ok=True, message_id="wamid.retry.ok", status="enviado"),
            ]
        )
        with patch.object(server, "create_whatsapp_provider", return_value=provider):
            with self.assertRaises(RuntimeError):
                server.handle_whatsapp_job({"queue_id": queue_id})
            result = server.handle_whatsapp_job({"queue_id": queue_id})
        self.assertTrue(result["ok"])
        self.assertEqual(provider.calls, 2)

    def test_late_webhook_reconciles_unknown_and_out_of_order_is_monotonic(self) -> None:
        queue_id = self.queue(status="desconocido")
        with server.connect() as db:
            row = dict(db.execute("SELECT * FROM communication_queue WHERE id = ?", (queue_id,)).fetchone())
            correlation_id = server.whatsapp_correlation_id(row)
        provider = FakeWhatsAppProvider()
        with patch.object(server, "create_whatsapp_provider", return_value=provider):
            with server.connect() as db:
                sent = server.apply_whatsapp_webhook(db, self.status_payload("wamid.late", "sent", "1", correlation_id))
                self.assertEqual(sent["statuses"][0]["stored_status"], "enviado")
                server.apply_whatsapp_webhook(db, self.status_payload("wamid.late", "delivered", "2", correlation_id))
                server.apply_whatsapp_webhook(db, self.status_payload("wamid.late", "read", "3", correlation_id))
                server.apply_whatsapp_webhook(db, self.status_payload("wamid.late", "sent", "4", correlation_id))
                server.apply_whatsapp_webhook(db, self.status_payload("wamid.late", "failed", "5", correlation_id))
                final = db.execute("SELECT status,provider_message_id FROM communication_queue WHERE id = ?", (queue_id,)).fetchone()
                self.assertEqual(final["status"], "leido")
                self.assertEqual(final["provider_message_id"], "wamid.late")

    def test_duplicate_webhook_has_no_second_effect(self) -> None:
        queue_id = self.queue(status="desconocido")
        with server.connect() as db:
            row = dict(db.execute("SELECT * FROM communication_queue WHERE id = ?", (queue_id,)).fetchone())
            correlation_id = server.whatsapp_correlation_id(row)
        payload = self.status_payload("wamid.duplicate", "delivered", "10", correlation_id)
        provider = FakeWhatsAppProvider()
        with patch.object(server, "create_whatsapp_provider", return_value=provider):
            with server.connect() as db:
                server.apply_whatsapp_webhook(db, payload)
                duplicate = server.apply_whatsapp_webhook(db, payload)
                total = int(db.execute("SELECT COUNT(*) AS c FROM whatsapp_delivery_events WHERE queue_id = ?", (queue_id,)).fetchone()["c"])
        self.assertEqual(duplicate["statuses"][0]["status"], "duplicate")
        self.assertEqual(total, 1)

    def test_stale_sending_becomes_unknown_after_restart(self) -> None:
        queue_id = self.queue(status="enviando", processed_at="2000-01-01T00:00:00+00:00")
        with patch.dict(os.environ, {"WHATSAPP_SENDING_STALE_SECONDS": "60"}, clear=False):
            self.assertEqual(server.recover_stale_whatsapp_claims(), 1)
        with server.connect() as db:
            self.assertEqual(db.execute("SELECT status FROM communication_queue WHERE id = ?", (queue_id,)).fetchone()["status"], "desconocido")

    def test_stale_job_is_recovered_without_resending_unknown_queue(self) -> None:
        queue_id = self.queue(status="enviando", processed_at="2000-01-01T00:00:00+00:00")
        service = server.job_queue_service()
        job_id = service.enqueue("whatsapp.send", {"queue_id": queue_id}, event_id=self.event_id)
        with server.connect() as db:
            db.execute(
                "UPDATE jobs SET status = 'processing', started_at = '2000-01-01T00:00:00+00:00', worker_id = 'dead-worker' WHERE id = ?",
                (job_id,),
            )
        self.assertEqual(server.recover_stale_whatsapp_claims(), 1)
        self.assertEqual(service.recover_stale_processing("whatsapp.send", stale_seconds=60), 1)
        with server.connect() as db:
            job = db.execute("SELECT status FROM jobs WHERE id = ?", (job_id,)).fetchone()
            queue = db.execute("SELECT status FROM communication_queue WHERE id = ?", (queue_id,)).fetchone()
        self.assertEqual(job["status"], "retrying")
        self.assertEqual(queue["status"], "desconocido")

    def test_unknown_requires_explicit_audited_resolution(self) -> None:
        associated_id = self.queue(status="desconocido")
        retry_id = self.queue(status="desconocido")
        failed_id = self.queue(status="desconocido")
        with server.connect() as db:
            associated = server.resolve_unknown_whatsapp(
                db,
                associated_id,
                "associate_provider_message",
                provider_message_id="wamid.manually.reconciled",
                actor="QA",
            )
            retry = server.resolve_unknown_whatsapp(db, retry_id, "confirmed_not_sent", actor="QA")
            failed = server.resolve_unknown_whatsapp(db, failed_id, "mark_failed", actor="QA")
            rows = {
                int(row["id"]): dict(row)
                for row in db.execute(
                    "SELECT id,status,provider_message_id FROM communication_queue WHERE id IN (?,?,?)",
                    (associated_id, retry_id, failed_id),
                ).fetchall()
            }
            audits = int(
                db.execute(
                    "SELECT COUNT(*) AS c FROM audit_logs WHERE action = 'communications.whatsapp_unknown_resolved' AND entity_id IN (?,?,?)",
                    (associated_id, retry_id, failed_id),
                ).fetchone()["c"]
            )
        self.assertEqual(associated["status"], "enviado")
        self.assertEqual(rows[associated_id]["provider_message_id"], "wamid.manually.reconciled")
        self.assertTrue(retry["enqueued"])
        self.assertEqual(rows[retry_id]["status"], "pendiente")
        self.assertEqual(failed["status"], "error")
        self.assertEqual(rows[failed_id]["status"], "error")
        self.assertEqual(audits, 3)


class WhatsAppProviderClassificationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.provider = MetaCloudWhatsAppProvider(
            access_token="synthetic",
            phone_number_id="synthetic",
            business_account_id="synthetic",
            verify_token="synthetic",
            app_secret="synthetic",
        )

    def test_network_timeout_is_ambiguous(self) -> None:
        with patch.object(
            self.provider,
            "_request",
            side_effect=MetaRequestError("timeout", ambiguous=True, error_code="timeout_unknown"),
        ):
            result = self.provider.send_message(to="5491100000000", message="Synthetic", correlation_id="bitora-wa:1:synthetic")
        self.assertFalse(result.ok)
        self.assertTrue(result.ambiguous)
        self.assertFalse(result.retryable)

    def test_explicit_provider_rejection_can_be_retryable(self) -> None:
        with patch.object(
            self.provider,
            "_request",
            side_effect=MetaRequestError("busy", retryable=True, error_code="http_503"),
        ):
            result = self.provider.send_message(to="5491100000000", message="Synthetic")
        self.assertTrue(result.retryable)
        self.assertFalse(result.ambiguous)

    def test_signature_fails_closed_without_secret(self) -> None:
        self.assertFalse(verify_meta_signature(b"{}", "sha256=anything", ""))

    def test_http_500_is_ambiguous(self) -> None:
        error = urllib.error.HTTPError(
            "https://graph.facebook.test/messages",
            500,
            "server error",
            {},
            BytesIO(b'{"error":{"message":"synthetic"}}'),
        )
        with patch("urllib.request.urlopen", side_effect=error):
            result = self.provider.send_message(to="5491100000000", message="Synthetic")
        self.assertTrue(result.ambiguous)
        self.assertFalse(result.retryable)

    def test_http_429_is_safe_to_retry(self) -> None:
        error = urllib.error.HTTPError(
            "https://graph.facebook.test/messages",
            429,
            "rate limited",
            {},
            BytesIO(b'{"error":{"message":"synthetic"}}'),
        )
        with patch("urllib.request.urlopen", side_effect=error):
            result = self.provider.send_message(to="5491100000000", message="Synthetic")
        self.assertTrue(result.retryable)
        self.assertFalse(result.ambiguous)

    def test_connection_refused_is_safe_pre_send_failure(self) -> None:
        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError(ConnectionRefusedError("synthetic")),
        ):
            result = self.provider.send_message(to="5491100000000", message="Synthetic")
        self.assertTrue(result.retryable)
        self.assertFalse(result.ambiguous)


if __name__ == "__main__":
    unittest.main()
