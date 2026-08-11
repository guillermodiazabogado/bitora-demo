from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.storage import StorageService


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def required_r2_config_present() -> bool:
    has_endpoint = bool(os.environ.get("R2_ENDPOINT") or os.environ.get("R2_ACCOUNT_ID") or os.environ.get("S3_ENDPOINT_URL"))
    return all(
        [
            has_endpoint,
            os.environ.get("R2_BUCKET") or os.environ.get("S3_BUCKET"),
            os.environ.get("R2_ACCESS_KEY_ID") or os.environ.get("S3_ACCESS_KEY_ID"),
            os.environ.get("R2_SECRET_ACCESS_KEY") or os.environ.get("S3_SECRET_ACCESS_KEY"),
        ]
    )


def assert_raises(label: str, fn) -> dict:
    try:
        fn()
    except Exception:
        return {"name": label, "status": "PASSED"}
    return {"name": label, "status": "FAILED", "detail": "Operacion insegura aceptada"}


def main() -> int:
    checks: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="bitora-storage-contract-") as temp:
        storage = StorageService(Path(temp), "local")
        storage.ensure()
        payload = b"BITORA storage contract"
        record = storage.save_event(7, "certificates", "contract.pdf", payload)
        checks.append({"name": "local_save_event", "status": "PASSED" if record["sha256"] == hashlib.sha256(payload).hexdigest() else "FAILED"})
        checks.append({"name": "local_read_event", "status": "PASSED" if storage.read_event(7, "certificates", "contract.pdf") == payload else "FAILED"})
        checks.append({"name": "local_inventory", "status": "PASSED" if storage.event_inventory(7) else "FAILED"})
        checks.append(assert_raises("path_traversal_name", lambda: storage.save_event(7, "certificates", "../evil.pdf", b"x")))
        checks.append(assert_raises("path_traversal_relative", lambda: storage.restore_event_file(7, "../evil.pdf", b"x")))

    r2_enabled = required_r2_config_present()
    if r2_enabled:
        storage = StorageService(Path("/tmp/bitora-unused"), "r2")
        key_name = f"contract-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.txt"
        payload = b"BITORA R2 live contract"
        record = storage.save_event(7, "uploads", key_name, payload)
        checks.append({"name": "r2_ready", "status": "PASSED" if storage.ready else "FAILED"})
        checks.append({"name": "r2_put", "status": "PASSED" if record["sha256"] == hashlib.sha256(payload).hexdigest() else "FAILED"})
        checks.append({"name": "r2_get", "status": "PASSED" if storage.read_event(7, "uploads", key_name) == payload else "FAILED"})
        inventory_keys = {item["key"] for item in storage.event_inventory(7)}
        checks.append({"name": "r2_list_prefix", "status": "PASSED" if record["key"] in inventory_keys else "FAILED"})
        checks.append({"name": "r2_delete", "status": "PASSED" if storage.delete_event(7, "uploads", key_name) else "FAILED"})
    else:
        checks.append({"name": "r2_live_config", "status": "OMITTED", "detail": "Faltan variables R2 reales"})

    failed = [check for check in checks if check["status"] == "FAILED"]
    report = {
        "timestamp": now(),
        "classification": "live" if r2_enabled else "contract",
        "r2_configured": r2_enabled,
        "checks": checks,
        "result": "FAILED" if failed else ("PASSED" if r2_enabled else "OMITTED"),
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
