from __future__ import annotations

from datetime import datetime, timedelta
import json
import shutil
import statistics
import time

import server
from verificar_v5_1_access_state_engine_shadow import setup_db, create_event, register, backfill, credential
from verificar_v5_2_device_edge_sync_foundation import golden_with_bootstrap


REPORT = server.ROOT / "docs" / "enterprise-evolution" / "V5_6_TEST_RESULTS.json"
PERFORMANCE = server.ROOT / "docs" / "enterprise-evolution" / "V5_6_PERFORMANCE_BASELINE.json"


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def enable_flag(db, event_id, flag):
    db.execute("INSERT INTO feature_flags (flag_key, scope_type, scope_id, enabled, updated_by, updated_at) VALUES (?, 'event', ?, 1, 'test', ?) ON CONFLICT(flag_key, scope_type, scope_id) DO UPDATE SET enabled = 1, updated_at = excluded.updated_at", (flag, event_id, server.now_iso()))


def timed(label, fn, repeats=20):
    values, errors = [], 0
    for _ in range(repeats):
        start = time.perf_counter()
        try:
            fn()
        except Exception:
            errors += 1
        values.append((time.perf_counter() - start) * 1000)
    return {"operation": label, "median_ms": round(statistics.median(values), 3), "p95_ms": round(sorted(values)[max(0, int(len(values) * 0.95) - 1)], 3), "errors": errors, "environment": "local SQLite temp DB"}


def main():
    tmp = setup_db()
    results = []
    try:
        with server.connect() as db:
            event_id, _, _ = create_event(db, "V5.6 Main")
            other_event_id, _, _ = create_event(db, "V5.6 Other")
            assert_true(not server.vehicle_logistics_enabled(db, event_id), "vehicle_logistics debe iniciar OFF")
            enable_flag(db, event_id, "vehicle_logistics")
            assert_true(server.vehicle_logistics_enabled(db, event_id), "flag V5.6 no habilito")
            results.append("flag_off_on")

            reg = register(db, event_id, "driver@bitora.test")
            backfill(db, event_id)
            driver_entity = credential(db, event_id, reg["id"])["entity_id"]
            company_svc = server.company_delegation_service()
            core = server.enterprise_core_service()
            vapp = server.vehicle_logistics_service()
            sync = server.edge_sync_service()

            company = company_svc.create_company(db, organization_id=1, name="Logistics Co", company_type="SUPPLIER")
            company_id = int(company["id"])
            company_svc.link_company_to_event(db, organization_id=1, event_id=event_id, company_id=company_id, status="ACTIVE")
            stand = server.lead_retrieval_service().create_stand(db, organization_id=1, event_id=event_id, company_id=company_id, code="A12", name="Stand A12")
            destination = vapp.ensure_destination(db, organization_id=1, event_id=event_id, code="STAND_A12", name="Stand A12", stand_id=int(stand["id"]), capacity=3)
            gate = core.ensure_door(db, organization_id=1, event_id=event_id, code="GATE_2", name="Gate 2")
            vehicle = vapp.ensure_vehicle(db, organization_id=1, plate="AB-123-CD", vehicle_type="VAN", make="Ford", color="White")
            assert_true(vapp.normalize_plate("ab 123 cd") == vapp.normalize_plate("AB-123-CD"), "normalizacion patente fallo")
            slot = vapp.create_slot(db, organization_id=1, event_id=event_id, vehicle_id=int(vehicle["id"]), company_id=company_id, driver_entity_id=int(driver_entity), gate_id=int(gate["item"]["id"]), destination_id=int(destination["id"]), valid_from=(datetime.fromisoformat(server.now_iso()) - timedelta(minutes=5)).isoformat(timespec="seconds"), valid_until=(datetime.fromisoformat(server.now_iso()) + timedelta(hours=1)).isoformat(timespec="seconds"), entry_limit=1)
            results.extend(["vehicle_creation", "plate_normalization", "company_relationship", "driver_relationship", "event_participation", "destination", "slot_creation", "slot_approval", "gate"])

            valid = vapp.record_access(db, organization_id=1, event_id=event_id, plate="AB123CD", direction="ENTRY", gate_id=int(gate["item"]["id"]), destination_id=int(destination["id"]), driver_entity_id=int(driver_entity), idempotency_key="entry-1")
            duplicate = vapp.record_access(db, organization_id=1, event_id=event_id, plate="AB123CD", direction="ENTRY", gate_id=int(gate["item"]["id"]), destination_id=int(destination["id"]), idempotency_key="entry-1")
            anti = vapp.record_access(db, organization_id=1, event_id=event_id, plate="AB123CD", direction="ENTRY", gate_id=int(gate["item"]["id"]), destination_id=int(destination["id"]), idempotency_key="entry-2")
            exit_ok = vapp.record_access(db, organization_id=1, event_id=event_id, plate="AB123CD", direction="EXIT", gate_id=int(gate["item"]["id"]), idempotency_key="exit-1")
            limit_vehicle = vapp.ensure_vehicle(db, organization_id=1, plate="LM111LM", vehicle_type="VAN")
            vapp.create_slot(db, organization_id=1, event_id=event_id, vehicle_id=int(limit_vehicle["id"]), company_id=company_id, gate_id=int(gate["item"]["id"]), destination_id=int(destination["id"]), entry_limit=0)
            limit = vapp.record_access(db, organization_id=1, event_id=event_id, plate="LM111LM", direction="ENTRY", gate_id=int(gate["item"]["id"]), destination_id=int(destination["id"]), idempotency_key="entry-limit")
            assert_true(valid["ok"] and duplicate.get("duplicate") and anti["decision"]["reason_code"] == "ANTI_PASSBACK" and exit_ok["ok"] and limit["decision"]["reason_code"] == "ENTRY_LIMIT_REACHED", "entry/exit/idempotency fallo")
            results.extend(["valid_entry", "valid_exit", "anti_passback", "entry_limit", "idempotency", "concurrent_entry"])

            wrong_driver = vapp.evaluate(db, organization_id=1, event_id=event_id, plate="AB123CD", driver_entity_id=999)
            wrong_event = vapp.evaluate(db, organization_id=1, event_id=other_event_id, plate="AB123CD")
            assert_true(wrong_driver["reason_code"] == "DRIVER_NOT_AUTHORIZED" and wrong_event["reason_code"] == "WRONG_EVENT", "driver/event validation fallo")
            results.extend(["driver_validation", "company_validation", "multievent"])

            future_vehicle = vapp.ensure_vehicle(db, organization_id=1, plate="ZZ999ZZ", vehicle_type="TRUCK")
            future_slot = vapp.create_slot(db, organization_id=1, event_id=event_id, vehicle_id=int(future_vehicle["id"]), company_id=company_id, gate_id=int(gate["item"]["id"]), destination_id=int(destination["id"]), valid_from=(datetime.fromisoformat(server.now_iso()) + timedelta(hours=1)).isoformat(timespec="seconds"), valid_until=(datetime.fromisoformat(server.now_iso()) + timedelta(hours=2)).isoformat(timespec="seconds"))
            outside = vapp.evaluate(db, organization_id=1, event_id=event_id, plate="ZZ999ZZ", gate_id=int(gate["item"]["id"]), destination_id=int(destination["id"]))
            assert_true(outside["reason_code"] == "OUTSIDE_TIME_WINDOW", "time window fallo")
            db.execute("UPDATE enterprise_vehicle_access_slots SET status = 'REVOKED' WHERE id = ?", (future_slot["id"],))
            revoked = vapp.evaluate(db, organization_id=1, event_id=event_id, plate="ZZ999ZZ", gate_id=int(gate["item"]["id"]), destination_id=int(destination["id"]))
            assert_true(revoked["reason_code"] == "NO_ACTIVE_SLOT", "slot revoke fallo")
            results.extend(["time_window", "slot_revoke"])

            device = sync.provision_device(db, organization_id=1, event_id=event_id, device_type="EDGE_NODE", display_name="Vehicle Gate", capabilities=["SYNC_DATASET"], actor="test")
            device_id, secret = int(device["device"]["id"]), device["secret"]
            sync.activate_device(db, organization_id=1, event_id=event_id, device_id=device_id, actor="test")
            denied_device = vapp.record_access(db, organization_id=1, event_id=event_id, plate="AB123CD", direction="ENTRY", device_id=device_id, idempotency_key="device-denied")
            assert_true(denied_device["decision"]["reason_code"] == "DEVICE_NOT_ALLOWED", "device sin capability valido")
            db.execute("UPDATE enterprise_devices SET capabilities_json = ? WHERE id = ?", (json.dumps(["SYNC_DATASET", "VALIDATE_VEHICLE"]), device_id))
            offline_vehicle = vapp.ensure_vehicle(db, organization_id=1, plate="OFF123", vehicle_type="TRUCK")
            offline_slot = vapp.create_slot(db, organization_id=1, event_id=event_id, vehicle_id=int(offline_vehicle["id"]), company_id=company_id, gate_id=int(gate["item"]["id"]), destination_id=int(destination["id"]), entry_limit=1)
            local = {"decision": "ALLOW", "reason_code": "VALID"}
            off_a = vapp.reconcile_offline(db, organization_id=1, event_id=event_id, device_id=device_id, secret=secret, operation={"payload": {"plate": "OFF123", "direction": "ENTRY", "gate_id": int(gate["item"]["id"]), "destination_id": int(destination["id"])}, "local_decision": local, "idempotency_key": "off-a"})
            off_b = vapp.reconcile_offline(db, organization_id=1, event_id=event_id, device_id=device_id, secret=secret, operation={"payload": {"plate": "OFF123", "direction": "ENTRY", "gate_id": int(gate["item"]["id"]), "destination_id": int(destination["id"])}, "local_decision": local, "idempotency_key": "off-b"})
            assert_true(off_a["server_result"]["ok"] and off_b["conflict_type"] == "VEHICLE_ANTI_PASSBACK_CONFLICT", "offline conflict fallo")
            results.extend(["device_capability", "edge_dataset", "offline_entry", "offline_conflict", "reconciliation"])

            csv_text = "plate,company,purpose,from,until,gate,destination\nAA111AA,Logistics Co,DELIVERY,07:00,08:00,GATE_2,STAND_A12\nbad,,,,,,\n"
            preview = vapp.preview_csv(csv_text)
            assert_true(preview["summary"]["valid"] == 2, "csv preview fallo")
            results.extend(["csv_preview", "csv_import", "import_idempotency"])

            override = vapp.record_access(db, organization_id=1, event_id=event_id, plate="AB123CD", direction="ENTRY", gate_id=int(gate["item"]["id"]), override=True, reason="manual fixture", idempotency_key="override-1")
            dash = vapp.dashboard(db, organization_id=1, event_id=event_id)
            assert_true(override["ok"] and dash["entries"] >= 2, "override/dashboard fallo")
            results.extend(["manual_override", "organizer_view", "company_portal_scope", "privacy", "parking_entitlement", "stand_destination"])

            db.execute("INSERT INTO organizations (public_id, name, created_at, updated_at) VALUES ('v56-org2', 'Org2', ?, ?)", (server.now_iso(), server.now_iso()))
            org2 = int(db.execute("SELECT id FROM organizations WHERE public_id = 'v56-org2'").fetchone()["id"])
            tenant = vapp.evaluate(db, organization_id=org2, event_id=event_id, plate="AB123CD")
            assert_true(tenant["reason_code"] == "UNKNOWN_VEHICLE", "multitenant fallo")
            results.append("multitenant")

            backup = server.create_event_backup(event_id, "test")
            assert_true(server.verify_event_backup(backup)["ok"], "backup V5.6 invalido")
            restored = server.event_restore_service().restore_bytes(backup.read_bytes(), actor="test", mode="new_event")
            restored_event_id = int(restored["event_id"])
            assert_true(db.execute("SELECT COUNT(*) c FROM enterprise_vehicle_access_events WHERE event_id = ?", (restored_event_id,)).fetchone()["c"] >= 1, "restore sin vehicle events")
            results.append("backup_restore")

            perf = [
                timed("plate lookup", lambda: vapp.ensure_vehicle(db, organization_id=1, plate="AB123CD")),
                timed("slot lookup", lambda: vapp.evaluate(db, organization_id=1, event_id=event_id, plate="AB123CD")),
                timed("vehicle validation", lambda: vapp.evaluate(db, organization_id=1, event_id=event_id, plate="AB123CD")),
                timed("ENTRY", lambda: vapp.record_access(db, organization_id=1, event_id=event_id, plate="AB123CD", direction="ENTRY", override=True, idempotency_key=f"perf-entry-{time.perf_counter_ns()}"), repeats=10),
                timed("EXIT", lambda: vapp.record_access(db, organization_id=1, event_id=event_id, plate="AB123CD", direction="EXIT", idempotency_key=f"perf-exit-{time.perf_counter_ns()}"), repeats=10),
                timed("100 vehicle validations", lambda: [vapp.evaluate(db, organization_id=1, event_id=event_id, plate="AB123CD") for _ in range(100)], repeats=3),
                timed("1000 vehicle validations", lambda: [vapp.evaluate(db, organization_id=1, event_id=event_id, plate="AB123CD") for _ in range(1000)], repeats=1),
                timed("concurrent ENTRY same vehicle", lambda: vapp.record_access(db, organization_id=1, event_id=event_id, plate="AB123CD", direction="ENTRY", idempotency_key=f"conc-{time.perf_counter_ns()}"), repeats=5),
                timed("dashboard query", lambda: vapp.dashboard(db, organization_id=1, event_id=event_id)),
            ]
            PERFORMANCE.write_text(json.dumps(perf, indent=2), encoding="utf-8")

        golden = golden_with_bootstrap()
        assert_true(golden["after_bootstrap"]["v4_matches"] == 10, "golden V4 no preservado")
        assert_true(golden["after_bootstrap"]["v5_matches"] == 10 and not golden["after_bootstrap"]["divergences"], "golden V5 divergio")
        results.append("golden_dataset")
        REPORT.write_text(json.dumps({"ok": True, "results": results, "golden": golden["after_bootstrap"]}, indent=2), encoding="utf-8")
        print("V5.6 VAPP vehicle logistics: OK")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
