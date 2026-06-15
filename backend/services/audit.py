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
        self.repository.insert_audit(
            db,
            actor=actor,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            payload_json=json.dumps(payload, ensure_ascii=True),
            created_at=self.now(),
        )
