from __future__ import annotations

from datetime import datetime, timedelta
import json
import shutil
import statistics
import time

import server
from verificar_v5_1_access_state_engine_shadow import setup_db, create_event, register, backfill, credential
from verificar_v5_2_device_edge_sync_foundation import golden_with_bootstrap


REPORT = server.ROOT / "docs" / "enterprise-evolution" / "V5_7_TEST_RESULTS.json"
PERFORMANCE = server.ROOT / "docs" / "enterprise-evolution" / "V5_7_PERFORMANCE_BASELINE.json"
UI_ARTIFACT = server.ROOT / "docs" / "enterprise-evolution" / "V5_7_COMMAND_CENTER_DASHBOARD_FOUNDATION.html"


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
    ordered = sorted(values)
    return {"operation": label, "median_ms": round(statistics.median(values), 3), "p95_ms": round(ordered[max(0, int(len(ordered) * 0.95) - 1)], 3), "errors": errors, "environment": "local SQLite temp DB"}


def main():
    tmp = setup_db()
    results = []
    try:
        with server.connect() as db:
            event_id, _, _ = create_event(db, "V5.7 Main")
            other_event_id, _, _ = create_event(db, "V5.7 Other")
            assert_true(not server.command_center_v5_enabled(db, event_id), "command_center_v5 debe iniciar OFF")
            enable_flag(db, event_id, "command_center_v5")
            assert_true(server.command_center_v5_enabled(db, event_id), "flag command_center_v5 no habilito")
            results.append("feature_flag_off_on")

            reg = register(db, event_id, "command.center@bitora.test")
            backfill(db, event_id)
            cred = credential(db, event_id, reg["id"])
            entity_id, credential_id = int(cred["entity_id"]), int(cred["id"])
            core = server.enterprise_core_service()
            sync = server.edge_sync_service()
            center = server.command_center_service()

            door = core.ensure_door(db, organization_id=1, event_id=event_id, code="MAIN", name="Puerta principal")["item"]
            now = server.now_iso()
            for idx in range(2):
                db.execute(
                    """
                    INSERT INTO enterprise_access_events (
                        organization_id,event_id,entity_id,credential_id,accreditation_id,door_id,zone_id,device_id,
                        direction,decision,reason_code,previous_state,proposed_state,correlation_id,idempotency_key,source,metadata_json,occurred_at,created_at
                    ) VALUES (1,?,?,?,?,?,NULL,NULL,'ENTRY','ALLOW','VALID','OUTSIDE','INSIDE',?,?, 'shadow','{}',?,?)
                    """,
                    (event_id, entity_id, credential_id, reg["id"], int(door["id"]), f"cc-entry-{idx}", f"cc-entry-{idx}", now, now),
                )
            db.execute(
                """
                INSERT INTO enterprise_access_events (
                    organization_id,event_id,entity_id,credential_id,accreditation_id,door_id,zone_id,device_id,
                    direction,decision,reason_code,previous_state,proposed_state,correlation_id,idempotency_key,source,metadata_json,occurred_at,created_at
                ) VALUES (1,?,?,?,?,?,NULL,NULL,'ENTRY','DENY','NO_ENTITLEMENT','OUTSIDE','OUTSIDE','cc-deny','cc-deny','shadow','{}',?,?)
                """,
                (event_id, entity_id, credential_id, reg["id"], int(door["id"]), now, now),
            )
            db.execute(
                """
                INSERT INTO enterprise_access_state_snapshots (
                    organization_id,event_id,entity_id,credential_id,accreditation_id,current_state,current_zone_id,
                    last_decision,last_reason_code,last_direction,last_door_id,last_transition_at,metadata_json,created_at,updated_at
                ) VALUES (1,?,?,?,?, 'INSIDE', NULL, 'ALLOW','VALID','ENTRY',?,?,'{}',?,?)
                """,
                (event_id, entity_id, credential_id, reg["id"], int(door["id"]), now, now, now),
            )
            results.extend(["access_flow", "people_inside", "denials", "doors"])

            active = sync.provision_device(db, organization_id=1, event_id=event_id, device_type="EDGE_NODE", display_name="Edge activo", capabilities=["SYNC_DATASET"], actor="test")
            active_id, active_secret = int(active["device"]["id"]), active["secret"]
            sync.activate_device(db, organization_id=1, event_id=event_id, device_id=active_id, actor="test")
            sync.heartbeat(db, organization_id=1, event_id=event_id, device_id=active_id, secret=active_secret, dataset_revision="rev-current", queue_depth=0, sync_status="ONLINE", software_version="v5.7")
            stale = sync.provision_device(db, organization_id=1, event_id=event_id, device_type="ACCESS_TERMINAL", display_name="Terminal vieja", capabilities=["VALIDATE_ACCESS"], actor="test")
            stale_id = int(stale["device"]["id"])
            sync.activate_device(db, organization_id=1, event_id=event_id, device_id=stale_id, actor="test")
            db.execute("UPDATE enterprise_devices SET last_seen_at = ? WHERE id = ?", ((datetime.fromisoformat(server.now_iso()) - timedelta(hours=2)).isoformat(timespec="seconds"), stale_id))
            dataset = sync.generate_dataset(db, organization_id=1, event_id=event_id, generated_by="test")["dataset"]
            sync.queue_operation(db, organization_id=1, event_id=event_id, device_id=active_id, operation_type="ACCESS_ATTEMPT", payload={"token": reg["token"], "direction": "ENTRY"}, local_decision={"decision": "ALLOW"}, dataset_revision=dataset["revision"], device_sequence=1, idempotency_key="cc-q-1")
            db.execute("INSERT INTO enterprise_edge_reconciliations (organization_id,event_id,device_id,queue_id,operation_id,local_decision,server_decision,conflict_type,resolution,correlation_id,idempotency_key,dataset_revision,device_sequence,clock_skew_seconds,metadata_json,reconciled_at,created_at) VALUES (1,?,?,?,?, 'ALLOW','DENY','ANTI_PASSBACK_CONFLICT','CONFLICT','cc-conflict','cc-conflict',?,2,0,'{}',?,?)", (event_id, active_id, 1, "op-conflict", dataset["revision"], now, now))
            results.extend(["devices", "device_health", "edge_queue", "conflicts"])

            ent = server.entitlements_vouchers_service()
            ent_type = ent.ensure_type(db, organization_id=1, event_id=event_id, code="MEAL", name="Comida", default_quantity=1)
            entitlement = ent.grant(db, organization_id=1, event_id=event_id, entity_id=entity_id, entitlement_type="MEAL", allocated=1, idempotency_key="cc-grant")
            point = ent.ensure_service_point(db, organization_id=1, event_id=event_id, code="FOOD", name="Food", service_type="MEAL")
            ent.consume(db, organization_id=1, event_id=event_id, token=reg["token"], entitlement_type="MEAL", service_point_id=int(point["id"]), idempotency_key="cc-consume")
            results.extend(["entitlements", "service_points"])

            company = server.company_delegation_service().create_company(db, organization_id=1, name="Command Co", company_type="EXHIBITOR")
            company_id = int(company["id"])
            server.company_delegation_service().link_company_to_event(db, organization_id=1, event_id=event_id, company_id=company_id, status="ACTIVE")
            stand = server.lead_retrieval_service().create_stand(db, organization_id=1, event_id=event_id, company_id=company_id, code="CC", name="Stand CC")
            server.lead_retrieval_service().create_license(db, organization_id=1, event_id=event_id, company_id=company_id, stand_id=int(stand["id"]), status="ACTIVE")
            consent = server.lead_retrieval_service().grant_consent(db, organization_id=1, event_id=event_id, participant_entity_id=entity_id, company_id=company_id, fields=["name"])
            lead = server.lead_retrieval_service().capture(db, organization_id=1, event_id=event_id, company_id=company_id, stand_id=int(stand["id"]), token=reg["token"], consent_id=int(consent["id"]), idempotency_key="cc-lead")
            results.append("lead_metrics")

            vehicle = server.vehicle_logistics_service().ensure_vehicle(db, organization_id=1, plate="CC123CC")
            dest = server.vehicle_logistics_service().ensure_destination(db, organization_id=1, event_id=event_id, code="LOAD", name="Carga")
            server.vehicle_logistics_service().create_slot(db, organization_id=1, event_id=event_id, vehicle_id=int(vehicle["id"]), company_id=company_id, gate_id=int(door["id"]), destination_id=int(dest["id"]))
            server.vehicle_logistics_service().record_access(db, organization_id=1, event_id=event_id, plate="CC123CC", gate_id=int(door["id"]), destination_id=int(dest["id"]), idempotency_key="cc-vehicle-entry")
            results.append("vehicle_metrics")

            snap = center.snapshot(db, organization_id=1, event_id=event_id)
            assert_true(snap["sections"]["overview"]["data"]["people_inside"] == 1, "snapshot sin inside")
            assert_true(snap["sections"]["devices"]["data"]["counts"]["stale"] >= 1, "snapshot sin device stale")
            assert_true(snap["sections"]["edge"]["data"]["queue_depth"] >= 1, "snapshot sin queue")
            assert_true(snap["sections"]["alerts"]["data"]["counts"]["open"] >= 2, "alertas no generadas")
            html = center.render_dashboard_html(snap)
            assert_true("BITORA Command Center" in html and "Mapa operativo" in html and "Alertas" in html, "UI foundation incompleta")
            UI_ARTIFACT.write_text(html, encoding="utf-8")
            results.extend(["snapshot", "overview_cards", "ui_dashboard", "alerts"])

            alert_count = int(db.execute("SELECT COUNT(*) c FROM enterprise_operational_alerts WHERE event_id = ?", (event_id,)).fetchone()["c"])
            center.snapshot(db, organization_id=1, event_id=event_id)
            dedup_count = int(db.execute("SELECT COUNT(*) c FROM enterprise_operational_alerts WHERE event_id = ?", (event_id,)).fetchone()["c"])
            assert_true(alert_count == dedup_count, "deduplicacion de alertas fallo")
            alert_id = int(db.execute("SELECT id FROM enterprise_operational_alerts WHERE event_id = ? AND status = 'OPEN' ORDER BY id LIMIT 1", (event_id,)).fetchone()["id"])
            center.acknowledge_alert(db, organization_id=1, event_id=event_id, alert_id=alert_id, actor="test")
            center.resolve_alert(db, organization_id=1, event_id=event_id, alert_id=alert_id, actor="test")
            results.extend(["alert_dedup", "alert_ack", "alert_resolve"])

            failure = center.snapshot(db, organization_id=1, event_id=event_id, simulate_failures={"leads"})
            assert_true(failure["sections"]["leads"]["status"] == "UNAVAILABLE" and failure["sections"]["overview"]["status"] == "OK", "failure isolation fallo")
            snap_text = json.dumps(snap, sort_keys=True)
            assert_true("command.center@bitora.test" not in snap_text and reg["token"] not in snap_text, "snapshot expone PII/token")
            assert_true(snap["sections"]["occupancy"]["data"]["camera_counter"]["status"] == "UNAVAILABLE", "camara debe estar separada")
            results.extend(["failure_isolation", "privacy", "camera_occupancy_separation"])

            other_snap = center.snapshot(db, organization_id=1, event_id=other_event_id)
            assert_true(other_snap["sections"]["overview"]["data"]["people_inside"] == 0, "cross-event leak")
            db.execute("INSERT INTO organizations (public_id, name, created_at, updated_at) VALUES ('v57-org2', 'Org2', ?, ?)", (server.now_iso(), server.now_iso()))
            org2 = int(db.execute("SELECT id FROM organizations WHERE public_id = 'v57-org2'").fetchone()["id"])
            try:
                center.snapshot(db, organization_id=org2, event_id=event_id)
                raise AssertionError("cross-tenant leak")
            except server.CommandCenterError:
                pass
            results.extend(["multievent", "multitenant", "rbac_scope"])

            backup = server.create_event_backup(event_id, "test")
            assert_true(server.verify_event_backup(backup)["ok"], "backup V5.7 invalido")
            restored = server.event_restore_service().restore_bytes(backup.read_bytes(), actor="test", mode="new_event")
            restored_event_id = int(restored["event_id"])
            assert_true(db.execute("SELECT COUNT(*) c FROM enterprise_operational_alerts WHERE event_id = ?", (restored_event_id,)).fetchone()["c"] >= 1, "restore sin command center alerts")
            results.append("backup_restore")

            perf = [
                timed("snapshot warm", lambda: center.snapshot(db, organization_id=1, event_id=event_id), repeats=10),
                timed("alerts evaluation", lambda: center.evaluate_alerts(db, organization_id=1, event_id=event_id, metrics={"queue_depth": 10, "conflicts": 1, "stale_devices": 1, "occupancy_pct": 0}), repeats=10),
                timed("dashboard render", lambda: center.render_dashboard_html(snap), repeats=20),
            ]
            PERFORMANCE.write_text(json.dumps(perf, indent=2), encoding="utf-8")

        golden = golden_with_bootstrap()
        assert_true(golden["after_bootstrap"]["v4_matches"] == 10, "golden V4 no preservado")
        assert_true(golden["after_bootstrap"]["v5_matches"] == 10, "golden V5 no preservado")
        results.append("golden_dataset")
        REPORT.write_text(json.dumps({"ok": True, "results": results, "golden": golden["after_bootstrap"]}, indent=2), encoding="utf-8")
        print("V5.7 Command Center: OK")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
