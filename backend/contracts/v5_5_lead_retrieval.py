from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from backend.services.lead_retrieval import LeadRetrievalError, LeadRetrievalService


ROUTES = {
    "capture": "POST /api/v5/organizations/{organization_id}/events/{event_id}/leads/captures",
    "offline_sync": "POST /api/v5/organizations/{organization_id}/events/{event_id}/leads/offline-sync",
    "list": "GET /api/v5/organizations/{organization_id}/events/{event_id}/companies/{company_id}/leads",
    "export": "POST /api/v5/organizations/{organization_id}/events/{event_id}/companies/{company_id}/leads/export",
}


@dataclass(frozen=True)
class EventScope:
    organization_id: int
    event_id: int

    def validate(self) -> None:
        if self.organization_id <= 0 or self.event_id <= 0:
            raise LeadRetrievalError("SCOPE_INVALID", "Organization y event son obligatorios", 400)


@dataclass(frozen=True)
class ActorContext:
    user_id: int
    name: str
    role: str

    @property
    def can_manage_all_companies(self) -> bool:
        return self.role in {"Super Admin", "Productor"}


class LeadRetrievalContract:
    """Validated, transport-neutral boundary for V5.5 routes.

    Authentication/RBAC remains the HTTP adapter's responsibility. This boundary
    guarantees that every service call carries the organization/event scope.
    """

    def __init__(self, service: LeadRetrievalService) -> None:
        self.service = service

    def capture(self, db, scope: EventScope, payload: dict[str, Any]) -> dict:
        scope.validate()
        idem = self._idempotency(payload)
        company_id = self._positive_int(payload.get("company_id"), "company_id")
        token = self._text(payload.get("token"), 512)
        if not token:
            raise LeadRetrievalError("TOKEN_REQUIRED", "Token requerido", 400)
        consent_id = self._optional_positive_int(payload.get("consent_id"), "consent_id")
        if consent_id is not None:
            consent = db.execute(
                "SELECT id FROM enterprise_lead_consents WHERE id = ? AND organization_id = ? AND event_id = ? AND (company_id IS NULL OR company_id = ?) AND status = 'GRANTED'",
                (consent_id, scope.organization_id, scope.event_id, company_id),
            ).fetchone()
            if not consent:
                raise LeadRetrievalError("CONSENT_SCOPE_ERROR", "Consentimiento fuera de alcance", 403)
        return self.service.capture(
            db,
            organization_id=scope.organization_id,
            event_id=scope.event_id,
            company_id=company_id,
            token=token,
            consent_id=consent_id,
            stand_id=self._optional_positive_int(payload.get("stand_id"), "stand_id"),
            user_email=self._email(payload.get("user_email")),
            device_id=self._optional_positive_int(payload.get("device_id"), "device_id"),
            idempotency_key=idem,
            source=self._key(payload.get("source") or "QR_SCAN", 40),
        )

    def offline_sync(self, db, scope: EventScope, payload: dict[str, Any]) -> dict:
        scope.validate()
        device_id = self._positive_int(payload.get("device_id"), "device_id")
        secret = self._text(payload.get("device_secret"), 512)
        operation = payload.get("operation")
        if not secret or not isinstance(operation, dict):
            raise LeadRetrievalError("OFFLINE_PAYLOAD_INVALID", "Credencial y operacion son obligatorias", 400)
        operation = dict(operation)
        operation["idempotency_key"] = self._idempotency(operation)
        operation_payload = operation.get("payload")
        if not isinstance(operation_payload, dict) or not operation_payload.get("consent_evidence"):
            raise LeadRetrievalError("CONSENT_REQUIRED", "Evidencia de consentimiento requerida", 422)
        return self.service.reconcile_offline_capture(
            db,
            organization_id=scope.organization_id,
            event_id=scope.event_id,
            device_id=device_id,
            secret=secret,
            operation=operation,
        )

    def list_company(self, db, scope: EventScope, company_id: Any, actor: ActorContext) -> dict:
        scope.validate()
        value = self._positive_int(company_id, "company_id")
        self._assert_company_scope(db, scope, value)
        self._assert_actor_company_access(db, scope, value, actor, "leads.read")
        return {"ok": True, "items": self.service.list_leads(db, organization_id=scope.organization_id, event_id=scope.event_id, company_id=value)}

    def export_company(self, db, scope: EventScope, company_id: Any, payload: dict[str, Any], actor: ActorContext) -> dict:
        scope.validate()
        fields = payload.get("fields")
        if not isinstance(fields, list):
            raise LeadRetrievalError("FIELDS_INVALID", "fields debe ser una lista", 400)
        company = self._positive_int(company_id, "company_id")
        self._assert_company_scope(db, scope, company)
        self._assert_actor_company_access(db, scope, company, actor, "leads.export")
        return self.service.export_csv(
            db,
            organization_id=scope.organization_id,
            event_id=scope.event_id,
            company_id=company,
            fields=[self._key(item, 40).lower() for item in fields],
            exported_by=self._text(actor.name, 120),
            idempotency_key=self._idempotency(payload),
        )

    @staticmethod
    def _assert_company_scope(db, scope: EventScope, company_id: int) -> None:
        row = db.execute(
            "SELECT id FROM enterprise_company_event_participation WHERE organization_id = ? AND event_id = ? AND company_id = ? AND status = 'ACTIVE'",
            (scope.organization_id, scope.event_id, company_id),
        ).fetchone()
        if not row:
            raise LeadRetrievalError("COMPANY_SCOPE_ERROR", "Company fuera de evento", 403)

    @staticmethod
    def _assert_actor_company_access(db, scope: EventScope, company_id: int, actor: ActorContext, permission: str) -> None:
        if actor.can_manage_all_companies:
            return
        if actor.user_id <= 0:
            raise LeadRetrievalError("COMPANY_ACCESS_DENIED", "Acceso a company denegado", 403)
        row = db.execute(
            """
            SELECT ecu.permissions_json
            FROM enterprise_company_users ecu
            LEFT JOIN users u ON u.id = ?
            WHERE ecu.organization_id = ? AND ecu.event_id = ? AND ecu.company_id = ?
              AND ecu.status = 'ACTIVE'
              AND (ecu.user_id = ? OR (u.email <> '' AND LOWER(ecu.email) = LOWER(u.email)))
            LIMIT 1
            """,
            (actor.user_id, scope.organization_id, scope.event_id, company_id, actor.user_id),
        ).fetchone()
        if not row:
            raise LeadRetrievalError("COMPANY_ACCESS_DENIED", "Acceso a company denegado", 403)
        raw_permissions = row["permissions_json"] if hasattr(row, "keys") and "permissions_json" in row.keys() else row[0]
        try:
            import json

            permissions = json.loads(raw_permissions or "[]")
        except (TypeError, ValueError):
            permissions = []
        if permission not in permissions and "*" not in permissions:
            raise LeadRetrievalError("COMPANY_ACCESS_DENIED", "Acceso a company denegado", 403)

    @staticmethod
    def _idempotency(payload: dict[str, Any]) -> str:
        value = LeadRetrievalContract._key(payload.get("idempotency_key"), 160)
        if not value:
            raise LeadRetrievalError("IDEMPOTENCY_KEY_REQUIRED", "Idempotency-Key requerido", 400)
        return value

    @staticmethod
    def _positive_int(value: Any, field: str) -> int:
        try:
            result = int(value)
        except (TypeError, ValueError) as exc:
            raise LeadRetrievalError("FIELD_INVALID", f"{field} invalido", 400) from exc
        if result <= 0:
            raise LeadRetrievalError("FIELD_INVALID", f"{field} invalido", 400)
        return result

    @classmethod
    def _optional_positive_int(cls, value: Any, field: str) -> int | None:
        return None if value in (None, "") else cls._positive_int(value, field)

    @staticmethod
    def _key(value: Any, limit: int) -> str:
        return re.sub(r"[^A-Za-z0-9_.:-]+", "_", str(value or "").strip()).strip("_")[:limit]

    @staticmethod
    def _text(value: Any, limit: int) -> str:
        return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(value or "")).strip()[:limit]

    @classmethod
    def _email(cls, value: Any) -> str:
        email = cls._text(value, 254).lower()
        if email and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            raise LeadRetrievalError("EMAIL_INVALID", "Email invalido", 400)
        return email

