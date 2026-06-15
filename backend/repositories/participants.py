from __future__ import annotations

from .sqlite import SQLiteRepository


class ParticipantRepository(SQLiteRepository):
    """Participant data boundary for people and communication preferences."""
