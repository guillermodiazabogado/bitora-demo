import threading
import time

import server


class FakePostgresConnection:
    engine = "postgres"


class FakeSqliteConnection:
    engine = "sqlite"


def main() -> None:
    postgres_entered = threading.Event()
    sqlite_entered = threading.Event()

    server.DB_LOCK.acquire()
    try:
        def enter_postgres() -> None:
            with server.access_validation_critical_section(FakePostgresConnection()):
                postgres_entered.set()

        postgres_thread = threading.Thread(target=enter_postgres, daemon=True)
        postgres_thread.start()
        postgres_thread.join(timeout=1)
        assert postgres_entered.is_set(), "PostgreSQL validation remained serialized by DB_LOCK"

        def enter_sqlite() -> None:
            with server.access_validation_critical_section(FakeSqliteConnection()):
                sqlite_entered.set()

        sqlite_thread = threading.Thread(target=enter_sqlite, daemon=True)
        sqlite_thread.start()
        time.sleep(0.1)
        assert not sqlite_entered.is_set(), "SQLite validation bypassed DB_LOCK"
    finally:
        server.DB_LOCK.release()

    sqlite_thread.join(timeout=1)
    assert sqlite_entered.is_set(), "SQLite validation did not resume after DB_LOCK release"
    print("PASS: PostgreSQL scans run independently while SQLite keeps its write lock")


if __name__ == "__main__":
    main()
