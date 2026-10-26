from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from backend.services.vehicle_logistics import VehicleLogisticsError, VehicleLogisticsService


ROUTES = {
    "access": "POST /api/v5/organizations/{organization_id}/events/{event_id}/vehicles/access",
    "offline_sync": "POST /api/v5/organizations/{organization_id}/events/{event_id}/vehicles/offline-sync",
    "dashboard": "GET /api/v5/organizations/{organization_id}/events/{event_id}/vehicles/dashboard",
    "csv_preview": "POST /api/v5/organizations/{organization_id}/events/{event_id}/vehicles/import-preview",
}


@dataclass(frozen=True)
class EventScope:
    organization_id: int
    event_id: int

    def validate(self) -> None:
        if self.organization_id <= 0 or self.event_id <= 0:
            raise VehicleLogisticsError("SCOPE_INVALID", "Organization y event son obligatorios", 400)


class VehicleLogisticsContract:
    """Validated event-scoped boundary; anti-passback remains service-owned."""

    def __init__(self, service: VehicleLogisticsService) -> None:
        self.service = service

    def access(self, db, scope: EventScope, payload: dict[str, Any]) -> dict:
        scope.validate()
        direction = self._key(payload.get("direction") or "ENTRY", 10)
        if direction not in {"ENTRY", "EXIT"}:
            raise VehicleLogisticsError("DIRECTION_INVALID", "Direccion invalida", 400)
        plate = self._plate(payload.get("plate"))
        if not plate:
            raise VehicleLogisticsError("PLATE_REQUIRED", "Patente requerida", 400)
        return self.service.record_access(
            db,
            organization_id=scope.organization_id,
            event_id=scope.event_id,
            plate=plate,
            direction=direction,
            gate_id=self._optional_positive_int(payload.get("gate_id"), "gate_id"),
            destination_id=self._optional_positive_int(payload.get("destination_id"), "destination_id"),
            driver_entity_id=self._optional_positive_int(payload.get("driver_entity_id"), "driver_entity_id"),
            device_id=self._optional_positive_int(payload.get("device_id"), "device_id"),
            idempotency_key=self._idempotency(payload),
            correlation_id=self._key(payload.get("correlation_id"), 160),
            override=False,
        )

    def offline_sync(self, db, scope: EventScope, payload: dict[str, Any]) -> dict:
        scope.validate()
        operation = payload.get("operation")
        secret = self._text(payload.get("device_secret"), 512)
        if not secret or not isinstance(operation, dict):
            raise VehicleLogisticsError("OFFLINE_PAYLOAD_INVALID", "Credencial y operacion son obligatorias", 400)
        operation = dict(operation)
        operation["idempotency_key"] = self._idempotency(operation)
        inner = operation.get("payload")
        if not isinstance(inner, dict):
            raise VehicleLogisticsError("OFFLINE_PAYLOAD_INVALID", "Payload de operacion invalido", 400)
        inner = dict(inner)
        inner["plate"] = self._plate(inner.get("plate"))
        inner["direction"] = self._key(inner.get("direction") or "ENTRY", 10)
        if not inner["plate"] or inner["direction"] not in {"ENTRY", "EXIT"}:
            raise VehicleLogisticsError("OFFLINE_PAYLOAD_INVALID", "Patente o direccion invalida", 400)
        operation["payload"] = inner
        return self.service.reconcile_offline(
            db,
            organization_id=scope.organization_id,
            event_id=scope.event_id,
            device_id=self._positive_int(payload.get("device_id"), "device_id"),
            secret=secret,
            operation=operation,
        )

    def dashboard(self, db, scope: EventScope) -> dict:
        scope.validate()
        self._assert_event_scope(db, scope)
        return {"ok": True, "metrics": self.service.dashboard(db, organization_id=scope.organization_id, event_id=scope.event_id)}

    def preview_csv(self, db, scope: EventScope, payload: dict[str, Any]) -> dict:
        scope.validate()
        self._assert_event_scope(db, scope)
        csv_text = self._text(payload.get("csv"), 2_000_000)
        if not csv_text:
            raise VehicleLogisticsError("CSV_REQUIRED", "CSV requerido", 400)
        return self.service.preview_csv(csv_text)

    @staticmethod
    def _assert_event_scope(db, scope: EventScope) -> None:
        row = db.execute(
            "SELECT id FROM events WHERE id = ? AND organization_id = ?",
            (scope.event_id, scope.organization_id),
        ).fetchone()
        if not row:
            raise VehicleLogisticsError("EVENT_SCOPE_ERROR", "Evento fuera de alcance", 403)

    @staticmethod
    def _idempotency(payload: dict[str, Any]) -> str:
        value = VehicleLogisticsContract._key(payload.get("idempotency_key"), 160)
        if not value:
            raise VehicleLogisticsError("IDEMPOTENCY_KEY_REQUIRED", "Idempotency-Key requerido", 400)
        return value

    @staticmethod
    def _positive_int(value: Any, field: str) -> int:
        try:
            result = int(value)
        except (TypeError, ValueError) as exc:
            raise VehicleLogisticsError("FIELD_INVALID", f"{field} invalido", 400) from exc
        if result <= 0:
            raise VehicleLogisticsError("FIELD_INVALID", f"{field} invalido", 400)
        return result

    @classmethod
    def _optional_positive_int(cls, value: Any, field: str) -> int | None:
        return None if value in (None, "") else cls._positive_int(value, field)

    @staticmethod
    def _key(value: Any, limit: int) -> str:
        return re.sub(r"[^A-Za-z0-9_.:-]+", "_", str(value or "").strip().upper()).strip("_")[:limit]

    @staticmethod
    def _text(value: Any, limit: int) -> str:
        return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(value or "")).strip()[:limit]

    @staticmethod
    def _plate(value: Any) -> str:
        return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())[:20]

