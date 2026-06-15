from __future__ import annotations

from .sqlite import SQLiteRepository


class AuditRepository(SQLiteRepository):
    """Audit-log data boundary."""
