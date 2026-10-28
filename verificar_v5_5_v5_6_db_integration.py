from __future__ import annotations

import json
import shutil
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import server
from backend.contracts.v5_5_lead_retrieval import EventScope as LeadScope, LeadRetrievalContract
from backend.services.lead_retrieval import LeadRetrievalError
from verificar_v5_1_access_state_engine_shadow import backfill, create_event, credential, register, setup_db


def require(condition, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def company_fixture(db, company_service, leads, event_id: int, name: str, code: str, *, license_status: str):
    company = company_service.create_company(db, organization_id=1, name=name, company_type="EXHIBITOR")
    company_id = int(company["id"])
    company_service.link_company_to_event(
        db, organization_id=1, event_id=event_id, company_id=company_id, status="ACTIVE"
    )
    company_service.grant_company_user(
        db,
        organization_id=1,
        event_id=event_id,
        company_id=company_id,
        email=f"seller-{code.lower()}@example.test",
        role="COMPANY_ADMIN",
    )
    stand = leads.create_stand(
        db,
        organization_id=1,
        event_id=event_id,
        company_id=company_id,
        code=code,
        name=f"Stand {code}",
    )
    stand_id = int(stand["id"])
    leads.create_license(
        db,
        organization_id=1,
        event_id=event_id,
        company_id=company_id,
        stand_id=stand_id,
        status=license_status,
        max_users=5,
        max_devices=2,
    )
    return company_id, stand_id


def verify_leads(db, event_id: int, registration: dict, entity_id: int) -> dict:
    companies = server.company_delegation_service()
    leads = server.lead_retrieval_service()
    company_a, stand_a = company_fixture(
        db, companies, leads, event_id, "Lead Company A", "A01", license_status="PENDING"
    )
    company_b, stand_b = company_fixture(
        db, companies, leads, event_id, "Lead Company B", "B01", license_status="ACTIVE"
    )

    inactive = leads.capture(
        db,
        organization_id=1,
        event_id=event_id,
        company_id=company_a,
        stand_id=stand_a,
        token=registration["token"],
        user_email="seller-a01@example.test",
        idempotency_key="lead-inactive-license",
    )
    require(inactive == {"ok": False, "reason_code": "LICENSE_INACTIVE"}, "inactive license accepted")
    leads.create_license(
        db,
        organization_id=1,
        event_id=event_id,
        company_id=company_a,
        stand_id=stand_a,
        status="ACTIVE",
        max_users=5,
        max_devices=2,
    )

    consent = leads.grant_consent(
        db,
        organization_id=1,
        event_id=event_id,
        participant_entity_id=entity_id,
        company_id=company_a,
        fields=["first_name", "last_name", "email"],
    )
    consent_id = int(consent["id"])
    capture_args = dict(
        organization_id=1,
        event_id=event_id,
        company_id=company_a,
        stand_id=stand_a,
        token=registration["token"],
        consent_id=consent_id,
        user_email="seller-a01@example.test",
        idempotency_key="lead-capture-a-1",
    )
    captured = leads.capture(db, **capture_args)
    replay = leads.capture(db, **capture_args)
    require(captured.get("ok") and replay.get("duplicate"), "lead capture idempotency failed")
    require(int(captured["lead"]["id"]) == int(replay["lead"]["id"]), "lead replay changed identity")
    interaction_count = int(
        db.execute(
            "SELECT COUNT(*) AS c FROM enterprise_lead_interactions WHERE organization_id=1 AND idempotency_key=?",
            ("lead-capture-a-1",),
        ).fetchone()["c"]
    )
    require(interaction_count == 1, "lead replay persisted a second interaction")

    require(
        len(leads.list_leads(db, organization_id=1, event_id=event_id, company_id=company_a)) == 1,
        "company A lead missing",
    )
    require(
        leads.list_leads(db, organization_id=1, event_id=event_id, company_id=company_b) == [],
        "company B observed company A lead",
    )
    # Exercise the production application contract as well as the real service:
    # it must reject a consent identifier issued to another company.
    contract = LeadRetrievalContract(leads)
    try:
        contract.capture(
            db,
            LeadScope(1, event_id),
            {
                "company_id": company_b,
                "stand_id": stand_b,
                "token": registration["token"],
                "consent_id": consent_id,
                "user_email": "seller-b01@example.test",
                "idempotency_key": "lead-cross-company",
            },
        )
    except LeadRetrievalError as exc:
        require(exc.code == "CONSENT_SCOPE_ERROR", "wrong cross-company consent error")
    else:
        raise AssertionError("company A consent crossed into company B")

    revoked = leads.revoke_consent(
        db, organization_id=1, event_id=event_id, consent_id=consent_id
    )
    require(revoked["status"] == "REVOKED", "consent was not revoked")
    after_revoke = leads.capture(
        db,
        organization_id=1,
        event_id=event_id,
        company_id=company_a,
        stand_id=stand_a,
        token=registration["token"],
        consent_id=consent_id,
        user_email="seller-a01@example.test",
        idempotency_key="lead-after-revoke",
    )
    require(after_revoke.get("reason_code") == "CONSENT_REQUIRED", "revoked consent accepted")

    exported = leads.export_csv(
        db,
        organization_id=1,
        event_id=event_id,
        company_id=company_a,
        fields=["first_name", "last_name", "email"],
        exported_by="seller-a01@example.test",
        idempotency_key="lead-export-a-1",
    )
    require(exported["ok"] and exported["count"] == 1, "lead export failed")
    participant_email = db.execute(
        "SELECT email FROM people WHERE id=?", (registration["person_id"],)
    ).fetchone()["email"]
    require(participant_email in exported["csv"] and "dni" not in exported["csv"].lower(), "export violated field policy")
    export_count = int(
        db.execute(
            "SELECT COUNT(*) AS c FROM enterprise_lead_exports WHERE organization_id=1 AND event_id=? AND company_id=? AND idempotency_key=?",
            (event_id, company_a, "lead-export-a-1"),
        ).fetchone()["c"]
    )
    require(export_count == 1, "export audit row missing")
    return {"company_a": company_a, "stand_a": stand_a}


def verify_vehicles(db, event_id: int, company_id: int, stand_id: int, driver_entity_id: int) -> None:
    core = server.enterprise_core_service()
    vehicles = server.vehicle_logistics_service()
    sync = server.edge_sync_service()
    destination = vehicles.ensure_destination(
        db,
        organization_id=1,
        event_id=event_id,
        code="LOAD_A",
        name="Carga A",
        stand_id=stand_id,
        capacity=10,
    )
    gate = core.ensure_door(db, organization_id=1, event_id=event_id, code="GATE_A", name="Gate A")
    gate_id = int(gate["item"]["id"])
    destination_id = int(destination["id"])
    vehicle = vehicles.ensure_vehicle(db, organization_id=1, plate="QA-123-AA", vehicle_type="VAN")
    vehicles.create_slot(
        db,
        organization_id=1,
        event_id=event_id,
        vehicle_id=int(vehicle["id"]),
        company_id=company_id,
        driver_entity_id=driver_entity_id,
        gate_id=gate_id,
        destination_id=destination_id,
        valid_from=(datetime.fromisoformat(server.now_iso()) - timedelta(minutes=5)).isoformat(timespec="seconds"),
        valid_until=(datetime.fromisoformat(server.now_iso()) + timedelta(hours=2)).isoformat(timespec="seconds"),
        entry_limit=3,
    )
    entry = vehicles.record_access(
        db,
        organization_id=1,
        event_id=event_id,
        plate="QA123AA",
        direction="ENTRY",
        gate_id=gate_id,
        destination_id=destination_id,
        driver_entity_id=driver_entity_id,
        idempotency_key="vehicle-entry-1",
    )
    entry_replay = vehicles.record_access(
        db,
        organization_id=1,
        event_id=event_id,
        plate="QA123AA",
        direction="ENTRY",
        gate_id=gate_id,
        destination_id=destination_id,
        idempotency_key="vehicle-entry-1",
    )
    anti = vehicles.record_access(
        db,
        organization_id=1,
        event_id=event_id,
        plate="QA123AA",
        direction="ENTRY",
        gate_id=gate_id,
        destination_id=destination_id,
        idempotency_key="vehicle-entry-anti",
    )
    exit_result = vehicles.record_access(
        db,
        organization_id=1,
        event_id=event_id,
        plate="QA123AA",
        direction="EXIT",
        gate_id=gate_id,
        idempotency_key="vehicle-exit-1",
    )
    require(entry["ok"] and entry_replay.get("duplicate"), "vehicle entry idempotency failed")
    require(anti["decision"]["reason_code"] == "ANTI_PASSBACK", "vehicle anti-passback failed")
    require(exit_result["ok"], "vehicle exit failed")

    device = sync.provision_device(
        db,
        organization_id=1,
        event_id=event_id,
        device_type="EDGE_NODE",
        display_name="QA Vehicle Gate",
        capabilities=["SYNC_DATASET", "VALIDATE_VEHICLE"],
        actor="db-integration",
    )
    device_id, secret = int(device["device"]["id"]), device["secret"]
    sync.activate_device(db, organization_id=1, event_id=event_id, device_id=device_id, actor="db-integration")
    operation = {
        "payload": {
            "plate": "QA123AA",
            "direction": "ENTRY",
            "gate_id": gate_id,
            "destination_id": destination_id,
        },
        "local_decision": {"decision": "ALLOW", "reason_code": "VALID"},
        "idempotency_key": "vehicle-offline-retry-1",
    }
    first_sync = vehicles.reconcile_offline(
        db, organization_id=1, event_id=event_id, device_id=device_id, secret=secret, operation=operation
    )
    retry_sync = vehicles.reconcile_offline(
        db, organization_id=1, event_id=event_id, device_id=device_id, secret=secret, operation=operation
    )
    require(first_sync["server_result"]["ok"], "offline vehicle entry failed")
    require(retry_sync["server_result"].get("duplicate"), "offline retry was not idempotent")
    retry_rows = int(
        db.execute(
            "SELECT COUNT(*) AS c FROM enterprise_vehicle_access_events WHERE organization_id=1 AND idempotency_key=?",
            ("vehicle-offline-retry-1",),
        ).fetchone()["c"]
    )
    require(retry_rows == 1, "offline retry persisted duplicate vehicle event")
    state = db.execute(
        "SELECT current_state FROM enterprise_vehicle_state_snapshots WHERE organization_id=1 AND event_id=? AND vehicle_id=?",
        (event_id, int(vehicle["id"])),
    ).fetchone()
    require(state and state["current_state"] == "INSIDE", "vehicle snapshot not persisted")


def main() -> None:
    temp_parent = Path.cwd() / "tmp"
    temp_parent.mkdir(parents=True, exist_ok=True)
    tempfile.tempdir = str(temp_parent)
    temp_root = setup_db()
    try:
        with server.connect() as db:
            event_id, _activity_id, _future_id = create_event(db, "V5.5/V5.6 DB integration")
            registration = register(db, event_id, "db-integration-participant@example.test")
            backfill(db, event_id)
            entity_id = int(credential(db, event_id, registration["id"])["entity_id"])
            lead_fixture = verify_leads(db, event_id, registration, entity_id)
            verify_vehicles(db, event_id, lead_fixture["company_a"], lead_fixture["stand_a"], entity_id)

            require(
                db.execute("PRAGMA quick_check").fetchone()[0] == "ok",
                "SQLite integrity check failed",
            )
        print("OK: V5.5/V5.6 real SQLite integration (leads, consent, licenses, export, vehicles, anti-passback, retry)")
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    main()
