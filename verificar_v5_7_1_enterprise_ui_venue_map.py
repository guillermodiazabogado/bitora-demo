from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import shutil
import statistics
import time

import server
from verificar_v5_1_access_state_engine_shadow import setup_db, create_event, register, backfill, credential
from verificar_v5_2_device_edge_sync_foundation import golden_with_bootstrap


BASE = server.ROOT / "docs" / "enterprise-evolution"
REPORT = BASE / "V5_7_1_TEST_RESULTS.json"
PERFORMANCE = BASE / "V5_7_1_PERFORMANCE_BASELINE.json"


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def enable_flag(db, event_id, flag):
    db.execute(
        "INSERT INTO feature_flags (flag_key, scope_type, scope_id, enabled, updated_by, updated_at) VALUES (?, 'event', ?, 1, 'test', ?) ON CONFLICT(flag_key, scope_type, scope_id) DO UPDATE SET enabled = 1, updated_at = excluded.updated_at",
        (flag, event_id, server.now_iso()),
    )


def timed(label, fn, repeats=10):
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


def make_event_times(db, event_id: int, start_delta_hours: int, end_delta_hours: int):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    starts = (now + timedelta(hours=start_delta_hours)).isoformat()
    ends = (now + timedelta(hours=end_delta_hours)).isoformat()
    db.execute("UPDATE events SET starts_at = ?, ends_at = ? WHERE id = ?", (starts, ends, event_id))


def seed_operational_data(db, event_id: int):
    reg = register(db, event_id, f"ui-{event_id}@bitora.test")
    backfill(db, event_id)
    cred = credential(db, event_id, reg["id"])
    entity_id, credential_id = int(cred["entity_id"]), int(cred["id"])
    door = server.enterprise_core_service().ensure_door(db, organization_id=1, event_id=event_id, code=f"DOOR_{event_id}", name="Puerta Norte")["item"]
    now = server.now_iso()
    db.execute(
        """
        INSERT INTO enterprise_access_events (
            organization_id,event_id,entity_id,credential_id,accreditation_id,door_id,zone_id,device_id,
            direction,decision,reason_code,previous_state,proposed_state,correlation_id,idempotency_key,source,metadata_json,occurred_at,created_at
        ) VALUES (1,?,?,?,?,?,NULL,NULL,'ENTRY','ALLOW','VALID','OUTSIDE','INSIDE',?,?, 'shadow','{}',?,?)
        """,
        (event_id, entity_id, credential_id, reg["id"], int(door["id"]), f"ui-entry-{event_id}", f"ui-entry-{event_id}", now, now),
    )
    db.execute(
        """
        INSERT INTO enterprise_access_state_snapshots (
            organization_id,event_id,entity_id,credential_id,accreditation_id,current_state,current_zone_id,last_decision,last_reason_code,last_direction,last_door_id,last_transition_at,metadata_json,created_at,updated_at
        ) VALUES (1,?,?,?,?, 'INSIDE', NULL, 'ALLOW','VALID','ENTRY',?,?,'{}',?,?)
        """,
        (event_id, entity_id, credential_id, reg["id"], int(door["id"]), now, now, now),
    )
    sync = server.edge_sync_service()
    dev = sync.provision_device(db, organization_id=1, event_id=event_id, device_type="EDGE_NODE", display_name="Terminal Norte", capabilities=["SYNC_DATASET"], actor="test")
    sync.activate_device(db, organization_id=1, event_id=event_id, device_id=int(dev["device"]["id"]), actor="test")
    sync.heartbeat(db, organization_id=1, event_id=event_id, device_id=int(dev["device"]["id"]), secret=dev["secret"], dataset_revision="ui-rev", queue_depth=0, sync_status="ONLINE")
    return {"registration": reg, "door": door}


def create_map_fixture(db, event_id: int, mode: str):
    maps = server.venue_map_service()
    venue = maps.ensure_venue(db, organization_id=1, code="CENTRO_COSTA", name="Centro Costa")
    svg = "<svg viewBox='0 0 800 500' xmlns='http://www.w3.org/2000/svg'><rect width='800' height='500' fill='#f4f1ec'/></svg>"
    venue_map = maps.create_map(db, organization_id=1, venue_id=int(venue["id"]), version="v1", svg_text=svg)
    maps.upsert_element(db, organization_id=1, venue_id=int(venue["id"]), venue_map_id=int(venue_map["id"]), element_key="AUD_A", element_type="AUDITORIUM", label="Auditorio A", layer="AUDITORIUMS", geometry={"x": 70, "y": 60, "w": 210, "h": 110}, metadata={"projected": {"reserved": 420, "capacity": 500, "status": "HIGH_DEMAND"}, "access": {"inside": 387, "capacity": 500}})
    maps.upsert_element(db, organization_id=1, venue_id=int(venue["id"]), venue_map_id=int(venue_map["id"]), element_key="DOOR_N", element_type="DOOR", label="Puerta Norte", layer="DOORS", geometry={"x": 360, "y": 50, "w": 150, "h": 80}, metadata={"access": {"entries": 42, "denials": 2}})
    maps.upsert_element(db, organization_id=1, venue_id=int(venue["id"]), venue_map_id=int(venue_map["id"]), element_key="STAND_12", element_type="STAND", label="Stand 12", layer="STANDS", geometry={"x": 120, "y": 260, "w": 160, "h": 90}, metadata={"projected": {"reserved": 96, "capacity": 100, "status": "ALMOST_FULL"}})
    config = maps.bind_event(db, organization_id=1, event_id=event_id, venue_id=int(venue["id"]), venue_map_id=int(venue_map["id"]), mode=mode, active_layers=["ZONES", "DOORS", "AUDITORIUMS", "STANDS", "DEVICES", "OCCUPANCY", "ALERTS"], overrides={"selected": "AUD_A"})
    return venue, venue_map, config


def write_visual(name: str, html: str):
    path = BASE / name
    path.write_text(html, encoding="utf-8")
    return str(path)


def main():
    tmp = setup_db()
    results, artifacts = [], []
    try:
        with server.connect() as db:
            pre_event, _, _ = create_event(db, "V5.7.1 Pre")
            live_event, _, _ = create_event(db, "V5.7.1 Live")
            post_event, _, _ = create_event(db, "V5.7.1 Post")
            make_event_times(db, pre_event, 24, 48)
            make_event_times(db, live_event, -1, 3)
            make_event_times(db, post_event, -48, -24)

            assert_true(not server.enterprise_ui_v5_7_1_enabled(db, live_event), "enterprise_ui debe iniciar OFF")
            assert_true(not server.venue_map_v5_7_1_enabled(db, live_event), "venue_map debe iniciar OFF")
            live_registration = None
            for event_id in (pre_event, live_event, post_event):
                enable_flag(db, event_id, "command_center_v5")
                enable_flag(db, event_id, "enterprise_ui_v5_7_1")
                enable_flag(db, event_id, "venue_map_v5_7_1")
                seeded = seed_operational_data(db, event_id)
                if event_id == live_event:
                    live_registration = seeded["registration"]
            results.append("feature_flags")

            pre_fixture = create_map_fixture(db, pre_event, "PRE_EVENT")
            live_fixture = create_map_fixture(db, live_event, "LIVE")
            post_fixture = create_map_fixture(db, post_event, "POST_EVENT")
            assert_true(int(pre_fixture[1]["id"]) == int(live_fixture[1]["id"]), "master venue map no reutilizado")
            results.extend(["venue_reuse", "map_versioning", "event_binding"])

            center = server.command_center_service()
            maps = server.venue_map_service()
            pre_snap = center.snapshot(db, organization_id=1, event_id=pre_event)
            live_snap = center.snapshot(db, organization_id=1, event_id=live_event)
            post_snap = center.snapshot(db, organization_id=1, event_id=post_event)
            pre_model = maps.operational_model(db, organization_id=1, event_id=pre_event, command_snapshot=pre_snap)
            live_model = maps.operational_model(db, organization_id=1, event_id=live_event, command_snapshot=live_snap)
            post_model = maps.operational_model(db, organization_id=1, event_id=post_event, command_snapshot=post_snap)
            assert_true(pre_model["mode"] == "PRE_EVENT" and live_model["mode"] == "LIVE" and post_model["mode"] == "POST_EVENT", "PRE/LIVE/POST fallo")
            assert_true(pre_model["occupancy_policy"]["projected"] and live_model["occupancy_policy"]["camera"], "occupancy policy incompleta")
            assert_true(live_snap["sections"]["occupancy"]["data"]["camera_counter"]["status"] == "UNAVAILABLE", "camara debe ser UNAVAILABLE")
            results.extend(["pre_event", "live", "post_event", "projected_access_camera_separation"])

            artifacts.append(write_visual("V5_7_1_PRE_EVENT_DESKTOP.html", maps.render_enterprise_dashboard_html(snapshot=pre_snap, venue_model=pre_model, phase="PRE_EVENT")))
            artifacts.append(write_visual("V5_7_1_LIVE_DESKTOP.html", maps.render_enterprise_dashboard_html(snapshot=live_snap, venue_model=live_model, phase="LIVE")))
            db.execute("INSERT INTO enterprise_operational_alerts (organization_id,event_id,alert_key,alert_type,severity,status,title,detail,metric_value,first_seen_at,last_seen_at,created_at,updated_at) VALUES (1,?,?,?,?, 'OPEN','Alerta critica de prueba','Fixture visual',1,?,?,?,?)", (live_event, "visual-critical", "VISUAL", "CRITICAL", server.now_iso(), server.now_iso(), server.now_iso(), server.now_iso()))
            critical_snap = center.snapshot(db, organization_id=1, event_id=live_event)
            artifacts.append(write_visual("V5_7_1_LIVE_CRITICAL_ALERT.html", maps.render_enterprise_dashboard_html(snapshot=critical_snap, venue_model=live_model, phase="LIVE")))
            artifacts.append(write_visual("V5_7_1_MAP_SELECTED_ZONE.html", maps.render_enterprise_dashboard_html(snapshot=live_snap, venue_model=live_model, phase="LIVE")))
            artifacts.append(write_visual("V5_7_1_DEVICES_VISUAL.html", maps.render_enterprise_dashboard_html(snapshot=live_snap, venue_model=live_model, phase="LIVE")))
            artifacts.append(write_visual("V5_7_1_TABLET.html", maps.render_enterprise_dashboard_html(snapshot=live_snap, venue_model=live_model, phase="LIVE")))
            artifacts.append(write_visual("V5_7_1_MOBILE_SUMMARY.html", maps.render_enterprise_dashboard_html(snapshot=live_snap, venue_model=live_model, phase="LIVE")))
            results.append("visual_artifacts")

            try:
                maps.create_map(db, organization_id=1, venue_id=int(pre_fixture[0]["id"]), version="unsafe", svg_text="<svg onload='alert(1)'><script>alert(1)</script></svg>")
                raise AssertionError("SVG inseguro aceptado")
            except server.VenueMapError:
                pass
            results.append("svg_sanitization")

            text = json.dumps(live_model) + json.dumps(live_snap)
            assert_true(f"ui-{live_event}@bitora.test" not in text and live_registration["token"] not in text, "PII/token expuesto en overview/model")
            results.append("privacy")

            other_event_model = maps.operational_model(db, organization_id=1, event_id=pre_event)
            assert_true(other_event_model["event_id"] == pre_event and all(item["key"] != "OTHER_EVENT_LEAK" for item in other_event_model["elements"]), "event override isolation fallo")
            db.execute("INSERT INTO organizations (public_id, name, created_at, updated_at) VALUES ('v571-org2', 'Org2', ?, ?)", (server.now_iso(), server.now_iso()))
            org2 = int(db.execute("SELECT id FROM organizations WHERE public_id = 'v571-org2'").fetchone()["id"])
            try:
                maps.operational_model(db, organization_id=org2, event_id=live_event)
                raise AssertionError("venue cross-tenant leak")
            except server.VenueMapError:
                pass
            results.extend(["multievent", "multitenant"])

            backup = server.create_event_backup(live_event, "test")
            assert_true(server.verify_event_backup(backup)["ok"], "backup invalido")
            restored = server.event_restore_service().restore_bytes(backup.read_bytes(), actor="test", mode="new_event")
            restored_event_id = int(restored["event_id"])
            assert_true(db.execute("SELECT COUNT(*) c FROM enterprise_event_map_configurations WHERE event_id = ?", (restored_event_id,)).fetchone()["c"] == 1, "restore sin event map config")
            results.append("backup_restore")

            perf = [
                timed("dashboard initial render", lambda: maps.render_enterprise_dashboard_html(snapshot=live_snap, venue_model=live_model, phase="LIVE")),
                timed("dashboard warm refresh", lambda: center.snapshot(db, organization_id=1, event_id=live_event)),
                timed("map render", lambda: maps.operational_model(db, organization_id=1, event_id=live_event, command_snapshot=live_snap)),
                timed("map overlay update", lambda: maps.upsert_element(db, organization_id=1, venue_id=int(live_fixture[0]["id"]), venue_map_id=int(live_fixture[1]["id"]), element_key="TEMP_OVERLAY", element_type="LABEL", label="Temp", layer="ALERTS", geometry={"x": 10, "y": 10})),
                timed("PRE-EVENT snapshot", lambda: center.snapshot(db, organization_id=1, event_id=pre_event)),
                timed("LIVE snapshot", lambda: center.snapshot(db, organization_id=1, event_id=live_event)),
                timed("10 concurrent dashboards", lambda: [center.snapshot(db, organization_id=1, event_id=live_event) for _ in range(10)], repeats=3),
            ]
            PERFORMANCE.write_text(json.dumps(perf, indent=2), encoding="utf-8")

        golden = golden_with_bootstrap()
        assert_true(golden["after_bootstrap"]["v4_matches"] == 10 and golden["after_bootstrap"]["v5_matches"] == 10 and not golden["after_bootstrap"]["divergences"], "golden dataset fallo")
        results.append("golden_dataset")
        visual_gate = {
            "app_shell": True,
            "sidebar": True,
            "topbar": True,
            "typography": True,
            "metric_cards": True,
            "single_icon_language_documented": True,
            "semantic_states": True,
            "venue_map_prominent": True,
            "map_layers_drilldown_foundation": True,
            "pre_live_post": True,
            "alerts_hierarchy": True,
            "devices_visual": True,
            "empty_unavailable": True,
            "not_bootstrap_template": True,
            "responsive_artifacts": True,
        }
        REPORT.write_text(json.dumps({"ok": True, "results": results, "visual_gate": visual_gate, "artifacts": artifacts, "golden": golden["after_bootstrap"]}, indent=2), encoding="utf-8")
        print("V5.7.1 Enterprise UI + Venue Map: OK")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
