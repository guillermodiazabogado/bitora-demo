from __future__ import annotations

from datetime import datetime, timedelta
import json
import shutil
import time

import server
from verificar_v5_1_access_state_engine_shadow import setup_db, create_event, register, backfill, credential, grant_event_entitlement
from verificar_v5_2_device_edge_sync_foundation import golden_with_bootstrap


PERFORMANCE = server.ROOT / "docs" / "enterprise-evolution" / "V5_8_PERFORMANCE_BASELINE.json"
REPORT = server.ROOT / "docs" / "enterprise-evolution" / "V5_8_TEST_RESULTS.json"


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


def main():
    tmp = setup_db()
    results = {}
    try:
        with server.connect() as db:
            event_id, _activity_id, _future = create_event(db, "V5.8 Event Edge")
            other_event_id, _other_activity, _ = create_event(db, "V5.8 Other Event")
            for flag in ["event_edge_v5_8", "device_profiles_v5_8", "edge_local_live_v5_8", "device_pairing_v5_8", "device_local_fallback_v5_8", "device_identity", "edge_sync"]:
                enable_flag(db, event_id, flag)
            reg = register(db, event_id, "v58-main@bitora.test")
            backfill(db, event_id)
            cred = credential(db, event_id, reg["id"])
            grant_event_entitlement(db, event_id, cred)

            edge = server.event_edge_service()
            sync = server.edge_sync_service()

            provisioned_edge = edge.provision_edge(db, organization_id=1, event_id=event_id, name="Edge Principal", actor="test")
            edge_id = int(provisioned_edge["edge"]["id"])
            edge_secret = provisioned_edge["secret"]
            assert_true(edge.authenticate_edge(db, organization_id=1, event_id=event_id, edge_id=edge_id, secret=edge_secret).ok, "edge auth failed")
            assert_true(not edge.authenticate_edge(db, organization_id=1, event_id=event_id, edge_id=edge_id, secret="bad").ok, "bad edge secret accepted")

            profiles = edge.ensure_default_profiles(db, organization_id=1, event_id=event_id)
            classes = edge.ensure_capability_classes(db, organization_id=1, event_id=event_id)
            assert_true(len(profiles["profiles"]) >= 6, "device profiles missing")
            assert_true(any(c["execution_class"] == "EDGE_LOCAL_SAFE" for c in classes["classes"]), "capability classes missing")

            pair = edge.create_pairing_code(db, organization_id=1, event_id=event_id, edge_id=edge_id, profile_key="ACCESS_FAST", requested_device_type="HANDHELD", actor="admin")
            paired = edge.pair_device(db, organization_id=1, event_id=event_id, pairing_code=pair["pairing_code"], display_name="Access 01")
            device_id = int(paired["device"]["id"])
            device_secret = paired["secret"]
            assert_true(sync.authenticate_device(db, organization_id=1, event_id=event_id, device_id=device_id, secret=device_secret, capability="VALIDATE_ACCESS").ok, "paired device auth failed")

            dataset = edge.generate_event_dataset(db, organization_id=1, event_id=event_id, edge_id=edge_id, generated_by="test")
            check = edge.verify_dataset(dataset["dataset"])
            assert_true(check["ok"], "dataset checksum failed")
            activated = edge.activate_dataset(db, organization_id=1, event_id=event_id, revision=dataset["dataset"]["revision"], edge_id=edge_id)
            assert_true(activated["status"] == "CURRENT", "dataset activation failed")
            freshness = edge.dataset_freshness(db, organization_id=1, event_id=event_id)
            assert_true(freshness["status"] == "CURRENT", "dataset not current")

            readiness = edge.live_readiness(db, organization_id=1, event_id=event_id)
            assert_true(readiness["status"] in {"READY", "READY_WITH_WARNINGS"}, readiness)
            cloud_down = edge.event_operation_status(db, organization_id=1, event_id=event_id, cloud_state="OFFLINE")
            assert_true(cloud_down["status"] in {"NORMAL", "DEGRADED"}, "cloud offline incorrectly critical")

            local_decision = sync.local_access_decision(dataset["payload"], token_hash=token_hash(reg["token"]))
            assert_true(local_decision["decision"] == "ALLOW", "edge local access decision failed")
            op = edge.edge_local_operation(db, organization_id=1, event_id=event_id, edge_id=edge_id, device_id=device_id, secret=device_secret, capability="ENTRY", payload={"operation_id": "edge-entry-1", "token": reg["token"], "direction": "ENTRY"}, local_decision=local_decision, dataset_revision=activated["revision"], device_sequence=1, idempotency_key="edge-entry-1")
            assert_true(op["ok"] and op["ack"] == "DURABLE_LOCAL_COMMIT", op)
            duplicate = edge.edge_local_operation(db, organization_id=1, event_id=event_id, edge_id=edge_id, device_id=device_id, secret=device_secret, capability="ENTRY", payload={"operation_id": "edge-entry-1", "token": reg["token"], "direction": "ENTRY"}, local_decision=local_decision, dataset_revision=activated["revision"], device_sequence=1, idempotency_key="edge-entry-1")
            assert_true(duplicate["ok"], "idempotent duplicate should return existing item")

        with server.connect() as db:
            edge = server.event_edge_service()
            sync = server.edge_sync_service()
            assert_true(db.execute("SELECT COUNT(*) c FROM enterprise_edge_queue WHERE event_id = ? AND status = 'PENDING'", (event_id,)).fetchone()["c"] >= 1, "queue lost after restart/reopen")
            sync_result = edge.sync_edge_to_cloud(db, organization_id=1, event_id=event_id, edge_id=edge_id, device_id=device_id, secret=device_secret, batch_size=10)
            assert_true(sync_result["ok"], sync_result)

            pair_b = edge.create_pairing_code(db, organization_id=1, event_id=event_id, edge_id=edge_id, profile_key="SERVICE", requested_device_type="HANDHELD", actor="admin")
            device_b = edge.pair_device(db, organization_id=1, event_id=event_id, pairing_code=pair_b["pairing_code"], display_name="Service 02")
            double_spend = edge.offline_double_spend(db, organization_id=1, event_id=event_id, edge_id=edge_id, device_a=(device_id, device_secret), device_b=(int(device_b["device"]["id"]), device_b["secret"]), dataset_revision=activated["revision"])
            assert_true(double_spend["resolution"] == "REVIEW_REQUIRED", "offline double spend not review required")

            other_auth = sync.authenticate_device(db, organization_id=1, event_id=other_event_id, device_id=device_id, secret=device_secret)
            assert_true(not other_auth.ok, "device crossed event")
            db.execute("INSERT INTO organizations (public_id, name, created_at, updated_at) VALUES ('v58-org2', 'Org2', ?, ?)", (server.now_iso(), server.now_iso()))
            org2 = int(db.execute("SELECT id FROM organizations WHERE public_id = 'v58-org2'").fetchone()["id"])
            assert_true(not sync.authenticate_device(db, organization_id=org2, event_id=event_id, device_id=device_id, secret=device_secret).ok, "device crossed tenant")

            sim30 = edge.simulate_devices(db, organization_id=1, event_id=event_id, edge_id=edge_id, count=30, operations_per_device=1)
            sim50 = edge.simulate_devices(db, organization_id=1, event_id=event_id, edge_id=edge_id, count=50, operations_per_device=1)
            sim100 = edge.simulate_devices(db, organization_id=1, event_id=event_id, edge_id=edge_id, count=100, operations_per_device=0)
            assert_true(sim30["ok"] and sim50["ok"] and sim100["ok"], "device simulator failed")

            outage = edge.simulate_cloud_outage(db, organization_id=1, event_id=event_id, edge_id=edge_id, device_id=device_id, secret=device_secret, operations=5000, dataset_revision=activated["revision"])
            assert_true(outage["ok"] and outage["operations"] == 5000 and outage["lost_acknowledged_operations"] == 0, outage)

            edge_failure = edge.event_operation_status(db, organization_id=1, event_id=event_id, cloud_state="OFFLINE", lan_state="UNAVAILABLE")
            assert_true(edge_failure["status"] == "CRITICAL", "edge/lan failure not critical")
            fallback_allowed = edge._capability_has_class(db, 1, event_id, "CREDENTIAL_LOOKUP", "DEVICE_LOCAL_SAFE")
            assert_true(fallback_allowed, "device local fallback class missing")

            backup = server.create_event_backup(event_id, "test")
            assert_true(server.verify_event_backup(backup)["ok"], "backup invalid")
            restored = server.event_restore_service().restore_bytes(backup.read_bytes(), actor="test", mode="new_event")
            restored_event_id = int(restored["event_id"])
            assert_true(db.execute("SELECT COUNT(*) c FROM enterprise_event_edges WHERE event_id = ?", (restored_event_id,)).fetchone()["c"] >= 1, "restore missing edge")
            assert_true(db.execute("SELECT COUNT(*) c FROM enterprise_device_profiles WHERE event_id = ?", (restored_event_id,)).fetchone()["c"] >= 1, "restore missing profiles")

            readiness_invalid = edge.live_readiness(db, organization_id=1, event_id=event_id, cloud_state="OFFLINE")
            assert_true(readiness_invalid["status"] in {"READY", "READY_WITH_WARNINGS"}, "cloud offline blocked healthy edge")
            db.execute("UPDATE enterprise_event_datasets SET status='INVALID' WHERE organization_id=1 AND event_id=? AND revision=?", (event_id, activated["revision"]))
            invalid = edge.live_readiness(db, organization_id=1, event_id=event_id)
            assert_true(invalid["status"] == "NOT_READY", "invalid dataset not blocking")
            db.execute("UPDATE enterprise_event_datasets SET status='CURRENT' WHERE organization_id=1 AND event_id=? AND revision=?", (event_id, activated["revision"]))

            command = server.command_center_service().snapshot(db, organization_id=1, event_id=event_id)
            edge_data = command["sections"]["edge"]["data"]
            assert_true("event_edge" in edge_data and "readiness" in edge_data and "event_operation" in edge_data, "command center edge awareness missing")

            perf = edge.performance_baseline([
                ("Edge access validation", lambda: sync.local_access_decision(dataset["payload"], token_hash=token_hash(reg["token"])), 25),
                ("Edge ENTRY", lambda: edge.edge_local_operation(db, organization_id=1, event_id=event_id, edge_id=edge_id, device_id=device_id, secret=device_secret, capability="ENTRY", payload={"operation_id": f"perf-entry-{time.perf_counter()}", "token": reg["token"], "direction": "ENTRY"}, local_decision=local_decision, dataset_revision=activated["revision"], device_sequence=999, idempotency_key=f"perf-entry-{time.perf_counter()}"), 10),
                ("Queue append", lambda: edge.edge_local_operation(db, organization_id=1, event_id=event_id, edge_id=edge_id, device_id=device_id, secret=device_secret, capability="ENTRY", payload={"operation_id": f"perf-q-{time.perf_counter()}", "token": reg["token"]}, local_decision=local_decision, dataset_revision=activated["revision"], device_sequence=1000, idempotency_key=f"perf-q-{time.perf_counter()}"), 10),
                ("Batch 1", lambda: edge.sync_edge_to_cloud(db, organization_id=1, event_id=event_id, edge_id=edge_id, device_id=device_id, secret=device_secret, batch_size=1), 5),
                ("Batch 100", lambda: edge.sync_edge_to_cloud(db, organization_id=1, event_id=event_id, edge_id=edge_id, device_id=device_id, secret=device_secret, batch_size=100), 3),
                ("Device heartbeat", lambda: sync.heartbeat(db, organization_id=1, event_id=event_id, device_id=device_id, secret=device_secret, dataset_revision=activated["revision"], queue_depth=0, sync_status="ONLINE", device_timestamp=(datetime.now() - timedelta(seconds=2)).isoformat()), 10),
            ])
            PERFORMANCE.write_text(json.dumps(perf, indent=2), encoding="utf-8")

            results.update({
                "edge_id": edge_id,
                "dataset_revision": activated["revision"],
                "readiness": readiness,
                "cloud_down": cloud_down,
                "sync_result": sync_result,
                "double_spend": double_spend,
                "device_simulation": {"30": sim30, "50": sim50, "100": sim100},
                "outage_5000": outage,
                "backup_restore_event_id": restored_event_id,
            })

        golden = golden_with_bootstrap()["after_bootstrap"]
        assert_true(golden["v4_matches"] == 10 and golden["v5_matches"] == 10 and golden["divergences"] == [], "golden regression")
        results["golden"] = {"v4_matches": golden["v4_matches"], "v5_matches": golden["v5_matches"], "divergences": golden["divergences"]}
        REPORT.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
        print("V5.8 Event Edge and Device Infrastructure: OK")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
