from pathlib import Path


source = Path(".github/workflows/operational-readiness.yml").read_text(encoding="utf-8")
required = [
    "workflow_dispatch", "verificar_operational_postgres_restore.py",
    "operational_postgres_restore.py", "operational_multiinstance.py",
    "pip-audit==2.10.1", "operational_cve_scan.py", "upload-artifact@v4",
]
missing = [token for token in required if token not in source]
forbidden = [token for token in ("push:", "deployment/v4-online", "environment: production") if token in source]
if missing or forbidden:
    raise SystemExit(f"FAIL - operational workflow: missing={missing}, forbidden={forbidden}")
print("OK - workflow operacional manual, aislado y con evidencia")
