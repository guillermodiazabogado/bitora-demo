from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import time
import uuid


ROOT = Path(__file__).resolve().parents[1]


def run(args: list[str], *, timeout: int = 900, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, cwd=ROOT, text=True, capture_output=True, timeout=timeout)
    if check and result.returncode:
        raise RuntimeError(f"COMMAND_FAILED:{args[0]}:{result.returncode}:{(result.stderr or result.stdout)[-2000:]}")
    return result


def docker(*args: str, timeout: int = 900, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run(["docker", *args], timeout=timeout, check=check)


def sql(container: str, database: str, statement: str) -> str:
    return docker("exec", container, "psql", "-U", "bitora", "-d", database, "-Atqc", statement).stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Backup/restore PostgreSQL 16 aislado de BITORA")
    parser.add_argument("--report", type=Path, default=ROOT / "artifacts" / "operational-postgres-restore.json")
    args = parser.parse_args()
    run_id = uuid.uuid4().hex[:10]
    container = f"bitora-restore-{run_id}"
    network = container
    image = f"bitora-restore-{run_id}:test"
    source_db, restored_db = "bitora_source", "bitora_restored"
    dsn = f"postgresql://bitora:temporary-operational@postgres:5432/{source_db}"
    report = {"ok": False, "run_id": run_id, "sha": run(["git", "rev-parse", "HEAD"]).stdout.strip(), "checks": {}, "started_at": datetime.now(timezone.utc).isoformat()}
    created = False
    try:
        if docker("info", timeout=30, check=False).returncode:
            raise RuntimeError("DOCKER_DAEMON_UNAVAILABLE")
        docker("network", "create", network)
        created = True
        docker("run", "-d", "--name", container, "--network", network, "--network-alias", "postgres", "-e", "POSTGRES_USER=bitora", "-e", "POSTGRES_PASSWORD=temporary-operational", "-e", f"POSTGRES_DB={source_db}", "postgres:16-alpine")
        for _ in range(60):
            if docker("exec", container, "pg_isready", "-U", "bitora", "-d", source_db, check=False, timeout=10).returncode == 0:
                break
            time.sleep(1)
        else:
            raise RuntimeError("POSTGRES_NOT_READY")
        docker("build", "-t", image, ".", timeout=1200)
        env = ["-e", "APP_ENV=development", "-e", "BITORA_SAFE_MODE=true", "-e", "QR_DB_ENGINE=postgres", "-e", f"QR_POSTGRES_DSN={dsn}", "-e", f"DATABASE_URL={dsn}"]
        docker("run", "--rm", "--network", network, *env, image, "python", "-c", "import server; server.init_db(); server.seed_if_empty()", timeout=600)
        sql(container, source_db, "INSERT INTO technical_logs(level,category,message,details,created_at) VALUES ('info','operational_restore','controlled-marker','{}',CURRENT_TIMESTAMP)")
        summary_query = "SELECT json_build_object('migrations',(SELECT count(*) FROM schema_migrations),'users',(SELECT count(*) FROM users),'events',(SELECT count(*) FROM events),'marker',(SELECT count(*) FROM technical_logs WHERE message='controlled-marker'))::text"
        source_summary = json.loads(sql(container, source_db, summary_query))
        backup_started = time.perf_counter()
        docker("exec", container, "pg_dump", "-U", "bitora", "-d", source_db, "-Fc", "-f", "/tmp/bitora.dump")
        backup_seconds = time.perf_counter() - backup_started
        checksum = docker("exec", container, "sha256sum", "/tmp/bitora.dump").stdout.split()[0]
        backup_bytes = int(docker("exec", container, "stat", "-c", "%s", "/tmp/bitora.dump").stdout.strip())
        docker("exec", container, "createdb", "-U", "bitora", restored_db)
        restore_started = time.perf_counter()
        docker("exec", container, "pg_restore", "-U", "bitora", "-d", restored_db, "--exit-on-error", "/tmp/bitora.dump")
        restore_seconds = time.perf_counter() - restore_started
        restored_summary = json.loads(sql(container, restored_db, summary_query))
        integrity = sql(container, restored_db, "SELECT count(*) FROM pg_constraint WHERE contype IN ('p','f','u','c')")
        report.update({
            "backup": {"bytes": backup_bytes, "sha256": checksum, "seconds": round(backup_seconds, 3)},
            "restore": {"seconds": round(restore_seconds, 3)},
            "source_summary": source_summary,
            "restored_summary": restored_summary,
            "observed_rto_seconds": round(restore_seconds, 3),
            "observed_rpo_seconds": 0,
            "rpo_qualification": "Observed only for a quiesced controlled dataset; not a production RPO objective and not evidence of continuous replication.",
            "constraints_after_restore": int(integrity),
        })
        report["checks"] = {
            "checksum_created": len(checksum) == 64,
            "nonempty_backup": backup_bytes > 0,
            "content_equal": source_summary == restored_summary,
            "controlled_marker_restored": restored_summary.get("marker") == 1,
            "constraints_present": int(integrity) > 0,
        }
        report["ok"] = all(report["checks"].values())
    except Exception as exc:
        report["error"] = str(exc)
    finally:
        if created:
            docker("rm", "-f", container, check=False, timeout=60)
            docker("network", "rm", network, check=False, timeout=60)
            docker("image", "rm", image, check=False, timeout=120)
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())

