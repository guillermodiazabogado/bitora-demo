from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from backend.services.whatsapp import normalize_phone


class WhatsAppPhoneNormalizationTest(unittest.TestCase):
    def test_argentine_local_ten_digits_is_e164(self) -> None:
        with patch.dict(os.environ, {"WHATSAPP_DEFAULT_REGION": "AR"}, clear=False):
            self.assertEqual(normalize_phone("299 548-3030"), "5492995483030")

    def test_argentine_local_mobile_is_e164(self) -> None:
        with patch.dict(os.environ, {"WHATSAPP_DEFAULT_REGION": "AR"}, clear=False):
            self.assertEqual(normalize_phone("011 5605-7770"), "5491156057770")

    def test_argentine_country_code_adds_mobile_nine(self) -> None:
        with patch.dict(os.environ, {"WHATSAPP_DEFAULT_REGION": "AR"}, clear=False):
            self.assertEqual(normalize_phone("+54 11 5605-7770"), "5491156057770")

    def test_argentine_e164_is_unchanged(self) -> None:
        with patch.dict(os.environ, {"WHATSAPP_DEFAULT_REGION": "AR"}, clear=False):
            self.assertEqual(normalize_phone("+54 9 11 5605-7770"), "5491156057770")

    def test_other_regions_are_not_rewritten(self) -> None:
        with patch.dict(os.environ, {"WHATSAPP_DEFAULT_REGION": ""}, clear=False):
            self.assertEqual(normalize_phone("011 5605-7770"), "01156057770")


if __name__ == "__main__":
    unittest.main()
