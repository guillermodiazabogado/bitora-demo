from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping

from backend.services.entitlements_vouchers import (
    EntitlementsVouchersError,
    EntitlementsVouchersService,
)


# These are transport-neutral route proposals. The HTTP adapter may bind them
# without moving domain behavior back into server.py.
VOUCHER_ROUTE_CONTRACTS = {
    "assign": "POST /api/organizations/{organization_id}/events/{event_id}/vouchers/assignments",
    "consume": "POST /api/organizations/{organization_id}/events/{event_id}/vouchers/consumptions",
    "participant": "GET /api/organizations/{organization_id}/events/{event_id}/vouchers/participants/current (X-Credential-Token)",
    "report": "GET /api/organizations/{organization_id}/events/{event_id}/vouchers/report",
}

_KEY = re.compile(r"^[A-Za-z0-9_.:-]+$")


@dataclass(frozen=True)
class VoucherScope:
    organization_id: int
    event_id: int
    actor: str = "voucher-api"

    def validated(self) -> "VoucherScope":
        if int(self.organization_id) <= 0 or int(self.event_id) <= 0:
            raise VoucherContractError("INVALID_SCOPE", "organization_id y event_id son obligatorios", 400)
        return self


class VoucherContractError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code

    def response(self) -> dict[str, Any]:
        return {"ok": False, "code": self.code, "error": self.message}


class VoucherApplicationContract:
    """Event/org-scoped facade for V5.4 entitlement and voucher operations.

    Authentication and permission checks remain a transport-adapter concern.
    This boundary independently guarantees tenant/event scoping, stable errors,
    mandatory consume idempotency and response allowlisting.
    """

    def __init__(self, service: EntitlementsVouchersService) -> None:
        self.service = service

    def assign(self, db, scope: VoucherScope, payload: Mapping[str, Any]) -> dict[str, Any]:
        scope = self._scope(db, scope)
        entity_id = self._positive_int(payload.get("entity_id"), "ENTITY_ID_REQUIRED")
        entitlement_type = self._key(payload.get("entitlement_type"), "ENTITLEMENT_TYPE_REQUIRED", 80)
        idempotency_key = self._key(payload.get("idempotency_key"), "IDEMPOTENCY_KEY_REQUIRED", 160)
        try:
            result = self.service.grant(
                db,
                organization_id=scope.organization_id,
                event_id=scope.event_id,
                entity_id=entity_id,
                entitlement_type=entitlement_type,
                allocated=max(0, int(payload.get("allocated", 1))),
                consumable=bool(payload.get("consumable", True)),
                scope_type=self._key(payload.get("scope_type", "EVENT"), "SCOPE_TYPE_REQUIRED", 60),
                scope_id=str(payload.get("scope_id", ""))[:160],
                valid_from=str(payload.get("valid_from", ""))[:64],
                valid_until=str(payload.get("valid_until", ""))[:64],
                source=self._key(payload.get("source", "MANUAL"), "SOURCE_REQUIRED", 80),
                source_reference=str(payload.get("source_reference", ""))[:160],
                idempotency_key=idempotency_key,
                actor=scope.actor,
            )
        except EntitlementsVouchersError as exc:
            raise self._service_error(exc) from exc
        return {
            "ok": True,
            "idempotent": bool(result.get("idempotent")),
            "entitlement": self._entitlement(result.get("entitlement") or {}),
        }

    def consume(self, db, scope: VoucherScope, payload: Mapping[str, Any]) -> dict[str, Any]:
        scope = self._scope(db, scope)
        # Consumption without a stable key is deliberately rejected before the
        # service can mutate quota. This is the externally visible invariant.
        idempotency_key = self._key(payload.get("idempotency_key"), "IDEMPOTENCY_KEY_REQUIRED", 160)
        token = str(payload.get("token", "")).strip()
        if not token:
            raise VoucherContractError("TOKEN_REQUIRED", "token es obligatorio", 400)
        entitlement_type = self._key(payload.get("entitlement_type"), "ENTITLEMENT_TYPE_REQUIRED", 80)
        try:
            result = self.service.consume(
                db,
                organization_id=scope.organization_id,
                event_id=scope.event_id,
                token=token,
                entitlement_type=entitlement_type,
                service_point_id=self._optional_positive_int(payload.get("service_point_id")),
                quantity=int(payload.get("quantity", 1)),
                device_id=self._optional_positive_int(payload.get("device_id")),
                idempotency_key=idempotency_key,
                correlation_id=self._optional_key(payload.get("correlation_id"), 160),
                source=self._optional_key(payload.get("source", "ONLINE"), 40) or "ONLINE",
            )
        except EntitlementsVouchersError as exc:
            raise self._service_error(exc) from exc
        consumption = result.get("consumption") or {}
        return {
            "ok": bool(result.get("ok")),
            "duplicate": bool(result.get("duplicate")),
            "result": str(result.get("result") or "DENIED"),
            "reason_code": str(result.get("reason_code") or "RULE_DENIED"),
            "consumption": self._consumption(consumption),
        }

    def participant(self, db, scope: VoucherScope, token: str) -> dict[str, Any]:
        scope = self._scope(db, scope)
        if not str(token or "").strip():
            raise VoucherContractError("TOKEN_REQUIRED", "token es obligatorio", 400)
        items = self.service.list_participant_entitlements(
            db,
            organization_id=scope.organization_id,
            event_id=scope.event_id,
            token=str(token).strip(),
        )
        return {"ok": True, "items": [self._entitlement(item) for item in items]}

    def report(self, db, scope: VoucherScope) -> dict[str, Any]:
        scope = self._scope(db, scope)
        report = self.service.organizer_report(
            db, organization_id=scope.organization_id, event_id=scope.event_id
        )
        return {
            "ok": True,
            "types": [
                {
                    "entitlement_type": str(row.get("entitlement_type") or ""),
                    "allocated": int(row.get("allocated") or 0),
                    "consumed": int(row.get("consumed") or 0),
                    "count": int(row.get("count") or 0),
                }
                for row in report.get("types", [])
            ],
            "denied": int(report.get("denied") or 0),
        }

    def _scope(self, db, scope: VoucherScope) -> VoucherScope:
        scope.validated()
        row = db.execute(
            "SELECT id FROM events WHERE id = ? AND organization_id = ?",
            (scope.event_id, scope.organization_id),
        ).fetchone()
        if not row:
            raise VoucherContractError("EVENT_SCOPE_ERROR", "Evento fuera de alcance", 403)
        return scope

    @staticmethod
    def _entitlement(item: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "id": int(item.get("id") or 0),
            "entity_id": int(item.get("entity_id") or 0),
            "entitlement_type": str(item.get("entitlement_type") or ""),
            "scope_type": str(item.get("scope_type") or ""),
            "scope_id": str(item.get("scope_id") or ""),
            "allocated": int(item.get("allocated") or 0),
            "consumed": int(item.get("consumed") or 0),
            "available": item.get("available"),
            "consumable": bool(item.get("consumable")),
            "status": str(item.get("status") or ""),
            "valid_from": str(item.get("valid_from") or ""),
            "valid_until": str(item.get("valid_until") or ""),
        }

    @staticmethod
    def _consumption(item: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "id": int(item.get("id") or 0),
            "entitlement_id": int(item.get("entitlement_id") or 0),
            "service_point_id": int(item.get("service_point_id") or 0),
            "device_id": int(item.get("device_id") or 0),
            "quantity": int(item.get("quantity") or 0),
            "result": str(item.get("result") or ""),
            "reason_code": str(item.get("reason_code") or ""),
            "occurred_at": str(item.get("occurred_at") or ""),
        }

    @staticmethod
    def _positive_int(value: Any, code: str) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError) as exc:
            raise VoucherContractError(code, "Identificador obligatorio", 400) from exc
        if parsed <= 0:
            raise VoucherContractError(code, "Identificador obligatorio", 400)
        return parsed

    @classmethod
    def _optional_positive_int(cls, value: Any) -> int | None:
        if value in (None, "", 0, "0"):
            return None
        return cls._positive_int(value, "INVALID_IDENTIFIER")

    @staticmethod
    def _key(value: Any, code: str, limit: int) -> str:
        text = str(value or "").strip()
        if not text or len(text) > limit or not _KEY.fullmatch(text):
            raise VoucherContractError(code, "Valor obligatorio o invalido", 400)
        return text

    @staticmethod
    def _optional_key(value: Any, limit: int) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        if len(text) > limit or not _KEY.fullmatch(text):
            raise VoucherContractError("INVALID_KEY", "Valor invalido", 400)
        return text

    @staticmethod
    def _service_error(exc: EntitlementsVouchersError) -> VoucherContractError:
        return VoucherContractError(exc.code, exc.message, exc.status_code)
