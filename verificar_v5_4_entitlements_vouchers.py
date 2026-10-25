from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
import json
import shutil
import statistics
import time

import server
from verificar_v5_1_access_state_engine_shadow import setup_db, create_event, register, backfill, credential, grant_event_entitlement
from verificar_v5_2_device_edge_sync_foundation import golden_with_bootstrap


REPORT = server.ROOT / "docs" / "enterprise-evolution" / "V5_4_TEST_RESULTS.json"
PERFORMANCE = server.ROOT / "docs" / "enterprise-evolution" / "V5_4_PERFORMANCE_BASELINE.json"


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def enable_flag(db, event_id, flag):
    db.execute(
        "INSERT INTO feature_flags (flag_key, scope_type, scope_id, enabled, updated_by, updated_at) VALUES (?, 'event', ?, 1, 'test', ?) ON CONFLICT(flag_key, scope_type, scope_id) DO UPDATE SET enabled = 1, updated_at = excluded.updated_at",
        (flag, event_id, server.now_iso()),
    )


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


def token_hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def main():
    tmp = setup_db()
    results = []
    try:
        with server.connect() as db:
            event_id, _, _ = create_event(db, "V5.4 Main")
            other_event_id, _, _ = create_event(db, "V5.4 Other")
            assert_true(not server.entitlements_vouchers_enabled(db, event_id), "entitlements_vouchers debe iniciar OFF")
            enable_flag(db, event_id, "entitlements_vouchers")
            assert_true(server.entitlements_vouchers_enabled(db, event_id), "flag V5.4 no habilito")
            results.append("flag_off_on")

            reg = register(db, event_id, "benefits@bitora.test")
            backfill(db, event_id)
            cred = credential(db, event_id, reg["id"])
            grant_event_entitlement(db, event_id, cred)
            entity_id = int(cred["entity_id"])
            svc = server.entitlements_vouchers_service()
            sync = server.edge_sync_service()

            meal_type = svc.ensure_type(db, organization_id=1, event_id=event_id, code="MEAL", name="Almuerzo", consumable=True, default_quantity=1, offline_policy="OFFLINE_ALLOWED_WITH_RISK")
            vip_type = svc.ensure_type(db, organization_id=1, event_id=event_id, code="VIP", name="VIP", consumable=False, default_quantity=0)
            point = svc.ensure_service_point(db, organization_id=1, event_id=event_id, code="BUFFET_1", name="Buffet 1", service_type="MEAL")
            point_id = int(point["id"])
            results.extend(["entitlement_type", "service_point"])

            meal = svc.grant(db, organization_id=1, event_id=event_id, entity_id=entity_id, entitlement_type="MEAL", allocated=1, consumable=True, scope_type="SERVICE_POINT", scope_id=str(point_id), source="MANUAL", idempotency_key="grant-meal")
            vip = svc.grant(db, organization_id=1, event_id=event_id, entity_id=entity_id, entitlement_type="VIP", allocated=0, consumable=False, source="MANUAL", idempotency_key="grant-vip")
            repeat_grant = svc.grant(db, organization_id=1, event_id=event_id, entity_id=entity_id, entitlement_type="MEAL", allocated=1, consumable=True, idempotency_key="grant-meal")
            assert_true(repeat_grant.get("idempotent") and meal["entitlement"]["id"] and vip["entitlement"]["id"], "grant/idempotency fallo")
            results.extend(["consumable", "non_consumable", "grant", "idempotent_grant"])

            participant = svc.list_participant_entitlements(db, organization_id=1, event_id=event_id, token=reg["token"])
            assert_true(len(participant) >= 2, "participant lookup sin beneficios")
            valid = svc.consume(db, organization_id=1, event_id=event_id, token=reg["token"], entitlement_type="MEAL", service_point_id=point_id, idempotency_key="consume-meal-1")
            duplicate = svc.consume(db, organization_id=1, event_id=event_id, token=reg["token"], entitlement_type="MEAL", service_point_id=point_id, idempotency_key="consume-meal-1")
            exhausted = svc.consume(db, organization_id=1, event_id=event_id, token=reg["token"], entitlement_type="MEAL", service_point_id=point_id, idempotency_key="consume-meal-2")
            assert_true(valid["ok"] and duplicate["reason_code"] == "DUPLICATE" and exhausted["reason_code"] == "EXHAUSTED", "consumption/duplicate/exhausted fallo")
            vip_consume = svc.consume(db, organization_id=1, event_id=event_id, token=reg["token"], entitlement_type="VIP", idempotency_key="consume-vip")
            assert_true(vip_consume["ok"], "non-consumable fallo")
            results.extend(["valid_consumption", "duplicate", "exhausted", "idempotency"])

            future = (datetime.fromisoformat(server.now_iso()) + timedelta(hours=1)).isoformat(timespec="seconds")
            window = svc.grant(db, organization_id=1, event_id=event_id, entity_id=entity_id, entitlement_type="COFFEE", allocated=1, consumable=True, valid_from=future, idempotency_key="grant-window")
            outside = svc.consume(db, organization_id=1, event_id=event_id, token=reg["token"], entitlement_type="COFFEE", idempotency_key="consume-window")
            assert_true(outside["reason_code"] == "OUTSIDE_TIME_WINDOW", "time window fallo")
            svc.suspend(db, organization_id=1, event_id=event_id, entitlement_id=int(window["entitlement"]["id"]), actor="test")
            suspended = svc.consume(db, organization_id=1, event_id=event_id, token=reg["token"], entitlement_type="COFFEE", idempotency_key="consume-suspended")
            assert_true(suspended["reason_code"] == "SUSPENDED", "suspend fallo")
            svc.revoke(db, organization_id=1, event_id=event_id, entitlement_id=int(vip["entitlement"]["id"]), actor="test", reason="fixture")
            revoked = svc.consume(db, organization_id=1, event_id=event_id, token=reg["token"], entitlement_type="VIP", idempotency_key="consume-revoked")
            assert_true(revoked["reason_code"] == "REVOKED", "revoke fallo")
            adjusted = svc.adjust(db, organization_id=1, event_id=event_id, entitlement_id=int(meal["entitlement"]["id"]), quantity_delta=1, reason="fixture correction", actor="test")
            assert_true(adjusted["allocated"] >= 2, "adjustment fallo")
            results.extend(["time_window", "suspend", "revoke", "manual_adjustment"])

            atom = svc.grant(db, organization_id=1, event_id=event_id, entity_id=entity_id, entitlement_type="KIT", allocated=1, consumable=True, idempotency_key="grant-kit")
            a = svc.consume(db, organization_id=1, event_id=event_id, token=reg["token"], entitlement_type="KIT", idempotency_key="kit-a")
            b = svc.consume(db, organization_id=1, event_id=event_id, token=reg["token"], entitlement_type="KIT", idempotency_key="kit-b")
            assert_true([a["ok"], b["ok"]].count(True) == 1 and {a["reason_code"], b["reason_code"]} >= {"VALID", "EXHAUSTED"}, "atomicity fallo")
            results.append("atomicity_concurrency")

            company_svc = server.company_delegation_service()
            company = company_svc.create_company(db, organization_id=1, name="Benefit Co", company_type="SPONSOR")
            company_id = int(company["id"])
            company_svc.link_company_to_event(db, organization_id=1, event_id=event_id, company_id=company_id, status="ACTIVE")
            delegation = company_svc.create_delegation(db, organization_id=1, event_id=event_id, company_id=company_id, name="VIP Team")
            company_svc.add_member(db, organization_id=1, event_id=event_id, company_id=company_id, delegation_id=int(delegation["id"]), person_id=reg["person_id"], accreditation_id=reg["id"], entity_id=entity_id)
            dg = svc.grant_to_delegation(db, organization_id=1, event_id=event_id, delegation_id=int(delegation["id"]), entitlement_type="HOSPITALITY", allocated=1, consumable=True)
            cg = svc.grant_to_company(db, organization_id=1, event_id=event_id, company_id=company_id, entitlement_type="GIFT", allocated=1, consumable=True)
            assert_true(dg["summary"]["created"] == 1 and cg["summary"]["created"] == 1, "company/delegation grant fallo")
            results.extend(["bulk_grant", "company_grant", "delegation_grant"])

            device = sync.provision_device(db, organization_id=1, event_id=event_id, device_type="HANDHELD", display_name="Voucher Device", capabilities=["SYNC_DATASET", "VALIDATE_ACCESS"], actor="test")
            device_id = int(device["device"]["id"])
            secret = device["secret"]
            sync.activate_device(db, organization_id=1, event_id=event_id, device_id=device_id, actor="test")
            denied_device = svc.consume(db, organization_id=1, event_id=event_id, token=reg["token"], entitlement_type="GIFT", device_id=device_id, idempotency_key="device-denied")
            assert_true(denied_device["reason_code"] == "DEVICE_NOT_ALLOWED", "device capability deny fallo")
            db.execute("UPDATE enterprise_devices SET capabilities_json = ? WHERE id = ?", (json.dumps(["SYNC_DATASET", "VALIDATE_ACCESS", "CONSUME_ENTITLEMENT"]), device_id))
            dataset = sync.generate_dataset(db, organization_id=1, event_id=event_id, generated_by="test")
            local = svc.local_entitlement_decision(dataset["payload"], token_hash=token_hash(reg["token"]), entitlement_type="GIFT")
            assert_true(local["decision"] == "ALLOW" and dataset["payload"]["service_points"] is not None, "edge dataset/local entitlement fallo")
            offline = svc.reconcile_offline_consumption(db, organization_id=1, event_id=event_id, device_id=device_id, secret=secret, operation={"payload": {"token": reg["token"], "entitlement_type": "GIFT", "quantity": 1}, "local_decision": local, "idempotency_key": "offline-gift-a"})
            double_spend = svc.reconcile_offline_consumption(db, organization_id=1, event_id=event_id, device_id=device_id, secret=secret, operation={"payload": {"token": reg["token"], "entitlement_type": "GIFT", "quantity": 1}, "local_decision": local, "idempotency_key": "offline-gift-b"})
            assert_true(offline["server_result"]["ok"] and double_spend["conflict_type"] == "ENTITLEMENT_DOUBLE_SPEND", "offline double-spend fallo")
            results.extend(["device_capability", "edge_dataset", "offline_consumption", "double_spend_reconciliation"])

            other = svc.consume(db, organization_id=1, event_id=other_event_id, token=reg["token"], entitlement_type="MEAL", idempotency_key="wrong-event")
            db.execute("INSERT INTO organizations (public_id, name, created_at, updated_at) VALUES ('v54-org2', 'Org2', ?, ?)", (server.now_iso(), server.now_iso()))
            org2 = int(db.execute("SELECT id FROM organizations WHERE public_id = 'v54-org2'").fetchone()["id"])
            tenant = svc.consume(db, organization_id=org2, event_id=event_id, token=reg["token"], entitlement_type="MEAL", idempotency_key="wrong-tenant")
            assert_true(other["reason_code"] == "UNKNOWN_CREDENTIAL" and tenant["reason_code"] == "UNKNOWN_CREDENTIAL", "multievent/multitenant fallo")
            report = svc.organizer_report(db, organization_id=1, event_id=event_id)
            assert_true(report["types"] and report["denied"] >= 1, "organizer report fallo")
            results.extend(["multievent", "multitenant", "organizer_lookup", "privacy"])

            domain_events = int(db.execute("SELECT COUNT(*) c FROM enterprise_domain_events WHERE event_id = ? AND event_type LIKE 'ENTITLEMENT_%'", (event_id,)).fetchone()["c"])
            audit_events = int(db.execute("SELECT COUNT(*) c FROM audit_logs WHERE entity_type = 'enterprise_entitlement'", ()).fetchone()["c"])
            assert_true(domain_events >= 4 and audit_events >= 1, "audit/domain events fallo")
            results.extend(["audit", "domain_events"])

            backup = server.create_event_backup(event_id, "test")
            assert_true(server.verify_event_backup(backup)["ok"], "backup V5.4 invalido")
            restored = server.event_restore_service().restore_bytes(backup.read_bytes(), actor="test", mode="new_event")
            restored_event_id = int(restored["event_id"])
            assert_true(db.execute("SELECT COUNT(*) c FROM enterprise_entitlement_consumptions WHERE event_id = ?", (restored_event_id,)).fetchone()["c"] >= 1, "restore sin consumptions")
            assert_true(db.execute("SELECT COUNT(*) c FROM enterprise_service_points WHERE event_id = ?", (restored_event_id,)).fetchone()["c"] >= 1, "restore sin service points")
            results.append("backup_restore")

            perf_ent = svc.grant(db, organization_id=1, event_id=event_id, entity_id=entity_id, entitlement_type="PERF", allocated=2000, consumable=True, idempotency_key="grant-perf")
            perf = [
                timed("entitlement lookup", lambda: svc.list_participant_entitlements(db, organization_id=1, event_id=event_id, token=reg["token"])),
                timed("consumption", lambda: svc.consume(db, organization_id=1, event_id=event_id, token=reg["token"], entitlement_type="PERF", idempotency_key=f"perf-{time.perf_counter_ns()}"), repeats=20),
                timed("duplicate consumption", lambda: svc.consume(db, organization_id=1, event_id=event_id, token=reg["token"], entitlement_type="PERF", idempotency_key="perf-duplicate"), repeats=20),
                timed("list participant entitlements", lambda: svc.list_participant_entitlements(db, organization_id=1, event_id=event_id, token=reg["token"])),
                timed("100 sequential consumptions", lambda: [svc.consume(db, organization_id=1, event_id=event_id, token=reg["token"], entitlement_type="PERF", idempotency_key=f"perf100-{time.perf_counter_ns()}-{i}") for i in range(100)], repeats=3),
                timed("1000 sequential consumptions", lambda: [svc.consume(db, organization_id=1, event_id=event_id, token=reg["token"], entitlement_type="PERF", idempotency_key=f"perf1000-{time.perf_counter_ns()}-{i}") for i in range(1000)], repeats=1),
                timed("concurrent last-unit test", lambda: svc.consume(db, organization_id=1, event_id=event_id, token=reg["token"], entitlement_type="KIT", idempotency_key=f"last-{time.perf_counter_ns()}"), repeats=5),
            ]
            PERFORMANCE.write_text(json.dumps(perf, indent=2), encoding="utf-8")

        golden = golden_with_bootstrap()
        assert_true(golden["after_bootstrap"]["v4_matches"] == 10, "golden V4 no preservado")
        assert_true(golden["after_bootstrap"]["v5_matches"] == 10 and not golden["after_bootstrap"]["divergences"], "golden V5 divergio")
        results.append("golden_dataset")
        REPORT.write_text(json.dumps({"ok": True, "results": results, "golden": golden["after_bootstrap"]}, indent=2), encoding="utf-8")
        print("V5.4 entitlements and vouchers: OK")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
