from __future__ import annotations

import json
import os
from pathlib import Path

from live_integrations_utils import classify, write_report


NAME = "backup_multitenant_live"
EVIDENCE = Path(__file__).resolve().parent / "output" / "live_integrations" / f"{NAME}.json"


def main() -> None:
    mode, missing = classify(["APP_ENV", "QR_POSTGRES_DSN", "BITORA_STORAGE_PATH"])
    if missing:
        result = {
            "name": NAME,
            "mode": mode,
            "status": "omitted",
            "missing_env": missing,
            "checks": {"reason": "Faltan variables live para backup multitenant."},
        }
        write_report(NAME, result)
        print(json.dumps(result, ensure_ascii=False))
        return
    if not EVIDENCE.exists():
        result = {
            "name": NAME,
            "mode": "live" if os.environ.get("APP_ENV") == "staging" else mode,
            "status": "omitted",
            "missing_env": [],
            "checks": {"reason": "Falta ejecutar python deployment/scripts/certify_backup_restore_live.py"},
        }
        write_report(NAME, result)
        print(json.dumps(result, ensure_ascii=False))
        return
    result = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    if result.get("mode") != "live" or result.get("status") != "passed":
        raise AssertionError(f"Evidencia live invalida para {NAME}: {result.get('status')}")
    checks = result.get("checks", {})
    if not checks.get("database_backup"):
        raise AssertionError("Backup de base no validado")
    if not checks.get("storage_backup"):
        raise AssertionError("Backup de storage no validado")
    if checks.get("secrets_exposed") != 0:
        raise AssertionError("Se detectaron secretos expuestos")
    write_report(NAME, result)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
