from __future__ import annotations

import json
import shutil
import statistics
import time
from pathlib import Path

from PIL import Image

import server
from verificar_v5_1_access_state_engine_shadow import setup_db, create_event
from verificar_v5_2_device_edge_sync_foundation import golden_with_bootstrap
from verificar_v5_7_1_enterprise_ui_venue_map import enable_flag, make_event_times, seed_operational_data, create_map_fixture


BASE = server.ROOT / "docs" / "enterprise-evolution"
REFERENCE = BASE / "ui-reference" / "BITORA_ENTERPRISE_MASTER_UI_REFERENCE_V1.png"
REPORT = BASE / "V5_7_3_TEST_RESULTS.json"
PERFORMANCE = BASE / "V5_7_3_PERFORMANCE_BASELINE.json"


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


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
        "environment": "local SQLite temp DB + real frontend inspection",
    }


def reference_properties():
    assert_true(REFERENCE.exists(), "MASTER UI reference no existe")
    image = Image.open(REFERENCE)
    props = {"format": image.format, "size": image.size, "mode": image.mode}
    assert_true(props["format"] == "PNG", "Master reference debe ser PNG")
    assert_true(props["size"] == (1536, 1024), f"Master reference dimensiones inesperadas: {props['size']}")
    assert_true(props["mode"] == "RGB", f"Master reference modo inesperado: {props['mode']}")
    return props


def inspect_frontend():
    index = text(server.ROOT / "frontend" / "index.html")
    app = text(server.ROOT / "frontend" / "app.js")
    css = text(server.ROOT / "frontend" / "styles.css")
    static_index = text(server.ROOT / "static" / "index.html")
    static_app = text(server.ROOT / "static" / "app.js")
    static_css = text(server.ROOT / "static" / "styles.css")
    combined = index + app + css
    for required in [
        'id="commandCenter"',
        'enterprise-admin-shell',
        'enterprise-sidebar',
        'enterprise-topbar',
        'enterpriseVenueMap',
        'enterpriseKpis',
        'Projected / Access / Camera',
    ]:
        assert_true(required in combined, f"Falta integracion real: {required}")
    for required in [
        "body.command-center-mode > .topbar",
        "grid-template-columns: repeat(6",
        "--bt-arena: #D2B89A",
        "commandCenterAvailable",
        "/api/events/${state.eventId}/command-center-v5",
        "PROJECTED",
        "ACCESS",
        "CAMERA",
    ]:
        assert_true(required in combined, f"Falta convergencia visual/funcional: {required}")
    for forbidden in ["😀", "3.842", "42/min", "84%", "queue_backlog=143"]:
        assert_true(forbidden not in combined, f"Dato demo/lenguaje tecnico prohibido: {forbidden}")
    assert_true(index == static_index and app == static_app and css == static_css, "frontend/static no sincronizados")
    return {"admin_real": "PASS", "static_sync": "PASS", "no_demo_data": "PASS"}


def main():
    tmp = setup_db()
    results = []
    try:
        props = reference_properties()
        frontend = inspect_frontend()
        results.extend(["reference_exists", "reference_readable", "frontend_integration"])
        with server.connect() as db:
            pre_event, _, _ = create_event(db, "V5.7.3 Pre")
            live_event, _, _ = create_event(db, "V5.7.3 Live")
            post_event, _, _ = create_event(db, "V5.7.3 Post")
            make_event_times(db, pre_event, 24, 48)
            make_event_times(db, live_event, -1, 4)
            make_event_times(db, post_event, -48, -24)
            for event_id in (pre_event, live_event, post_event):
                for flag in ("command_center_v5", "enterprise_ui_v5_7_1", "venue_map_v5_7_1"):
                    enable_flag(db, event_id, flag)
                seed_operational_data(db, event_id)
                create_map_fixture(db, event_id, "PRE_EVENT" if event_id == pre_event else "POST_EVENT" if event_id == post_event else "LIVE")
            assert_true(server.command_center_v5_enabled(db, live_event), "command_center_v5 no habilitado")
            assert_true(server.enterprise_ui_v5_7_1_enabled(db, live_event), "enterprise_ui no habilitado")
            assert_true(server.venue_map_v5_7_1_enabled(db, live_event), "venue map no habilitado")
            results.append("feature_flags")

            center = server.command_center_service()
            maps = server.venue_map_service()
            snapshots = {
                "PRE_EVENT": center.snapshot(db, organization_id=1, event_id=pre_event),
                "LIVE": center.snapshot(db, organization_id=1, event_id=live_event),
                "POST_EVENT": center.snapshot(db, organization_id=1, event_id=post_event),
            }
            models = {
                key: maps.operational_model(db, organization_id=1, event_id={"PRE_EVENT": pre_event, "LIVE": live_event, "POST_EVENT": post_event}[key], command_snapshot=snapshot)
                for key, snapshot in snapshots.items()
            }
            assert_true(models["PRE_EVENT"]["mode"] == "PRE_EVENT", "PRE no integrado")
            assert_true(models["LIVE"]["mode"] == "LIVE", "LIVE no integrado")
            assert_true(models["POST_EVENT"]["mode"] == "POST_EVENT", "POST no integrado")
            assert_true(models["LIVE"]["elements"], "Venue Map sin elementos")
            assert_true(snapshots["LIVE"]["sections"]["occupancy"]["data"]["camera_counter"]["status"] == "UNAVAILABLE", "CAMERA debe ser UNAVAILABLE sin fuente")
            payload = json.dumps({"snapshots": snapshots, "models": models}, sort_keys=True)
            assert_true("@bitora.test" not in payload and "token" not in payload.lower(), "PII/token en overview")
            results.extend(["snapshot_consumption", "venue_binding", "pre_live_post", "projected_access_camera", "privacy"])

            other_event, _, _ = create_event(db, "V5.7.3 Other")
            other = center.snapshot(db, organization_id=1, event_id=other_event)
            assert_true(other["sections"]["overview"]["data"]["people_inside"] == 0, "cross-event leak")
            db.execute("INSERT INTO organizations (public_id, name, created_at, updated_at) VALUES ('v573-org2', 'Org2', ?, ?)", (server.now_iso(), server.now_iso()))
            org2 = int(db.execute("SELECT id FROM organizations WHERE public_id = 'v573-org2'").fetchone()["id"])
            try:
                center.snapshot(db, organization_id=org2, event_id=live_event)
                raise AssertionError("cross-tenant command center leak")
            except server.CommandCenterError:
                pass
            try:
                maps.operational_model(db, organization_id=org2, event_id=live_event, command_snapshot=snapshots["LIVE"])
                raise AssertionError("cross-tenant venue map leak")
            except server.VenueMapError:
                pass
            results.extend(["multievent", "multitenant"])

            backup = server.create_event_backup(live_event, "v573")
            assert_true(server.verify_event_backup(backup)["ok"], "backup invalido")
            restored = server.event_restore_service().restore_bytes(backup.read_bytes(), actor="v573", mode="new_event")
            restored_event_id = int(restored["event_id"])
            count = db.execute("SELECT COUNT(*) c FROM enterprise_event_map_configurations WHERE event_id = ?", (restored_event_id,)).fetchone()["c"]
            assert_true(count == 1, "restore sin map config")
            results.append("backup_restore")

            perf = [
                timed("dashboard initial render", lambda: center.snapshot(db, organization_id=1, event_id=live_event)),
                timed("warm refresh", lambda: center.snapshot(db, organization_id=1, event_id=live_event)),
                timed("map initial render", lambda: maps.operational_model(db, organization_id=1, event_id=live_event, command_snapshot=snapshots["LIVE"])),
                timed("map overlay update", lambda: maps.operational_model(db, organization_id=1, event_id=live_event, command_snapshot=snapshots["LIVE"])),
                timed("PRE snapshot", lambda: center.snapshot(db, organization_id=1, event_id=pre_event)),
                timed("LIVE snapshot", lambda: center.snapshot(db, organization_id=1, event_id=live_event)),
                timed("10 concurrent dashboards", lambda: [center.snapshot(db, organization_id=1, event_id=live_event) for _ in range(10)], repeats=3),
            ]
            PERFORMANCE.write_text(json.dumps(perf, indent=2), encoding="utf-8")
            results.append("performance")

        golden = golden_with_bootstrap()
        assert_true(golden["after_bootstrap"]["v4_matches"] == 10, "Golden V4 != 10/10")
        assert_true(golden["after_bootstrap"]["v5_matches"] == 10, "Golden V5 != 10/10")
        assert_true(not golden["after_bootstrap"]["divergences"], "Golden divergences != 0")
        results.append("golden")
        REPORT.write_text(json.dumps({"ok": True, "reference": props, "frontend": frontend, "results": results, "golden": golden["after_bootstrap"]}, indent=2), encoding="utf-8")
        print("V5.7.3 Master UI convergence verifier: OK")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
