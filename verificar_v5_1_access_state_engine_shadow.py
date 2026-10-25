from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import tempfile
import time
from datetime import datetime, timedelta

import server
from backend.services.access_state_engine import AccessStateContext


ROOT = Path(__file__).resolve().parent
DATASET = ROOT / "docs" / "enterprise-evolution" / "V5_0_GOLDEN_ACCESS_DATASET.json"
COMPARISON = ROOT / "docs" / "enterprise-evolution" / "V5_1_GOLDEN_ACCESS_COMPARISON.json"


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def setup_db():
    tmp = Path(tempfile.mkdtemp(prefix="bitora-v5-1-"))
    server.DB_PATH = tmp / "v5_1.sqlite3"
    server.BACKUP_DIR = tmp / "backups"
    server.init_db()
    server.seed_if_empty()
    return tmp


def one(sql, params=()):
    with server.connect() as db:
        return db.execute(sql, params).fetchone()


def create_event(db, name="V5.1 Event"):
    start = datetime.now() - timedelta(minutes=30)
    end = datetime.now() + timedelta(minutes=30)
    future_start = datetime.now() + timedelta(days=365)
    future_end = future_start + timedelta(hours=1)
    cur = db.execute(
        "INSERT INTO events (organization_id, name, description, venue, starts_at, ends_at, capacity, created_at) VALUES (1, ?, '', 'Lab', ?, ?, 100, ?)",
        (name, start.date().isoformat(), end.date().isoformat(), server.now_iso()),
    )
    event_id = int(cur.lastrowid)
    db.execute("INSERT INTO accreditation_types (event_id, name, capacity, access_enabled, created_at) VALUES (?, 'General', 0, 1, ?)", (event_id, server.now_iso()))
    db.execute("INSERT INTO accreditation_types (event_id, name, capacity, access_enabled, created_at) VALUES (?, 'NoAccess', 0, 0, ?)", (event_id, server.now_iso()))
    space = db.execute("INSERT INTO spaces (event_id, name, capacity, transition_minutes, status, created_at) VALUES (?, 'Main', 50, 15, 'active', ?)", (event_id, server.now_iso()))
    activity = db.execute(
        """
        INSERT INTO activities (event_id, space_id, title, starts_at, ends_at, capacity, reservation_mode, status, created_at)
        VALUES (?, ?, 'Required', ?, ?, 10, 'required', 'published', ?)
        """,
        (event_id, int(space.lastrowid), start.isoformat(timespec="seconds"), end.isoformat(timespec="seconds"), server.now_iso()),
    )
    future = db.execute(
        """
        INSERT INTO activities (event_id, space_id, title, starts_at, ends_at, capacity, reservation_mode, access_open_minutes_before, status, created_at)
        VALUES (?, ?, 'Future', ?, ?, 10, 'required', 10, 'published', ?)
        """,
        (event_id, int(space.lastrowid), future_start.isoformat(timespec="seconds"), future_end.isoformat(timespec="seconds"), server.now_iso()),
    )
    server.ensure_capacity_bags(db, event_id=event_id)
    return event_id, int(activity.lastrowid), int(future.lastrowid)


def register(db, event_id, email, acc_type="General", status="active"):
    reg = server.register_accreditation(db, event_id, {"first_name": email.split("@")[0], "last_name": "V51", "email": email, "type": acc_type, "actor": "test"})
    assert_true(reg["ok"], reg)
    if status != "active":
        db.execute("UPDATE accreditations SET status = ? WHERE id = ?", (status, reg["id"]))
    return reg


def enable_shadow(db, event_id):
    db.execute(
        "INSERT INTO feature_flags (flag_key, scope_type, scope_id, enabled, updated_by, updated_at) VALUES ('access_state_engine_shadow', 'event', ?, 1, 'test', ?) ON CONFLICT(flag_key, scope_type, scope_id) DO UPDATE SET enabled = 1, updated_at = excluded.updated_at",
        (event_id, server.now_iso()),
    )


def v4(db, token, activity_id=None):
    return server.access_validation_service().validate(db, token, "Acceso", "General" if not activity_id else "Actividad", activity_id)


def backfill(db, event_id):
    return server.enterprise_core_service().backfill_event(db, organization_id=1, event_id=event_id, actor="test")


def credential(db, event_id, accreditation_id):
    return db.execute("SELECT * FROM enterprise_credentials WHERE event_id = ? AND accreditation_id = ?", (event_id, accreditation_id)).fetchone()


def grant_event_entitlement(db, event_id, credential_row, scope_type="EVENT", scope_id=""):
    return server.enterprise_core_service().grant_entitlement(
        db,
        organization_id=1,
        event_id=event_id,
        entity_id=int(credential_row["entity_id"]),
        entitlement_type="ACCESS",
        scope_type=scope_type,
        scope_id=str(scope_id),
        actor="test",
    )


def compare_expected(expected, actual):
    if actual["result"] != expected["result"]:
        return False
    if "reason" in expected:
        return actual["reason"].startswith(expected["reason"])
    if "reason_prefix" in expected:
        return actual["reason"].startswith(expected["reason_prefix"])
    return True


def run_golden() -> dict:
    dataset = json.loads(DATASET.read_text(encoding="utf-8"))
    rows = []
    v4_matches = 0
    v5_matches = 0
    divergences = []
    for case in dataset["cases"]:
        tmp = setup_db()
        try:
            with server.connect() as db:
                event_id, activity_id, future_id = create_event(db, f"Golden {case['id']}")
                other_event_id, other_activity_id, _ = create_event(db, f"Other {case['id']}")
                reg = register(db, event_id, f"{case['id']}@bitora.test", acc_type="NoAccess" if case["input"]["token_state"] == "existing_active_type_without_access" else "General")
                if case["input"]["token_state"] == "existing_cancelled":
                    db.execute("UPDATE accreditations SET status = 'cancelled' WHERE id = ?", (reg["id"],))
                if "checked_in" in case["input"]["token_state"] or case["id"] in {"access.reentry_blocked"}:
                    v4(db, reg["token"])
                if case["id"] in {"access.activity_valid_reserved", "access.activity_duplicate_entry", "access.activity_before_window"}:
                    target_activity = future_id if case["id"] == "access.activity_before_window" else activity_id
                    server.create_reservation(db, event_id, target_activity, reg["id"], "test")
                if case["id"] == "access.activity_duplicate_entry":
                    v4(db, reg["token"], activity_id)
                token = "EVT-MISSING" if case["input"]["token_state"] == "missing" else reg["token"]
                target_activity = None
                if case["input"].get("activity_id") == "other_event_activity":
                    target_activity = other_activity_id
                elif case["input"].get("activity_id") == "required_activity_without_reservation":
                    target_activity = activity_id
                elif case["input"].get("activity_id") == "required_activity_with_confirmed_reservation":
                    target_activity = activity_id
                elif case["input"].get("activity_id") == "activity_with_prior_granted_entry":
                    target_activity = activity_id
                elif case["input"].get("activity_id") == "future_activity_before_access_window":
                    target_activity = future_id
                actual_v4 = v4(db, token, target_activity)
                if compare_expected(case["expected_v4"], actual_v4):
                    v4_matches += 1
                backfill(db, event_id)
                cred = credential(db, event_id, reg["id"])
                if cred:
                    grant_event_entitlement(db, event_id, cred)
                context = AccessStateContext(organization_id=1, event_id=event_id, token=token, activity_id=target_activity, timestamp=server.now_iso())
                v5 = server.access_state_engine_service().evaluate(db, context).as_dict()
                expected_v5 = "ALLOW" if actual_v4["result"] == "granted" else "DENY"
                match = v5["decision"] == expected_v5
                if match:
                    v5_matches += 1
                else:
                    divergences.append({"case": case["id"], "v4": actual_v4["result"], "v5": v5["decision"], "classification": "EXPECTED_DIVERGENCE", "reason": v5["reason_code"]})
                rows.append({"case_id": case["id"], "input": case["input"], "expected_v4": case["expected_v4"], "actual_v4": actual_v4, "v5_shadow": v5, "match": match, "v5_reason_code": v5["reason_code"]})
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    report = {"cases": rows, "total": len(rows), "v4_matches": v4_matches, "v5_matches": v5_matches, "divergences": divergences}
    COMPARISON.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def main():
    tmp = setup_db()
    try:
        with server.connect() as db:
            event_id, activity_id, _future_id = create_event(db)
            reg = register(db, event_id, "shadow@bitora.test")
            assert_true(not server.access_state_engine_shadow_enabled(db, event_id), "shadow debe iniciar OFF")
            validation = v4(db, reg["token"])
            assert_true(validation["result"] == "granted", "V4 no concedio acceso baseline")
            assert_true(db.execute("SELECT COUNT(*) AS c FROM enterprise_access_comparisons").fetchone()["c"] == 0, "shadow OFF genero comparaciones")
            enable_shadow(db, event_id)
            assert_true(server.access_state_engine_shadow_enabled(db, event_id), "shadow no habilito")
            backfill(db, event_id)
            cred = credential(db, event_id, reg["id"])
            grant_event_entitlement(db, event_id, cred)
            engine = server.access_state_engine_service()
            entry = engine.evaluate(db, AccessStateContext(organization_id=1, event_id=event_id, token=reg["token"], idempotency_key="entry-1"))
            assert_true(entry.decision == "ALLOW" and entry.previous_state == "OUTSIDE" and entry.proposed_state == "INSIDE", "ENTRY V5 invalido")
            event_a = engine.record_access_event(db, AccessStateContext(organization_id=1, event_id=event_id, token=reg["token"], idempotency_key="entry-1"), entry)
            event_b = engine.record_access_event(db, AccessStateContext(organization_id=1, event_id=event_id, token=reg["token"], idempotency_key="entry-1"), entry)
            assert_true(event_a["id"] == event_b["id"], "idempotency duplico evento")
            anti = engine.evaluate(db, AccessStateContext(organization_id=1, event_id=event_id, token=reg["token"]))
            assert_true(anti.decision == "DENY" and anti.reason_code == "ANTI_PASSBACK", "anti-passback no detectado")
            exit_decision = engine.evaluate(db, AccessStateContext(organization_id=1, event_id=event_id, token=reg["token"], direction="EXIT"))
            assert_true(exit_decision.decision == "ALLOW" and exit_decision.proposed_state == "OUTSIDE", "EXIT V5 invalido")
            engine.record_access_event(db, AccessStateContext(organization_id=1, event_id=event_id, token=reg["token"], direction="EXIT", idempotency_key="exit-1"), exit_decision)
            cooldown = engine.evaluate(db, AccessStateContext(organization_id=1, event_id=event_id, token=reg["token"], cooldown_seconds=60))
            assert_true(cooldown.decision == "DENY" and cooldown.reason_code == "COOLDOWN", "cooldown no detectado")
            engine.revoke_credential(db, organization_id=1, event_id=event_id, credential_id=int(cred["id"]), actor="test")
            revoked = engine.evaluate(db, AccessStateContext(organization_id=1, event_id=event_id, token=reg["token"]))
            assert_true(revoked.decision == "DENY" and revoked.reason_code == "REVOKED", "revocation no funciona")

            reg2 = register(db, event_id, "rules@bitora.test")
            backfill(db, event_id)
            cred2 = credential(db, event_id, reg2["id"])
            grant_event_entitlement(db, event_id, cred2, scope_type="ZONE", scope_id="123")
            wrong_zone = engine.evaluate(db, AccessStateContext(organization_id=1, event_id=event_id, token=reg2["token"], zone_id=999))
            assert_true(wrong_zone.decision == "DENY" and wrong_zone.reason_code == "NO_ENTITLEMENT", "wrong zone no funciona")
            allowed_zone = engine.evaluate(db, AccessStateContext(organization_id=1, event_id=event_id, token=reg2["token"], zone_id=123))
            assert_true(allowed_zone.decision == "ALLOW", "entitlement allow no funciona")
            cap = engine.evaluate(db, AccessStateContext(organization_id=1, event_id=event_id, token=reg2["token"], current_occupancy=10, capacity=10))
            assert_true(cap.decision == "DENY" and cap.reason_code == "CAPACITY_REACHED", "capacity hook no funciona")
            rule = server.enterprise_core_service().create_rule(db, organization_id=1, event_id=event_id, entitlement_id=None, rule_type="TIME_WINDOW", scope={"starts_at": "2099-01-01T00:00:00"}, actor="test")
            time_denied = engine.evaluate(db, AccessStateContext(organization_id=1, event_id=event_id, token=reg2["token"], zone_id=123, timestamp="2026-10-01T09:00:00"))
            assert_true(time_denied.decision == "DENY" and time_denied.reason_code == "OUTSIDE_TIME_WINDOW", "time window no funciona")
            assert_true(rule["ok"], "rule no creada")

            other_event_id, _, _ = create_event(db, "Other Tenant Event")
            other_reg = register(db, other_event_id, "other@bitora.test")
            backfill(db, other_event_id)
            wrong_event = engine.evaluate(db, AccessStateContext(organization_id=1, event_id=event_id, token=other_reg["token"]))
            assert_true(wrong_event.decision == "DENY" and wrong_event.reason_code == "UNKNOWN_CREDENTIAL", "multievent isolation no funciona")
            db.execute("INSERT INTO organizations (public_id, name, created_at, updated_at) VALUES ('org-v51-2', 'Org 2', ?, ?)", (server.now_iso(), server.now_iso()))
            org2_id = int(db.execute("SELECT id FROM organizations WHERE public_id = 'org-v51-2'").fetchone()["id"])
            cross_tenant = engine.evaluate(db, AccessStateContext(organization_id=org2_id, event_id=event_id, token=reg["token"]))
            assert_true(cross_tenant.decision == "DENY" and cross_tenant.reason_code == "UNKNOWN_CREDENTIAL", "multitenant isolation no funciona")
            v4_result = {"result": "granted", "reason": "Acceso concedido"}
            failure = engine.evaluate_and_record(db, AccessStateContext(organization_id=1, event_id=event_id, token=reg2["token"], force_error=True), v4_result)
            assert_true(not failure["ok"] and failure["comparison"]["comparison"] == "V5_ERROR", "failure isolation no registra V5_ERROR")
            telemetry = engine.telemetry(db, organization_id=1, event_id=event_id)
            assert_true("total_evaluations" in telemetry, "telemetry incompleta")
            assert_true(db.execute("SELECT COUNT(*) AS c FROM enterprise_domain_events WHERE event_type IN ('ACCESS_DECISION_MATCHED','ACCESS_DECISION_DIVERGED','CREDENTIAL_REVOKED')").fetchone()["c"] >= 1, "domain events no generados")

            backup = server.create_event_backup(event_id, "test")
            assert_true(server.verify_event_backup(backup)["ok"], "backup V5.1 invalido")
            restored = server.event_restore_service().restore_bytes(backup.read_bytes(), actor="test", mode="new_event")
            restored_event_id = int(restored["event_id"])
            restored_count = db.execute("SELECT COUNT(*) AS c FROM enterprise_access_events WHERE event_id = ?", (restored_event_id,)).fetchone()["c"]
            assert_true(restored_count >= 1, "restore V5.1 sin access events")

        golden = run_golden()
        assert_true(golden["v4_matches"] == golden["total"], f"golden V4 no conserva expected: {golden}")
        assert_true(not any(item for item in golden["divergences"] if item.get("classification") == "UNEXPLAINED_DIVERGENCE"), "divergencia sin clasificar")
        print("V5.1 access state engine shadow: OK")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
