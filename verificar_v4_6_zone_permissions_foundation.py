import os
import tempfile
from pathlib import Path

tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
root = Path(tmp.name)
os.environ["QR_SQLITE_PATH"] = str(root / "v4_6_zones.sqlite3")
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
    people = {}
    accreditations = {}
    for org_name in ("Alfa Zones", "Beta Zones"):
        cur = db.execute(
            """
            INSERT INTO organizations (public_id, name, legal_name, trade_name, status, plan, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'active', 'standard', ?, ?)
            """,
            (org_name.lower().replace(" ", "_"), org_name, org_name, org_name, now, now),
        )
        orgs.append(int(cur.lastrowid))
    for org_index, org_id in enumerate(orgs):
        event = db.execute(
            "INSERT INTO events (organization_id, name, starts_at, ends_at, created_at) VALUES (?, ?, ?, ?, ?)",
            (org_id, f"Evento Zones {org_index}", "2026-12-01T09:00:00+00:00", "2026-12-01T18:00:00+00:00", now),
        )
        event_id = int(event.lastrowid)
        events.append(event_id)
        people[event_id] = []
        accreditations[event_id] = []
        for idx in range(3):
            person = db.execute(
                "INSERT INTO people (first_name, last_name, email, source, device_type, created_at) VALUES (?, 'Zone', ?, 'test', 'desktop', ?)",
                (f"Persona{org_index}{idx}", f"zone-{org_index}-{idx}@example.test", now),
            )
            person_id = int(person.lastrowid)
            people[event_id].append(person_id)
            accreditation = db.execute(
                "INSERT INTO accreditations (event_id, person_id, token, type, status, created_at) VALUES (?, ?, ?, 'General', 'active', ?)",
                (event_id, person_id, f"ZONE{org_index}{idx}", now),
            )
            accreditations[event_id].append(int(accreditation.lastrowid))
    return {"orgs": orgs, "events": events, "people": people, "accreditations": accreditations}


def main():
    server.init_db()
    service = server.zone_permission_service()
    with server.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        data = seed(db)
        db.execute("COMMIT")

    org_id = data["orgs"][0]
    other_org_id = data["orgs"][1]
    event_id = data["events"][0]
    other_event_id = data["events"][1]
    person_id = data["people"][event_id][0]
    denied_person_id = data["people"][event_id][1]
    other_person_id = data["people"][other_event_id][0]
    accreditation_id = data["accreditations"][event_id][0]
    other_accreditation_id = data["accreditations"][other_event_id][0]

    with server.connect() as db:
        assert_true(server.zone_permissions_v4_enabled(db, event_id), "feature flag de zonas no habilitado")

    with server.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        parent = service.create_zone(db, organization_id=org_id, event_id=event_id, actor="Admin", code="BACKSTAGE", name="Backstage")["item"]
        child = service.create_zone(db, organization_id=org_id, event_id=event_id, actor="Admin", code="VIP_ROOM", name="Sala VIP", parent_zone_id=parent["id"])["item"]
        try:
            service.create_zone(db, organization_id=other_org_id, event_id=event_id, actor="Admin", code="X", name="Cruce")
            raise AssertionError("zona cross-org aceptada")
        except server.ZoneDomainError:
            pass
        assignment = service.assign_access(db, organization_id=org_id, event_id=event_id, zone_id=child["id"], actor="Admin", person_id=person_id)["item"]
        assert_true(assignment["person_id"] == person_id, "asignacion incorrecta")
        allowed = service.validate_access(db, organization_id=org_id, event_id=event_id, zone_id=child["id"], actor="Acceso", accreditation_id=accreditation_id, idempotency_key="allow-1")["item"]
        assert_true(allowed["decision"] == "ALLOWED", "acceso autorizado fue denegado")
        replay = service.validate_access(db, organization_id=org_id, event_id=event_id, zone_id=child["id"], actor="Acceso", accreditation_id=accreditation_id, idempotency_key="allow-1")
        assert_true(replay.get("idempotent") is True, "validacion idempotente no detectada")
        denied = service.validate_access(db, organization_id=org_id, event_id=event_id, zone_id=child["id"], actor="Acceso", person_id=denied_person_id, idempotency_key="deny-1")["item"]
        assert_true(denied["decision"] == "DENIED", "persona sin zona no fue denegada")
        wrong_event = service.validate_access(db, organization_id=org_id, event_id=event_id, zone_id=child["id"], actor="Acceso", accreditation_id=other_accreditation_id, idempotency_key="wrong-event")["item"]
        assert_true(wrong_event["decision"] == "WRONG_EVENT", "credencial de otro evento no fue bloqueada")
        try:
            service.assign_access(db, organization_id=org_id, event_id=event_id, zone_id=child["id"], actor="Admin", person_id=other_person_id)
            raise AssertionError("persona de otro evento asignada")
        except server.ZoneDomainError as exc:
            assert_true(exc.code == "ZONE_CREDENTIAL_INVALID", "cross-event no rechazo correctamente")
        override = service.create_override(db, organization_id=org_id, event_id=event_id, zone_id=child["id"], actor="Admin", override_type="ALLOW_OVERRIDE", reason="Operacion controlada", person_id=denied_person_id)["item"]
        assert_true(override["override_type"] == "ALLOW_OVERRIDE", "override no creado")
        allowed_by_override = service.validate_access(db, organization_id=org_id, event_id=event_id, zone_id=child["id"], actor="Acceso", person_id=denied_person_id, idempotency_key="override-allow")["item"]
        assert_true(allowed_by_override["decision"] == "ALLOWED", "override allow no autorizo")
        try:
            service.create_override(db, organization_id=org_id, event_id=event_id, zone_id=child["id"], actor="Admin", override_type="DENY_OVERRIDE", reason="", person_id=person_id)
            raise AssertionError("override sin motivo aceptado")
        except server.ZoneDomainError as exc:
            assert_true(exc.code == "ZONE_OVERRIDE_REASON_REQUIRED", "override sin motivo no fue rechazado")
        audit_count = db.execute("SELECT COUNT(*) AS c FROM audit_logs WHERE action LIKE 'zones.%'").fetchone()["c"]
        assert_true(int(audit_count) >= 6, "auditoria de zonas insuficiente")
        db.execute("COMMIT")

    bundle = server.event_backup_service().create_event_bundle(event_id, "test")
    restored = server.event_restore_service().restore_bytes(bundle.read_bytes(), mode="new_event", actor="test", new_event_name="Evento zones restaurado")
    assert_true(restored["ok"], "restore de zonas fallo")
    restored_event_id = int(restored["event_id"])
    with server.connect() as db:
        restored_counts = {
            table: db.execute(f"SELECT COUNT(*) AS c FROM {table} WHERE event_id = ?", (restored_event_id,)).fetchone()["c"]
            for table in ("event_zones", "zone_access_assignments", "zone_access_validations", "zone_access_overrides")
        }
        assert_true(all(int(value) > 0 for value in restored_counts.values()), f"restore zonas incompleto: {restored_counts}")

    print("V4.6 zone permissions foundation: OK")


if __name__ == "__main__":
    try:
        main()
    finally:
        tmp.cleanup()
