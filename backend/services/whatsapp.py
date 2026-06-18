from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class WhatsAppSendResult:
    ok: bool
    message_id: str = ""
    status: str = "error"
    error: str = ""
    raw: dict[str, Any] | None = None


class WhatsAppProvider(ABC):
    name = "unknown"

    @property
    @abstractmethod
    def ready(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def send_message(self, *, to: str, message: str) -> WhatsAppSendResult:
        raise NotImplementedError

    @abstractmethod
    def send_template(self, *, to: str, template: str, variables: list[str] | None = None, language: str = "es_AR") -> WhatsAppSendResult:
        raise NotImplementedError

    @abstractmethod
    def send_media(self, *, to: str, media_url: str, caption: str = "") -> WhatsAppSendResult:
        raise NotImplementedError

    @abstractmethod
    def get_status(self) -> dict[str, Any]:
        raise NotImplementedError


class DemoWhatsAppProvider(WhatsAppProvider):
    name = "demo"

    @property
    def ready(self) -> bool:
        return False

    def send_message(self, *, to: str, message: str) -> WhatsAppSendResult:
        del to, message
        return WhatsAppSendResult(ok=True, status="enviado", raw={"mode": "demo"})

    def send_template(self, *, to: str, template: str, variables: list[str] | None = None, language: str = "es_AR") -> WhatsAppSendResult:
        del to, template, variables, language
        return WhatsAppSendResult(ok=True, status="enviado", raw={"mode": "demo"})

    def send_media(self, *, to: str, media_url: str, caption: str = "") -> WhatsAppSendResult:
        del to, media_url, caption
        return WhatsAppSendResult(ok=True, status="enviado", raw={"mode": "demo"})

    def get_status(self) -> dict[str, Any]:
        return {"status": "demo"}


class MetaCloudWhatsAppProvider(WhatsAppProvider):
    name = "meta"

    def __init__(self, *, access_token: str, phone_number_id: str, business_account_id: str = "", api_url: str = "https://graph.facebook.com/v22.0", timeout: float = 15) -> None:
        self.access_token = access_token.strip()
        self.phone_number_id = phone_number_id.strip()
        self.business_account_id = business_account_id.strip()
        self.api_url = api_url.rstrip("/")
        self.timeout = timeout

    @property
    def ready(self) -> bool:
        return bool(self.access_token and self.phone_number_id)

    def _request(self, method: str, path: str, payload: dict | None = None) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(
            self.api_url + path,
            data=body,
            headers={"Authorization": f"Bearer {self.access_token}", "Content-Type": "application/json", "User-Agent": "BITORA/7.0"},
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
                return json.loads(raw.decode("utf-8")) if raw else {}
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Meta Cloud API HTTP {exc.code}: {raw}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"No se pudo conectar con Meta Cloud API: {exc.reason}") from exc

    def _send(self, payload: dict[str, Any]) -> WhatsAppSendResult:
        if not self.ready:
            return WhatsAppSendResult(ok=False, error="Proveedor Meta no configurado")
        try:
            result = self._request("POST", f"/{self.phone_number_id}/messages", {"messaging_product": "whatsapp", **payload})
            messages = result.get("messages") or []
            message_id = str(messages[0].get("id") if messages else "")
            return WhatsAppSendResult(ok=bool(message_id), message_id=message_id, status="enviado" if message_id else "error", error="" if message_id else "Meta no devolvio identificador", raw=result)
        except RuntimeError as exc:
            return WhatsAppSendResult(ok=False, error=str(exc))

    def send_message(self, *, to: str, message: str) -> WhatsAppSendResult:
        return self._send({"to": normalize_phone(to), "type": "text", "text": {"preview_url": True, "body": message}})

    def send_template(self, *, to: str, template: str, variables: list[str] | None = None, language: str = "es_AR") -> WhatsAppSendResult:
        components = []
        if variables:
            components.append({"type": "body", "parameters": [{"type": "text", "text": value} for value in variables]})
        return self._send({"to": normalize_phone(to), "type": "template", "template": {"name": template, "language": {"code": language}, "components": components}})

    def send_media(self, *, to: str, media_url: str, caption: str = "") -> WhatsAppSendResult:
        return self._send({"to": normalize_phone(to), "type": "image", "image": {"link": media_url, "caption": caption}})

    def get_status(self) -> dict[str, Any]:
        if not self.ready:
            return {"status": "disconnected"}
        try:
            result = self._request("GET", f"/{self.phone_number_id}?fields=display_phone_number,verified_name")
            return {"status": "connected", "display_phone_number": result.get("display_phone_number", ""), "verified_name": result.get("verified_name", "")}
        except RuntimeError as exc:
            return {"status": "error", "error": str(exc)}


def normalize_phone(value: str) -> str:
    return "".join(character for character in str(value or "") if character.isdigit())


def create_whatsapp_provider() -> WhatsAppProvider:
    provider = (os.environ.get("WHATSAPP_PROVIDER", "demo").strip() or "demo").lower()
    enabled = os.environ.get("WHATSAPP_ENABLED", "false").strip().lower() in {"1", "true", "yes", "si"}
    if not enabled or provider == "demo":
        return DemoWhatsAppProvider()
    if provider == "meta":
        return MetaCloudWhatsAppProvider(
            access_token=os.environ.get("WHATSAPP_ACCESS_TOKEN", ""),
            phone_number_id=os.environ.get("WHATSAPP_PHONE_NUMBER_ID", os.environ.get("WHATSAPP_PHONE_ID", "")),
            business_account_id=os.environ.get("WHATSAPP_BUSINESS_ACCOUNT_ID", ""),
            api_url=os.environ.get("WHATSAPP_META_API_URL", "https://graph.facebook.com/v22.0"),
            timeout=float(os.environ.get("WHATSAPP_TIMEOUT_SECONDS", "15")),
        )
    raise ValueError(f"Proveedor WhatsApp no soportado: {provider}")
