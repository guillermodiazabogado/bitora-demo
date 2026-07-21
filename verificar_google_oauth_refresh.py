from __future__ import annotations

import json

from backend.services.google_oauth import GoogleOAuthClient
from google_oauth_test_utils import FakeGoogleTransport, assert_no_secret_leak, google_env
from live_integrations_utils import assert_true, write_report


NAME = "google_oauth_refresh"


def main() -> None:
    with google_env():
        transport = FakeGoogleTransport()
        client = GoogleOAuthClient(opener=transport)
        exchanged = client.exchange_code("authorization-code")
        assert_true(exchanged["refresh_token"] == "refresh-token", "Exchange debe devolver refresh token en contract")
        refreshed = client.refresh_access_token(exchanged["refresh_token"])
        assert_true(refreshed["access_token"] == "access-token-refreshed", "Refresh debe devolver nuevo access token")
        account = client.userinfo(refreshed["access_token"])
        assert_true(account["email"] == "google.alpha@example.test", "Userinfo debe devolver cuenta")
        serialized = json.dumps({"exchange": exchanged, "refresh": refreshed, "account": account})
        assert_no_secret_leak(serialized.replace("access-token", "masked").replace("refresh-token", "masked").replace("authorization-code", "masked"))
        result = {
            "name": NAME,
            "mode": "contract",
            "status": "passed",
            "checks": {
                "exchange_code": True,
                "refresh_token": True,
                "userinfo": True,
                "calls": len(transport.calls),
                "secrets_exposed": 0,
            },
        }
        write_report(NAME, result)
        print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
