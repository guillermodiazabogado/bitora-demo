from __future__ import annotations

from .sqlite import SQLiteRepository


class AccessRepository(SQLiteRepository):
    """Access validation and access-log data boundary."""
