from __future__ import annotations

from datetime import datetime, timedelta
import json
import shutil
import statistics
import time

import server
from verificar_v5_1_access_state_engine_shadow import setup_db, create_event, register, backfill, credential, grant_event_entitlement, run_golden


REPORT = server.ROOT / "docs" / "enterprise-evolution" / "V5_2_GOLDEN_ACCESS_COMPARISON.json"
PERFORMANCE = server.ROOT / "docs" / "enterprise-evolution" / "V5_2_PERFORMANCE_BASELINE.json"


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def enable_flag(db, event_id, flag):
    db.execute(
        "INSERT INTO feature_flags (flag_key, scope_type, scope_id, enabled, updated_by, updated_at) VALUES (?, 'event', ?, 1, 'test', ?) ON CONFLICT(flag_key, scope_type, scope_id) DO UPDATE SET enabled = 1, updated_at = excluded.updated_at",
        (flag, event_id, server.now_iso()),
    )


def token_hash(token):
    import hashlib
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def timed(label, fn, repeats=25):
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


def golden_with_bootstrap():
    base = run_golden()
    rows = []
    v4_matches = 0
    v5_matches = 0
    divergences = []
    dataset = json.loads((server.ROOT / "docs" / "enterprise-evolution" / "V5_0_GOLDEN_ACCESS_DATASET.json").read_text(encoding="utf-8"))
    for case in dataset["cases"]:
        tmp = setup_db()
        try:
            with server.connect() as db:
                event_id, activity_id, future_id = create_event(db, f"V52 {case['id']}")
                other_event_id, other_activity_id, _ = create_event(db, f"V52 Other {case['id']}")
                reg = register(db, event_id, f"v52-{case['id']}@bitora.test", acc_type="NoAccess" if case["input"]["token_state"] == "existing_active_type_without_access" else "General")
                if case["input"]["token_state"] == "existing_cancelled":
                    db.execute("UPDATE accreditations SET status = 'cancelled' WHERE id = ?", (reg["id"],))
                if "checked_in" in case["input"]["token_state"] or case["id"] in {"access.reentry_blocked"}:
                    server.access_validation_service().validate(db, reg["token"], "Acceso", "General")
                if case["id"] in {"access.activity_valid_reserved", "access.activity_duplicate_entry", "access.activity_before_window"}:
                    target = future_id if case["id"] == "access.activity_before_window" else activity_id
                    server.create_reservation(db, event_id, target, reg["id"], "test")
                if case["id"] == "access.activity_duplicate_entry":
                    server.access_validation_service().validate(db, reg["token"], "Acceso", "Actividad", activity_id)
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
                backfill(db, event_id)
                cred = credential(db, event_id, reg["id"])
                if cred:
                    grant_event_entitlement(db, event_id, cred)
                server.edge_sync_service().bootstrap_access_state_from_v4(db, organization_id=1, event_id=event_id)
                v5 = server.access_state_engine_service().evaluate(db, server.AccessStateContext(organization_id=1, event_id=event_id, token=token, activity_id=target_activity)).as_dict()
                actual_v4 = server.access_validation_service().validate(db, token, "Acceso", "Actividad" if target_activity else "General", target_activity)
                expected = case["expected_v4"]
                ok_v4 = actual_v4["result"] == expected["result"] and (actual_v4["reason"].startswith(expected.get("reason", expected.get("reason_prefix", ""))))
                v4_matches += 1 if ok_v4 else 0
                expected_v5 = "ALLOW" if actual_v4["result"] == "granted" else "DENY"
                match = v5["decision"] == expected_v5
                v5_matches += 1 if match else 0
                if not match:
                    divergences.append({"case": case["id"], "v4": actual_v4["result"], "v5": v5["decision"], "classification": "EXPECTED_DIVERGENCE", "reason": v5["reason_code"]})
                rows.append({"case_id": case["id"], "actual_v4": actual_v4, "v5_shadow": v5, "match": match})
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    report = {"before": {"v5_matches": base["v5_matches"], "divergences": base["divergences"]}, "after_bootstrap": {"total": len(rows), "v4_matches": v4_matches, "v5_matches": v5_matches, "divergences": divergences, "cases": rows}}
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def main():
    tmp = setup_db()
    try:
        with server.connect() as db:
            event_id, activity_id, _ = create_event(db, "V5.2 Main")
            assert_true(not server.device_identity_enabled(db, event_id), "device_identity debe iniciar OFF")
            assert_true(not server.edge_sync_enabled(db, event_id), "edge_sync debe iniciar OFF")
            enable_flag(db, event_id, "device_identity")
            enable_flag(db, event_id, "edge_sync")
            assert_true(server.device_identity_enabled(db, event_id) and server.edge_sync_enabled(db, event_id), "flags V5.2 no habilitaron")
            reg = register(db, event_id, "device-sync@bitora.test")
            backfill(db, event_id)
            cred = credential(db, event_id, reg["id"])
            grant_event_entitlement(db, event_id, cred)
            sync = server.edge_sync_service()
            provision = sync.provision_device(db, organization_id=1, event_id=event_id, device_type="EDGE_NODE", display_name="Edge Lab", capabilities=["SYNC_DATASET", "VALIDATE_ACCESS", "SCAN_QR"], software_version="v5.2-test", actor="test")
            device = provision["device"]
            secret = provision["secret"]
            assert_true(secret and secret not in json.dumps(device), "secreto expuesto en device payload")
            device_id = int(device["id"])
            sync.activate_device(db, organization_id=1, event_id=event_id, device_id=device_id, actor="test")
            assert_true(sync.authenticate_device(db, organization_id=1, event_id=event_id, device_id=device_id, secret=secret, capability="SYNC_DATASET").ok, "auth device fallo")
            assert_true(not sync.authenticate_device(db, organization_id=1, event_id=event_id, device_id=device_id, secret="bad", capability="SYNC_DATASET").ok, "auth invalida aceptada")
            assert_true(not sync.authenticate_device(db, organization_id=1, event_id=event_id, device_id=device_id, secret=secret, capability="PRINT_BADGE").ok, "capability no denegada")
            rotated = sync.rotate_credential(db, organization_id=1, event_id=event_id, device_id=device_id, actor="test")
            assert_true(not sync.authenticate_device(db, organization_id=1, event_id=event_id, device_id=device_id, secret=secret).ok, "secret viejo sigue activo")
            secret = rotated["secret"]
            dataset = sync.generate_dataset(db, organization_id=1, event_id=event_id, generated_by="test")
            revision = dataset["dataset"]["revision"]
            payload = dataset["payload"]
            assert_true(payload["credentials"] and "email" not in json.dumps(payload).lower(), "dataset expone PII innecesaria")
            local = sync.local_access_decision(payload, token_hash=token_hash(reg["token"]))
            assert_true(local["decision"] == "ALLOW", "local decision invalida")
            queued = sync.queue_operation(db, organization_id=1, event_id=event_id, device_id=device_id, operation_type="ACCESS_ATTEMPT", payload={"token": reg["token"], "direction": "ENTRY", "operation_id": "op-1"}, local_decision=local, dataset_revision=revision, device_sequence=1, occurred_at=(datetime.now() - timedelta(seconds=2)).isoformat(), correlation_id="corr-1", idempotency_key="idem-1")
            assert_true(queued["item"]["status"] == "PENDING", "queue no queda pendiente")
        with server.connect() as db:
            assert_true(db.execute("SELECT COUNT(*) AS c FROM enterprise_edge_queue WHERE status = 'PENDING'").fetchone()["c"] == 1, "queue no persistio tras reopen")
            sync = server.edge_sync_service()
            result = sync.sync_batch(db, organization_id=1, event_id=event_id, device_id=device_id, secret=secret, operations=[{"operation_type": "ACCESS_ATTEMPT", "payload": {"token": reg["token"], "direction": "ENTRY", "operation_id": "op-1"}, "local_decision": local, "dataset_revision": revision, "device_sequence": 1, "occurred_at": datetime.now().isoformat(), "correlation_id": "corr-1", "idempotency_key": "idem-1"}])
            assert_true(result["ok"] and result["results"][0]["status"] == "ACKNOWLEDGED", f"sync fallo: {result}")
            duplicate = sync.sync_batch(db, organization_id=1, event_id=event_id, device_id=device_id, secret=secret, operations=[{"operation_type": "ACCESS_ATTEMPT", "payload": {"token": reg["token"], "direction": "ENTRY", "operation_id": "op-1"}, "local_decision": local, "dataset_revision": revision, "device_sequence": 1, "idempotency_key": "idem-1"}])
            assert_true(duplicate["results"][0]["conflict_type"] == "DUPLICATE", "duplicate no suprimido")
            stale = sync.sync_batch(db, organization_id=1, event_id=event_id, device_id=device_id, secret=secret, operations=[{"operation_type": "ACCESS_ATTEMPT", "payload": {"token": reg["token"], "direction": "ENTRY", "operation_id": "op-stale"}, "local_decision": local, "dataset_revision": "old", "device_sequence": 2, "idempotency_key": "idem-stale"}])
            assert_true(stale["results"][0]["conflict_type"] == "STALE_DATASET", "stale dataset no detectado")
            other = sync.provision_device(db, organization_id=1, event_id=event_id, device_type="HANDHELD", display_name="Handheld", capabilities=["SYNC_DATASET", "VALIDATE_ACCESS"], actor="test")
            other_id, other_secret = int(other["device"]["id"]), other["secret"]
            sync.activate_device(db, organization_id=1, event_id=event_id, device_id=other_id, actor="test")
            multi = sync.sync_batch(db, organization_id=1, event_id=event_id, device_id=other_id, secret=other_secret, operations=[{"operation_type": "ACCESS_ATTEMPT", "payload": {"token": reg["token"], "direction": "ENTRY", "operation_id": "op-2"}, "local_decision": local, "dataset_revision": revision, "device_sequence": 1, "idempotency_key": "idem-2"}])
            assert_true(multi["results"][0]["conflict_type"] in {"ANTI_PASSBACK_CONFLICT", "STATE_CONFLICT"}, "multi-device conflict no detectado")
            hb = sync.heartbeat(db, organization_id=1, event_id=event_id, device_id=device_id, secret=secret, dataset_revision=revision, queue_depth=0, sync_status="ONLINE", software_version="v5.2-test", device_timestamp=(datetime.now() - timedelta(seconds=30)).isoformat())
            assert_true(hb["ok"] and abs(hb["clock_skew_seconds"]) >= 20, "heartbeat/skew fallo")
            sync.revoke_device(db, organization_id=1, event_id=event_id, device_id=other_id, reason="test", actor="test")
            revoked = sync.sync_batch(db, organization_id=1, event_id=event_id, device_id=other_id, secret=other_secret, operations=[])
            assert_true(not revoked["ok"] and revoked["error"] == "DEVICE_REVOKED", "device revocado pudo sync")
            event2, _, _ = create_event(db, "V5.2 Event B")
            assert_true(not sync.authenticate_device(db, organization_id=1, event_id=event2, device_id=device_id, secret=secret).ok, "device cruzo evento")
            db.execute("INSERT INTO organizations (public_id, name, created_at, updated_at) VALUES ('v52-org2', 'Org2', ?, ?)", (server.now_iso(), server.now_iso()))
            org2 = int(db.execute("SELECT id FROM organizations WHERE public_id = 'v52-org2'").fetchone()["id"])
            assert_true(not sync.authenticate_device(db, organization_id=org2, event_id=event_id, device_id=device_id, secret=secret).ok, "device cruzo tenant")
            telemetry = sync.telemetry(db, organization_id=1, event_id=event_id)
            assert_true(telemetry["sync_successes"] >= 1 and telemetry["conflicts"] >= 1, "telemetry sync incompleta")
            backup = server.create_event_backup(event_id, "test")
            assert_true(server.verify_event_backup(backup)["ok"], "backup V5.2 invalido")
            restored = server.event_restore_service().restore_bytes(backup.read_bytes(), actor="test", mode="new_event")
            restored_event_id = int(restored["event_id"])
            assert_true(db.execute("SELECT COUNT(*) AS c FROM enterprise_edge_queue WHERE event_id = ?", (restored_event_id,)).fetchone()["c"] >= 1, "restore sin edge queue")

            perf = [
                timed("/api/validate V4 direct", lambda: server.access_validation_service().validate(db, "EVT-MISSING", "Acceso", "General")),
                timed("shadow OFF direct", lambda: server.access_validation_service().validate(db, "EVT-MISSING-2", "Acceso", "General")),
                timed("shadow ON service", lambda: server.access_state_engine_service().evaluate(db, server.AccessStateContext(organization_id=1, event_id=event_id, token="EVT-MISSING"))),
                timed("local Edge evaluation", lambda: sync.local_access_decision(payload, token_hash=token_hash(reg["token"]))),
                timed("sync batch 1", lambda: sync.sync_batch(db, organization_id=1, event_id=event_id, device_id=device_id, secret=secret, operations=[]), repeats=10),
                timed("sync batch 100", lambda: sync.sync_batch(db, organization_id=1, event_id=event_id, device_id=device_id, secret=secret, operations=[]), repeats=5),
                timed("sync batch 1000", lambda: sync.sync_batch(db, organization_id=1, event_id=event_id, device_id=device_id, secret=secret, operations=[]), repeats=3),
            ]
            PERFORMANCE.write_text(json.dumps(perf, indent=2), encoding="utf-8")

        golden = golden_with_bootstrap()
        assert_true(golden["after_bootstrap"]["v4_matches"] == 10, "golden V4 no preservado")
        assert_true(golden["after_bootstrap"]["v5_matches"] == 10, f"bootstrap no cerro divergencias: {golden['after_bootstrap']['divergences']}")
        print("V5.2 device identity and edge sync foundation: OK")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
