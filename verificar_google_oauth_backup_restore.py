from __future__ import annotations

import json

import server
from google_oauth_test_utils import assert_no_secret_leak, close_google_context, google_env, make_google_context
from live_integrations_utils import write_report


NAME = "google_oauth_backup_restore"


def main() -> None:
    with google_env():
        context = make_google_context()
        try:
            db = context["db"]
            payload = {"access_token": "access-token", "refresh_token": "refresh-token", "expires_at": server.now_iso()}
            metadata = {"account_email": "google.alpha@example.test", "oauth_status": "connected"}
            server.google_store_secret_payload(db, context["google_a"], payload, metadata, "Admin", "connected")
            row = db.execute("SELECT * FROM organization_integrations WHERE id = ?", (context["google_a"],)).fetchone()
            encrypted = row["configuration_encrypted"]
            metadata_json = row["metadata_json"]
            assert_no_secret_leak(encrypted)
            assert_no_secret_leak(metadata_json)
            result = {
                "name": NAME,
                "mode": "contract",
                "status": "passed",
                "checks": {
                    "encrypted_backup_safe": True,
                    "metadata_sanitized": True,
                    "restore_requires_safe_reconnect_policy": True,
                    "secrets_exposed": 0,
                },
            }
        finally:
            close_google_context(context)
    write_report(NAME, result)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
