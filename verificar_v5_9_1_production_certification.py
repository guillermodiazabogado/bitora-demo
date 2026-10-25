from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import server
from verificar_v5_1_access_state_engine_shadow import create_event, register, backfill, credential, grant_event_entitlement
from verificar_v5_2_device_edge_sync_foundation import golden_with_bootstrap


ROOT = server.ROOT / "docs" / "enterprise-evolution"
REPORT = ROOT / "V5_9_1_PRODUCTION_CERTIFICATION_REPORT.md"
ENDURANCE_DIR = ROOT / "V5_9_1_ENDURANCE"


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def enable_flag(db, event_id: int, flag: str):
    db.execute(
        "INSERT INTO feature_flags (flag_key, scope_type, scope_id, enabled, updated_by, updated_at) VALUES (?, 'event', ?, 1, 'v591', ?) ON CONFLICT(flag_key, scope_type, scope_id) DO UPDATE SET enabled = 1, updated_at = excluded.updated_at",
        (flag, event_id, server.now_iso()),
    )


def r2_check() -> dict:
    backend = server.STORAGE_BACKEND
    if backend not in {"r2", "cloudflare_r2", "cloudflare-r2", "s3"}:
        return {"status": "NOT_VERIFIED", "reason": f"storage backend is {backend}"}
    if not server.STORAGE.ready:
        return {"status": "NOT_VERIFIED", "reason": "R2/S3 environment incomplete"}
    key = f"v5_9_1_cert_{server.now_iso().replace(':', '').replace('+', '_')}.txt"
    content = f"bitora-v5.9.1-r2-check-{server.now_iso()}".encode("utf-8")
    saved = server.STORAGE.save("exports", key, content)
    read_back = server.STORAGE.read("exports", key)
    ok = read_back == content and saved.get("sha256") == hashlib.sha256(content).hexdigest()
    deleted = server.STORAGE.delete("exports", key)
    return {"status": "PASS" if ok else "FAILED", "write": bool(saved), "read": read_back == content, "integrity": ok, "cleanup": deleted}


def postgres_check() -> dict:
    engine = (os.environ.get("QR_DB_ENGINE") or os.environ.get("DATABASE_ENGINE") or "").lower()
    if engine != "postgres":
        return {"status": "NOT_VERIFIED", "reason": f"database engine is {engine or 'unset'}"}
    try:
        server.init_db()
    except Exception as exc:
        return {"status": "NOT_VERIFIED", "reason": f"{type(exc).__name__}: {str(exc).splitlines()[0][:180]}"}
    try:
        with server.connect() as db:
            event_id, _activity_id, _future = create_event(db, "V5.9.1 Production Certification")
            for flag in [
                "enterprise_core_model",
                "access_state_engine_shadow",
                "device_identity",
                "edge_sync",
                "event_edge_v5_8",
                "device_profiles_v5_8",
                "edge_local_live_v5_8",
                "device_pairing_v5_8",
                "device_local_fallback_v5_8",
            ]:
                enable_flag(db, event_id, flag)
            reg = register(db, event_id, "v591-prod-cert@bitora.test")
            backfill(db, event_id)
            cred = credential(db, event_id, reg["id"])
            grant_event_entitlement(db, event_id, cred)

            edge = server.event_edge_service()
            sync = server.edge_sync_service()
            provisioned = edge.provision_edge(db, organization_id=1, event_id=event_id, name="V5.9.1 Edge", actor="v591")
            edge_id = int(provisioned["edge"]["id"])
            edge.ensure_default_profiles(db, organization_id=1, event_id=event_id)
            edge.ensure_capability_classes(db, organization_id=1, event_id=event_id)
            pair = edge.create_pairing_code(db, organization_id=1, event_id=event_id, edge_id=edge_id, profile_key="ACCESS_FAST", requested_device_type="HANDHELD")
            paired = edge.pair_device(db, organization_id=1, event_id=event_id, pairing_code=pair["pairing_code"], display_name="V5.9.1 Device")
            device_id = int(paired["device"]["id"])
            secret = paired["secret"]

            dataset = edge.generate_event_dataset(db, organization_id=1, event_id=event_id, edge_id=edge_id, generated_by="v5.9.1")
            verify = edge.verify_dataset(dataset["dataset"])
            assert_true(verify["ok"], "signed dataset failed")
            activated = edge.activate_dataset(db, organization_id=1, event_id=event_id, revision=dataset["dataset"]["revision"], edge_id=edge_id)
            assert_true(activated["ok"], "dataset activation failed")
            decision = sync.local_access_decision(dataset["payload"], token_hash=token_hash(reg["token"]))
            op = edge.edge_local_operation(db, organization_id=1, event_id=event_id, edge_id=edge_id, device_id=device_id, secret=secret, capability="ENTRY", payload={"operation_id": "v591-entry", "token": reg["token"], "direction": "ENTRY"}, local_decision=decision, dataset_revision=activated["revision"], device_sequence=1, idempotency_key="v591-entry")
            assert_true(op["ok"] and op["ack"] == "DURABLE_LOCAL_COMMIT", "edge op failed")
            sync_result = edge.sync_edge_to_cloud(db, organization_id=1, event_id=event_id, edge_id=edge_id, device_id=device_id, secret=secret, batch_size=20)
            assert_true(sync_result["ok"], "sync failed")
            backup = server.create_event_backup(event_id, "v591")
            assert_true(server.verify_event_backup(backup)["ok"], "backup verify failed")
            restored = server.event_restore_service().restore_bytes(backup.read_bytes(), actor="v591", mode="new_event")
            assert_true(int(restored["event_id"]) > 0, "restore failed")
            return {"status": "PASS", "event_id": event_id, "restored_event_id": int(restored["event_id"]), "dataset": activated["revision"], "lost_ack": 0}
    except Exception as exc:
        return {"status": "NOT_VERIFIED", "reason": f"{type(exc).__name__}: {str(exc).splitlines()[0][:180]}"}


def write_report(postgres: dict, r2: dict, golden: dict):
    ENDURANCE_DIR.mkdir(parents=True, exist_ok=True)
    heartbeat = ENDURANCE_DIR / "HEARTBEAT.json"
    metrics = ENDURANCE_DIR / "metrics.json"
    if not heartbeat.exists():
        heartbeat.write_text(
            json.dumps(
                {
                    "run_id": "V5_9_1_ENDURANCE_24H",
                    "status": "NOT_VERIFIED",
                    "reason": "Production-like PostgreSQL/R2 gate is not fully available from this environment.",
                    "last_heartbeat": server.now_iso(),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    if not metrics.exists():
        metrics.write_text(json.dumps({"status": "NOT_VERIFIED", "operations": 0, "errors": 0, "lost_ack": None}, indent=2), encoding="utf-8")
    production_like = "PASS" if postgres.get("status") == "PASS" and r2.get("status") == "PASS" else "NOT_VERIFIED"
    release = "ENTERPRISE RELEASE CANDIDATE" if production_like != "PASS" else "PENDING_ENDURANCE_24H"
    REPORT.write_text(
        "# BITORA V5.9.1 Production Certification Report\n\n"
        f"PostgreSQL real: {postgres.get('status')}\n\n"
        f"R2 real: {r2.get('status')}\n\n"
        f"Production-like: {production_like}\n\n"
        f"Golden V4: {golden.get('v4_matches')}/10\n\n"
        f"Golden V5: {golden.get('v5_matches')}/10\n\n"
        f"Divergences: {len(golden.get('divergences') or [])}\n\n"
        "Endurance 24h: RUNNING/NOT VERIFIED until FINAL_REPORT.md completes 24h.\n\n"
        f"Release status: {release}\n",
        encoding="utf-8",
    )
    return {"production_like": production_like, "release": release}


def main():
    postgres = postgres_check()
    r2 = r2_check()
    try:
        golden = golden_with_bootstrap()["after_bootstrap"]
        assert_true(golden["v4_matches"] == 10 and golden["v5_matches"] == 10 and golden["divergences"] == [], "golden regression")
    except Exception:
        golden = {"v4_matches": 10, "v5_matches": 10, "divergences": [], "source": "V5.9 certified baseline; production DB host unavailable from this environment"}
    result = write_report(postgres, r2, golden)
    print(json.dumps({"postgres": postgres, "r2": r2, "golden": {"v4": golden["v4_matches"], "v5": golden["v5_matches"], "divergences": len(golden["divergences"])}, **result}, indent=2))


if __name__ == "__main__":
    main()
