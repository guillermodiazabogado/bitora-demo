from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class DatabaseConfig:
    engine: str
    sqlite_path: str
    postgres_dsn: str

    @property
    def production_ready(self) -> bool:
        return self.engine == "postgres" and bool(self.postgres_dsn)


def load_database_config() -> DatabaseConfig:
    return DatabaseConfig(
        engine=os.environ.get("QR_DB_ENGINE", "sqlite").lower(),
        sqlite_path=os.environ.get("QR_SQLITE_PATH", "acreditaciones.sqlite3"),
        postgres_dsn=os.environ.get("QR_POSTGRES_DSN", ""),
    )
