import base64
import io
import json
import unittest
import urllib.error
from email import policy
from email.parser import BytesParser
from unittest.mock import patch

from backend.services.email import GmailEmailProvider


class GmailTests(unittest.TestCase):
    def provider(self):
        return GmailEmailProvider(client_id="client", client_secret="secret", refresh_token="refresh",
                                  from_email="BITORA <agenciabarda@gmail.com>")

    @patch("backend.services.email.GoogleOAuthClient.refresh_access_token", return_value={"access_token": "access"})
    @patch("backend.services.email.urllib.request.urlopen")
    def test_send_mime_and_send_only_delivery(self, opener, refresh):
        opener.return_value.__enter__.return_value.read.return_value = b'{"id":"gmail-id"}'
        provider = self.provider()
        result = provider.send_email(to="test@example.com", subject="Inscripcion", html="<b>Tu QR</b>",
                                     text="Tu QR", reply_to="agenciabarda@gmail.com")
        self.assertTrue(result.ok)
        self.assertEqual(result.message_id, "gmail-id")
        request = opener.call_args.args[0]
        self.assertEqual(request.full_url, "https://gmail.googleapis.com/gmail/v1/users/me/messages/send")
        raw = base64.urlsafe_b64decode(json.loads(request.data)["raw"])
        message = BytesParser(policy=policy.default).parsebytes(raw)
        self.assertEqual(message["To"], "test@example.com")
        self.assertEqual(message["Reply-To"], "agenciabarda@gmail.com")
        self.assertTrue(message.is_multipart())
        self.assertEqual(provider.get_delivery_status("gmail-id")["status"], "unknown")

    @patch("backend.services.email.GoogleOAuthClient.refresh_access_token", return_value={"access_token": "secret-access"})
    @patch("backend.services.email.urllib.request.urlopen")
    def test_api_error_does_not_expose_credentials(self, opener, refresh):
        opener.side_effect = urllib.error.HTTPError("https://gmail.googleapis.com", 403, "Forbidden", {}, io.BytesIO(b"secret-access"))
        result = self.provider().send_email(to="test@example.com", subject="Test", html="Test")
        self.assertFalse(result.ok)
        self.assertNotIn("secret-access", result.error)
        self.assertIn("403", result.error)

    def test_missing_authorization(self):
        provider = GmailEmailProvider(client_id="", client_secret="", refresh_token="", from_email="")
        self.assertFalse(provider.ready)
        self.assertFalse(provider.send_email(to="test@example.com", subject="Test", html="Test").ok)


if __name__ == "__main__":
    unittest.main()
