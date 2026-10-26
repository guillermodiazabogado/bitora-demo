from __future__ import annotations

from pathlib import Path
import shutil
import tempfile

import server
from verificar_v5_1_access_state_engine_shadow import create_event


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main() -> None:
    workspace_tmp = Path(__file__).resolve().parent / "tmp"
    workspace_tmp.mkdir(parents=True, exist_ok=True)
    temp_root = Path(tempfile.mkdtemp(prefix="bitora-p0-device-security-", dir=workspace_tmp))
    original_db_path = server.DB_PATH
    original_backup_dir = server.BACKUP_DIR
    try:
        server.DB_PATH = temp_root / "device-security.sqlite3"
        server.BACKUP_DIR = temp_root / "backups"
        server.init_db()
        server.seed_if_empty()
        with server.connect() as db:
            event_id, _activity, _future = create_event(db, "Device Security")
            other_event_id, _activity_b, _future_b = create_event(db, "Other Device Event")
            admin = server.edge_admin_action(db, event_id, "profiles", {}, actor="Admin")
            assert_true(admin["ok"], admin)
            edge = server.edge_admin_action(db, event_id, "provision", {"name": "Edge"}, actor="Admin")
            edge_id = int(edge["edge"]["id"])
            pairing = server.edge_admin_action(
                db,
                event_id,
                "pairing-code",
                {"edge_id": edge_id, "profile_key": "ACCESS_FAST", "device_type": "HANDHELD"},
                actor="Admin",
            )

            service = server.event_edge_service()
            for attempt in range(5):
                try:
                    service.pair_device(
                        db,
                        organization_id=1,
                        event_id=event_id,
                        pairing_code="000000",
                        display_name="Attacker",
                        request_fingerprint="fingerprint-a",
                    )
                except ValueError as exc:
                    assert_true(str(exc) == "PAIRING_CODE_INVALID", (attempt, exc))
                else:
                    raise AssertionError("Invalid pairing code accepted")
            try:
                service.pair_device(
                    db,
                    organization_id=1,
                    event_id=event_id,
                    pairing_code=pairing["pairing_code"],
                    display_name="Blocked Device",
                    request_fingerprint="fingerprint-a",
                )
            except ValueError as exc:
                assert_true(str(exc) == "PAIRING_RATE_LIMITED", exc)
            else:
                raise AssertionError("Rate-limited fingerprint was accepted")

            paired = service.pair_device(
                db,
                organization_id=1,
                event_id=event_id,
                pairing_code=pairing["pairing_code"],
                display_name="Access 01",
                request_fingerprint="fingerprint-b",
            )
            device_id = int(paired["device"]["id"])
            device_secret = paired["secret"]
            assert_true("credential_hash" in paired["device"], "Service contract unexpectedly changed")

            try:
                service.pair_device(
                    db,
                    organization_id=1,
                    event_id=event_id,
                    pairing_code=pairing["pairing_code"],
                    display_name="Replay",
                    request_fingerprint="fingerprint-c",
                )
            except ValueError as exc:
                assert_true(str(exc) == "PAIRING_CODE_INVALID", exc)
            else:
                raise AssertionError("Pairing code replay accepted")

            sync = server.edge_sync_service()
            heartbeat = sync.heartbeat(
                db,
                organization_id=1,
                event_id=event_id,
                device_id=device_id,
                secret=device_secret,
                dataset_revision="",
                queue_depth=0,
                sync_status="ONLINE",
            )
            assert_true(heartbeat["ok"], heartbeat)
            rejected = sync.heartbeat(
                db,
                organization_id=1,
                event_id=other_event_id,
                device_id=device_id,
                secret=device_secret,
                dataset_revision="",
                queue_depth=0,
                sync_status="ONLINE",
            )
            assert_true(not rejected["ok"] and rejected["error"] == "DEVICE_NOT_FOUND", rejected)
        print("P0 pairing rate limit, one-time codes, device auth and event isolation: OK")
    finally:
        server.DB_PATH = original_db_path
        server.BACKUP_DIR = original_backup_dir
        shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    main()
