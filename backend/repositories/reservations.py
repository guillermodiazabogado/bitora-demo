from __future__ import annotations

from .sqlite import SQLiteRepository


class ReservationRepository(SQLiteRepository):
    """Reservation and waitlist data boundary."""
