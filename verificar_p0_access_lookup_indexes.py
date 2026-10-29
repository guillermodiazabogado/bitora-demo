import os
import tempfile

import server


def main() -> None:
    fd, path = tempfile.mkstemp(prefix="bitora-access-indexes-", suffix=".db")
    os.close(fd)
    previous = server.DB_PATH
    try:
        server.DB_PATH = path
        server.init_db()
        server.seed_if_empty()
        with server.connect() as db:
            indexes = {
                row["name"]
                for row in db.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'index' AND name IN (?, ?)",
                    (
                        "idx_accreditations_token_normalized",
                        "idx_enterprise_credentials_token_lookup",
                    ),
                ).fetchall()
            }
            assert indexes == {
                "idx_accreditations_token_normalized",
                "idx_enterprise_credentials_token_lookup",
            }, indexes
            legacy_plan = " ".join(
                str(row["detail"])
                for row in db.execute(
                    "EXPLAIN QUERY PLAN SELECT id FROM accreditations WHERE lower(token) = lower(?)",
                    ("TEST",),
                ).fetchall()
            )
            enterprise_plan = " ".join(
                str(row["detail"])
                for row in db.execute(
                    """
                    EXPLAIN QUERY PLAN SELECT id FROM enterprise_credentials
                    WHERE organization_id = ? AND event_id = ?
                      AND credential_type = 'QR_TOKEN' AND legacy_token_hash = ?
                    """,
                    (1, 1, "hash"),
                ).fetchall()
            )
            assert "idx_accreditations_token_normalized" in legacy_plan, legacy_plan
            assert "idx_enterprise_credentials_token_lookup" in enterprise_plan, enterprise_plan
        print("PASS: QR token lookups use dedicated indexes")
    finally:
        server.DB_PATH = previous
        try:
            os.remove(path)
        except OSError:
            pass


if __name__ == "__main__":
    main()
