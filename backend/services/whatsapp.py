from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
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

    def validate_configuration(self) -> dict[str, Any]:
        return {"ok": self.ready, "errors": [] if self.ready else ["Proveedor WhatsApp no configurado"]}

    def normalize_webhook(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        del payload
        return []


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

    def validate_configuration(self) -> dict[str, Any]:
        return {"ok": False, "errors": ["WhatsApp esta en modo demo"]}


class MetaCloudWhatsAppProvider(WhatsAppProvider):
    name = "meta"

    def __init__(
        self,
        *,
        access_token: str,
        phone_number_id: str,
        business_account_id: str = "",
        verify_token: str = "",
        app_secret: str = "",
        api_url: str = "https://graph.facebook.com/v22.0",
        timeout: float = 15,
    ) -> None:
        self.access_token = access_token.strip()
        self.phone_number_id = phone_number_id.strip()
        self.business_account_id = business_account_id.strip()
        self.verify_token = verify_token.strip()
        self.app_secret = app_secret.strip()
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
        phone = normalize_phone(to)
        if not valid_phone(phone):
            return WhatsAppSendResult(ok=False, error="Telefono WhatsApp invalido")
        return self._send({"to": phone, "type": "text", "text": {"preview_url": True, "body": message}})

    def send_template(self, *, to: str, template: str, variables: list[str] | None = None, language: str = "es_AR") -> WhatsAppSendResult:
        phone = normalize_phone(to)
        if not valid_phone(phone):
            return WhatsAppSendResult(ok=False, error="Telefono WhatsApp invalido")
        if not template:
            return WhatsAppSendResult(ok=False, error="Falta plantilla aprobada por Meta")
        components = []
        if variables:
            components.append({"type": "body", "parameters": [{"type": "text", "text": value} for value in variables]})
        return self._send({"to": phone, "type": "template", "template": {"name": template, "language": {"code": language}, "components": components}})

    def send_media(self, *, to: str, media_url: str, caption: str = "") -> WhatsAppSendResult:
        phone = normalize_phone(to)
        if not valid_phone(phone):
            return WhatsAppSendResult(ok=False, error="Telefono WhatsApp invalido")
        return self._send({"to": phone, "type": "image", "image": {"link": media_url, "caption": caption}})

    def get_status(self) -> dict[str, Any]:
        if not self.ready:
            return {"status": "disconnected"}
        try:
            result = self._request("GET", f"/{self.phone_number_id}?fields=display_phone_number,verified_name")
            return {"status": "connected", "display_phone_number": result.get("display_phone_number", ""), "verified_name": result.get("verified_name", "")}
        except RuntimeError as exc:
            return {"status": "error", "error": str(exc)}

    def validate_configuration(self) -> dict[str, Any]:
        errors = []
        if not self.access_token:
            errors.append("Falta WHATSAPP_ACCESS_TOKEN")
        if not self.phone_number_id:
            errors.append("Falta WHATSAPP_PHONE_NUMBER_ID")
        if not self.business_account_id:
            errors.append("Falta WHATSAPP_BUSINESS_ACCOUNT_ID")
        if not self.verify_token:
            errors.append("Falta WHATSAPP_VERIFY_TOKEN")
        if os.environ.get("APP_ENV", "development").strip().lower() == "production" and not self.app_secret:
            errors.append("En produccion configurar WHATSAPP_APP_SECRET para verificar firma")
        return {"ok": not errors, "errors": errors}

    def normalize_webhook(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        for entry in payload.get("entry") or []:
            for change in entry.get("changes") or []:
                value = change.get("value") or {}
                metadata = value.get("metadata") or {}
                for status_item in value.get("statuses") or []:
                    raw_status = str(status_item.get("status") or "").lower()
                    events.append(
                        {
                            "kind": "status",
                            "message_id": str(status_item.get("id") or ""),
                            "external_event_id": webhook_event_id("status", status_item),
                            "status": {
                                "sent": "enviado",
                                "delivered": "entregado",
                                "read": "leido",
                                "failed": "error",
                            }.get(raw_status, "pendiente"),
                            "raw_status": raw_status,
                            "phone": normalize_phone(status_item.get("recipient_id") or ""),
                            "timestamp": str(status_item.get("timestamp") or ""),
                            "errors": status_item.get("errors") or [],
                            "phone_number_id": str(metadata.get("phone_number_id") or ""),
                            "payload": status_item,
                        }
                    )
                for message in value.get("messages") or []:
                    events.append(
                        {
                            "kind": "message",
                            "message_id": str(message.get("id") or ""),
                            "external_event_id": webhook_event_id("message", message),
                            "phone": normalize_phone(message.get("from") or ""),
                            "timestamp": str(message.get("timestamp") or ""),
                            "message_type": str(message.get("type") or ""),
                            "text": str((message.get("text") or {}).get("body") or ""),
                            "phone_number_id": str(metadata.get("phone_number_id") or ""),
                            "payload": message,
                        }
                    )
        return events


def normalize_phone(value: str) -> str:
    return "".join(character for character in str(value or "") if character.isdigit())


def valid_phone(value: str) -> bool:
    phone = normalize_phone(value)
    return bool(re.fullmatch(r"[1-9][0-9]{7,14}", phone))


def whatsapp_safe_mode_enabled() -> bool:
    return os.environ.get("WHATSAPP_SAFE_MODE", "true").strip().lower() in {"1", "true", "yes", "si"}


def forced_whatsapp_recipient() -> str:
    return normalize_phone(os.environ.get("WHATSAPP_FORCE_RECIPIENT") or os.environ.get("WHATSAPP_TEST_RECIPIENT") or "")


def webhook_event_id(kind: str, payload: dict[str, Any]) -> str:
    explicit = str(payload.get("id") or "")
    timestamp = str(payload.get("timestamp") or "")
    status = str(payload.get("status") or payload.get("type") or "")
    if explicit or timestamp or status:
        return "|".join([kind, explicit, timestamp, status])
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def verify_meta_signature(raw_body: bytes, signature_header: str, app_secret: str) -> bool:
    if not app_secret:
        return True
    if not signature_header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(app_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)


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
            verify_token=os.environ.get("WHATSAPP_VERIFY_TOKEN", ""),
            app_secret=os.environ.get("WHATSAPP_APP_SECRET", ""),
            api_url=os.environ.get("WHATSAPP_META_API_URL", "https://graph.facebook.com/v22.0"),
            timeout=float(os.environ.get("WHATSAPP_TIMEOUT_SECONDS", "15")),
        )
    raise ValueError(f"Proveedor WhatsApp no soportado: {provider}")
