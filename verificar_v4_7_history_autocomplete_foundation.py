import os
import tempfile
from pathlib import Path

tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
root = Path(tmp.name)
os.environ["QR_SQLITE_PATH"] = str(root / "v4_7_history_autocomplete.sqlite3")
os.environ["BITORA_HISTORY_AUTOCOMPLETE_V4_ENABLED"] = "true"
os.environ["BITORA_SPEAKERS_V4_ENABLED"] = "true"
os.environ["BITORA_ZONE_PERMISSIONS_V4_ENABLED"] = "true"
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
    for idx, name in enumerate(("Alfa History", "Beta History")):
        cur = db.execute(
            """
            INSERT INTO organizations (public_id, name, legal_name, trade_name, status, plan, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'active', 'standard', ?, ?)
            """,
            (f"history-{idx}", name, name, name, now, now),
        )
        orgs.append(int(cur.lastrowid))
    people_by_event = {}
    acc_by_event = {}
    for org_index, org_id in enumerate(orgs):
        event = db.execute(
            "INSERT INTO events (organization_id, name, starts_at, ends_at, created_at) VALUES (?, ?, ?, ?, ?)",
            (org_id, f"Evento Historial {org_index}", "2026-12-02T09:00:00+00:00", "2026-12-02T18:00:00+00:00", now),
        )
        event_id = int(event.lastrowid)
        events.append(event_id)
        people_by_event[event_id] = []
        acc_by_event[event_id] = []
        for person_index in range(3):
            person = db.execute(
                "INSERT INTO people (first_name, last_name, email, phone, dni, company, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (f"Historia{org_index}{person_index}", "Persona", f"historia-{org_index}-{person_index}@example.test", "", f"DNI{org_index}{person_index}", f"Compania {org_index}", now),
            )
            person_id = int(person.lastrowid)
            people_by_event[event_id].append(person_id)
            accreditation = db.execute(
                "INSERT INTO accreditations (event_id, person_id, token, type, status, created_at) VALUES (?, ?, ?, 'General', 'active', ?)",
                (event_id, person_id, f"HIST{org_index}{person_index}", now),
            )
            acc_by_event[event_id].append(int(accreditation.lastrowid))
        space = db.execute(
            "INSERT INTO spaces (event_id, name, capacity, created_at) VALUES (?, ?, 100, ?)",
            (event_id, f"Sala Historial {org_index}", now),
        )
        activity = db.execute(
            """
            INSERT INTO activities (event_id, space_id, title, description, speaker, activity_type, starts_at, ends_at, capacity, status, created_at)
            VALUES (?, ?, ?, '', '', 'Charla', ?, ?, 100, 'active', ?)
            """,
            (event_id, int(space.lastrowid), f"Actividad Historial {org_index}", "2026-12-02T10:00:00+00:00", "2026-12-02T11:00:00+00:00", now),
        )
        speaker = db.execute(
            """
            INSERT INTO speaker_profiles (organization_id, public_id, display_name, first_name, last_name, title, company, city, status, visibility, created_by, created_at, updated_at)
            VALUES (?, ?, ?, 'Ada', 'Speaker', 'Keynote', ?, ?, 'PUBLISHED', 'EVENT', 'test', ?, ?)
            """,
            (org_id, f"speaker-hist-{org_index}", f"Ada Speaker {org_index}", f"Compania {org_index}", f"Ciudad {org_index}", now, now),
        )
        speaker_id = int(speaker.lastrowid)
        db.execute(
            "INSERT INTO speaker_event_assignments (organization_id, event_id, speaker_profile_id, roles_json, status, visibility, created_by, created_at, updated_at) VALUES (?, ?, ?, ?, 'CONFIRMED', 'PUBLIC', 'test', ?, ?)",
            (org_id, event_id, speaker_id, '["SPEAKER"]', now, now),
        )
        db.execute(
            "INSERT INTO speaker_activity_assignments (organization_id, event_id, activity_id, speaker_profile_id, role, status, visibility, created_by, created_at, updated_at) VALUES (?, ?, ?, ?, 'MODERATOR', 'CONFIRMED', 'PUBLIC', 'test', ?, ?)",
            (org_id, event_id, int(activity.lastrowid), speaker_id, now, now),
        )
        db.execute(
            "INSERT INTO audit_logs (event_id, actor, action, entity_type, entity_id, payload, created_at) VALUES (?, 'tester', 'history.seeded', 'person', ?, ?, ?)",
            (event_id, people_by_event[event_id][0], '{"email":"historia@example.test","secret":"no-debe-salir"}', now),
        )
    return {"orgs": orgs, "events": events, "people": people_by_event, "accreditations": acc_by_event}


def main():
    server.init_db()
    service = server.history_autocomplete_service()
    with server.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        data = seed(db)
        db.execute("COMMIT")

    org_id = data["orgs"][0]
    other_org_id = data["orgs"][1]
    event_id = data["events"][0]
    other_event_id = data["events"][1]
    person_id = data["people"][event_id][0]
    other_person_id = data["people"][other_event_id][0]

    with server.connect() as db:
        assert_true(server.history_autocomplete_v4_enabled(db, event_id), "feature flag V4.7 no habilitado")
        event_history = service.event_history(db, organization_id=org_id, event_id=event_id)
        assert_true(event_history["items"], "historial de evento vacio")
        assert_true("payload" not in event_history["items"][0], "payload sensible expuesto sin permiso")
        sensitive = service.event_history(db, organization_id=org_id, event_id=event_id, include_sensitive=True)
        assert_true("payload" in sensitive["items"][0], "payload no disponible con permiso sensible")
        entity_history = service.entity_history(db, organization_id=org_id, event_id=event_id, entity_type="person", entity_id=person_id)
        assert_true(entity_history["items"], "historial por entidad vacio")
        try:
            service.event_history(db, organization_id=other_org_id, event_id=event_id)
            raise AssertionError("historial cross-org permitido")
        except server.HistoryAutocompleteError:
            pass
        try:
            service.entity_history(db, organization_id=org_id, event_id=event_id, entity_type="../users", entity_id=person_id)
            raise AssertionError("entity_type inseguro aceptado")
        except server.HistoryAutocompleteError:
            pass

        autocomplete = service.autocomplete_participants(db, organization_id=org_id, event_id=event_id, query="historia00")
        assert_true(len(autocomplete["items"]) == 1, "autocomplete de participantes no acotado")
        assert_true("email" not in autocomplete["items"][0], "email privado expuesto")
        private = service.autocomplete_participants(db, organization_id=org_id, event_id=event_id, query="historia00", include_private=True)
        assert_true(private["items"][0]["email"].endswith("@example.test"), "autocomplete privado no devuelve email con permiso")
        cross = service.autocomplete_participants(db, organization_id=org_id, event_id=event_id, query="historia10")
        assert_true(not cross["items"], "autocomplete filtro un participante de otro tenant")
        speakers = service.autocomplete_speakers(db, organization_id=org_id, query="ada")
        assert_true(len(speakers["items"]) == 1, "autocomplete de disertantes fallo")
        companies = service.autocomplete_values(db, organization_id=org_id, field="organizations", query="compania")
        assert_true(companies["items"], "autocomplete de instituciones fallo")
        cities = service.autocomplete_values(db, organization_id=org_id, field="cities", query="ciudad")
        assert_true(cities["items"], "autocomplete de ciudades fallo")
        roles = service.autocomplete_values(db, organization_id=org_id, field="roles", query="moder")
        assert_true(roles["items"], "autocomplete de roles fallo")
        duplicates = service.duplicate_candidates(db, organization_id=org_id, email="historia-0-0@example.test")
        assert_true(any(item["person_id"] == person_id for item in duplicates["items"]), "duplicado por email no detectado")
        cross_duplicate = service.duplicate_candidates(db, organization_id=org_id, email="historia-1-0@example.test")
        assert_true(not any(item["person_id"] == other_person_id for item in cross_duplicate["items"]), "duplicado cross-org detectado")

    with server.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        decision = service.record_duplicate_decision(db, organization_id=org_id, event_id=event_id, actor="tester", candidate_person_id=person_id, decision="CONFIRMED_MATCH", reason="Coincide email")["item"]
        assert_true(decision["decision"] == "CONFIRMED_MATCH", "decision de duplicado no registrada")
        try:
            service.record_duplicate_decision(db, organization_id=org_id, event_id=event_id, actor="tester", candidate_person_id=other_person_id, decision="DISMISSED")
            raise AssertionError("decision cross-org aceptada")
        except server.HistoryAutocompleteError:
            pass
        audit_count = db.execute("SELECT COUNT(*) AS c FROM audit_logs WHERE action = 'duplicates.decision.recorded'").fetchone()["c"]
        assert_true(int(audit_count) == 1, "auditoria de duplicados incorrecta")
        db.execute("COMMIT")

    bundle = server.event_backup_service().create_event_bundle(event_id, "test")
    restored = server.event_restore_service().restore_bytes(bundle.read_bytes(), mode="new_event", actor="test", new_event_name="Evento historial restaurado")
    assert_true(restored["ok"], "restore V4.7 fallo")
    restored_event_id = int(restored["event_id"])
    with server.connect() as db:
        restored_audits = db.execute("SELECT COUNT(*) AS c FROM audit_logs WHERE event_id = ?", (restored_event_id,)).fetchone()["c"]
        restored_decisions = db.execute("SELECT COUNT(*) AS c FROM duplicate_resolution_decisions WHERE event_id = ?", (restored_event_id,)).fetchone()["c"]
        assert_true(int(restored_audits) > 0, "historial no preservado en restore")
        assert_true(int(restored_decisions) == 1, "decision de duplicado no preservada/remapeada")

    print("V4.7 history and autocomplete foundation: OK")


if __name__ == "__main__":
    try:
        main()
    finally:
        tmp.cleanup()
