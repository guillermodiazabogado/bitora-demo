from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import server


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="bitora-v6-diagnostics-"))
    old_db, old_backup = server.DB_PATH, server.BACKUP_DIR
    try:
        server.DB_PATH = tmp / "diagnostics.sqlite3"
        server.BACKUP_DIR = tmp / "backups"
        server.init_db()
        server.seed_if_empty()
        server.technical_log("warning", "test", "Advertencia controlada", "EMAIL_API_KEY=test")
        with server.connect() as db:
            data = server.diagnostics_service().collect(
                db,
                runtime={**server.RUNTIME_METRICS.snapshot(), "worker_alive": True},
                sessions=[{"name": "Admin", "role": "Super Admin"}],
                auto_backup_minutes=10,
            )
        assert data["services"]["api"]["status"] == "online"
        assert data["database"]["engine"] == "sqlite"
        assert "p95_response_ms" in data["metrics"]
        assert data["cache"]["backend"] == "no configurada"
        assert data["recent_errors"] == []
        assert any(row["module"] == "test" for row in data["logs"])
        serialized = str(data)
        assert "EMAIL_API_KEY=test" not in serialized
        html = (Path("frontend") / "index.html").read_text(encoding="utf-8")
        assert "Diagnostico Tecnico" in html and 'id="diagnosticsNav"' in html
        print("OK: V6.0 diagnostico, metricas, alertas, logs y secretos protegidos")
    finally:
        server.DB_PATH, server.BACKUP_DIR = old_db, old_backup
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
