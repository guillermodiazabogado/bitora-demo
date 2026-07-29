from __future__ import annotations

import os
import tempfile
import threading
from pathlib import Path

tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
root = Path(tmp.name)
os.environ["QR_SQLITE_PATH"] = str(root / "v4_4_surveys.sqlite3")
os.environ["BITORA_SURVEYS_V4_ENABLED"] = "true"
os.environ["BITORA_STORAGE_PATH"] = str(root / "storage")
os.environ["QR_REQUIRE_LOGIN"] = ""

import server  # noqa: E402


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def seed(db):
    now = server.now_iso()
    orgs = []
    events = []
    people = {}
    for org_name in ("Alfa Surveys", "Beta Surveys"):
        cur = db.execute(
            """
            INSERT INTO organizations (public_id, name, legal_name, trade_name, status, plan, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'active', 'standard', ?, ?)
            """,
            (org_name.lower().replace(" ", "_"), org_name, org_name, org_name, now, now),
        )
        orgs.append(int(cur.lastrowid))
    for org_index, org_id in enumerate(orgs):
        for event_index in range(10):
            event = db.execute(
                "INSERT INTO events (organization_id, name, starts_at, ends_at, created_at) VALUES (?, ?, ?, ?, ?)",
                (org_id, f"Evento Encuestas {org_index}-{event_index}", "2026-10-01T09:00:00+00:00", "2026-10-01T18:00:00+00:00", now),
            )
            event_id = int(event.lastrowid)
            events.append(event_id)
            space = db.execute("INSERT INTO spaces (event_id, name, capacity, status, created_at) VALUES (?, ?, 100, 'active', ?)", (event_id, f"Sala {event_id}", now))
            db.execute(
                """
                INSERT INTO activities (
                    event_id, space_id, title, starts_at, ends_at, capacity,
                    reservation_mode, requiere_asistencia, status, created_at
                ) VALUES (?, ?, ?, ?, ?, 100, 'optional', 1, 'published', ?)
                """,
                (event_id, int(space.lastrowid), "Actividad principal", "2026-10-01T10:00:00+00:00", "2026-10-01T11:00:00+00:00", now),
            )
            people[event_id] = []
            for person_index in range(50):
                person = db.execute(
                    "INSERT INTO people (first_name, last_name, email, source, device_type, created_at) VALUES (?, ?, ?, 'test', 'desktop', ?)",
                    (f"Persona{org_index}{event_index}{person_index}", "Survey", f"survey-{org_index}-{event_index}-{person_index}@example.test", now),
                )
                person_id = int(person.lastrowid)
                people[event_id].append(person_id)
                db.execute(
                    "INSERT INTO accreditations (event_id, person_id, token, type, status, created_at) VALUES (?, ?, ?, 'General', 'active', ?)",
                    (event_id, person_id, f"SVY{org_index}{event_index}{person_index}", now),
                )
    return {"orgs": orgs, "events": events, "people": people}


QUESTIONS = [
    {"key": "SAT", "prompt": "Satisfaccion general", "type": "SCALE", "required": True, "config": {"min": 1, "max": 5}},
    {"key": "NPS", "prompt": "Recomendarias el evento", "type": "YES_NO", "required": True},
    {"key": "ROOM", "prompt": "Sala preferida", "type": "SINGLE_CHOICE", "required": True, "options": [{"key": "A", "label": "Sala A"}, {"key": "B", "label": "Sala B"}]},
    {"key": "TOPICS", "prompt": "Temas de interes", "type": "MULTIPLE_CHOICE", "required": False, "options": [{"key": "AI", "label": "IA"}, {"key": "OPS", "label": "Operacion"}]},
    {"key": "COMMENT", "prompt": "Comentario", "type": "LONG_TEXT", "required": False},
    {"key": "BADGE", "prompt": "Nombre visible", "type": "SHORT_TEXT", "required": False},
]


def build_survey(db, service, org_id, event_id, mode="IDENTIFIED", name="Encuesta principal"):
    survey_type = service.create_type(db, organization_id=org_id, event_id=event_id, actor="Admin", code=f"{mode}_TYPE", name=f"Tipo {mode}")["item"]
    survey = service.create_survey(
        db,
        organization_id=org_id,
        event_id=event_id,
        actor="Admin",
        survey_type_id=survey_type["id"],
        name=name,
        response_mode=mode,
        access_policy="TOKEN" if mode == "ANONYMOUS" else "EVENT_PARTICIPANTS",
        duplicate_policy="ONE_PER_TOKEN" if mode == "ANONYMOUS" else "ONE_PER_PARTICIPANT",
    )["item"]
    version = service.create_version(db, organization_id=org_id, event_id=event_id, survey_id=survey["id"], actor="Admin", title=f"Version {mode}", instructions="BITORA STAGING", questions=QUESTIONS)["item"]
    published = service.publish_version(db, organization_id=org_id, event_id=event_id, survey_id=survey["id"], version_id=version["id"], actor="Admin", idempotency_key=f"publish-{mode}")["item"]
    assignment = service.assign_survey(db, organization_id=org_id, event_id=event_id, survey_id=survey["id"], actor="Admin", version_id=published["id"])["item"]
    return survey, published, assignment


def answers_for(version):
    by_key = {question["key"]: question for question in version["questions"]}
    return [
        {"question_id": by_key["SAT"]["id"], "value": 5},
        {"question_id": by_key["NPS"]["id"], "value": True},
        {"question_id": by_key["ROOM"]["id"], "value": "A"},
        {"question_id": by_key["TOPICS"]["id"], "value": ["AI", "OPS"]},
        {"question_id": by_key["COMMENT"]["id"], "value": "=cmd|bad"},
        {"question_id": by_key["BADGE"]["id"], "value": "Asistente"},
    ]


def main():
    server.init_db()
    service = server.survey_service()
    with server.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        data = seed(db)
        db.execute("COMMIT")

    org_id = data["orgs"][0]
    other_org_id = data["orgs"][1]
    event_id = data["events"][0]
    other_event_id = data["events"][10]
    participant_id = data["people"][event_id][0]
    other_participant_id = data["people"][other_event_id][0]

    with server.connect() as db:
        assert_true(server.surveys_v4_enabled(db, event_id), "feature flag de encuestas no habilitado")

    with server.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        identified_survey, identified_version, identified_assignment = build_survey(db, service, org_id, event_id, "IDENTIFIED", "Encuesta identificada")
        anonymous_survey, anonymous_version, anonymous_assignment = build_survey(db, service, org_id, event_id, "ANONYMOUS", "Encuesta anonima")
        try:
            service.create_version(db, organization_id=org_id, event_id=event_id, survey_id=identified_survey["id"], actor="Admin", title="Maliciosa", questions=[{"key": "X", "prompt": "<script>alert(1)</script>", "type": "SHORT_TEXT"}])
            raise AssertionError("pregunta insegura aceptada")
        except server.SurveyDomainError as exc:
            assert_true(exc.code == "SURVEY_TEXT_UNSAFE", "error de sanitizacion incorrecto")

        session = service.start_response(db, organization_id=org_id, event_id=event_id, assignment_id=identified_assignment["id"], participant_id=participant_id, idempotency_key="identified-start")["item"]
        submitted = service.submit_response(db, organization_id=org_id, event_id=event_id, session_id=session["id"], answers=answers_for(identified_version))["item"]
        assert_true(submitted["status"] == "SUBMITTED", "respuesta identificada no enviada")
        try:
            service.start_response(db, organization_id=org_id, event_id=event_id, assignment_id=identified_assignment["id"], participant_id=participant_id, idempotency_key="identified-dupe")
            raise AssertionError("respuesta duplicada identificada aceptada")
        except server.SurveyDomainError as exc:
            assert_true(exc.code == "SURVEY_DUPLICATE_RESPONSE", "duplicado identificado no rechazado")
        try:
            service.start_response(db, organization_id=org_id, event_id=event_id, assignment_id=identified_assignment["id"], participant_id=other_participant_id, idempotency_key="other-participant")
            raise AssertionError("participante de otro evento aceptado")
        except server.SurveyDomainError as exc:
            assert_true(exc.code == "SURVEY_PARTICIPANT_NOT_ALLOWED", "participante ajeno no rechazado")

        token = service.create_access_token(db, organization_id=org_id, event_id=event_id, assignment_id=anonymous_assignment["id"], participant_id=participant_id)["token"]
        public = service.public_access(db, token=token)
        assert_true(public["valid"] and "questions" in public["survey"], "acceso publico anonimo invalido")
        anon_session = service.start_response(db, organization_id=org_id, event_id=event_id, assignment_id=anonymous_assignment["id"], token=token, idempotency_key="anon-start")["item"]
        assert_true("participant_id" not in anon_session, "sesion anonima expone participante")
        service.submit_response(db, organization_id=org_id, event_id=event_id, session_id=anon_session["id"], token=token, answers=answers_for(anonymous_version))
        stored_anon = db.execute("SELECT participant_id, anonymous_subject_hash FROM survey_response_sessions WHERE id = ?", (anon_session["id"],)).fetchone()
        assert_true(stored_anon["participant_id"] is None, "respuesta anonima almacena participante directo")
        assert_true(len(stored_anon["anonymous_subject_hash"]) == 64, "hash anonimo invalido")
        try:
            service.start_response(db, organization_id=org_id, event_id=event_id, assignment_id=anonymous_assignment["id"], token=token, idempotency_key="anon-reuse")
            raise AssertionError("token anonimo reutilizado")
        except server.SurveyDomainError as exc:
            assert_true(exc.code == "SURVEY_TOKEN_INVALID", "token usado no fue rechazado")
        try:
            service.submit_response(db, organization_id=org_id, event_id=event_id, session_id=session["id"], answers=[{"question_id": identified_version["questions"][0]["id"], "value": 99}])
            raise AssertionError("edicion de sesion enviada aceptada")
        except server.SurveyDomainError as exc:
            assert_true(exc.code == "SURVEY_SESSION_CLOSED", "sesion cerrada no fue protegida")
        try:
            service.results(db, organization_id=other_org_id, event_id=event_id, survey_id=identified_survey["id"])
            raise AssertionError("resultados cross-org aceptados")
        except server.SurveyDomainError:
            pass
        try:
            service.start_response(db, organization_id=org_id, event_id=other_event_id, assignment_id=identified_assignment["id"], participant_id=participant_id, idempotency_key="cross-event")
            raise AssertionError("respuesta cross-event aceptada")
        except server.SurveyDomainError:
            pass
        results = service.results(db, organization_id=org_id, event_id=event_id, survey_id=identified_survey["id"])
        assert_true(results["total_responses"] == 1, "conteo de resultados incorrecto")
        csv_body = service.export_csv(db, organization_id=org_id, event_id=event_id, survey_id=identified_survey["id"])
        assert_true("'=cmd|bad" in csv_body, "CSV injection no fue neutralizada")
        version_two = service.create_version(
            db,
            organization_id=org_id,
            event_id=event_id,
            survey_id=identified_survey["id"],
            actor="Admin",
            title="Version identificada 2",
            questions=[{"key": "FOLLOWUP", "prompt": "Seguimiento posterior", "type": "SHORT_TEXT", "required": True}],
        )["item"]
        published_two = service.publish_version(
            db,
            organization_id=org_id,
            event_id=event_id,
            survey_id=identified_survey["id"],
            version_id=version_two["id"],
            actor="Admin",
            idempotency_key="publish-identified-v2",
        )["item"]
        assignment_two = service.assign_survey(db, organization_id=org_id, event_id=event_id, survey_id=identified_survey["id"], actor="Admin", version_id=published_two["id"])["item"]
        second_session = service.start_response(
            db,
            organization_id=org_id,
            event_id=event_id,
            assignment_id=assignment_two["id"],
            participant_id=data["people"][event_id][1],
            idempotency_key="identified-v2-start",
        )["item"]
        service.submit_response(
            db,
            organization_id=org_id,
            event_id=event_id,
            session_id=second_session["id"],
            answers=[{"question_id": published_two["questions"][0]["id"], "value": "Revision versionada"}],
        )
        versioned_results = service.results(db, organization_id=org_id, event_id=event_id, survey_id=identified_survey["id"])
        assert_true(versioned_results["total_responses"] == 2, "conteo versionado total incorrecto")
        assert_true(len(versioned_results["versions"]) == 2, "resultados no separan versiones")
        assert_true([item["total_responses"] for item in versioned_results["versions"]] == [1, 1], "respuestas mezcladas entre versiones")
        assert_true(versioned_results["items"][0]["key"] == "FOLLOWUP", "resultados actuales no usan la version vigente")
        versioned_csv = service.export_csv(db, organization_id=org_id, event_id=event_id, survey_id=identified_survey["id"])
        assert_true("v1.SAT" in versioned_csv.splitlines()[0] and "v2.FOLLOWUP" in versioned_csv.splitlines()[0], "CSV no separa columnas por version")
        anonymous_csv = service.export_csv(db, organization_id=org_id, event_id=event_id, survey_id=anonymous_survey["id"])
        assert_true("participant_id" not in anonymous_csv.splitlines()[0], "CSV anonimo expone participante")
        service.close_assignment(db, organization_id=org_id, event_id=event_id, assignment_id=identified_assignment["id"], actor="Admin")
        try:
            service.start_response(db, organization_id=org_id, event_id=event_id, assignment_id=identified_assignment["id"], participant_id=data["people"][event_id][1], idempotency_key="after-close")
            raise AssertionError("encuesta cerrada acepto respuesta")
        except server.SurveyDomainError as exc:
            assert_true(exc.code == "SURVEY_NOT_OPEN", "cierre no fue aplicado")
        service.archive_survey(db, organization_id=org_id, event_id=event_id, survey_id=identified_survey["id"], actor="Admin")
        audit_count = db.execute("SELECT COUNT(*) AS c FROM audit_logs WHERE event_id = ? AND action LIKE 'surveys.%'", (event_id,)).fetchone()["c"]
        assert_true(int(audit_count) >= 6, "auditoria de encuestas insuficiente")
        db.execute("COMMIT")

    bundle = server.event_backup_service().create_event_bundle(event_id, "test")
    restored = server.event_restore_service().restore_bytes(bundle.read_bytes(), mode="new_event", actor="test", new_event_name="Evento encuestas restaurado")
    assert_true(restored["ok"], "restore con encuestas fallo")
    restored_event_id = int(restored["event_id"])
    with server.connect() as db:
        restored_counts = {table: db.execute(f"SELECT COUNT(*) AS c FROM {table} WHERE event_id = ?", (restored_event_id,)).fetchone()["c"] for table in ("surveys", "survey_versions", "survey_questions", "survey_response_sessions", "survey_answers")}
        assert_true(all(int(value) > 0 for value in restored_counts.values()), f"restore incompleto: {restored_counts}")
        restored_anon = db.execute("SELECT participant_id FROM survey_response_sessions WHERE event_id = ? AND response_mode = 'ANONYMOUS' LIMIT 1", (restored_event_id,)).fetchone()
        assert_true(restored_anon and restored_anon["participant_id"] is None, "restore rompio anonimato")
        restored_tokens = db.execute("SELECT status FROM survey_access_tokens WHERE event_id = ?", (restored_event_id,)).fetchall()
        assert_true(restored_tokens and all(str(row["status"]) == "RESTORED_INACTIVE" for row in restored_tokens), "tokens restaurados no quedaron inactivos")

    def concurrent_submit(results):
        with server.DB_LOCK, server.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                row = db.execute("SELECT * FROM survey_response_sessions WHERE event_id = ? AND status = 'SUBMITTED' ORDER BY id LIMIT 1", (event_id,)).fetchone()
                result = service.submit_response(db, organization_id=org_id, event_id=event_id, session_id=int(row["id"]), answers=[])
                db.execute("COMMIT")
                results.append(result.get("idempotent") is True)
            except Exception as exc:
                db.execute("ROLLBACK")
                results.append(exc)

    concurrent_results = []
    threads = [threading.Thread(target=concurrent_submit, args=(concurrent_results,)) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert_true(all(item is True for item in concurrent_results), "reenvio concurrente no fue idempotente")

    print("V4.4 surveys foundation: OK")


if __name__ == "__main__":
    try:
        main()
    finally:
        tmp.cleanup()
