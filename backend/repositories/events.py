from __future__ import annotations

from .sqlite import SQLiteRepository


class EventRepository(SQLiteRepository):
    """Event data boundary.

    Currently backed by SQLiteRepository. Split out so a future PostgreSQL
    implementation can replace event access without touching services.
    """
