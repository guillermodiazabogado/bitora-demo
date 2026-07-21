from __future__ import annotations

import os
import tempfile
from pathlib import Path

import server
from backend.storage import StorageService


def assert_true(condition, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    original_db_path = server.DB_PATH
    server.DB_PATH = Path(db_path)
    storage_tmp = tempfile.TemporaryDirectory(prefix="bitora-multievent-storage-")
    storage = StorageService(Path(storage_tmp.name))
    try:
        server.init_db()
        with server.connect() as db:
            event_ids: list[int] = []
            user_ids: list[int] = []
            for index in range(50):
                user_id = db.execute(
                    "INSERT INTO users (name, role, pin_hash, active, created_at) VALUES (?, ?, ?, 1, ?)",
                    (f"Usuario QA {index}", "Visualizador", server.hash_pin(str(7000 + index)), server.now_iso()),
                ).lastrowid
                user_ids.append(int(user_id))
            for event_index in range(20):
                event_id = server.insert_event_from_config(
                    db,
                    {
                        "name": f"Evento aislamiento {event_index}",
                        "venue": "Staging",
                        "capacity": 1000,
                        "status": "published",
                    },
                    "Admin",
                    status="published",
                )
                event_ids.append(event_id)
                server.assign_user_to_event(db, user_ids[event_index % len(user_ids)], event_id, "Productor")
                space_id = db.execute(
                    "INSERT INTO spaces (event_id, name, capacity, created_at) VALUES (?, ?, ?, ?)",
                    (event_id, f"Sala {event_index}", 80, server.now_iso()),
                ).lastrowid
                activity_id = db.execute(
                    """
                    INSERT INTO activities (event_id, space_id, title, starts_at, ends_at, capacity, reservation_mode, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, 'required', ?)
                    """,
                    (event_id, space_id, f"Actividad {event_index}", "2027-01-01 09:00", "2027-01-01 10:00", 80, server.now_iso()),
                ).lastrowid
                for person_index in range(50):
                    global_index = event_index * 50 + person_index
                    person_id = db.execute(
                        "INSERT INTO people (first_name, last_name, email, phone, company, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                        (
                            f"Nombre{global_index}",
                            f"Apellido{global_index}",
                            f"qa{global_index}@example.test",
                            f"5491100{global_index:06d}",
                            f"Empresa {event_index}",
                            server.now_iso(),
                        ),
                    ).lastrowid
                    acc_id = db.execute(
                        """
                        INSERT INTO accreditations (event_id, person_id, type, token, status, created_at)
                        VALUES (?, ?, 'General', ?, 'active', ?)
                        """,
                        (event_id, person_id, f"EVT-ISO-{event_index:02d}-{person_index:03d}", server.now_iso()),
                    ).lastrowid
                    if person_index < 5:
                        db.execute(
                            """
                            INSERT INTO reservations (event_id, activity_id, accreditation_id, status, created_at)
                            VALUES (?, ?, ?, 'confirmed', ?)
                            """,
                            (event_id, activity_id, acc_id, server.now_iso()),
                        )
                storage.save_event(event_id, "uploads", "evidence.txt", f"evento {event_id}".encode("utf-8"))

            assert_true(len(event_ids) == 20, "deben existir 20 eventos sinteticos")
            people_count = db.execute("SELECT COUNT(*) AS c FROM people WHERE email LIKE 'qa%@example.test'").fetchone()["c"]
            assert_true(int(people_count) == 1000, "deben existir 1000 participantes sinteticos")

            cross_reads = 0
            cross_modifications = 0
            for index, event_id in enumerate(event_ids):
                user_id = user_ids[index % len(user_ids)]
                session = {"id": user_id, "name": f"Usuario QA {index}", "role": "Visualizador"}
                assert_true(server.session_can_access_event(db, session, event_id), "usuario asignado debe acceder a su evento")
                other_event_id = event_ids[(index + 1) % len(event_ids)]
                if server.session_can_access_event(db, session, other_event_id):
                    cross_reads += 1
                if server.user_has_permission(db, session, other_event_id, "communications.send"):
                    cross_modifications += 1

            assert_true(cross_reads == 0, f"lecturas cruzadas permitidas: {cross_reads}")
            assert_true(cross_modifications == 0, f"modificaciones cruzadas permitidas: {cross_modifications}")

            token_row = db.execute("SELECT token, event_id FROM accreditations WHERE token = 'EVT-ISO-00-000'").fetchone()
            assert_true(token_row and int(token_row["event_id"]) == event_ids[0], "QR debe pertenecer a su evento")
            wrong_event_hits = db.execute(
                "SELECT COUNT(*) AS c FROM accreditations WHERE token = ? AND event_id = ?",
                ("EVT-ISO-00-000", event_ids[1]),
            ).fetchone()["c"]
            assert_true(int(wrong_event_hits) == 0, "QR no debe aparecer en otro evento")

            files_event_0 = storage.event_inventory(event_ids[0])
            files_event_1 = storage.event_inventory(event_ids[1])
            assert_true(len(files_event_0) == 1 and len(files_event_1) == 1, "storage por evento debe existir")
            assert_true(files_event_0[0]["key"] != files_event_1[0]["key"], "storage no debe cruzar archivos entre eventos")
            try:
                storage.save_event(event_ids[0], "uploads", "../escape.txt", b"x")
                raise AssertionError("storage permitio traversal")
            except ValueError:
                pass

        print("OK: aislamiento multievento 20 eventos / 1000 participantes")
    finally:
        server.DB_PATH = original_db_path
        storage_tmp.cleanup()
        try:
            os.remove(db_path)
        except OSError:
            pass


if __name__ == "__main__":
    main()
