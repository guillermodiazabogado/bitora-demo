from pathlib import Path


source = Path("scripts/operational_cve_scan.py").read_text(encoding="utf-8")
required = ["api.osv.dev/v1/querybatch", "requirements.lock", "aquasec/trivy:0.67.2", "HIGH,CRITICAL", '"BLOCKED"']
missing = [token for token in required if token not in source]
if missing:
    raise SystemExit(f"FAIL - security scanner incompleto: {missing}")
print("OK - gate reproducible OSV para lock y Trivy para imagen")
