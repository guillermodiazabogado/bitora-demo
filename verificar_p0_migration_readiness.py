from __future__ import annotations

from pathlib import Path
import sqlite3
import tempfile

from backend.database import migration_status


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="bitora-migration-readiness-", dir=Path(__file__).resolve().parent / "tmp") as temp:
        migrations = Path(temp) / "migrations"
        migrations.mkdir()
        (migrations / "001_first.sql").write_text("SELECT 1;", encoding="utf-8")
        (migrations / "002_second.sql").write_text("SELECT 2;", encoding="utf-8")
        db = sqlite3.connect(":memory:")
        db.row_factory = sqlite3.Row
        db.execute("CREATE TABLE schema_migrations (version TEXT PRIMARY KEY)")

        empty = migration_status(db, migrations)
        assert_true(not empty["ok"] and empty["missing"] == ["001_first.sql", "002_second.sql"], empty)
        db.execute("INSERT INTO schema_migrations(version) VALUES ('001_first.sql')")
        partial = migration_status(db, migrations)
        assert_true(not partial["ok"] and partial["missing"] == ["002_second.sql"], partial)
        db.execute("INSERT INTO schema_migrations(version) VALUES ('002_second.sql')")
        complete = migration_status(db, migrations)
        assert_true(complete["ok"] and complete["expected_count"] == complete["applied_count"] == 2, complete)
        db.execute("INSERT INTO schema_migrations(version) VALUES ('999_unknown.sql')")
        drift = migration_status(db, migrations)
        assert_true(not drift["ok"] and drift["unexpected"] == ["999_unknown.sql"], drift)
        db.close()
    print("P0 exact migration readiness: OK")


if __name__ == "__main__":
    main()
