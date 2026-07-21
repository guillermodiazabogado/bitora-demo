ALTER TABLE communication_queue
    ADD COLUMN IF NOT EXISTS read_at TEXT;

ALTER TABLE communication_queue
    ADD COLUMN IF NOT EXISTS failed_at TEXT;

CREATE TABLE IF NOT EXISTS whatsapp_delivery_events (
    id BIGSERIAL PRIMARY KEY,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    queue_id BIGINT REFERENCES communication_queue(id) ON DELETE SET NULL,
    provider TEXT NOT NULL DEFAULT 'meta',
    message_id TEXT NOT NULL DEFAULT '',
    external_event_id TEXT NOT NULL DEFAULT '',
    event_type TEXT NOT NULL,
    phone TEXT NOT NULL DEFAULT '',
    payload TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS whatsapp_suppressions (
    id BIGSERIAL PRIMARY KEY,
    event_id BIGINT REFERENCES events(id) ON DELETE CASCADE,
    phone TEXT NOT NULL,
    normalized_phone TEXT NOT NULL,
    reason TEXT NOT NULL,
    scope TEXT NOT NULL DEFAULT 'global',
    source TEXT NOT NULL DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(normalized_phone, scope, event_id)
);

CREATE INDEX IF NOT EXISTS idx_whatsapp_delivery_message
    ON whatsapp_delivery_events(message_id, created_at);

CREATE UNIQUE INDEX IF NOT EXISTS idx_whatsapp_delivery_unique_event
    ON whatsapp_delivery_events(provider, external_event_id)
    WHERE external_event_id <> '';

CREATE INDEX IF NOT EXISTS idx_whatsapp_suppressions_lookup
    ON whatsapp_suppressions(normalized_phone, active, scope, event_id);
