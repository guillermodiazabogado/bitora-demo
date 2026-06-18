ALTER TABLE communication_queue
    ADD COLUMN IF NOT EXISTS max_attempts INTEGER NOT NULL DEFAULT 3;

ALTER TABLE communication_queue
    ADD COLUMN IF NOT EXISTS provider_message_id TEXT NOT NULL DEFAULT '';

ALTER TABLE communication_queue
    ADD COLUMN IF NOT EXISTS delivered_at TEXT;

ALTER TABLE communication_queue
    ADD COLUMN IF NOT EXISTS bounced_at TEXT;

CREATE TABLE IF NOT EXISTS email_delivery_events (
    id BIGSERIAL PRIMARY KEY,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    queue_id BIGINT REFERENCES communication_queue(id) ON DELETE SET NULL,
    provider TEXT NOT NULL DEFAULT '',
    message_id TEXT NOT NULL DEFAULT '',
    event_type TEXT NOT NULL,
    payload TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_communication_queue_provider_message
    ON communication_queue(provider_message_id);

CREATE INDEX IF NOT EXISTS idx_email_delivery_message
    ON email_delivery_events(message_id, created_at);
