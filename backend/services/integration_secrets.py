from __future__ import annotations

import base64
import hashlib
import os
from dataclasses import dataclass

from cryptography.fernet import Fernet, InvalidToken


class IntegrationSecretError(RuntimeError):
    pass


@dataclass
class IntegrationSecretService:
    """Encrypts organization integration secrets with a backend-only master key."""

    env_name: str = "BITORA_INTEGRATION_ENCRYPTION_KEY"

    def _fernet(self) -> Fernet:
        raw = os.environ.get(self.env_name, "").strip()
        if raw:
            try:
                return Fernet(raw.encode("utf-8"))
            except Exception as exc:
                raise IntegrationSecretError(f"{self.env_name} invalida") from exc
        if os.environ.get("APP_ENV", "").lower() in {"production", "staging"}:
            raise IntegrationSecretError(f"{self.env_name} es obligatoria en staging/production")
        seed = b"bitora-local-development-secret-key"
        key = base64.urlsafe_b64encode(hashlib.sha256(seed).digest())
        return Fernet(key)

    def encrypt(self, plaintext: str) -> str:
        if not plaintext:
            return ""
        return self._fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")

    def decrypt(self, ciphertext: str) -> str:
        if not ciphertext:
            return ""
        try:
            return self._fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise IntegrationSecretError("Secreto de integracion invalido o clave incorrecta") from exc


def mask_secret(value: str, visible: int = 4) -> str:
    text = str(value or "")
    if not text:
        return ""
    if len(text) <= visible:
        return "*" * len(text)
    return "*" * 12 + text[-visible:]
