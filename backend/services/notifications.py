from __future__ import annotations

from backend.jobs import Job, default_queue
from backend.services.email import EmailProvider, EmailSendResult, create_email_provider


class NotificationService:
    def notify(self, channel: str, payload: dict) -> Job:
        return default_queue.enqueue(f"notification.{channel}", payload)


class EmailService:
    def __init__(self, provider: EmailProvider | None = None) -> None:
        self.provider = provider or create_email_provider()

    def send(self, to: str, subject: str, body: str, metadata: dict | None = None) -> Job:
        return default_queue.enqueue(
            "email.send",
            {"to": to, "subject": subject, "body": body, "metadata": metadata or {}},
        )

    def deliver(self, to: str, subject: str, body: str, metadata: dict | None = None) -> EmailSendResult:
        return self.provider.send_email(
            to=to,
            subject=subject,
            html=body,
            text=body,
            metadata={str(key): str(value) for key, value in (metadata or {}).items()},
        )


class WhatsAppService:
    def send(self, phone: str, message: str, metadata: dict | None = None) -> Job:
        return default_queue.enqueue(
            "whatsapp.send",
            {"phone": phone, "message": message, "metadata": metadata or {}},
        )
