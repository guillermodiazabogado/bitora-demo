CREATE TABLE IF NOT EXISTS enterprise_pairing_rate_limits (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    request_fingerprint TEXT NOT NULL,
    window_started_at TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    blocked_until TEXT,
    last_attempt_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, event_id, request_fingerprint)
);

CREATE INDEX IF NOT EXISTS idx_enterprise_pairing_rate_scope
ON enterprise_pairing_rate_limits(organization_id, event_id, request_fingerprint, blocked_until);
