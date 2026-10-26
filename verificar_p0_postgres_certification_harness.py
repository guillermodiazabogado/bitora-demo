from __future__ import annotations

import os
from pathlib import Path

from scripts import certify_postgres


def assert_raises(code: str, callback) -> None:
    try:
        callback()
    except RuntimeError as exc:
        if str(exc) != code:
            raise AssertionError((code, str(exc))) from exc
    else:
        raise AssertionError(f"Expected {code}")


def main() -> None:
    saved = {key: os.environ.get(key) for key in ("BITORA_CERT_POSTGRES_DSN", "BITORA_CERT_CONFIRM", "BITORA_CERT_ALLOW_REMOTE")}
    try:
        for key in saved:
            os.environ.pop(key, None)
        assert_raises("BITORA_CERT_POSTGRES_DSN_REQUIRED", certify_postgres.require_safe_admin_dsn)

        os.environ["BITORA_CERT_POSTGRES_DSN"] = "postgresql://postgres:test@db.example.test:5432/postgres"
        os.environ["BITORA_CERT_CONFIRM"] = "TEMPORARY_DATABASES"
        assert_raises("REMOTE_POSTGRES_REQUIRES_BITORA_CERT_ALLOW_REMOTE=1", certify_postgres.require_safe_admin_dsn)

        os.environ["BITORA_CERT_POSTGRES_DSN"] = "postgresql://postgres:test@127.0.0.1:5432/postgres"
        os.environ.pop("BITORA_CERT_CONFIRM", None)
        assert_raises("BITORA_CERT_CONFIRM=TEMPORARY_DATABASES_REQUIRED", certify_postgres.require_safe_admin_dsn)

        os.environ["BITORA_CERT_CONFIRM"] = "TEMPORARY_DATABASES"
        if not certify_postgres.require_safe_admin_dsn().startswith("postgresql://"):
            raise AssertionError("Safe local DSN rejected")

        migrations = sorted(Path(certify_postgres.MIGRATIONS).glob("*.sql"))
        inventory = certify_postgres.migration_inventory()
        if set(inventory["duplicate_sequence_prefixes"]) != {"007", "015"}:
            raise AssertionError(inventory["duplicate_sequence_prefixes"])
        if not migrations or migrations[-1].name != "048_auth_login_rate_limits.sql":
            raise AssertionError(migrations[-1].name if migrations else "no migrations")
        print("P0 PostgreSQL certification harness safety and migration inventory: OK")
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


if __name__ == "__main__":
    main()
