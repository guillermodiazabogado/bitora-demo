from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EmailSendResult:
    ok: bool
    message_id: str = ""
    status: str = "error"
    error: str = ""
    raw: dict[str, Any] | None = None


class EmailProvider(ABC):
    name = "unknown"

    @property
    @abstractmethod
    def ready(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def send_email(
        self,
        *,
        to: str,
        subject: str,
        html: str,
        text: str = "",
        reply_to: str = "",
        metadata: dict[str, str] | None = None,
    ) -> EmailSendResult:
        raise NotImplementedError

    def send_template(
        self,
        *,
        to: str,
        subject: str,
        html: str,
        text: str = "",
        reply_to: str = "",
        metadata: dict[str, str] | None = None,
    ) -> EmailSendResult:
        return self.send_email(
            to=to,
            subject=subject,
            html=html,
            text=text,
            reply_to=reply_to,
            metadata=metadata,
        )

    @abstractmethod
    def get_delivery_status(self, message_id: str) -> dict[str, Any]:
        raise NotImplementedError


class DemoEmailProvider(EmailProvider):
    name = "demo"

    @property
    def ready(self) -> bool:
        return False

    def send_email(
        self,
        *,
        to: str,
        subject: str,
        html: str,
        text: str = "",
        reply_to: str = "",
        metadata: dict[str, str] | None = None,
    ) -> EmailSendResult:
        del to, subject, html, text, reply_to, metadata
        return EmailSendResult(ok=True, status="enviado", raw={"mode": "demo"})

    def get_delivery_status(self, message_id: str) -> dict[str, Any]:
        return {"id": message_id, "status": "demo"}


class ResendEmailProvider(EmailProvider):
    name = "resend"

    def __init__(
        self,
        *,
        api_key: str,
        from_email: str,
        reply_to: str = "",
        api_url: str = "https://api.resend.com",
        timeout: float = 15.0,
    ) -> None:
        self.api_key = api_key.strip()
        self.from_email = from_email.strip()
        self.reply_to = reply_to.strip()
        self.api_url = api_url.rstrip("/")
        self.timeout = timeout

    @property
    def ready(self) -> bool:
        return bool(self.api_key and self.from_email)

    def _request(self, method: str, path: str, payload: dict | None = None) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(
            self.api_url + path,
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "BITORA/6.1",
            },
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
                return json.loads(raw.decode("utf-8")) if raw else {}
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                detail = json.loads(raw)
                message = detail.get("message") or detail.get("error") or raw
            except json.JSONDecodeError:
                message = raw
            raise RuntimeError(f"Resend HTTP {exc.code}: {message}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"No se pudo conectar con Resend: {exc.reason}") from exc

    def send_email(
        self,
        *,
        to: str,
        subject: str,
        html: str,
        text: str = "",
        reply_to: str = "",
        metadata: dict[str, str] | None = None,
    ) -> EmailSendResult:
        if not self.ready:
            return EmailSendResult(ok=False, error="Proveedor Resend no configurado")
        payload: dict[str, Any] = {
            "from": self.from_email,
            "to": [to],
            "subject": subject,
            "html": html,
        }
        if text:
            payload["text"] = text
        effective_reply_to = reply_to.strip() or self.reply_to
        if effective_reply_to:
            payload["reply_to"] = effective_reply_to
        if metadata:
            payload["tags"] = [
                {"name": str(key)[:256], "value": str(value)[:256]}
                for key, value in metadata.items()
                if value is not None
            ]
        try:
            result = self._request("POST", "/emails", payload)
            message_id = str(result.get("id") or "")
            if not message_id:
                return EmailSendResult(ok=False, error="Resend no devolvio identificador", raw=result)
            return EmailSendResult(ok=True, message_id=message_id, status="enviado", raw=result)
        except RuntimeError as exc:
            return EmailSendResult(ok=False, error=str(exc))

    def get_delivery_status(self, message_id: str) -> dict[str, Any]:
        if not message_id:
            return {"status": "unknown"}
        return self._request("GET", f"/emails/{message_id}")


def create_email_provider() -> EmailProvider:
    provider = (os.environ.get("EMAIL_PROVIDER", "demo").strip() or "demo").lower()
    enabled = os.environ.get("EMAIL_ENABLED", "true").strip().lower() in {"1", "true", "yes", "si"}
    if not enabled or provider == "demo":
        return DemoEmailProvider()
    if provider == "resend":
        return ResendEmailProvider(
            api_key=os.environ.get("EMAIL_API_KEY", ""),
            from_email=os.environ.get("EMAIL_FROM", ""),
            reply_to=os.environ.get("EMAIL_REPLY_TO", ""),
            api_url=os.environ.get("EMAIL_RESEND_API_URL", "https://api.resend.com"),
            timeout=float(os.environ.get("EMAIL_TIMEOUT_SECONDS", "15")),
        )
    raise ValueError(f"Proveedor de email no soportado: {provider}")
