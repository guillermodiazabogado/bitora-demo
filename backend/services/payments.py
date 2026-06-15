from __future__ import annotations

from backend.jobs import Job, default_queue


class PaymentService:
    def create_checkout(self, accreditation_id: int, amount: float, metadata: dict | None = None) -> Job:
        return default_queue.enqueue(
            "payment.checkout.create",
            {
                "accreditation_id": accreditation_id,
                "amount": amount,
                "metadata": metadata or {},
            },
        )

    def handle_webhook(self, provider: str, payload: dict) -> Job:
        return default_queue.enqueue(
            "payment.webhook.received",
            {"provider": provider, "payload": payload},
        )
