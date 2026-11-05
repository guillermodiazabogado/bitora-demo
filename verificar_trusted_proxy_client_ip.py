from __future__ import annotations

import os

import server


class Handler:
    def __init__(self, peer: str, real_ip: str | None = None) -> None:
        self.client_address = (peer, 443)
        self.headers = {} if real_ip is None else {"X-Real-IP": real_ip}


def main() -> None:
    previous = os.environ.get("BITORA_TRUST_PROXY_HEADERS")
    previous_secret = os.environ.get("SESSION_SECRET")
    try:
        os.environ["SESSION_SECRET"] = "proxy-contract-test-only"
        os.environ.pop("BITORA_TRUST_PROXY_HEADERS", None)
        if server.request_client_ip(Handler("10.0.0.1", "198.51.100.10")) != "10.0.0.1":
            raise AssertionError("Proxy headers must be ignored unless explicitly trusted")

        os.environ["BITORA_TRUST_PROXY_HEADERS"] = "true"
        first = Handler("10.0.0.1", "198.51.100.10")
        second = Handler("10.0.0.2", "198.51.100.10")
        if server.request_client_ip(first) != "198.51.100.10":
            raise AssertionError("Trusted X-Real-IP was not selected")
        if server.login_request_fingerprint(first, "operator") != server.login_request_fingerprint(second, "operator"):
            raise AssertionError("The same client must share a rate-limit fingerprint across proxy nodes")
        if server.request_client_ip(Handler("10.0.0.3", "spoofed, 198.51.100.10")) != "10.0.0.3":
            raise AssertionError("Malformed proxy header must fall back to the socket peer")
    finally:
        if previous is None:
            os.environ.pop("BITORA_TRUST_PROXY_HEADERS", None)
        else:
            os.environ["BITORA_TRUST_PROXY_HEADERS"] = previous
        if previous_secret is None:
            os.environ.pop("SESSION_SECRET", None)
        else:
            os.environ["SESSION_SECRET"] = previous_secret
    print("Trusted proxy client IP and multi-proxy fingerprint contract: OK")


if __name__ == "__main__":
    main()
