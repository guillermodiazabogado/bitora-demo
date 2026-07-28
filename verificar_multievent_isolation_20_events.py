from __future__ import annotations

import os
import secrets
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
            run_id = secrets.token_hex(5)
            now = server.now_iso()
            event_ids: list[int] = []
            user_ids: list[int] = []
            organization_ids: list[int] = []
            integration_ids: list[int] = []
            job_ids: list[int] = []
            queue_ids: list[int] = []
            for org_index in range(4):
                org_id = int(db.execute(
                    """
                    INSERT INTO organizations (
                        public_id, name, legal_name, status, plan,
                        safe_mode_email, safe_mode_whatsapp,
                        force_email_recipient, force_whatsapp_recipient,
                        created_at, updated_at
                    )
                    VALUES (?, ?, ?, 'active', 'standard', 1, 1, ?, ?, ?, ?)
                    """,
                    (
                        server.make_public_id("org"),
                        f"Org aislamiento {run_id} {org_index}",
                        f"Org aislamiento {run_id} {org_index}",
                        f"safe-{run_id}-{org_index}@example.test",
                        "5491100000000",
                        now,
                        now,
                    ),
                ).lastrowid)
                organization_ids.append(org_id)
                encrypted = server.integration_secret_service().encrypt(
                    f'{{"provider":"demo","run_id":"{run_id}","org":{org_index}}}'
                )
                integration_id = int(db.execute(
                    """
                    INSERT INTO organization_integrations (
                        organization_id, provider, integration_type, name, mode, status,
                        configuration_encrypted, metadata_json, created_by, updated_by,
                        created_at, updated_at
                    )
                    VALUES (?, 'demo', 'email_provider', ?, 'platform_managed', 'connected', ?, '{}', 'QA', 'QA', ?, ?)
                    """,
                    (org_id, f"Demo email aislamiento {run_id} {org_index}", encrypted, now, now),
                ).lastrowid)
                integration_ids.append(integration_id)
            for index in range(50):
                user_id = db.execute(
                    "INSERT INTO users (name, role, pin_hash, active, created_at) VALUES (?, ?, ?, 1, ?)",
                    (f"Usuario QA {run_id} {index}", "Visualizador", server.hash_pin(str(7000 + index)), now),
                ).lastrowid
                user_ids.append(int(user_id))
            for event_index in range(20):
                organization_id = organization_ids[event_index % len(organization_ids)]
                integration_id = integration_ids[event_index % len(integration_ids)]
                event_id = server.insert_event_from_config(
                    db,
                    {
                        "name": f"Evento aislamiento {event_index}",
                        "venue": "Staging",
                        "capacity": 1000,
                        "status": "published",
                        "organization_id": organization_id,
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
                    (event_id, space_id, f"Actividad {event_index}", "2027-01-01 09:00", "2027-01-01 10:00", 80, now),
                ).lastrowid
                db.execute(
                    """
                    INSERT INTO event_integrations (event_id, channel, organization_integration_id, is_default, enabled, created_at, updated_at)
                    VALUES (?, 'email', ?, 1, 1, ?, ?)
                    """,
                    (event_id, integration_id, now, now),
                )
                for person_index in range(50):
                    global_index = event_index * 50 + person_index
                    person_id = db.execute(
                        "INSERT INTO people (first_name, last_name, email, phone, company, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                        (
                            f"Nombre{global_index}",
                            f"Apellido{global_index}",
                            f"qa{run_id}.{global_index}@example.test",
                            f"5491100{global_index:06d}",
                            f"Empresa {event_index}",
                            now,
                        ),
                    ).lastrowid
                    acc_id = db.execute(
                        """
                        INSERT INTO accreditations (event_id, person_id, type, token, status, created_at)
                        VALUES (?, ?, 'General', ?, 'active', ?)
                        """,
                        (event_id, person_id, f"EVT-ISO-{run_id.upper()}-{event_index:02d}-{person_index:03d}", now),
                    ).lastrowid
                    if person_index < 5:
                        db.execute(
                            """
                            INSERT INTO reservations (event_id, activity_id, accreditation_id, status, created_at)
                            VALUES (?, ?, ?, 'confirmed', ?)
                            """,
                            (event_id, activity_id, acc_id, now),
                        )
                    if person_index == 0:
                        queue_id = int(db.execute(
                            """
                            INSERT INTO communication_queue (
                                event_id, organization_id, integration_id, person_id, accreditation_id,
                                channel, audience, template_code, subject, content, recipient, status,
                                provider, created_by, created_at
                            )
                            VALUES (?, ?, ?, ?, ?, 'email', 'isolation', 'isolation', ?, 'Aislamiento', ?, 'pendiente', 'demo', 'QA', ?)
                            """,
                            (
                                event_id,
                                organization_id,
                                integration_id,
                                person_id,
                                acc_id,
                                f"Aislamiento {run_id} {event_index}",
                                f"qa{run_id}.{global_index}@example.test",
                                now,
                            ),
                        ).lastrowid)
                        queue_ids.append(queue_id)
                        job_id = int(db.execute(
                            """
                            INSERT INTO jobs (
                                event_id, organization_id, integration_id, kind, priority, status,
                                payload, retry_count, max_retries, created_by, created_at, updated_at
                            )
                            VALUES (?, ?, ?, 'email.send', 'low', 'pending', ?, 0, 3, 'QA', ?, ?)
                            """,
                            (
                                event_id,
                                organization_id,
                                integration_id,
                                f'{{"queue_id":{queue_id},"run_id":"{run_id}"}}',
                                now,
                                now,
                            ),
                        ).lastrowid)
                        job_ids.append(job_id)
                        server.audit(
                            db,
                            "QA",
                            "isolation.event_seeded",
                            "event",
                            event_id,
                            {"organization_id": organization_id, "integration_id": integration_id, "job_id": job_id, "queue_id": queue_id},
                        )
                storage.save_event(event_id, "uploads", "evidence.txt", f"evento {event_id}".encode("utf-8"))

            assert_true(len(event_ids) == 20, "deben existir 20 eventos sinteticos")
            people_count = db.execute("SELECT COUNT(*) AS c FROM people WHERE email LIKE ?", (f"qa{run_id}.%@example.test",)).fetchone()["c"]
            assert_true(int(people_count) == 1000, "deben existir 1000 participantes sinteticos")
            assert_true(len(set(organization_ids)) == 4, "deben existir multiples organizaciones")
            assert_true(len(queue_ids) == 20 and len(job_ids) == 20, "deben existir colas y jobs por evento")

            cross_reads = 0
            cross_modifications = 0
            for index, event_id in enumerate(event_ids):
                user_id = user_ids[index % len(user_ids)]
                session = {"id": user_id, "name": f"Usuario QA {run_id} {index}", "role": "Visualizador"}
                assert_true(server.session_can_access_event(db, session, event_id), "usuario asignado debe acceder a su evento")
                other_event_id = event_ids[(index + 1) % len(event_ids)]
                if server.session_can_access_event(db, session, other_event_id):
                    cross_reads += 1
                if server.user_has_permission(db, session, other_event_id, "communications.send"):
                    cross_modifications += 1

            assert_true(cross_reads == 0, f"lecturas cruzadas permitidas: {cross_reads}")
            assert_true(cross_modifications == 0, f"modificaciones cruzadas permitidas: {cross_modifications}")

            cross_integrations = 0
            cross_jobs = 0
            for event_index, event_id in enumerate(event_ids):
                organization_id = organization_ids[event_index % len(organization_ids)]
                integration_id = integration_ids[event_index % len(integration_ids)]
                wrong_integration = db.execute(
                    """
                    SELECT oi.id
                    FROM event_integrations ei
                    JOIN organization_integrations oi ON oi.id = ei.organization_integration_id
                    JOIN events e ON e.id = ei.event_id
                    WHERE ei.event_id = ? AND oi.organization_id <> e.organization_id
                    """,
                    (event_id,),
                ).fetchone()
                if wrong_integration:
                    cross_integrations += 1
                wrong_job = db.execute(
                    """
                    SELECT id FROM jobs
                    WHERE event_id = ? AND (organization_id <> ? OR integration_id <> ?)
                    """,
                    (event_id, organization_id, integration_id),
                ).fetchone()
                if wrong_job:
                    cross_jobs += 1
            assert_true(cross_integrations == 0, f"integraciones cruzadas: {cross_integrations}")
            assert_true(cross_jobs == 0, f"jobs cruzados: {cross_jobs}")

            token_value = f"EVT-ISO-{run_id.upper()}-00-000"
            token_row = db.execute("SELECT token, event_id FROM accreditations WHERE token = ?", (token_value,)).fetchone()
            assert_true(token_row and int(token_row["event_id"]) == event_ids[0], "QR debe pertenecer a su evento")
            wrong_event_hits = db.execute(
                "SELECT COUNT(*) AS c FROM accreditations WHERE token = ? AND event_id = ?",
                (token_value, event_ids[1]),
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
