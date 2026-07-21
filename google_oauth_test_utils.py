from __future__ import annotations

import json
import os
from contextlib import contextmanager
from typing import Any

import server
from live_integrations_utils import assert_true, close_context, synthetic_multitenant_db


@contextmanager
def google_env() -> Any:
    keys = {
        "GOOGLE_OAUTH_ENABLED": "true",
        "GOOGLE_OAUTH_CLIENT_ID": "google-client-id.apps.googleusercontent.com",
        "GOOGLE_OAUTH_CLIENT_SECRET": "google-client-secret",
        "GOOGLE_OAUTH_REDIRECT_URI": "http://localhost:8788/api/integrations/google/callback",
        "GOOGLE_OAUTH_SCOPES": "openid email profile",
    }
    previous = {key: os.environ.get(key) for key in keys}
    os.environ.update(keys)
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def make_google_context() -> dict[str, Any]:
    context = synthetic_multitenant_db()
    db = context["db"]
    now = server.now_iso()
    encrypted = server.integration_secret_service().encrypt(json.dumps({"placeholder": "google"}))
    google_a = int(db.execute(
        """
        INSERT INTO organization_integrations (
            organization_id, provider, integration_type, name, mode, status,
            configuration_encrypted, metadata_json, created_by, updated_by, created_at, updated_at
        )
        VALUES (?, 'google', 'oauth_provider', 'Google Alfa', 'client_owned', 'disconnected', ?, '{}', 'Admin', 'Admin', ?, ?)
        """,
        (context["org_a"], encrypted, now, now),
    ).lastrowid)
    google_b = int(db.execute(
        """
        INSERT INTO organization_integrations (
            organization_id, provider, integration_type, name, mode, status,
            configuration_encrypted, metadata_json, created_by, updated_by, created_at, updated_at
        )
        VALUES (?, 'google', 'oauth_provider', 'Google Beta', 'client_owned', 'disconnected', ?, '{}', 'Admin', 'Admin', ?, ?)
        """,
        (context["org_b"], encrypted, now, now),
    ).lastrowid)
    context["google_a"] = google_a
    context["google_b"] = google_b
    return context


def close_google_context(context: dict[str, Any]) -> None:
    close_context(context)


def assert_no_secret_leak(text: str) -> None:
    forbidden = ["google-client-secret", "access-token", "refresh-token", "authorization-code"]
    for item in forbidden:
        assert_true(item not in text, f"Se filtro secreto: {item}")


class FakeGoogleResponse:
    def __init__(self, payload: dict | None = None) -> None:
        self.payload = payload or {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class FakeGoogleTransport:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def __call__(self, request, timeout=15):
        url = request.full_url
        self.calls.append(url)
        if "token" in url:
            body = (request.data or b"").decode("utf-8")
            if "grant_type=refresh_token" in body:
                return FakeGoogleResponse({"access_token": "access-token-refreshed", "expires_in": 3600, "token_type": "Bearer", "scope": "openid email profile"})
            return FakeGoogleResponse({"access_token": "access-token", "refresh_token": "refresh-token", "expires_in": 3600, "token_type": "Bearer", "scope": "openid email profile"})
        if "userinfo" in url:
            return FakeGoogleResponse({"sub": "google-account-1", "email": "google.alpha@example.test"})
        return FakeGoogleResponse({})
