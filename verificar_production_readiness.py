from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import server
from backend.storage import StorageService


def main() -> None:
    valid = server.validate_production_configuration(
        {
            "APP_ENV": "production",
            "BASE_URL": "https://app.bitora.ar",
            "HTTPS_REQUIRED": "true",
            "QR_REQUIRE_LOGIN": "1",
            "QR_DB_ENGINE": "postgres",
            "QR_POSTGRES_DSN": "postgresql://user:secret@db/bitora",
            "STORAGE_BACKEND": "local",
        }
    )
    assert valid["ok"]
    invalid = server.validate_production_configuration(
        {
            "APP_ENV": "production",
            "BASE_URL": "http://bitora.test",
            "HTTPS_REQUIRED": "false",
            "QR_REQUIRE_LOGIN": "0",
            "QR_DB_ENGINE": "sqlite",
            "QR_POSTGRES_DSN": "",
        }
    )
    assert not invalid["ok"] and len(invalid["errors"]) >= 4

    tmp = Path(tempfile.mkdtemp(prefix="bitora-production-readiness-"))
    old_db = server.DB_PATH
    old_backup = server.BACKUP_DIR
    try:
        server.DB_PATH = tmp / "readiness.sqlite3"
        server.BACKUP_DIR = tmp / "backups"
        server.init_db()
        server.seed_if_empty()
        payload, status = server.production_health_payload()
        assert status == 200
        for key in ("status", "env", "version", "db", "jobs", "cache", "backup", "storage", "uptime"):
            assert key in payload

        storage = StorageService(tmp / "storage")
        storage.ensure()
        saved = storage.save("exports", "readiness.txt", b"ok")
        assert saved["size"] == 2 and storage.read("exports", "readiness.txt") == b"ok"
        try:
            storage.save("exports", "../escape.txt", b"bad")
        except ValueError:
            pass
        else:
            raise AssertionError("Storage permitio una ruta insegura")

        old_env = server.APP_ENV
        server.APP_ENV = "production"
        try:
            message = server.safe_public_error(RuntimeError("postgresql://user:secret@host/db"))
            assert message == "Error interno controlado" and "secret" not in message
        finally:
            server.APP_ENV = old_env
    finally:
        server.DB_PATH = old_db
        server.BACKUP_DIR = old_backup
        shutil.rmtree(tmp, ignore_errors=True)

    required_docs = (
        "PRODUCTION_RECOVERY_PLAN.md",
        "PRE_EVENT_PRODUCTION_CHECKLIST.md",
        "PRODUCTION_DEPLOYMENT.md",
        "BITORA_PRODUCTION_READINESS_REPORT.md",
    )
    assert all(Path(name).exists() for name in required_docs)
    frontend = Path("frontend/index.html").read_text(encoding="utf-8")
    assert "Recepcion" in frontend and "Data Visualization" in frontend
    assert Path("frontend/noc.html").exists() and Path("frontend/scan.html").exists()
    print("OK: readiness productiva, health, HTTPS/config, storage, seguridad y documentos")


if __name__ == "__main__":
    main()
