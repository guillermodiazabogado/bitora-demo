from __future__ import annotations

import json
from datetime import datetime, timedelta

import server
from google_oauth_test_utils import assert_no_secret_leak, close_google_context, google_env, make_google_context
from live_integrations_utils import assert_true, write_report


NAME = "google_oauth_security"


def main() -> None:
    with google_env():
        context = make_google_context()
        try:
            db = context["db"]
            state = server.create_google_oauth_state(
                db,
                organization_id=context["org_a"],
                integration_id=context["google_a"],
                user_id=1,
                actor="Admin",
                redirect_after="/",
            )
            row = server.consume_google_oauth_state(db, state)
            assert_true(int(row["organization_id"]) == context["org_a"], "State debe resolver organizacion")
            reused = False
            try:
                server.consume_google_oauth_state(db, state)
            except Exception:
                reused = True
            assert_true(reused, "State reutilizado debe fallar")

            expired_state = server.create_google_oauth_state(
                db,
                organization_id=context["org_a"],
                integration_id=context["google_a"],
                user_id=1,
                actor="Admin",
                redirect_after="/",
            )
            db.execute(
                "UPDATE google_oauth_states SET expires_at = ? WHERE state_token = ?",
                ((datetime.fromisoformat(server.now_iso()) - timedelta(minutes=1)).isoformat(timespec="seconds"), expired_state),
            )
            expired = False
            try:
                server.consume_google_oauth_state(db, expired_state)
            except Exception:
                expired = True
            assert_true(expired, "State vencido debe fallar")

            payload = {"access_token": "access-token", "refresh_token": "refresh-token"}
            encrypted = server.integration_secret_service().encrypt(json.dumps(payload))
            assert_no_secret_leak(encrypted)
            result = {
                "name": NAME,
                "mode": "contract",
                "status": "passed",
                "checks": {
                    "state_single_use": True,
                    "state_expiration": True,
                    "token_encryption": True,
                    "tokens_exposed": 0,
                    "secrets_exposed": 0,
                },
            }
        finally:
            close_google_context(context)
    write_report(NAME, result)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
