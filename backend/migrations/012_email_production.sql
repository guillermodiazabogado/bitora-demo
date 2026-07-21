ALTER TABLE communication_queue
    ADD COLUMN IF NOT EXISTS complained_at TEXT;

ALTER TABLE communication_queue
    ADD COLUMN IF NOT EXISTS opened_at TEXT;

ALTER TABLE communication_queue
    ADD COLUMN IF NOT EXISTS clicked_at TEXT;

ALTER TABLE communication_queue
    ADD COLUMN IF NOT EXISTS idempotency_key TEXT NOT NULL DEFAULT '';

ALTER TABLE email_delivery_events
    ADD COLUMN IF NOT EXISTS external_event_id TEXT NOT NULL DEFAULT '';

CREATE TABLE IF NOT EXISTS email_suppressions (
    id BIGSERIAL PRIMARY KEY,
    event_id BIGINT REFERENCES events(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    normalized_email TEXT NOT NULL,
    reason TEXT NOT NULL,
    scope TEXT NOT NULL DEFAULT 'global',
    source TEXT NOT NULL DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(normalized_email, scope, event_id)
);

CREATE INDEX IF NOT EXISTS idx_email_suppressions_lookup
    ON email_suppressions(normalized_email, active, scope, event_id);

CREATE UNIQUE INDEX IF NOT EXISTS idx_email_delivery_unique_event
    ON email_delivery_events(provider, external_event_id)
    WHERE external_event_id <> '';

CREATE UNIQUE INDEX IF NOT EXISTS idx_communication_queue_idempotency
    ON communication_queue(idempotency_key)
    WHERE idempotency_key <> '';
