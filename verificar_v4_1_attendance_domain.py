from __future__ import annotations

import os
import tempfile
import threading
from pathlib import Path

tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
os.environ["QR_SQLITE_PATH"] = str(Path(tmp.name) / "v4_1_attendance.sqlite3")
os.environ["BITORA_ATTENDANCE_V4_ENABLED"] = "true"
os.environ["QR_REQUIRE_LOGIN"] = ""

import server  # noqa: E402


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def seed(db):
    now = server.now_iso()
    orgs = []
    for name in ("Alfa V4.1", "Beta V4.1"):
        cur = db.execute(
            """
            INSERT INTO organizations (public_id, name, legal_name, trade_name, status, plan, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'active', 'standard', ?, ?)
            """,
            (name.lower().replace(" ", "_"), name, name, name, now, now),
        )
        orgs.append(int(cur.lastrowid))
    events = []
    for org_id, suffix in [(orgs[0], "A1"), (orgs[0], "A2"), (orgs[1], "B1"), (orgs[1], "B2")]:
        cur = db.execute(
            """
            INSERT INTO events (organization_id, name, starts_at, ends_at, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (org_id, f"Evento {suffix}", "2026-08-01T09:00:00", "2026-08-01T18:00:00", now),
        )
        event_id = int(cur.lastrowid)
        events.append(event_id)
        space = db.execute(
            "INSERT INTO spaces (event_id, name, capacity, status, created_at) VALUES (?, ?, 100, 'active', ?)",
            (event_id, f"Sala {suffix}", now),
        )
        for index in range(2):
            db.execute(
                """
                INSERT INTO activities (
                    event_id, space_id, title, starts_at, ends_at, capacity,
                    reservation_mode, requiere_asistencia, porcentaje_minimo_asistencia,
                    habilita_certificado, status, created_at
                )
                VALUES (?, ?, ?, ?, ?, 100, 'optional', 1, 80, 0, 'published', ?)
                """,
                (event_id, int(space.lastrowid), f"Actividad {suffix}-{index}", "2026-08-01T10:00:00", "2026-08-01T11:00:00", now),
            )
    people = []
    accreditations = []
    for idx, event_id in enumerate(events):
        person = db.execute(
            """
            INSERT INTO people (first_name, last_name, email, source, device_type, created_at)
            VALUES (?, ?, ?, 'test', 'desktop', ?)
            """,
            (f"Persona{idx}", "V41", f"persona{idx}@example.test", now),
        )
        people.append(int(person.lastrowid))
        acc = db.execute(
            """
            INSERT INTO accreditations (event_id, person_id, token, type, status, created_at)
            VALUES (?, ?, ?, 'General', 'active', ?)
            """,
            (event_id, int(person.lastrowid), f"V41TOKEN{idx}", now),
        )
        accreditations.append(int(acc.lastrowid))
    return {"orgs": orgs, "events": events, "people": people, "accreditations": accreditations}


def main():
    server.init_db()
    with server.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        data = seed(db)
        db.execute("COMMIT")

    service = server.attendance_service()
    with server.connect() as db:
        org_id = data["orgs"][0]
        event_id = data["events"][0]
        other_event = data["events"][2]
        person_id = data["people"][0]
        accreditation_id = data["accreditations"][0]
        activity_id = db.execute("SELECT id FROM activities WHERE event_id = ? ORDER BY id LIMIT 1", (event_id,)).fetchone()["id"]
        db.execute("BEGIN IMMEDIATE")
        result = service.record_attendance(
            db,
            organization_id=org_id,
            event_id=event_id,
            participant_id=person_id,
            accreditation_id=accreditation_id,
            activity_id=activity_id,
            attendance_type="ACTIVITY",
            status="PRESENT",
            source="MANUAL",
            actor="Admin",
            idempotency_key="v41-key-001",
            correlation_id="v41-correlation",
            metadata={"note": "registro controlado", "token": "no debe guardarse"},
        )
        assert_true(result["ok"] and not result["idempotent"], "registro inicial fallido")
        attendance_id = result["item"]["id"]
        replay = service.record_attendance(
            db,
            organization_id=org_id,
            event_id=event_id,
            participant_id=person_id,
            accreditation_id=accreditation_id,
            activity_id=activity_id,
            attendance_type="ACTIVITY",
            status="PRESENT",
            source="MANUAL",
            actor="Admin",
            idempotency_key="v41-key-001",
            correlation_id="v41-correlation",
            metadata={"note": "registro controlado", "token": "no debe guardarse"},
        )
        assert_true(replay["idempotent"], "reintento no fue idempotente")
        count = db.execute("SELECT COUNT(*) AS c FROM attendance_records WHERE idempotency_key = 'v41-key-001'").fetchone()["c"]
        assert_true(int(count) == 1, "idempotencia genero duplicados")
        try:
            service.record_attendance(
                db,
                organization_id=org_id,
                event_id=event_id,
                participant_id=person_id,
                accreditation_id=accreditation_id,
                activity_id=activity_id,
                attendance_type="ACTIVITY",
                status="ABSENT",
                source="MANUAL",
                actor="Admin",
                idempotency_key="v41-key-001",
                metadata={},
            )
            raise AssertionError("payload distinto con misma key no fallo")
        except server.AttendanceDomainError as exc:
            assert_true(exc.code == "ATTENDANCE_IDEMPOTENCY_CONFLICT", "conflicto de idempotencia incorrecto")
        other_activity = db.execute("SELECT id FROM activities WHERE event_id = ? ORDER BY id LIMIT 1", (other_event,)).fetchone()["id"]
        try:
            service.record_attendance(
                db,
                organization_id=org_id,
                event_id=event_id,
                participant_id=person_id,
                accreditation_id=accreditation_id,
                activity_id=other_activity,
                attendance_type="ACTIVITY",
                status="PRESENT",
                source="MANUAL",
                actor="Admin",
                idempotency_key="v41-key-002",
            )
            raise AssertionError("actividad de otro evento aceptada")
        except server.AttendanceDomainError as exc:
            assert_true(exc.code == "ATTENDANCE_ACTIVITY_EVENT_MISMATCH", "error cross-event incorrecto")
        corrected = service.correct_attendance(
            db,
            attendance_id=attendance_id,
            organization_id=org_id,
            event_id=event_id,
            actor="Admin",
            status="PARTIAL",
            reason="Correccion controlada",
        )
        assert_true(corrected["item"]["status"] == "PARTIAL", "correccion no actualizo estado")
        corrections = db.execute("SELECT COUNT(*) AS c FROM attendance_corrections WHERE attendance_id = ?", (attendance_id,)).fetchone()["c"]
        assert_true(int(corrections) == 1, "correccion no preservo historial")
        invalidated = service.invalidate_attendance(
            db,
            attendance_id=attendance_id,
            organization_id=org_id,
            event_id=event_id,
            actor="Admin",
            reason="Invalidacion controlada",
        )
        assert_true(invalidated["item"]["status"] == "INVALIDATED", "invalidacion no marco estado")
        audit_count = db.execute("SELECT COUNT(*) AS c FROM audit_logs WHERE event_id = ? AND action LIKE 'attendance.%'", (event_id,)).fetchone()["c"]
        assert_true(int(audit_count) >= 3, "auditoria insuficiente")
        db.execute("COMMIT")

    def write_same_key(results):
        with server.DB_LOCK, server.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                item = service.record_attendance(
                    db,
                    organization_id=data["orgs"][0],
                    event_id=data["events"][1],
                    participant_id=data["people"][1],
                    accreditation_id=data["accreditations"][1],
                    attendance_type="EVENT",
                    status="PRESENT",
                    source="MANUAL",
                    actor="Admin",
                    idempotency_key="v41-concurrent",
                )
                db.execute("COMMIT")
                results.append(item)
            except Exception as exc:
                db.execute("ROLLBACK")
                results.append(exc)

    results = []
    threads = [threading.Thread(target=write_same_key, args=(results,)) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert_true(len(results) == 2, "concurrencia incompleta")
    with server.connect() as db:
        duplicate_count = db.execute("SELECT COUNT(*) AS c FROM attendance_records WHERE idempotency_key = 'v41-concurrent'").fetchone()["c"]
        assert_true(int(duplicate_count) == 1, "concurrencia genero duplicado")
        assert_true(server.attendance_v4_enabled(db, data["events"][0]), "feature flag env no habilito modulo")
        payload = server.EventBackupService(server.BACKUP_DIR, server.connect, server.DB_LOCK, server.APP_VERSION, server.STORAGE)._event_payload(data["events"][0], "test")
        assert_true("attendance_records" in payload["tables"], "backup de evento no incluye attendance_records")

    print("V4.1 attendance domain foundation: OK")


if __name__ == "__main__":
    try:
        main()
    finally:
        tmp.cleanup()
