from __future__ import annotations

from .sqlite import SQLiteRepository


class ActivityRepository(SQLiteRepository):
    """Activity and space data boundary."""
