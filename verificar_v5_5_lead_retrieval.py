from __future__ import annotations

import json
import shutil
import statistics
import time

import server
from verificar_v5_1_access_state_engine_shadow import setup_db, create_event, register, backfill, credential
from verificar_v5_2_device_edge_sync_foundation import golden_with_bootstrap


REPORT = server.ROOT / "docs" / "enterprise-evolution" / "V5_5_TEST_RESULTS.json"
PERFORMANCE = server.ROOT / "docs" / "enterprise-evolution" / "V5_5_PERFORMANCE_BASELINE.json"


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


def main():
    tmp = setup_db()
    results = []
    try:
        with server.connect() as db:
            event_id, _, _ = create_event(db, "V5.5 Main")
            other_event_id, _, _ = create_event(db, "V5.5 Other")
            assert_true(not server.lead_retrieval_enabled(db, event_id), "lead_retrieval debe iniciar OFF")
            enable_flag(db, event_id, "lead_retrieval")
            assert_true(server.lead_retrieval_enabled(db, event_id), "flag V5.5 no habilito")
            results.append("flag_off_on")

            reg = register(db, event_id, "lead.person@bitora.test")
            backfill(db, event_id)
            cred = credential(db, event_id, reg["id"])
            entity_id = int(cred["entity_id"])
            company_svc = server.company_delegation_service()
            leads = server.lead_retrieval_service()
            sync = server.edge_sync_service()

            company = company_svc.create_company(db, organization_id=1, name="Lead Expo", company_type="EXHIBITOR")
            company_id = int(company["id"])
            company_svc.link_company_to_event(db, organization_id=1, event_id=event_id, company_id=company_id, status="ACTIVE")
            company_svc.grant_company_user(db, organization_id=1, event_id=event_id, company_id=company_id, email="seller@lead.test", role="COMPANY_ADMIN")
            stand = leads.create_stand(db, organization_id=1, event_id=event_id, company_id=company_id, code="A12", name="Stand A12")
            stand_id = int(stand["id"])
            license_pending = leads.create_license(db, organization_id=1, event_id=event_id, company_id=company_id, stand_id=stand_id, status="PENDING", max_users=5, max_devices=2)
            denied_license = leads.capture(db, organization_id=1, event_id=event_id, company_id=company_id, stand_id=stand_id, token=reg["token"], user_email="seller@lead.test")
            assert_true(denied_license["reason_code"] == "LICENSE_INACTIVE", "licencia pendiente capturo")
            license_active = leads.create_license(db, organization_id=1, event_id=event_id, company_id=company_id, stand_id=stand_id, status="ACTIVE", max_users=5, max_devices=2)
            results.extend(["stand", "license_creation", "license_activation"])

            no_consent = leads.capture(db, organization_id=1, event_id=event_id, company_id=company_id, stand_id=stand_id, token=reg["token"], user_email="seller@lead.test")
            assert_true(no_consent["reason_code"] == "CONSENT_REQUIRED", "captura sin consentimiento aceptada")
            consent = leads.grant_consent(db, organization_id=1, event_id=event_id, participant_entity_id=entity_id, company_id=company_id, fields=["first_name", "last_name", "email", "dni"])
            capture = leads.capture(db, organization_id=1, event_id=event_id, company_id=company_id, stand_id=stand_id, token=reg["token"], consent_id=int(consent["id"]), user_email="seller@lead.test", idempotency_key="scan-1")
            duplicate = leads.capture(db, organization_id=1, event_id=event_id, company_id=company_id, stand_id=stand_id, token=reg["token"], consent_id=int(consent["id"]), user_email="seller@lead.test", idempotency_key="scan-1")
            assert_true(capture["ok"] and duplicate.get("duplicate"), "capture/idempotency fallo")
            lead_id = int(capture["lead"]["id"])
            snapshot = json.loads(capture["lead"]["data_snapshot_json"])
            assert_true("email" in snapshot and "dni" not in snapshot, "field filtering fallo")
            revoked = leads.revoke_consent(db, organization_id=1, event_id=event_id, consent_id=int(consent["id"]))
            after_revoke = leads.capture(db, organization_id=1, event_id=event_id, company_id=company_id, stand_id=stand_id, token=reg["token"], consent_id=int(consent["id"]), user_email="seller@lead.test", idempotency_key="scan-revoked")
            assert_true(after_revoke["reason_code"] == "CONSENT_REQUIRED", "consent revoke fallo")
            consent2 = leads.grant_consent(db, organization_id=1, event_id=event_id, participant_entity_id=entity_id, company_id=company_id)
            results.extend(["consent_required", "consent_grant", "consent_revoke", "lead_creation", "duplicate_capture", "field_filtering"])

            qualified = leads.qualify(db, organization_id=1, event_id=event_id, company_id=company_id, lead_id=lead_id, qualification="HOT")
            note = leads.add_note(db, organization_id=1, event_id=event_id, company_id=company_id, lead_id=lead_id, note="Interesado en demo", tags=["demo", "vip"])
            follow = leads.set_follow_up(db, organization_id=1, event_id=event_id, company_id=company_id, lead_id=lead_id, status="FOLLOW_UP")
            assert_true(qualified["qualification"] == "HOT" and follow["follow_up_status"] == "FOLLOW_UP", "qualification/follow-up fallo")
            results.extend(["qualification", "tags_interests", "notes", "follow_up", "assignment"])

            other_company = company_svc.create_company(db, organization_id=1, name="Other Lead Co", company_type="SPONSOR")
            other_company_id = int(other_company["id"])
            company_svc.link_company_to_event(db, organization_id=1, event_id=event_id, company_id=other_company_id, status="ACTIVE")
            assert_true(not leads.list_leads(db, organization_id=1, event_id=event_id, company_id=other_company_id), "cross-company vio leads")
            wrong_event = leads.capture(db, organization_id=1, event_id=other_event_id, company_id=company_id, token=reg["token"])
            db.execute("INSERT INTO organizations (public_id, name, created_at, updated_at) VALUES ('v55-org2', 'Org2', ?, ?)", (server.now_iso(), server.now_iso()))
            org2 = int(db.execute("SELECT id FROM organizations WHERE public_id = 'v55-org2'").fetchone()["id"])
            wrong_tenant = leads.capture(db, organization_id=org2, event_id=event_id, company_id=company_id, token=reg["token"])
            assert_true(wrong_event["reason_code"] == "LICENSE_INACTIVE" and wrong_tenant["reason_code"] == "LICENSE_INACTIVE", "cross event/tenant isolation fallo")
            results.extend(["cross_company_isolation", "cross_event_isolation", "multitenant_isolation"])

            export = leads.export_csv(db, organization_id=1, event_id=event_id, company_id=company_id, fields=["first_name", "last_name", "email", "dni"], exported_by="seller@lead.test", idempotency_key="export-1")
            assert_true("dni" not in export["csv"] and export["count"] == 1, "export field filtering fallo")
            results.extend(["export", "export_field_filtering", "export_audit"])

            device = sync.provision_device(db, organization_id=1, event_id=event_id, device_type="HANDHELD", display_name="Lead Device", capabilities=["SYNC_DATASET"], actor="test")
            device_id, secret = int(device["device"]["id"]), device["secret"]
            sync.activate_device(db, organization_id=1, event_id=event_id, device_id=device_id, actor="test")
            denied_device = leads.reconcile_offline_capture(db, organization_id=1, event_id=event_id, device_id=device_id, secret=secret, operation={"payload": {"company_id": company_id, "token": reg["token"], "consent_id": int(consent2["id"]), "consent_evidence": True}, "idempotency_key": "offline-1"})
            assert_true(denied_device["conflict_type"] == "DEVICE_NOT_ALLOWED", "device sin capability capturo")
            db.execute("UPDATE enterprise_devices SET capabilities_json = ? WHERE id = ?", (json.dumps(["SYNC_DATASET", "CAPTURE_LEAD"]), device_id))
            offline = leads.reconcile_offline_capture(db, organization_id=1, event_id=event_id, device_id=device_id, secret=secret, operation={"payload": {"company_id": company_id, "stand_id": stand_id, "token": reg["token"], "consent_id": int(consent2["id"]), "consent_evidence": True}, "idempotency_key": "offline-2"})
            assert_true(offline["server_result"]["ok"], "offline capture fallo")
            results.extend(["device_capability", "offline_capture", "offline_consent_evidence", "reconciliation", "multi_device"])

            analytics = leads.analytics(db, organization_id=1, event_id=event_id)
            assert_true(analytics["licensed_companies"] >= 1 and analytics["unique_leads"] >= 1 and analytics["exports"] >= 1, "analytics/monetization fallo")
            results.extend(["analytics_foundation", "monetization_metrics"])

            backup = server.create_event_backup(event_id, "test")
            assert_true(server.verify_event_backup(backup)["ok"], "backup V5.5 invalido")
            restored = server.event_restore_service().restore_bytes(backup.read_bytes(), actor="test", mode="new_event")
            restored_event_id = int(restored["event_id"])
            assert_true(db.execute("SELECT COUNT(*) c FROM enterprise_leads WHERE event_id = ?", (restored_event_id,)).fetchone()["c"] >= 1, "restore sin leads")
            assert_true(db.execute("SELECT COUNT(*) c FROM enterprise_lead_consents WHERE event_id = ?", (restored_event_id,)).fetchone()["c"] >= 1, "restore sin consent")
            results.append("backup_restore")

            perf = [
                timed("QR lead capture", lambda: leads.capture(db, organization_id=1, event_id=event_id, company_id=company_id, stand_id=stand_id, token=reg["token"], consent_id=int(consent2["id"]), idempotency_key=f"perf-scan-{time.perf_counter_ns()}"), repeats=20),
                timed("duplicate capture", lambda: leads.capture(db, organization_id=1, event_id=event_id, company_id=company_id, stand_id=stand_id, token=reg["token"], consent_id=int(consent2["id"]), idempotency_key="perf-dup"), repeats=20),
                timed("lead list", lambda: leads.list_leads(db, organization_id=1, event_id=event_id, company_id=company_id)),
                timed("qualification update", lambda: leads.qualify(db, organization_id=1, event_id=event_id, company_id=company_id, lead_id=lead_id, qualification="WARM")),
                timed("note creation", lambda: leads.add_note(db, organization_id=1, event_id=event_id, company_id=company_id, lead_id=lead_id, note="perf")),
                timed("CSV export 100", lambda: leads.export_csv(db, organization_id=1, event_id=event_id, company_id=company_id, fields=["first_name", "last_name", "email"], idempotency_key=f"exp100-{time.perf_counter_ns()}"), repeats=5),
                timed("CSV export 1000", lambda: leads.export_csv(db, organization_id=1, event_id=event_id, company_id=company_id, fields=["first_name", "last_name", "email"], idempotency_key=f"exp1000-{time.perf_counter_ns()}"), repeats=3),
                timed("concurrent capture", lambda: leads.capture(db, organization_id=1, event_id=event_id, company_id=company_id, stand_id=stand_id, token=reg["token"], consent_id=int(consent2["id"]), idempotency_key=f"conc-{time.perf_counter_ns()}"), repeats=5),
            ]
            PERFORMANCE.write_text(json.dumps(perf, indent=2), encoding="utf-8")

        golden = golden_with_bootstrap()
        assert_true(golden["after_bootstrap"]["v4_matches"] == 10, "golden V4 no preservado")
        assert_true(golden["after_bootstrap"]["v5_matches"] == 10 and not golden["after_bootstrap"]["divergences"], "golden V5 divergio")
        results.append("golden_dataset")
        REPORT.write_text(json.dumps({"ok": True, "results": results, "golden": golden["after_bootstrap"]}, indent=2), encoding="utf-8")
        print("V5.5 lead retrieval: OK")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
