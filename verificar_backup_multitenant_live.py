from __future__ import annotations

import json

from live_integrations_utils import assert_true, classify, close_context, contract_result, synthetic_multitenant_db, write_report


NAME = "backup_multitenant_live"


def main() -> None:
    mode, missing = classify(["APP_ENV", "QR_POSTGRES_DSN", "BITORA_STORAGE_PATH"])
    context = synthetic_multitenant_db()
    checks = {}
    try:
        db = context["db"]
        orgs = db.execute("SELECT COUNT(*) AS c FROM organizations").fetchone()["c"]
        events = db.execute("SELECT COUNT(*) AS c FROM events WHERE organization_id IS NOT NULL").fetchone()["c"]
        encrypted = context["encrypted"]
        assert_true(orgs >= 2, "Debe existir mas de una organizacion")
        assert_true(events >= 2, "Debe existir mas de un evento multi-tenant")
        assert_true("secret-value" not in encrypted, "Backup no debe partir de secretos planos")
        checks = {
            "organizations_present": int(orgs),
            "events_with_organization": int(events),
            "plain_secrets": 0,
        }
    finally:
        close_context(context)
    result = contract_result(NAME, mode, missing, checks)
    write_report(NAME, result)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
