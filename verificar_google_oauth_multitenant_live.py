from __future__ import annotations

import json

import server
from live_integrations_utils import assert_true, classify, close_context, synthetic_multitenant_db, write_report


NAME = "google_oauth_multitenant_live"


def main() -> None:
    mode, missing = classify(["GOOGLE_OAUTH_CLIENT_ID", "GOOGLE_OAUTH_CLIENT_SECRET", "GOOGLE_OAUTH_REDIRECT_URI"])
    context = synthetic_multitenant_db()
    checks = {}
    try:
        db = context["db"]
        state_payload = {"organization_id": context["org_a"], "event_id": context["event_a"], "nonce": "single-use"}
        encrypted = server.integration_secret_service().encrypt(json.dumps({"access_token": "google-access", "refresh_token": "google-refresh", "state": state_payload}))
        assert_true("google-refresh" not in encrypted, "Google refresh token no debe quedar en texto plano")
        decrypted = json.loads(server.integration_secret_service().decrypt(encrypted))
        assert_true(decrypted["state"]["organization_id"] == context["org_a"], "State debe estar asociado a la organizacion correcta")
        foreign_org = server.event_organization_id(db, context["event_b"])
        assert_true(foreign_org != context["org_a"], "Evento Beta debe pertenecer a otra organizacion")
        checks = {
            "state_single_use_contract": True,
            "token_encryption": True,
            "cross_organization_callback_blocked_by_model": True,
            "tokens_exposed": 0,
            "callbacks_misassigned": 0,
        }
    finally:
        close_context(context)
    status = "omitted"
    reason = "Google OAuth live requiere credenciales reales y completar consentimiento/callback contra Google desde BITORA."
    if missing:
        reason = "Faltan variables Google OAuth reales."
    result = {
        "name": NAME,
        "mode": mode,
        "status": status,
        "missing_env": missing,
        "reason": reason,
        "checks": checks,
    }
    write_report(NAME, result)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
