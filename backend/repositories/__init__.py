from .access import AccessRepository
from .accreditations import AccreditationRepository
from .activities import ActivityRepository
from .audit import AuditRepository
from .backups import BackupRepository
from .capacity_buckets import CapacityBucketRepository
from .communications import CommunicationRepository
from .events import EventRepository
from .participants import ParticipantRepository
from .postgres import PostgresRepository
from .reservations import ReservationRepository
from .sqlite import SQLiteRepository


def create_repository(engine: str = "sqlite"):
    return PostgresRepository() if engine == "postgres" else SQLiteRepository()

__all__ = [
    "AccessRepository",
    "AccreditationRepository",
    "ActivityRepository",
    "AuditRepository",
    "BackupRepository",
    "CapacityBucketRepository",
    "CommunicationRepository",
    "EventRepository",
    "ParticipantRepository",
    "PostgresRepository",
    "ReservationRepository",
    "SQLiteRepository",
    "create_repository",
]
