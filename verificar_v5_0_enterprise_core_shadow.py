from __future__ import annotations

import os
import tempfile
from pathlib import Path


tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
root = Path(tmp.name)
os.environ["QR_SQLITE_PATH"] = str(root / "v5_0_enterprise.sqlite3")
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
    for org_name in ("Alfa Enterprise", "Beta Enterprise"):
        cur = db.execute(
            """
            INSERT INTO organizations (public_id, name, legal_name, trade_name, status, plan, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'active', 'standard', ?, ?)
            """,
            (org_name.lower().replace(" ", "_"), org_name, org_name, org_name, now, now),
        )
        orgs.append(int(cur.lastrowid))
    for index, org_id in enumerate(orgs):
        event = db.execute(
            "INSERT INTO events (organization_id, name, starts_at, ends_at, created_at) VALUES (?, ?, ?, ?, ?)",
            (org_id, f"Evento Enterprise {index}", "2026-12-01T09:00:00+00:00", "2026-12-01T18:00:00+00:00", now),
        )
        event_id = int(event.lastrowid)
        events.append(event_id)
        db.execute("INSERT INTO accreditation_types (event_id, name, capacity, access_enabled, created_at) VALUES (?, 'General', 0, 1, ?)", (event_id, now))
        for participant in range(3):
            person = db.execute(
                "INSERT INTO people (first_name, last_name, email, dni, company, created_at) VALUES (?, 'Shadow', ?, ?, ?, ?)",
                (f"Persona{index}{participant}", f"enterprise-{index}-{participant}@example.test", f"80{index}{participant}", "Empresa Demo" if participant < 2 else "Otra Empresa", now),
            )
            person_id = int(person.lastrowid)
            db.execute(
                "INSERT INTO accreditations (event_id, person_id, token, type, status, max_reentries, created_at) VALUES (?, ?, ?, 'General', ?, 0, ?)",
                (event_id, person_id, f"EVTV50{index}{participant}", "cancelled" if participant == 2 else "active", now),
            )
    return {"orgs": orgs, "events": events}


def access_decision(token: str) -> tuple[str, str]:
    with server.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        result = server.access_validation_service().validate(db, token, "tester", "Puerta principal")
        db.execute("COMMIT")
    return result["result"], result["reason"]


def main():
    server.init_db()
    with server.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        data = seed(db)
        db.execute("COMMIT")

    org_id, other_org_id = data["orgs"]
    event_id, other_event_id = data["events"]
    service = server.enterprise_core_service()

    with server.connect() as db:
        assert_true(not server.enterprise_core_model_enabled(db, event_id), "enterprise_core_model debe iniciar OFF")
    os.environ["BITORA_ENTERPRISE_CORE_MODEL"] = "true"
    with server.connect() as db:
        assert_true(server.enterprise_core_model_enabled(db, event_id), "enterprise_core_model no habilito por env flag")

    before_valid = access_decision("EVTV5000")
    before_invalid = access_decision("EVTNOEXISTE")
    before_cancelled = access_decision("EVTV5002")

    with server.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        result1 = service.backfill_event(db, organization_id=org_id, event_id=event_id, actor="test")
        result2 = service.backfill_event(db, organization_id=org_id, event_id=event_id, actor="test")
        summary = service.summary(db, organization_id=org_id, event_id=event_id)
        assert_true(result1["ok"], f"backfill inicial fallo: {result1}")
        assert_true(result2["ok"], f"backfill idempotente fallo: {result2}")
        assert_true(summary["entities"] == 8, f"entities esperadas 8, obtuvo {summary}")
        assert_true(summary["credentials"] == 3, f"credentials esperadas 3, obtuvo {summary}")
        person_entity = db.execute("SELECT * FROM enterprise_entities WHERE event_id = ? AND entity_type = 'PERSON' ORDER BY id LIMIT 1", (event_id,)).fetchone()
        entitlement = service.grant_entitlement(
            db,
            organization_id=org_id,
            event_id=event_id,
            entity_id=int(person_entity["id"]),
            entitlement_type="VIP_ACCESS",
            scope_type="EVENT",
            allocated=0,
            consumable=False,
            idempotency_key="v5-entitlement-test",
            actor="test",
        )
        entitlement_replay = service.grant_entitlement(
            db,
            organization_id=org_id,
            event_id=event_id,
            entity_id=int(person_entity["id"]),
            entitlement_type="VIP_ACCESS",
            scope_type="EVENT",
            idempotency_key="v5-entitlement-test",
            actor="test",
        )
        assert_true(entitlement["ok"] and entitlement_replay.get("idempotent"), "entitlement no fue idempotente")
        rule = service.create_rule(db, organization_id=org_id, event_id=event_id, entitlement_id=int(entitlement["item"]["id"]), rule_type="TIME_WINDOW", scope={"from": "09:00", "until": "18:00"}, actor="test")
        assert_true(rule["ok"], "rule no persistio")
        zone = server.zone_permission_service().create_zone(db, organization_id=org_id, event_id=event_id, actor="test", code="VIP", name="Zona VIP")["item"]
        door = service.ensure_door(db, organization_id=org_id, event_id=event_id, code="MAIN_VIP", name="Ingreso VIP", zone_id=zone["id"])
        assert_true(door["ok"], "door no persistio")
        device = service.register_device(db, organization_id=org_id, event_id=event_id, device_uid="device-v5-shadow", device_type="KIOSK", version="test")
        assert_true(device["ok"], "device no persistio")
        domain_event = service.record_domain_event(db, organization_id=org_id, event_id=event_id, entity_id=int(person_entity["id"]), device_id=int(device["item"]["id"]), event_type="ENTITLEMENT_GRANTED", idempotency_key="domain-event-1")
        domain_event_replay = service.record_domain_event(db, organization_id=org_id, event_id=event_id, event_type="ENTITLEMENT_GRANTED", idempotency_key="domain-event-1")
        assert_true(domain_event["ok"] and domain_event_replay.get("idempotent"), "domain event no fue idempotente")
        try:
            service.backfill_event(db, organization_id=other_org_id, event_id=event_id, actor="test")
            raise AssertionError("cross-tenant backfill aceptado")
        except server.EnterpriseCoreError:
            pass
        db.execute("COMMIT")

    after_valid = access_decision("EVTV5001")
    after_invalid = access_decision("EVTNOEXISTE")
    after_cancelled = access_decision("EVTV5002")
    assert_true(before_valid[0] == after_valid[0] == "granted", f"V5 altero acceso valido: {before_valid} / {after_valid}")
    assert_true(before_invalid == after_invalid, f"V5 altero token inexistente: {before_invalid} / {after_invalid}")
    assert_true(before_cancelled == after_cancelled, f"V5 altero cancelado: {before_cancelled} / {after_cancelled}")

    bundle = server.event_backup_service().create_event_bundle(event_id, "test")
    check = server.verify_event_backup(bundle)
    assert_true(check["ok"], f"backup evento fallo: {check}")
    restored = server.event_restore_service().restore_bytes(bundle.read_bytes(), mode="new_event", actor="test", new_event_name="Evento Enterprise restaurado")
    assert_true(restored["ok"], f"restore evento fallo: {restored}")
    restored_event_id = int(restored["event_id"])
    with server.connect() as db:
        restored_counts = {
            table: db.execute(f"SELECT COUNT(*) AS c FROM {table} WHERE event_id = ?", (restored_event_id,)).fetchone()["c"]
            for table in ("enterprise_entities", "enterprise_identities", "enterprise_credentials", "enterprise_doors", "enterprise_devices", "enterprise_entitlements", "enterprise_rules", "enterprise_domain_events")
        }
        assert_true(restored_counts["enterprise_entities"] >= 5, f"restore V5 sin entities: {restored_counts}")
        assert_true(restored_counts["enterprise_credentials"] >= 3, f"restore V5 sin credentials: {restored_counts}")
        inactive_credentials = db.execute("SELECT COUNT(*) AS c FROM enterprise_credentials WHERE event_id = ? AND status = 'INACTIVE'", (restored_event_id,)).fetchone()["c"]
        assert_true(int(inactive_credentials) >= 3, "credenciales shadow restauradas deben quedar inactivas por regeneracion de token")

    with server.connect() as db:
        other_count = db.execute("SELECT COUNT(*) AS c FROM enterprise_entities WHERE event_id = ?", (other_event_id,)).fetchone()["c"]
        assert_true(int(other_count) == 0, "backfill cruzo otro evento")

    print("V5.0 enterprise core shadow model: OK")


if __name__ == "__main__":
    try:
        main()
    finally:
        tmp.cleanup()
