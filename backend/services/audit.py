from __future__ import annotations

import json
from collections.abc import Callable

from backend.repositories import SQLiteRepository


class AuditService:
    def __init__(self, repository: SQLiteRepository | None = None, now: Callable[[], str] | None = None) -> None:
        self.repository = repository or SQLiteRepository()
        self.now = now

    def record(self, db, actor: str, action: str, entity_type: str, entity_id: int | None, payload: dict) -> None:
        if not self.now:
            raise RuntimeError("AuditService requires a now provider")
        event_id = self._event_id(entity_type, entity_id, payload)
        self.repository.insert_audit(
            db,
            actor=actor,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            payload_json=json.dumps(payload, ensure_ascii=True),
            created_at=self.now(),
            event_id=event_id,
        )

    def _event_id(self, entity_type: str, entity_id: int | None, payload: dict) -> int | None:
        if entity_type == "event" and entity_id:
            try:
                return int(entity_id)
            except (TypeError, ValueError):
                return None
        try:
            value = int((payload or {}).get("event_id") or 0)
        except (TypeError, ValueError):
            return None
        return value or None
