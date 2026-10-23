from __future__ import annotations

import os
import tempfile
import threading
from pathlib import Path

tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
os.environ["QR_SQLITE_PATH"] = str(Path(tmp.name) / "v4_2_attendance.sqlite3")
os.environ["BITORA_ATTENDANCE_V4_ENABLED"] = "true"
os.environ["BITORA_ATTENDANCE_CLOSURE_ELIGIBILITY_V4_ENABLED"] = "true"
os.environ["QR_REQUIRE_LOGIN"] = ""

import server  # noqa: E402


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def seed(db):
    now = server.now_iso()
    orgs = []
    events = []
    activities = {}
    people = {}
    accreditations = {}
    for org_name in ("Alfa V4.2", "Beta V4.2"):
        org = db.execute(
            """
            INSERT INTO organizations (public_id, name, legal_name, trade_name, status, plan, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'active', 'standard', ?, ?)
            """,
            (org_name.lower().replace(" ", "_"), org_name, org_name, org_name, now, now),
        )
        orgs.append(int(org.lastrowid))
    for org_index, org_id in enumerate(orgs):
        for event_index in range(2):
            event = db.execute(
                "INSERT INTO events (organization_id, name, starts_at, ends_at, created_at) VALUES (?, ?, ?, ?, ?)",
                (org_id, f"Evento V4.2 {org_index}-{event_index}", "2026-09-01T09:00:00", "2026-09-01T18:00:00", now),
            )
            event_id = int(event.lastrowid)
            events.append(event_id)
            space = db.execute("INSERT INTO spaces (event_id, name, capacity, status, created_at) VALUES (?, ?, 100, 'active', ?)", (event_id, f"Sala {event_id}", now))
            activities[event_id] = []
            for activity_index in range(2):
                activity = db.execute(
                    """
                    INSERT INTO activities (
                        event_id, space_id, title, starts_at, ends_at, capacity,
                        reservation_mode, requiere_asistencia, porcentaje_minimo_asistencia,
                        habilita_certificado, status, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, 100, 'optional', 1, 80, 0, 'published', ?)
                    """,
                    (event_id, int(space.lastrowid), f"Actividad {activity_index}", "2026-09-01T10:00:00", "2026-09-01T11:00:00", now),
                )
                activities[event_id].append(int(activity.lastrowid))
            people[event_id] = []
            accreditations[event_id] = []
            for person_index in range(2):
                person = db.execute(
                    """
                    INSERT INTO people (first_name, last_name, email, source, device_type, created_at)
                    VALUES (?, ?, ?, 'test', 'desktop', ?)
                    """,
                    (f"Persona{org_index}{event_index}{person_index}", "V42", f"v42-{org_index}-{event_index}-{person_index}@example.test", now),
                )
                person_id = int(person.lastrowid)
                people[event_id].append(person_id)
                accreditation = db.execute(
                    "INSERT INTO accreditations (event_id, person_id, token, type, status, created_at) VALUES (?, ?, ?, 'General', 'active', ?)",
                    (event_id, person_id, f"V42TOKEN{org_index}{event_index}{person_index}", now),
                )
                accreditations[event_id].append(int(accreditation.lastrowid))
    return {"orgs": orgs, "events": events, "activities": activities, "people": people, "accreditations": accreditations}


def main():
    server.init_db()
    with server.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        data = seed(db)
        db.execute("COMMIT")

    service = server.attendance_service()
    org_id = data["orgs"][0]
    event_id = data["events"][0]
    other_org_id = data["orgs"][1]
    other_event_id = data["events"][2]
    activity_1, activity_2 = data["activities"][event_id]
    participant_1, participant_2 = data["people"][event_id]
    accreditation_1, accreditation_2 = data["accreditations"][event_id]

    with server.connect() as db:
        assert_true(server.attendance_v4_enabled(db, event_id), "V4.1 flag no habilitado")
        assert_true(server.attendance_closure_v4_enabled(db, event_id), "V4.2 flag no habilitado")

    with server.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        attendance = service.record_attendance(
            db,
            organization_id=org_id,
            event_id=event_id,
            participant_id=participant_1,
            accreditation_id=accreditation_1,
            activity_id=activity_1,
            attendance_type="ACTIVITY",
            status="PRESENT",
            source="MANUAL",
            actor="Admin",
            occurred_at="2026-09-01T10:05:00+00:00",
            idempotency_key="v42-attendance-001",
        )
        assert_true(attendance["ok"], "no se pudo crear asistencia base")
        rule_set = service.create_rule_set(db, organization_id=org_id, event_id=event_id, actor="Admin", name="Regla evento V4.2", scope_type="EVENT")
        version = service.create_rule_set_version(
            db,
            organization_id=org_id,
            event_id=event_id,
            rule_set_id=rule_set["item"]["id"],
            actor="Admin",
            configuration={
                "minimum_attendance_percentage": "50",
                "mandatory_activity_ids": [activity_1],
                "require_all_mandatory_activities": True,
                "allow_manual_override": True,
            },
        )
        published = service.publish_rule_set_version(
            db,
            organization_id=org_id,
            event_id=event_id,
            rule_set_id=rule_set["item"]["id"],
            version_id=version["item"]["id"],
            actor="Admin",
            idempotency_key="v42-publish-001",
        )
        assert_true(published["item"]["status"] == "PUBLISHED", "version no publicada")
        try:
            service.create_rule_set_version(db, organization_id=org_id, event_id=event_id, rule_set_id=rule_set["item"]["id"], actor="Admin", configuration={"unknown_rule": True})
            raise AssertionError("configuracion desconocida aceptada")
        except server.AttendanceDomainError as exc:
            assert_true(exc.code == "ATTENDANCE_RULE_CONFIGURATION_INVALID", "error de regla invalido")
        closure = service.close_attendance(
            db,
            organization_id=org_id,
            event_id=event_id,
            actor="Admin",
            rule_set_version_id=version["item"]["id"],
            scope_type="EVENT",
            cutoff_at="2026-09-01T23:59:00+00:00",
            idempotency_key="v42-close-001",
        )
        assert_true(closure["item"]["status"] == "CLOSED", "cierre no finalizo")
        first_snapshot_hash = closure["item"]["snapshot_hash"]
        replay = service.close_attendance(
            db,
            organization_id=org_id,
            event_id=event_id,
            actor="Admin",
            rule_set_version_id=version["item"]["id"],
            scope_type="EVENT",
            cutoff_at="2026-09-01T23:59:00+00:00",
            idempotency_key="v42-close-001",
        )
        assert_true(replay["idempotent"], "cierre repetido no fue idempotente")
        try:
            service.close_attendance(db, organization_id=org_id, event_id=event_id, actor="Admin", rule_set_version_id=version["item"]["id"], scope_type="EVENT", cutoff_at="2026-09-02T00:00:00+00:00", idempotency_key="v42-close-001")
            raise AssertionError("idempotencia de cierre con payload distinto no fallo")
        except server.AttendanceDomainError as exc:
            assert_true(exc.code == "ATTENDANCE_CLOSURE_IDEMPOTENCY_CONFLICT", "conflicto de cierre incorrecto")
        evaluations = service.list_closure_evaluations(db, organization_id=org_id, event_id=event_id, closure_id=closure["item"]["id"])["items"]
        assert_true(len(evaluations) == 2, "evaluaciones incompletas")
        eligible = [row for row in evaluations if row["participant_id"] == participant_1][0]
        not_eligible = [row for row in evaluations if row["participant_id"] == participant_2][0]
        assert_true(eligible["result_status"] == "ELIGIBLE", "participante asistido no elegible")
        assert_true(not_eligible["result_status"] == "NOT_ELIGIBLE", "participante ausente elegible")
        decision = service.override_eligibility(
            db,
            organization_id=org_id,
            event_id=event_id,
            participant_id=participant_2,
            actor="Admin",
            manual_result="MANUALLY_APPROVED",
            reason="Excepcion controlada",
            closure_id=closure["item"]["id"],
            idempotency_key="v42-override-001",
        )
        assert_true(decision["item"]["effective_result"] == "MANUALLY_APPROVED", "override no actualizo decision efectiva")
        reopened = service.reopen_closure(db, organization_id=org_id, event_id=event_id, closure_id=closure["item"]["id"], actor="Admin", reason="Correccion posterior", idempotency_key="v42-reopen-001")
        assert_true(reopened["item"]["status"] == "REOPENED", "reapertura fallo")
        service.record_attendance(
            db,
            organization_id=org_id,
            event_id=event_id,
            participant_id=participant_1,
            accreditation_id=accreditation_1,
            activity_id=activity_2,
            attendance_type="ACTIVITY",
            status="PRESENT",
            source="MANUAL",
            actor="Admin",
            occurred_at="2026-09-01T11:05:00+00:00",
            idempotency_key="v42-attendance-002",
        )
        recierre = service.close_attendance(db, organization_id=org_id, event_id=event_id, actor="Admin", rule_set_version_id=version["item"]["id"], scope_type="EVENT", cutoff_at="2026-09-01T23:59:00+00:00", idempotency_key="v42-close-002")
        assert_true(recierre["item"]["status"] == "CLOSED", "recierre no finalizo")
        original = service.get_closure(db, organization_id=org_id, event_id=event_id, closure_id=closure["item"]["id"])
        assert_true(original["status"] == "SUPERSEDED", "cierre anterior no quedo superseded")
        assert_true(original["snapshot_hash"] == first_snapshot_hash, "snapshot historico muto")
        try:
            service.close_attendance(db, organization_id=other_org_id, event_id=event_id, actor="Admin", rule_set_version_id=version["item"]["id"], scope_type="EVENT", idempotency_key="v42-cross-001")
            raise AssertionError("cierre cross tenant aceptado")
        except server.AttendanceDomainError as exc:
            assert_true(exc.code == "ATTENDANCE_SCOPE_MISMATCH", "error cross tenant incorrecto")
        try:
            service.create_rule_set(db, organization_id=org_id, event_id=event_id, actor="Admin", name="Regla actividad cruzada", scope_type="ACTIVITY", activity_id=data["activities"][other_event_id][0])
            raise AssertionError("actividad ajena aceptada")
        except server.AttendanceDomainError as exc:
            assert_true(exc.code == "ATTENDANCE_SCOPE_MISMATCH", "error cross activity incorrecto")
        payload = server.EventBackupService(server.BACKUP_DIR, server.connect, server.DB_LOCK, server.APP_VERSION, server.STORAGE)._event_payload(event_id, "test")
        for table in ("attendance_rule_sets", "attendance_rule_set_versions", "attendance_closures", "attendance_evaluations", "attendance_eligibility_decisions", "attendance_overrides", "attendance_reopenings"):
            assert_true(table in payload["tables"], f"backup no incluye {table}")
        audit_count = db.execute("SELECT COUNT(*) AS c FROM audit_logs WHERE event_id = ? AND action LIKE 'attendance.%'", (event_id,)).fetchone()["c"]
        assert_true(int(audit_count) >= 8, "auditoria V4.2 insuficiente")
        db.execute("COMMIT")

    def close_same_key(results):
        with server.DB_LOCK, server.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                event = data["events"][1]
                org = org_id
                activity = data["activities"][event][0]
                person = data["people"][event][0]
                acc = data["accreditations"][event][0]
                service.record_attendance(db, organization_id=org, event_id=event, participant_id=person, accreditation_id=acc, activity_id=activity, attendance_type="ACTIVITY", status="PRESENT", source="MANUAL", actor="Admin", occurred_at="2026-09-01T10:05:00+00:00", idempotency_key=f"v42-concurrent-att-{len(results)}")
                rs = service.create_rule_set(db, organization_id=org, event_id=event, actor="Admin", name=f"Concurrente {len(results)}", scope_type="ACTIVITY", activity_id=activity)
                rv = service.create_rule_set_version(db, organization_id=org, event_id=event, rule_set_id=rs["item"]["id"], actor="Admin", configuration={"minimum_attendance_percentage": "100"})
                service.publish_rule_set_version(db, organization_id=org, event_id=event, rule_set_id=rs["item"]["id"], version_id=rv["item"]["id"], actor="Admin", idempotency_key=f"v42-concurrent-pub-{len(results)}")
                item = service.close_attendance(db, organization_id=org, event_id=event, actor="Admin", rule_set_version_id=rv["item"]["id"], scope_type="ACTIVITY", activity_id=activity, cutoff_at="2026-09-01T23:59:00+00:00", idempotency_key="v42-concurrent-close")
                db.execute("COMMIT")
                results.append(item)
            except Exception as exc:
                db.execute("ROLLBACK")
                results.append(exc)

    results = []
    threads = [threading.Thread(target=close_same_key, args=(results,)) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    with server.connect() as db:
        duplicate_count = db.execute("SELECT COUNT(*) AS c FROM attendance_closures WHERE idempotency_key = 'v42-concurrent-close'").fetchone()["c"]
        assert_true(int(duplicate_count) == 1, "concurrencia genero cierres duplicados")
        assert_true(server.attendance_v4_enabled(db, event_id), "regresion feature flag V4.1")

    print("V4.2 attendance closure and eligibility foundation: OK")


if __name__ == "__main__":
    try:
        main()
    finally:
        tmp.cleanup()
