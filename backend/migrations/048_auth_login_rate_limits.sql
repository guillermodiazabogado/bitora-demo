CREATE TABLE IF NOT EXISTS auth_login_rate_limits (
    request_fingerprint TEXT PRIMARY KEY,
    window_started_at TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    blocked_until TEXT,
    last_attempt_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_auth_login_rate_blocked
ON auth_login_rate_limits(blocked_until);
