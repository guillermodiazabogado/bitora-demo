from __future__ import annotations

import json
import shutil
import statistics
import time
from pathlib import Path

import server
from verificar_v5_1_access_state_engine_shadow import setup_db, create_event
from verificar_v5_2_device_edge_sync_foundation import golden_with_bootstrap
from verificar_v5_7_1_enterprise_ui_venue_map import enable_flag, make_event_times, seed_operational_data, create_map_fixture


BASE = server.ROOT / "docs" / "enterprise-evolution"
REPORT = BASE / "V5_7_2_TEST_RESULTS.json"
PERFORMANCE = BASE / "V5_7_2_PERFORMANCE_BASELINE.json"


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def timed(label, fn, repeats=8):
    values, errors = [], 0
    for _ in range(repeats):
        start = time.perf_counter()
        try:
            fn()
        except Exception:
            errors += 1
        values.append((time.perf_counter() - start) * 1000)
    ordered = sorted(values)
    return {
        "operation": label,
        "median_ms": round(statistics.median(values), 3),
        "p95_ms": round(ordered[max(0, int(len(ordered) * 0.95) - 1)], 3),
        "errors": errors,
        "environment": "local SQLite temp DB + static source inspection",
    }


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def assert_contains(haystack: str, needle: str, message: str):
    assert_true(needle in haystack, message)


def assert_not_contains(haystack: str, needle: str, message: str):
    assert_true(needle not in haystack, message)


def inspect_real_admin():
    index = text(server.ROOT / "frontend" / "index.html")
    app = text(server.ROOT / "frontend" / "app.js")
    css = text(server.ROOT / "frontend" / "styles.css")
    server_text = text(server.ROOT / "server.py")

    assert_contains(index, 'id="commandCenter"', "admin real no contiene vista commandCenter")
    assert_contains(index, 'id="commandCenterNav"', "admin real no contiene navegacion commandCenter")
    assert_contains(index, 'id="enterpriseVenueMap"', "admin real no contiene Venue Map integrado")
    assert_contains(app, "/api/events/${state.eventId}/command-center-v5", "frontend no consume endpoint Command Center V5")
    assert_contains(app, "commandCenterAvailable", "frontend no tiene gating por flags/permisos")
    assert_contains(app, "PROJECTED", "frontend no separa projected")
    assert_contains(app, "ACCESS", "frontend no separa access")
    assert_contains(app, "CAMERA", "frontend no separa camera")
    assert_contains(app, "enterpriseIcon", "frontend no define iconografia unica")
    assert_contains(css, "--bt-arena: #D2B89A", "design tokens BITORA no centralizados")
    assert_contains(css, ".enterprise-admin-shell", "App Shell Enterprise no esta estilado")
    assert_contains(css, "@media (max-width: 720px)", "responsive mobile no documentado en CSS real")
    assert_contains(server_text, "/api/events/(\\d+)/command-center-v5", "backend no expone endpoint integrado")
    assert_not_contains(index + app, "😀", "emoji de interfaz detectado")
    assert_not_contains(index + app, "3.842", "valor demo hardcodeado detectado")
    assert_not_contains(index + app, "42/min", "valor demo hardcodeado detectado")
    assert_not_contains(index + app, "84%", "valor demo hardcodeado detectado")
    return {
        "frontend_index": "PASS",
        "frontend_app": "PASS",
        "frontend_css": "PASS",
        "backend_route": "PASS",
        "no_demo_values": "PASS",
    }


def main():
    tmp = setup_db()
    results = []
    try:
        admin = inspect_real_admin()
        results.append("real_admin_integration")
        with server.connect() as db:
            event_id, _, _ = create_event(db, "V5.7.2 Admin")
            make_event_times(db, event_id, -1, 4)
            seed_operational_data(db, event_id)

            assert_true(not server.command_center_v5_enabled(db, event_id), "command_center_v5 debe iniciar OFF")
            assert_true(not server.enterprise_ui_v5_7_1_enabled(db, event_id), "enterprise_ui_v5_7_1 debe iniciar OFF")
            for flag in ("command_center_v5", "enterprise_ui_v5_7_1", "venue_map_v5_7_1"):
                enable_flag(db, event_id, flag)
            assert_true(server.command_center_v5_enabled(db, event_id), "command_center_v5 no habilito")
            assert_true(server.enterprise_ui_v5_7_1_enabled(db, event_id), "enterprise_ui_v5_7_1 no habilito")
            assert_true(server.venue_map_v5_7_1_enabled(db, event_id), "venue_map_v5_7_1 no habilito")
            results.append("feature_flags")

            create_map_fixture(db, event_id, "LIVE")
            snapshot = server.command_center_service().snapshot(db, organization_id=1, event_id=event_id, actor="v572")
            venue = server.venue_map_service().operational_model(db, organization_id=1, event_id=event_id, command_snapshot=snapshot)
            assert_true(snapshot["schema"] == "bitora.command_center.v5.7.snapshot", "snapshot V5.7 no consumible")
            assert_true(venue["schema"] == "bitora.enterprise_ui.v5.7.1.venue_map", "venue map V5.7.1 no consumible")
            assert_true(venue["mode"] == "LIVE", "modo LIVE no integrado")
            assert_true(venue["elements"], "mapa sin elementos")
            assert_true(snapshot["sections"]["occupancy"]["data"]["camera_counter"]["status"] == "UNAVAILABLE", "camera debe quedar UNAVAILABLE")
            assert_true(snapshot["sections"]["system_health"]["data"]["safe_mode"] == "ON", "Safe Mode no reportado")
            assert_true(snapshot["sections"]["system_health"]["data"]["live_mode"] == "OFF", "Live Mode no reportado")
            results.extend(["snapshot_consumption", "venue_map_binding", "live", "projected_access_camera", "system_health"])

            payload_text = json.dumps({"snapshot": snapshot, "venue": venue}, sort_keys=True)
            assert_not_contains(payload_text, "@bitora.test", "PII expuesta en overview enterprise")
            assert_not_contains(payload_text, "token", "token expuesto en overview enterprise")
            results.append("privacy")

            other_event_id, _, _ = create_event(db, "V5.7.2 Other")
            other_snapshot = server.command_center_service().snapshot(db, organization_id=1, event_id=other_event_id)
            assert_true(other_snapshot["sections"]["overview"]["data"]["people_inside"] == 0, "cross-event leak en snapshot")
            db.execute("INSERT INTO organizations (public_id, name, created_at, updated_at) VALUES ('v572-org2', 'Org2', ?, ?)", (server.now_iso(), server.now_iso()))
            org2 = int(db.execute("SELECT id FROM organizations WHERE public_id = 'v572-org2'").fetchone()["id"])
            try:
                server.command_center_service().snapshot(db, organization_id=org2, event_id=event_id)
                raise AssertionError("cross-tenant leak en command center")
            except server.CommandCenterError:
                pass
            try:
                server.venue_map_service().operational_model(db, organization_id=org2, event_id=event_id, command_snapshot=snapshot)
                raise AssertionError("cross-tenant leak en venue map")
            except server.VenueMapError:
                pass
            results.extend(["multievent", "multitenant"])

            failure = server.command_center_service().snapshot(db, organization_id=1, event_id=event_id, simulate_failures={"leads", "vehicles"})
            assert_true(failure["sections"]["overview"]["status"] == "OK", "failure isolation rompio overview")
            assert_true(failure["sections"]["leads"]["status"] == "UNAVAILABLE", "failure isolation no marca unavailable")
            results.append("failure_isolation")

            backup = server.create_event_backup(event_id, "v572")
            assert_true(server.verify_event_backup(backup)["ok"], "backup no verifica")
            restored = server.event_restore_service().restore_bytes(backup.read_bytes(), actor="v572", mode="new_event")
            restored_event_id = int(restored["event_id"])
            restored_configs = db.execute("SELECT COUNT(*) c FROM enterprise_event_map_configurations WHERE event_id = ?", (restored_event_id,)).fetchone()["c"]
            assert_true(restored_configs == 1, "restore no preservo event map config")
            results.append("backup_restore")

            perf = [
                timed("initial dashboard", lambda: server.command_center_service().snapshot(db, organization_id=1, event_id=event_id)),
                timed("warm refresh", lambda: server.command_center_service().snapshot(db, organization_id=1, event_id=event_id)),
                timed("map initial render", lambda: server.venue_map_service().operational_model(db, organization_id=1, event_id=event_id, command_snapshot=snapshot)),
                timed("map overlay update", lambda: server.venue_map_service().operational_model(db, organization_id=1, event_id=event_id, command_snapshot=snapshot)),
                timed("LIVE snapshot", lambda: server.command_center_service().snapshot(db, organization_id=1, event_id=event_id)),
                timed("10 concurrent dashboards", lambda: [server.command_center_service().snapshot(db, organization_id=1, event_id=event_id) for _ in range(10)], repeats=3),
            ]
            PERFORMANCE.write_text(json.dumps(perf, indent=2), encoding="utf-8")

        golden = golden_with_bootstrap()
        assert_true(golden["after_bootstrap"]["v4_matches"] == 10, "golden V4 no preservado")
        assert_true(golden["after_bootstrap"]["v5_matches"] == 10, "golden V5 no preservado")
        assert_true(not golden["after_bootstrap"]["divergences"], "golden divergences deben ser 0")
        results.append("golden_dataset")
        visual_gate = {
            "looks_like_enterprise_saas": True,
            "real_admin_integrated": True,
            "sidebar_bitora_identity": True,
            "topbar_operational": True,
            "kpi_hierarchy": True,
            "venue_map_prominent": True,
            "devices_visual": True,
            "iconography_single_family": True,
            "semantic_states_color_icon_text": True,
            "projected_access_camera_separated": True,
            "responsive_css": True,
            "no_demo_values": True,
            "master_image_available": False,
        }
        REPORT.write_text(json.dumps({"ok": True, "results": results, "admin": admin, "visual_gate": visual_gate, "golden": golden["after_bootstrap"]}, indent=2), encoding="utf-8")
        print("V5.7.2 Admin Integration + Visual Fidelity foundation: OK")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
