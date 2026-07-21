from __future__ import annotations

import json
from urllib.parse import parse_qs, urlparse

from backend.services.google_oauth import GoogleOAuthClient
from google_oauth_test_utils import assert_no_secret_leak, google_env
from live_integrations_utils import assert_true, write_report


NAME = "google_oauth_contract"


def main() -> None:
    with google_env():
        client = GoogleOAuthClient()
        validation = client.validate_configuration()
        assert_true(validation["ok"], "Configuracion Google contract debe ser valida")
        url = client.authorization_url(state="state-contract")
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        assert_true(params["state"][0] == "state-contract", "Authorization URL debe incluir state")
        assert_true(params["access_type"][0] == "offline", "OAuth debe pedir offline access")
        assert_true(params["prompt"][0] == "consent", "OAuth debe pedir consentimiento explicito")
        assert_true("openid" in params["scope"][0], "Debe pedir scope openid")
        assert_no_secret_leak(url)
        result = {
            "name": NAME,
            "mode": "contract",
            "status": "passed",
            "checks": {
                "authorization_url": True,
                "offline_access": True,
                "prompt_consent": True,
                "scopes_minimos": validation["scopes"],
                "secret_exposed": 0,
            },
        }
        write_report(NAME, result)
        print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
