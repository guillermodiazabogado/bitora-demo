from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
TRACE = ROOT / "R2_RESTORE_ISOLATED_TRACE.log"


def trace(step: str) -> None:
    with TRACE.open("a", encoding="utf-8") as handle:
        handle.write(step + "\n")


def main() -> int:
    TRACE.write_text("", encoding="utf-8")
    trace("start")
    backup = Path(os.environ.get("BITORA_R2_RESTORE_BACKUP", "")).expanduser()
    if not backup.exists():
        raise SystemExit("BITORA_R2_RESTORE_BACKUP no existe")

    isolated = Path(tempfile.mkdtemp(prefix="bitora-r2-restore-isolated-"))
    os.environ.update(
        {
            "QR_DB_ENGINE": "sqlite",
            "QR_SQLITE_PATH": str(isolated / "restore.sqlite3"),
            "BITORA_STORAGE_PROVIDER": "local",
            "BITORA_STORAGE_PATH": str(isolated / "storage"),
            "APP_ENV": "local",
            "BITORA_LIVE_MODE": "false",
            "BITORA_SAFE_MODE": "true",
            "EMAIL_ENABLED": "false",
            "WHATSAPP_ENABLED": "false",
            "GOOGLE_OAUTH_ENABLED": "false",
        }
    )

    trace("import_server")
    import server
    from backend.services.backup import EventBackupService, EventRestoreService
    from backend.storage import StorageService

    trace("init_db")
    server.init_db()
    trace("read_backup")
    raw = backup.read_bytes()
    storage = StorageService(isolated / "storage", "local")
    storage.ensure()
    backup_service = EventBackupService(
        isolated / "backups",
        server.connect,
        server.DB_LOCK,
        app_version="restore-isolated",
        storage=storage,
    )
    token_counter = {"value": 0}

    def restored_token() -> str:
        token_counter["value"] += 1
        return f"RESTORED-TOKEN-{token_counter['value']:06d}"

    restore_service = EventRestoreService(
        server.connect,
        server.DB_LOCK,
        restored_token,
        server.now_iso,
        app_version="restore-isolated",
        backup_service=backup_service,
        storage=storage,
    )
    trace("inspect")
    inspected = restore_service.inspect_bytes(raw, backup.name)
    trace("restore")
    restored = restore_service.restore_bytes(
        raw,
        mode="new_event",
        actor="R2_RESTORE_VALIDATOR",
        new_event_name="BITORA R2 Restore Validation",
    )
    trace("validate")
    new_event_id = int(restored["event_id"])
    with server.connect() as db:
        counts = {
            "organizations": db.execute("SELECT COUNT(*) AS c FROM organizations").fetchone()["c"],
            "events": db.execute("SELECT COUNT(*) AS c FROM events").fetchone()["c"],
            "people": db.execute("SELECT COUNT(*) AS c FROM people").fetchone()["c"],
            "accreditations_restored": db.execute(
                "SELECT COUNT(*) AS c FROM accreditations WHERE event_id = ?", (new_event_id,)
            ).fetchone()["c"],
            "certificate_documents_restored": db.execute(
                "SELECT COUNT(*) AS c FROM certificate_documents WHERE event_id = ?", (new_event_id,)
            ).fetchone()["c"],
            "jobs_restored": db.execute("SELECT COUNT(*) AS c FROM jobs WHERE event_id = ?", (new_event_id,)).fetchone()["c"],
            "audit_restore": db.execute(
                "SELECT COUNT(*) AS c FROM audit_logs WHERE event_id = ? AND action = 'backup.event_restored'",
                (new_event_id,),
            ).fetchone()["c"],
        }
    files = storage.event_inventory(new_event_id)
    report = {
        "status": "PASSED"
        if inspected.get("ok")
        and restored.get("ok")
        and counts["accreditations_restored"] == inspected["counts"]["accreditations"]
        and len(files) == inspected["counts"]["files"]
        else "FAILED",
        "backup_file": backup.name,
        "backup_sha256": hashlib.sha256(raw).hexdigest().upper(),
        "isolated_root": str(isolated),
        "inspect": {
            "ok": inspected.get("ok"),
            "participants": inspected["counts"]["participants"],
            "accreditations": inspected["counts"]["accreditations"],
            "files": inspected["counts"]["files"],
            "files_size": inspected["counts"]["files_size"],
        },
        "restore": {
            "ok": restored.get("ok"),
            "new_event_id": new_event_id,
            "files_restored": restored.get("files_restored"),
            "duration_ms": restored.get("duration_ms"),
            "token_regenerated": restored.get("token_regenerated"),
        },
        "counts": counts,
        "storage_files_restored": len(files),
        "external_effects": 0,
    }
    (ROOT / "R2_RESTORE_ISOLATED_VALIDATION.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    trace("done")
    return 0 if report["status"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
