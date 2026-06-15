from __future__ import annotations

from .sqlite import SQLiteRepository


class CommunicationRepository(SQLiteRepository):
    """Communication preferences, templates and logs data boundary."""
