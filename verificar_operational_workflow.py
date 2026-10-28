from pathlib import Path


source = Path(".github/workflows/operational-readiness.yml").read_text(encoding="utf-8")
required = [
    "workflow_dispatch", "verificar_operational_postgres_restore.py",
    "operational_postgres_restore.py", "operational_integrated_endurance.py",
    "pip-audit==2.10.1", "operational_cve_scan.py", "upload-artifact@v4",
    "certification/5.8.2-operational-readiness", "inputs.endurance_stage || '15m'",
    "field-endurance-checkpoint.json", "timeout-minutes: 90",
]
missing = [token for token in required if token not in source]
forbidden = [token for token in ("deployment/v4-online", "environment: production", "main", "deploy") if token in source.lower()]
if missing or forbidden:
    raise SystemExit(f"FAIL - operational workflow: missing={missing}, forbidden={forbidden}")
print("OK - workflow operacional restringido a certificación, aislado y con evidencia")
