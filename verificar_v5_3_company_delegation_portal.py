from __future__ import annotations

import json
import shutil
import statistics
import time

import server
from backend.services.company_delegation import CompanyDelegationError
from verificar_v5_1_access_state_engine_shadow import setup_db, create_event, register, backfill
from verificar_v5_2_device_edge_sync_foundation import golden_with_bootstrap


REPORT = server.ROOT / "docs" / "enterprise-evolution" / "V5_3_TEST_RESULTS.json"
PERFORMANCE = server.ROOT / "docs" / "enterprise-evolution" / "V5_3_PERFORMANCE_BASELINE.json"


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def enable_flag(db, event_id, flag):
    db.execute(
        "INSERT INTO feature_flags (flag_key, scope_type, scope_id, enabled, updated_by, updated_at) VALUES (?, 'event', ?, 1, 'test', ?) ON CONFLICT(flag_key, scope_type, scope_id) DO UPDATE SET enabled = 1, updated_at = excluded.updated_at",
        (flag, event_id, server.now_iso()),
    )


def timed(label, fn, repeats=20):
    values = []
    errors = 0
    for _ in range(repeats):
        start = time.perf_counter()
        try:
            fn()
        except Exception:
            errors += 1
        values.append((time.perf_counter() - start) * 1000)
    return {
        "operation": label,
        "median_ms": round(statistics.median(values), 3),
        "p95_ms": round(sorted(values)[max(0, int(len(values) * 0.95) - 1)], 3),
        "errors": errors,
        "environment": "local SQLite temp DB",
    }


def main():
    tmp = setup_db()
    results = []
    try:
        with server.connect() as db:
            event_id, _, _ = create_event(db, "V5.3 Main")
            other_event_id, _, _ = create_event(db, "V5.3 Other")
            assert_true(not server.delegations_enabled(db, event_id), "delegations debe iniciar OFF")
            assert_true(not server.company_portal_enabled(db, event_id), "company_portal debe iniciar OFF")
            results.append("flags_off")
            enable_flag(db, event_id, "delegations")
            enable_flag(db, event_id, "company_portal")
            assert_true(server.delegations_enabled(db, event_id) and server.company_portal_enabled(db, event_id), "flags V5.3 no habilitaron")
            svc = server.company_delegation_service()

            company = svc.create_company(db, organization_id=1, name="Expo Company", company_type="EXHIBITOR", actor="test")
            company_id = int(company["id"])
            participation = svc.link_company_to_event(db, organization_id=1, event_id=event_id, company_id=company_id, status="ACTIVE", approval_mode="REQUIRES_APPROVAL", actor="test")
            delegation = svc.create_delegation(db, organization_id=1, event_id=event_id, company_id=company_id, name="Equipo expositor", actor="test")
            delegation_id = int(delegation["id"])
            assert_true(participation["entity_id"] and delegation["entity_id"], "company/delegation sin enterprise entity")
            results.extend(["company_creation", "event_participation", "delegation_creation"])

            total_quota = svc.set_quota(db, organization_id=1, event_id=event_id, company_id=company_id, delegation_id=delegation_id, quota_type="TOTAL", allocated=10, actor="test")
            assert_true(total_quota["available"] == 10, "quota inicial invalida")
            one = svc.consume_quota(db, organization_id=1, event_id=event_id, company_id=company_id, delegation_id=delegation_id, quota_type="TOTAL")
            assert_true(one["consumed"] == 1 and one["available"] == 9, "quota consumption fallo")
            race_quota = svc.set_quota(db, organization_id=1, event_id=event_id, company_id=company_id, quota_type="PRESS", allocated=1)
            svc.consume_quota(db, organization_id=1, event_id=event_id, company_id=company_id, quota_type="PRESS")
            try:
                svc.consume_quota(db, organization_id=1, event_id=event_id, company_id=company_id, quota_type="PRESS")
                raise AssertionError("quota concurrency permitio excedente")
            except CompanyDelegationError as exc:
                assert_true(exc.code == "QUOTA_EXCEEDED", "quota concurrency error incorrecto")
            results.extend(["quota_allocation", "quota_consumption", "quota_concurrency"])

            admin = svc.grant_company_user(db, organization_id=1, event_id=event_id, company_id=company_id, email="admin@expo.test", role="COMPANY_ADMIN", actor="test")
            viewer = svc.grant_company_user(db, organization_id=1, event_id=event_id, company_id=company_id, email="viewer@expo.test", role="VIEWER", actor="test")
            assert_true(svc.authorize_company_user(db, organization_id=1, event_id=event_id, company_id=company_id, email="admin@expo.test", permission="imports.manage"), "company admin no autorizado")
            assert_true(not svc.authorize_company_user(db, organization_id=1, event_id=event_id, company_id=company_id, email="viewer@expo.test", permission="imports.manage"), "viewer escalo permiso")
            assert_true(not svc.authorize_company_user(db, organization_id=1, event_id=other_event_id, company_id=company_id, email="admin@expo.test", permission="company.view"), "company user cruzo evento")
            results.extend(["company_user_auth", "company_scope", "event_scope"])

            invitation = svc.create_invitation(db, organization_id=1, event_id=event_id, company_id=company_id, delegation_id=delegation_id, email="guest@expo.test", quota_type="TOTAL", idempotency_key="invite-1")
            assert_true(invitation["token"] and invitation["token"] not in json.dumps(invitation["invitation"]), "token expuesto en payload persistente")
            repeat = svc.create_invitation(db, organization_id=1, event_id=event_id, company_id=company_id, delegation_id=delegation_id, email="guest@expo.test", quota_type="TOTAL", idempotency_key="invite-1")
            assert_true(repeat.get("idempotent"), "invitation idempotency fallo")
            registered = svc.register_from_invitation(db, organization_id=1, token=invitation["token"], first_name="Guest", last_name="Expo", dni="53000001", email="guest@expo.test")
            assert_true(registered["person_id"] and registered["accreditation_id"], "registration from invitation fallo")
            approval = svc.submit_approval(db, organization_id=1, event_id=event_id, company_id=company_id, delegation_id=delegation_id, person_id=registered["person_id"], accreditation_id=registered["accreditation_id"])
            approved = svc.review_approval(db, organization_id=1, event_id=event_id, approval_id=int(approval["id"]), approve=True, reviewer="organizer")
            rejection = svc.submit_approval(db, organization_id=1, event_id=event_id, company_id=company_id, person_id=registered["person_id"], accreditation_id=registered["accreditation_id"])
            rejected = svc.review_approval(db, organization_id=1, event_id=event_id, approval_id=int(rejection["id"]), approve=False, reviewer="organizer", reason="fixture")
            assert_true(approved["status"] == "APPROVED" and rejected["status"] == "REJECTED", "approval workflow fallo")
            revoke_invite = svc.create_invitation(db, organization_id=1, event_id=event_id, company_id=company_id, delegation_id=delegation_id, email="revoke@expo.test", quota_type="TOTAL")
            revoked = svc.revoke_invitation(db, organization_id=1, event_id=event_id, invitation_id=int(revoke_invite["invitation"]["id"]), actor="test")
            assert_true(revoked["status"] == "REVOKED", "revocation fallo")
            results.extend(["invitation_creation", "invitation_idempotency", "registration_from_invitation", "approval", "rejection", "invitation_revocation"])

            csv_text = "first_name,last_name,email,dni,quota_type\nAna,Uno,ana.import@expo.test,531,TOTAL\nBob,Dos,bob.import@expo.test,532,TOTAL\nBad,Email,bad-email,533,TOTAL\n"
            preview = svc.preview_csv_import(db, organization_id=1, event_id=event_id, company_id=company_id, delegation_id=delegation_id, csv_text=csv_text)
            assert_true(len(preview["valid_rows"]) == 2 and preview["errors"], "csv validation fallo")
            import_csv = "first_name,last_name,email,dni,quota_type\nAna,Uno,ana.import@expo.test,531,TOTAL\nBob,Dos,bob.import@expo.test,532,TOTAL\n"
            imported = svc.confirm_csv_import(db, organization_id=1, event_id=event_id, company_id=company_id, delegation_id=delegation_id, csv_text=import_csv, import_id="import-1")
            duplicate = svc.confirm_csv_import(db, organization_id=1, event_id=event_id, company_id=company_id, delegation_id=delegation_id, csv_text=import_csv, import_id="import-1")
            assert_true(imported["summary"]["created"] == 2 and duplicate.get("idempotent"), "csv import/idempotency fallo")
            results.extend(["csv_validation", "csv_preview", "csv_import", "duplicate_import"])

            dashboard = svc.dashboard(db, organization_id=1, event_id=event_id, company_id=company_id)
            assert_true(dashboard["company"]["name"] == "Expo Company" and dashboard["people"] >= 3, "company dashboard fallo")
            other_company = svc.create_company(db, organization_id=1, name="Other Company", company_type="SPONSOR")
            svc.link_company_to_event(db, organization_id=1, event_id=event_id, company_id=int(other_company["id"]), status="ACTIVE")
            assert_true(not svc.authorize_company_user(db, organization_id=1, event_id=event_id, company_id=int(other_company["id"]), email="admin@expo.test", permission="company.view"), "cross-company isolation fallo")
            results.extend(["membership", "person_reuse", "accreditation_relationship", "company_portal_dashboard", "organizer_view", "cross_company_isolation"])

            domain_events = db.execute("SELECT COUNT(*) AS c FROM enterprise_domain_events WHERE event_id = ? AND event_type IN ('COMPANY_EVENT_LINKED','DELEGATION_MEMBER_REGISTERED')", (event_id,)).fetchone()["c"]
            audit_events = db.execute("SELECT COUNT(*) AS c FROM audit_logs WHERE event_id = ? OR entity_type LIKE 'enterprise_%'", (event_id,)).fetchone()["c"]
            assert_true(domain_events >= 2 and audit_events >= 1, "audit/domain events incompletos")
            results.extend(["audit", "domain_events"])

            backup = server.create_event_backup(event_id, "test")
            assert_true(server.verify_event_backup(backup)["ok"], "backup V5.3 invalido")
            restored = server.event_restore_service().restore_bytes(backup.read_bytes(), actor="test", mode="new_event")
            restored_event_id = int(restored["event_id"])
            assert_true(db.execute("SELECT COUNT(*) AS c FROM enterprise_companies c JOIN enterprise_company_event_participation p ON p.company_id = c.id WHERE p.event_id = ?", (restored_event_id,)).fetchone()["c"] >= 1, "restore sin companies")
            assert_true(db.execute("SELECT COUNT(*) AS c FROM enterprise_delegations WHERE event_id = ?", (restored_event_id,)).fetchone()["c"] >= 1, "restore sin delegations")
            results.append("backup_restore")

            backfill(db, event_id)
            assert_true(server.edge_sync_service().generate_dataset(db, organization_id=1, event_id=event_id)["ok"], "V5.2 edge dataset roto")
            svc.set_quota(db, organization_id=1, event_id=event_id, company_id=company_id, quota_type="TOTAL", allocated=100)

            perf = [
                timed("company dashboard", lambda: svc.dashboard(db, organization_id=1, event_id=event_id, company_id=company_id)),
                timed("people list", lambda: db.execute("SELECT * FROM enterprise_delegation_members WHERE organization_id = ? AND event_id = ? AND company_id = ?", (1, event_id, company_id)).fetchall()),
                timed("invitation creation", lambda: svc.create_invitation(db, organization_id=1, event_id=event_id, company_id=company_id, email=f"perf-{time.perf_counter_ns()}@expo.test", quota_type="TOTAL"), repeats=5),
                timed("quota check", lambda: svc.dashboard(db, organization_id=1, event_id=event_id, company_id=company_id)["quotas"]),
                timed("CSV 100 preview", lambda: svc.preview_csv_import(db, organization_id=1, event_id=event_id, company_id=company_id, csv_text=make_csv(100))),
                timed("CSV 1000 preview", lambda: svc.preview_csv_import(db, organization_id=1, event_id=event_id, company_id=company_id, csv_text=make_csv(1000)), repeats=5),
            ]
            PERFORMANCE.write_text(json.dumps(perf, indent=2), encoding="utf-8")

        golden = golden_with_bootstrap()
        assert_true(golden["after_bootstrap"]["v4_matches"] == 10, "golden V4 no preservado")
        assert_true(golden["after_bootstrap"]["v5_matches"] == 10 and not golden["after_bootstrap"]["divergences"], "golden V5 divergio")
        results.append("golden_dataset")
        REPORT.write_text(json.dumps({"ok": True, "results": results, "golden": golden["after_bootstrap"]}, indent=2), encoding="utf-8")
        print("V5.3 company and delegation portal foundation: OK")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def make_csv(rows: int) -> str:
    lines = ["first_name,last_name,email,dni,quota_type"]
    for index in range(rows):
        lines.append(f"Name{index},Last{index},bulk{index}@expo.test,{900000 + index},TOTAL")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
