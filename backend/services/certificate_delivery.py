from __future__ import annotations

import hashlib


class CertificateDeliveryError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class CertificateDeliveryService:
    """Connect an issued certificate to the existing durable Gmail queue."""

    def __init__(self, audit_service, now) -> None:
        self.audit_service = audit_service
        self.now = now

    def queue_email(
        self,
        db,
        *,
        organization_id: int,
        event_id: int,
        issuance_id: int,
        actor: str,
        resend_key: str = "",
    ) -> dict:
        event = db.execute(
            "SELECT status FROM events WHERE id = ? AND organization_id = ?",
            (event_id, organization_id),
        ).fetchone()
        if not event:
            raise CertificateDeliveryError("EVENT_NOT_FOUND", "Evento inexistente", 404)
        if str(event["status"] or "").strip().lower() != "closed":
            raise CertificateDeliveryError(
                "EVENT_NOT_CLOSED",
                "El evento debe estar finalizado antes de enviar certificados",
                409,
            )
        row = db.execute(
            """
            SELECT ci.id, ci.status, ci.participant_id, p.email, p.first_name, p.last_name,
                   a.id AS accreditation_id, a.token, e.name AS event_name
            FROM certificate_issuances ci
            JOIN people p ON p.id = ci.participant_id
            JOIN events e ON e.id = ci.event_id
            LEFT JOIN accreditations a ON a.event_id = ci.event_id AND a.person_id = ci.participant_id
            WHERE ci.id = ? AND ci.organization_id = ? AND ci.event_id = ?
            ORDER BY a.id LIMIT 1
            """,
            (issuance_id, organization_id, event_id),
        ).fetchone()
        if not row:
            raise CertificateDeliveryError("CERTIFICATE_NOT_FOUND", "Certificado inexistente", 404)
        if str(row["status"]) != "ISSUED":
            raise CertificateDeliveryError("CERTIFICATE_NOT_ISSUED", "Solo se puede enviar un certificado emitido", 409)
        email = str(row["email"] or "").strip().lower()
        if "@" not in email:
            raise CertificateDeliveryError("CERTIFICATE_RECIPIENT_INVALID", "El participante no tiene un email valido", 409)

        resend_key = str(resend_key or "").strip()
        logical_key = f"certificate-email:{organization_id}:{event_id}:{issuance_id}"
        if resend_key:
            logical_key += f":resend:{resend_key}"
        idempotency_key = hashlib.sha256(logical_key.encode("utf-8")).hexdigest()
        existing = db.execute(
            "SELECT * FROM communication_queue WHERE idempotency_key = ?",
            (idempotency_key,),
        ).fetchone()
        if existing:
            return {"ok": True, "idempotent": True, "queue_id": int(existing["id"]), "status": existing["status"]}

        now = self.now()
        name = " ".join(part for part in (row["first_name"], row["last_name"]) if part).strip()
        subject = f"Certificado disponible - {row['event_name']}"
        content = (
            f"Hola {name}, tu certificado de {row['event_name']} esta disponible "
            "en tu portal de participante."
        )
        cur = db.execute(
            """
            INSERT INTO communication_queue (
                event_id, organization_id, person_id, accreditation_id, channel, audience,
                template_code, subject, content, recipient, status, attempts, max_attempts,
                provider, idempotency_key, created_by, created_at
            ) VALUES (?, ?, ?, ?, 'email', ?, 'certificate_available', ?, ?, ?,
                      'pendiente', 0, 3, 'gmail', ?, ?, ?)
            """,
            (
                event_id,
                organization_id,
                int(row["participant_id"]),
                int(row["accreditation_id"] or 0) or None,
                f"certificate:{issuance_id}",
                subject,
                content,
                email,
                idempotency_key,
                actor,
                now,
            ),
        )
        queue_id = int(cur.lastrowid)
        self.audit_service.record(
            db,
            actor,
            "certificates.email_queued" if not resend_key else "certificates.email_requeued",
            "certificate_issuance",
            issuance_id,
            {"organization_id": organization_id, "event_id": event_id, "queue_id": queue_id},
        )
        return {"ok": True, "idempotent": False, "queue_id": queue_id, "status": "pendiente"}

    def history(self, db, *, organization_id: int, event_id: int, issuance_id: int) -> dict:
        rows = db.execute(
            """
            SELECT id, status, attempts, provider, provider_message_id, last_error,
                   scheduled_at, processed_at, delivered_at, created_by, created_at
            FROM communication_queue
            WHERE organization_id = ? AND event_id = ? AND template_code = 'certificate_available'
              AND audience = ?
            ORDER BY id DESC
            """,
            (organization_id, event_id, f"certificate:{issuance_id}"),
        ).fetchall()
        return {"items": [dict(row) for row in rows]}
