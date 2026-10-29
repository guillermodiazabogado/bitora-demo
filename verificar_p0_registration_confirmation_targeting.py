import os
import tempfile

import server


def main() -> None:
    fd, path = tempfile.mkstemp(prefix="bitora-registration-target-", suffix=".db")
    os.close(fd)
    previous = server.DB_PATH
    try:
        server.DB_PATH = path
        server.init_db()
        server.seed_if_empty()
        with server.connect() as db:
            event_id = int(db.execute("SELECT id FROM events ORDER BY id LIMIT 1").fetchone()["id"])
            registrations = []
            for index in range(40):
                result = server.register_accreditation(
                    db,
                    event_id,
                    {
                        "first_name": "Audience",
                        "last_name": f"Person {index:03d}",
                        "email": f"audience-{index:03d}@bitora.test",
                        "type": "General",
                        "actor": "regression",
                    },
                )
                assert result["ok"], result
                registrations.append(result)

            target = registrations[23]
            rows = server.communication_audience_rows(
                db,
                event_id,
                "all",
                {"accreditation_id": target["id"]},
            )
            assert len(rows) == 1, len(rows)
            assert int(rows[0]["accreditation_id"]) == int(target["id"]), dict(rows[0])
            assert rows[0]["email"] == "audience-023@bitora.test", dict(rows[0])
        print("PASS: registration confirmation selects only its accreditation")
    finally:
        server.DB_PATH = previous
        try:
            os.remove(path)
        except OSError:
            pass


if __name__ == "__main__":
    main()
