from __future__ import annotations

from collections.abc import Callable
import re
from urllib.parse import parse_qs, urlparse


class QRService:
    def payload_for_token(self, token: str) -> str:
        raw = str(token or "").strip()
        match = re.search(r"EVT-[A-Z0-9]+", raw, re.IGNORECASE)
        if match:
            return match.group(0).upper()
        parsed = urlparse(raw)
        if parsed.query:
            candidate = parse_qs(parsed.query).get("token", [""])[0]
            match = re.search(r"EVT-[A-Z0-9]+", candidate, re.IGNORECASE)
            if match:
                return match.group(0).upper()
        return raw.upper()

    def token_exists(self, db, token: str) -> bool:
        return bool(db.execute("SELECT 1 FROM accreditations WHERE token = ?", (self.payload_for_token(token),)).fetchone())

    def svg(self, db, token: str, renderer: Callable[[str], str]) -> str | None:
        payload = self.payload_for_token(token)
        if not self.token_exists(db, payload):
            return None
        return renderer(payload)
