from __future__ import annotations

from .sqlite import SQLiteRepository


class AccreditationRepository(SQLiteRepository):
    """Accreditation and QR-token data boundary."""
