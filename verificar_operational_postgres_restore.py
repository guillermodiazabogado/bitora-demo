from pathlib import Path


source = Path("scripts/operational_postgres_restore.py").read_text(encoding="utf-8")
required = {
    "postgres:16-alpine": "PostgreSQL 16",
    '"pg_dump"': "pg_dump",
    '"pg_restore"': "pg_restore",
    '"sha256sum"': "backup checksum",
    "source_summary == restored_summary": "content comparison",
    "observed_rto_seconds": "RTO measurement",
    "observed_rpo_seconds": "RPO observation",
    "not a production RPO objective": "RPO qualification",
    'docker("rm", "-f", container': "isolated cleanup",
    "technical_logs(level,module,message,detail,request_path,created_at)": "current technical_logs schema",
}
missing = [label for token, label in required.items() if token not in source]
forbidden = [token for token in ("docker system prune", "docker volume prune", "DROP DATABASE bitora_staging") if token.lower() in source.lower()]
if missing or forbidden:
    raise SystemExit(f"FAIL - restore harness: missing={missing}, forbidden={forbidden}")
print("OK - harness PostgreSQL backup/restore aislado, medido y seguro")
