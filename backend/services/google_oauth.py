from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable


DEFAULT_GOOGLE_SCOPES = "openid email profile"


class GoogleOAuthError(RuntimeError):
    def __init__(self, message: str, code: str = "google_oauth_error") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class GoogleOAuthConfig:
    enabled: bool
    client_id: str
    client_secret: str
    redirect_uri: str
    scopes: str
    auth_url: str = "https://accounts.google.com/o/oauth2/v2/auth"
    token_url: str = "https://oauth2.googleapis.com/token"
    revoke_url: str = "https://oauth2.googleapis.com/revoke"
    userinfo_url: str = "https://openidconnect.googleapis.com/v1/userinfo"
    timeout: float = 15.0

    @property
    def ready(self) -> bool:
        return bool(self.enabled and self.client_id and self.client_secret and self.redirect_uri)

    @property
    def scope_list(self) -> list[str]:
        return [scope for scope in self.scopes.split() if scope]


def load_google_oauth_config() -> GoogleOAuthConfig:
    enabled = os.environ.get("GOOGLE_OAUTH_ENABLED", "").strip().lower() in {"1", "true", "yes", "si"}
    client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID") or os.environ.get("GOOGLE_CLIENT_ID") or ""
    client_secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET") or os.environ.get("GOOGLE_CLIENT_SECRET") or ""
    redirect_uri = os.environ.get("GOOGLE_OAUTH_REDIRECT_URI") or os.environ.get("GOOGLE_REDIRECT_URI") or ""
    scopes = os.environ.get("GOOGLE_OAUTH_SCOPES") or DEFAULT_GOOGLE_SCOPES
    return GoogleOAuthConfig(
        enabled=enabled,
        client_id=client_id.strip(),
        client_secret=client_secret.strip(),
        redirect_uri=redirect_uri.strip(),
        scopes=" ".join(scopes.split()),
        auth_url=os.environ.get("GOOGLE_OAUTH_AUTH_URL", "https://accounts.google.com/o/oauth2/v2/auth").strip(),
        token_url=os.environ.get("GOOGLE_OAUTH_TOKEN_URL", "https://oauth2.googleapis.com/token").strip(),
        revoke_url=os.environ.get("GOOGLE_OAUTH_REVOKE_URL", "https://oauth2.googleapis.com/revoke").strip(),
        userinfo_url=os.environ.get("GOOGLE_OAUTH_USERINFO_URL", "https://openidconnect.googleapis.com/v1/userinfo").strip(),
        timeout=float(os.environ.get("GOOGLE_OAUTH_TIMEOUT_SECONDS", "15")),
    )


def sanitize_google_error(exc: Exception) -> str:
    text = str(exc or "")
    for key in ("access_token", "refresh_token", "client_secret", "authorization_code", "id_token"):
        text = text.replace(key, "[redacted]")
    return text[:300] or "Error Google OAuth"


class GoogleOAuthClient:
    def __init__(self, config: GoogleOAuthConfig | None = None, opener: Callable[..., Any] | None = None) -> None:
        self.config = config or load_google_oauth_config()
        self._opener = opener or urllib.request.urlopen

    def validate_configuration(self) -> dict[str, Any]:
        errors = []
        if not self.config.enabled:
            errors.append("GOOGLE_OAUTH_ENABLED no esta activo")
        if self.config.enabled and not self.config.client_id:
            errors.append("GOOGLE_OAUTH_CLIENT_ID faltante")
        if self.config.enabled and not self.config.client_secret:
            errors.append("GOOGLE_OAUTH_CLIENT_SECRET faltante")
        if self.config.enabled and not self.config.redirect_uri:
            errors.append("GOOGLE_OAUTH_REDIRECT_URI faltante")
        if self.config.redirect_uri and not self.config.redirect_uri.startswith(("http://", "https://")):
            errors.append("GOOGLE_OAUTH_REDIRECT_URI invalida")
        return {"ok": not errors, "ready": self.config.ready, "errors": errors, "scopes": self.config.scope_list}

    def authorization_url(self, *, state: str, login_hint: str = "", prompt: str = "consent") -> str:
        validation = self.validate_configuration()
        if not validation["ok"]:
            raise GoogleOAuthError("; ".join(validation["errors"]), "configuration_incomplete")
        params = {
            "client_id": self.config.client_id,
            "redirect_uri": self.config.redirect_uri,
            "response_type": "code",
            "scope": self.config.scopes,
            "state": state,
            "access_type": "offline",
            "include_granted_scopes": "true",
            "prompt": prompt,
        }
        if login_hint:
            params["login_hint"] = login_hint
        return self.config.auth_url + "?" + urllib.parse.urlencode(params)

    def exchange_code(self, code: str) -> dict[str, Any]:
        if not code:
            raise GoogleOAuthError("Authorization code faltante", "missing_code")
        payload = {
            "code": code,
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
            "redirect_uri": self.config.redirect_uri,
            "grant_type": "authorization_code",
        }
        return self._post_form(self.config.token_url, payload)

    def refresh_access_token(self, refresh_token: str) -> dict[str, Any]:
        if not refresh_token:
            raise GoogleOAuthError("Refresh token faltante", "missing_refresh_token")
        payload = {
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
        return self._post_form(self.config.token_url, payload)

    def revoke_token(self, token: str) -> bool:
        if not token:
            return False
        payload = {"token": token}
        self._post_form(self.config.revoke_url, payload, allow_empty=True)
        return True

    def userinfo(self, access_token: str) -> dict[str, Any]:
        if not access_token:
            raise GoogleOAuthError("Access token faltante", "missing_access_token")
        request = urllib.request.Request(
            self.config.userinfo_url,
            headers={"Authorization": f"Bearer {access_token}", "User-Agent": "BITORA/GoogleOAuth"},
            method="GET",
        )
        return self._open_json(request)

    def _post_form(self, url: str, payload: dict[str, str], allow_empty: bool = False) -> dict[str, Any]:
        body = urllib.parse.urlencode(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": "BITORA/GoogleOAuth"},
            method="POST",
        )
        result = self._open_json(request, allow_empty=allow_empty)
        if not allow_empty and not result:
            raise GoogleOAuthError("Google no devolvio respuesta valida", "invalid_response")
        return result

    def _open_json(self, request: urllib.request.Request, allow_empty: bool = False) -> dict[str, Any]:
        try:
            with self._opener(request, timeout=self.config.timeout) as response:
                raw = response.read()
                if not raw and allow_empty:
                    return {}
                return json.loads(raw.decode("utf-8")) if raw else {}
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                detail = json.loads(raw)
                message = detail.get("error_description") or detail.get("error") or raw
            except json.JSONDecodeError:
                message = raw
            raise GoogleOAuthError(f"Google HTTP {exc.code}: {message}", "google_http_error") from exc
        except urllib.error.URLError as exc:
            raise GoogleOAuthError(f"No se pudo conectar con Google: {exc.reason}", "google_network_error") from exc
        except json.JSONDecodeError as exc:
            raise GoogleOAuthError("Google devolvio JSON invalido", "invalid_json") from exc


def token_expires_at(now_iso: Callable[[], str], expires_in: int | str | None) -> str:
    from datetime import datetime, timedelta

    try:
        seconds = max(0, int(expires_in or 0))
    except (TypeError, ValueError):
        seconds = 0
    return (datetime.fromisoformat(now_iso()) + timedelta(seconds=seconds)).isoformat(timespec="seconds")


def granted_scopes(payload: dict[str, Any], fallback: list[str]) -> list[str]:
    scope = str(payload.get("scope") or "").strip()
    return [item for item in scope.split() if item] if scope else fallback
