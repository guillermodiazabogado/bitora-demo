from __future__ import annotations

from collections.abc import Callable


class QRService:
    def payload_for_token(self, token: str) -> str:
        return token.strip().upper()

    def token_exists(self, db, token: str) -> bool:
        return bool(db.execute("SELECT 1 FROM accreditations WHERE token = ?", (self.payload_for_token(token),)).fetchone())

    def svg(self, db, token: str, renderer: Callable[[str], str]) -> str | None:
        payload = self.payload_for_token(token)
        if not self.token_exists(db, payload):
            return None
        return renderer(payload)
