from __future__ import annotations

from backend.jobs import Job, default_queue


class NotificationService:
    def notify(self, channel: str, payload: dict) -> Job:
        return default_queue.enqueue(f"notification.{channel}", payload)


class EmailService:
    def send(self, to: str, subject: str, body: str, metadata: dict | None = None) -> Job:
        return default_queue.enqueue(
            "email.send",
            {"to": to, "subject": subject, "body": body, "metadata": metadata or {}},
        )


class WhatsAppService:
    def send(self, phone: str, message: str, metadata: dict | None = None) -> Job:
        return default_queue.enqueue(
            "whatsapp.send",
            {"phone": phone, "message": message, "metadata": metadata or {}},
        )
