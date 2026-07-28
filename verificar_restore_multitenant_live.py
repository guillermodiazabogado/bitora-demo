from __future__ import annotations

import json
import os
from pathlib import Path

from live_integrations_utils import classify, write_report


NAME = "restore_multitenant_live"
EVIDENCE = Path(__file__).resolve().parent / "output" / "live_integrations" / f"{NAME}.json"


def main() -> None:
    mode, missing = classify(["APP_ENV", "QR_POSTGRES_DSN", "BITORA_STORAGE_PATH"])
    if missing:
        result = {
            "name": NAME,
            "mode": mode,
            "status": "omitted",
            "missing_env": missing,
            "checks": {"reason": "Faltan variables live para restore multitenant."},
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
    if not checks.get("isolated_restore"):
        raise AssertionError("Restore aislado no validado")
    if not checks.get("manifest_comparison"):
        raise AssertionError("Comparacion de manifiestos no validada")
    if checks.get("external_effects_post_restore") != 0:
        raise AssertionError("Restore produjo efectos externos")
    if checks.get("cross_event_access") != 0 or checks.get("cross_organization_access") != 0:
        raise AssertionError("Restore permitio cruces multitenant")
    if checks.get("duplicate_sends") != 0:
        raise AssertionError("Restore produjo envios duplicados")
    write_report(NAME, result)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
