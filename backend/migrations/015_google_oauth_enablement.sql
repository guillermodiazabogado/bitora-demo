CREATE TABLE IF NOT EXISTS google_oauth_states (
    id BIGSERIAL PRIMARY KEY,
    state_token TEXT NOT NULL UNIQUE,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    integration_id BIGINT NOT NULL REFERENCES organization_integrations(id) ON DELETE CASCADE,
    user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    actor TEXT NOT NULL DEFAULT '',
    redirect_after TEXT NOT NULL DEFAULT '',
    nonce_hash TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    used_at TEXT,
    error_message_sanitized TEXT NOT NULL DEFAULT ''
);

ALTER TABLE organization_integrations
    ADD COLUMN IF NOT EXISTS last_error_code TEXT NOT NULL DEFAULT '';

CREATE INDEX IF NOT EXISTS idx_google_oauth_states_token ON google_oauth_states(state_token, status, expires_at);
CREATE INDEX IF NOT EXISTS idx_google_oauth_states_integration ON google_oauth_states(integration_id, status, created_at);
