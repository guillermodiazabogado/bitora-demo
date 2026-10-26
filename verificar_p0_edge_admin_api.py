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
    temp_root = Path(tempfile.mkdtemp(prefix="bitora-p0-edge-admin-", dir=workspace_tmp))
    original_db_path = server.DB_PATH
    original_backup_dir = server.BACKUP_DIR
    try:
        server.DB_PATH = temp_root / "edge-admin.sqlite3"
        server.BACKUP_DIR = temp_root / "backups"
        server.init_db()
        server.seed_if_empty()
        with server.connect() as db:
            event_id, _activity_id, _future_id = create_event(db, "P0 Edge Admin")
            other_event_id, _other_activity, _other_future = create_event(db, "P0 Other Event")

            profiles = server.edge_admin_action(db, event_id, "profiles", {}, actor="Admin")
            assert_true(len(profiles["profiles"]) >= 6, profiles)
            assert_true(profiles["capability_classes"], profiles)

            provisioned = server.edge_admin_action(
                db,
                event_id,
                "provision",
                {"name": "Edge Principal", "software_version": "test"},
                actor="Admin",
            )
            assert_true(provisioned["secret"].startswith("edge_"), provisioned)
            assert_true("credential_hash" not in provisioned["edge"], provisioned)
            edge_id = int(provisioned["edge"]["id"])

            pairing = server.edge_admin_action(
                db,
                event_id,
                "pairing-code",
                {"edge_id": edge_id, "profile_key": "ACCESS_FAST", "device_type": "HANDHELD"},
                actor="Admin",
            )
            assert_true(len(pairing["pairing_code"]) == 6, pairing)

            dataset = server.edge_admin_action(
                db, event_id, "dataset", {"edge_id": edge_id}, actor="Admin"
            )
            assert_true("payload_json" not in dataset["dataset"], dataset)
            assert_true("metadata_json" not in dataset["dataset"], dataset)
            revision = dataset["dataset"]["revision"]
            activated = server.edge_admin_action(
                db,
                event_id,
                "dataset-activate",
                {"edge_id": edge_id, "revision": revision},
                actor="Admin",
            )
            assert_true(activated["ok"] and activated["status"] == "CURRENT", activated)
            readiness = server.edge_admin_action(db, event_id, "readiness", {}, actor="Admin")
            assert_true(readiness["readiness"]["status"] in {"READY", "READY_WITH_WARNINGS"}, readiness)

            try:
                server.edge_admin_action(
                    db,
                    other_event_id,
                    "pairing-code",
                    {"edge_id": edge_id, "profile_key": "ACCESS_FAST"},
                    actor="Admin",
                )
            except ValueError as exc:
                assert_true(str(exc) == "EDGE_NOT_FOUND", exc)
            else:
                raise AssertionError("An Edge de otro evento fue aceptado")

            assert_true("edge.provision" in server.PERMISSION_MATRIX["Productor"]["actions"], "Productor sin permiso Edge")
            assert_true("edge.provision" not in server.PERMISSION_MATRIX["Operador de acceso"]["actions"], "Operador con permiso administrativo Edge")
        print("P0 Edge admin contract, secret sanitization and event isolation: OK")
    finally:
        server.DB_PATH = original_db_path
        server.BACKUP_DIR = original_backup_dir
        shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    main()
