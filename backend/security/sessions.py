"""Persistent, transport-independent authentication session storage.

Only SHA-256 digests of bearer and CSRF tokens are retained.  Callers must
generate high-entropy tokens (``secrets.token_urlsafe(32)`` or stronger).
Database methods commit their own unit of work and therefore should receive a
dedicated connection, not a connection participating in a wider transaction.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Mapping


Clock = Callable[[], datetime]


@dataclass(frozen=True)
class Session:
    user_id: int
    data: dict[str, Any]
    created_at: datetime
    expires_at: datetime
    last_seen_at: datetime
    revoked_at: datetime | None = None

    @property
    def active(self) -> bool:
        return self.revoked_at is None and self.expires_at > datetime.now(timezone.utc)


class SessionStore:
    """DB-backed session store compatible with SQLite and BITORA's PG adapter."""

    def __init__(self, connection: Any, *, clock: Clock | None = None) -> None:
        self.connection = connection
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def create(
        self,
        token: str,
        user_id: int,
        csrf_token: str,
        data: Mapping[str, Any] | None = None,
        *,
        ttl_seconds: int = 86_400,
    ) -> Session:
        now = _utc(self._clock())
        expires = now + timedelta(seconds=_positive_ttl(ttl_seconds))
        payload = _json(data)
        try:
            self.connection.execute(
                """INSERT INTO auth_sessions
                   (token_hash, user_id, csrf_hash, data_json, created_at,
                    expires_at, last_seen_at, revoked_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, NULL)""",
                (_digest(token), int(user_id), _digest(csrf_token), payload,
                 _stamp(now), _stamp(expires), _stamp(now)),
            )
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise
        return Session(int(user_id), json.loads(payload), now, expires, now)

    def get(self, token: str, *, touch: bool = False) -> Session | None:
        token_hash = _digest(token)
        row = self.connection.execute(
            "SELECT * FROM auth_sessions WHERE token_hash = ?", (token_hash,)
        ).fetchone()
        if not row:
            return None
        session = _session(row)
        now = _utc(self._clock())
        if session.revoked_at is not None or session.expires_at <= now:
            return None
        if touch:
            self.connection.execute(
                "UPDATE auth_sessions SET last_seen_at = ? WHERE token_hash = ?",
                (_stamp(now), token_hash),
            )
            self.connection.commit()
            session = Session(session.user_id, session.data, session.created_at,
                              session.expires_at, now, session.revoked_at)
        return session

    def verify_csrf(self, token: str, csrf_token: str) -> bool:
        row = self.connection.execute(
            "SELECT csrf_hash FROM auth_sessions WHERE token_hash = ?",
            (_digest(token),),
        ).fetchone()
        return bool(row and self.get(token) and hmac.compare_digest(str(row["csrf_hash"]), _digest(csrf_token)))

    def revoke(self, token: str) -> bool:
        cursor = self.connection.execute(
            """UPDATE auth_sessions SET revoked_at = ?
               WHERE token_hash = ? AND revoked_at IS NULL""",
            (_stamp(_utc(self._clock())), _digest(token)),
        )
        self.connection.commit()
        return cursor.rowcount > 0

    def revoke_user(self, user_id: int) -> int:
        cursor = self.connection.execute(
            "UPDATE auth_sessions SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL",
            (_stamp(_utc(self._clock())), int(user_id)),
        )
        self.connection.commit()
        return cursor.rowcount

    def active_payloads(self) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT user_id, data_json, created_at, expires_at, last_seen_at FROM auth_sessions WHERE revoked_at IS NULL AND expires_at > ?",
            (_stamp(_utc(self._clock())),),
        ).fetchall()
        return [
            {"id": int(row["user_id"]), **json.loads(row["data_json"]), "created_at": row["created_at"], "expires_at": row["expires_at"], "last_seen_at": row["last_seen_at"]}
            for row in rows
        ]

    def update(
        self,
        token: str,
        *,
        data: Mapping[str, Any] | None = None,
        csrf_token: str | None = None,
        ttl_seconds: int | None = None,
    ) -> Session | None:
        current = self.get(token)
        if current is None:
            return None
        fields: list[str] = []
        params: list[Any] = []
        if data is not None:
            fields.append("data_json = ?")
            params.append(_json(data))
        if csrf_token is not None:
            fields.append("csrf_hash = ?")
            params.append(_digest(csrf_token))
        if ttl_seconds is not None:
            fields.append("expires_at = ?")
            params.append(_stamp(_utc(self._clock()) + timedelta(seconds=_positive_ttl(ttl_seconds))))
        if fields:
            params.append(_digest(token))
            self.connection.execute(
                f"UPDATE auth_sessions SET {', '.join(fields)} WHERE token_hash = ?",
                tuple(params),
            )
            self.connection.commit()
        return self.get(token)

    def cleanup(self, *, revoked_retention_seconds: int = 0) -> int:
        now = _utc(self._clock())
        cutoff = now - timedelta(seconds=max(0, int(revoked_retention_seconds)))
        cursor = self.connection.execute(
            """DELETE FROM auth_sessions
               WHERE expires_at <= ? OR (revoked_at IS NOT NULL AND revoked_at <= ?)""",
            (_stamp(now), _stamp(cutoff)),
        )
        self.connection.commit()
        return cursor.rowcount


class MemorySessionStore:
    """API-compatible local store; non-durable and unsuitable for replicas."""

    def __init__(self, *, clock: Clock | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._rows: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()

    def create(self, token: str, user_id: int, csrf_token: str,
               data: Mapping[str, Any] | None = None, *, ttl_seconds: int = 86_400) -> Session:
        now = _utc(self._clock())
        key = _digest(token)
        with self._lock:
            if key in self._rows:
                raise ValueError("session token already exists")
            self._rows[key] = {"token_hash": key, "user_id": int(user_id),
                "csrf_hash": _digest(csrf_token), "data_json": _json(data),
                "created_at": _stamp(now),
                "expires_at": _stamp(now + timedelta(seconds=_positive_ttl(ttl_seconds))),
                "last_seen_at": _stamp(now), "revoked_at": None}
            return _session(self._rows[key])

    def get(self, token: str, *, touch: bool = False) -> Session | None:
        with self._lock:
            row = self._rows.get(_digest(token))
            if not row:
                return None
            value = _session(row)
            now = _utc(self._clock())
            if value.revoked_at is not None or value.expires_at <= now:
                return None
            if touch:
                row["last_seen_at"] = _stamp(now)
                value = _session(row)
            return value

    def verify_csrf(self, token: str, csrf_token: str) -> bool:
        with self._lock:
            row = self._rows.get(_digest(token))
            return bool(row and self.get(token) and hmac.compare_digest(row["csrf_hash"], _digest(csrf_token)))

    def revoke(self, token: str) -> bool:
        with self._lock:
            row = self._rows.get(_digest(token))
            if not row or row["revoked_at"] is not None:
                return False
            row["revoked_at"] = _stamp(_utc(self._clock()))
            return True

    def revoke_user(self, user_id: int) -> int:
        with self._lock:
            count = 0
            for row in self._rows.values():
                if int(row["user_id"]) == int(user_id) and row["revoked_at"] is None:
                    row["revoked_at"] = _stamp(_utc(self._clock()))
                    count += 1
            return count

    def active_payloads(self) -> list[dict[str, Any]]:
        with self._lock:
            items = []
            for row in self._rows.values():
                value = _session(row)
                if value.revoked_at is None and value.expires_at > _utc(self._clock()):
                    items.append({"id": value.user_id, **value.data, "created_at": _stamp(value.created_at), "expires_at": _stamp(value.expires_at), "last_seen_at": _stamp(value.last_seen_at)})
            return items

    def update(self, token: str, *, data: Mapping[str, Any] | None = None,
               csrf_token: str | None = None, ttl_seconds: int | None = None) -> Session | None:
        with self._lock:
            row = self._rows.get(_digest(token))
            if not row or self.get(token) is None:
                return None
            if data is not None:
                row["data_json"] = _json(data)
            if csrf_token is not None:
                row["csrf_hash"] = _digest(csrf_token)
            if ttl_seconds is not None:
                row["expires_at"] = _stamp(_utc(self._clock()) + timedelta(seconds=_positive_ttl(ttl_seconds)))
            return self.get(token)

    def cleanup(self, *, revoked_retention_seconds: int = 0) -> int:
        now = _utc(self._clock())
        cutoff = now - timedelta(seconds=max(0, int(revoked_retention_seconds)))
        with self._lock:
            doomed = [key for key, row in self._rows.items()
                      if _parse(row["expires_at"]) <= now or
                      (row["revoked_at"] and _parse(row["revoked_at"]) <= cutoff)]
            for key in doomed:
                del self._rows[key]
            return len(doomed)


def _digest(secret: str) -> str:
    if not isinstance(secret, str) or not secret:
        raise ValueError("token must be a non-empty string")
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def _positive_ttl(value: int) -> int:
    ttl = int(value)
    if ttl <= 0:
        raise ValueError("ttl_seconds must be positive")
    return ttl


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("clock must return a timezone-aware datetime")
    return value.astimezone(timezone.utc)


def _stamp(value: datetime) -> str:
    return _utc(value).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)


def _json(data: Mapping[str, Any] | None) -> str:
    return json.dumps(dict(data or {}), ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _session(row: Any) -> Session:
    return Session(user_id=int(row["user_id"]), data=json.loads(row["data_json"]),
                   created_at=_parse(row["created_at"]), expires_at=_parse(row["expires_at"]),
                   last_seen_at=_parse(row["last_seen_at"]),
                   revoked_at=_parse(row["revoked_at"]) if row["revoked_at"] else None)
