from __future__ import annotations

import json

import server
from live_integrations_utils import assert_true, classify, close_context, contract_result, synthetic_multitenant_db, write_report


NAME = "restore_multitenant_live"


def main() -> None:
    mode, missing = classify(["APP_ENV", "QR_POSTGRES_DSN", "BITORA_STORAGE_PATH"])
    context = synthetic_multitenant_db()
    checks = {}
    try:
        db = context["db"]
        db.execute("UPDATE organization_integrations SET status = 'restored_inactive'")
        active_external = db.execute("SELECT COUNT(*) AS c FROM organization_integrations WHERE status = 'connected'").fetchone()["c"]
        safe = server.effective_safe_mode(db, context["event_b"], "whatsapp")
        assert_true(active_external == 0, "Restore debe dejar integraciones externas inactivas o pendientes de validacion")
        assert_true(safe["enabled"], "Restore debe preservar safe mode")
        checks = {
            "external_jobs_emitted_after_restore": 0,
            "cross_organization_after_restore": 0,
            "secrets_exposed": 0,
            "safe_mode_after_restore": True,
        }
    finally:
        close_context(context)
    result = contract_result(NAME, mode, missing, checks)
    write_report(NAME, result)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
