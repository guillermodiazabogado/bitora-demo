ALTER TABLE events ADD COLUMN IF NOT EXISTS waiting_room_enabled INTEGER NOT NULL DEFAULT 0;
ALTER TABLE events ADD COLUMN IF NOT EXISTS waiting_room_open_at TEXT NOT NULL DEFAULT '';
ALTER TABLE events ADD COLUMN IF NOT EXISTS users_allowed_per_minute INTEGER NOT NULL DEFAULT 60;
ALTER TABLE events ADD COLUMN IF NOT EXISTS turn_duration_minutes INTEGER NOT NULL DEFAULT 10;
ALTER TABLE events ADD COLUMN IF NOT EXISTS show_waiting_position INTEGER NOT NULL DEFAULT 1;
ALTER TABLE events ADD COLUMN IF NOT EXISTS show_estimated_time INTEGER NOT NULL DEFAULT 1;
ALTER TABLE events ADD COLUMN IF NOT EXISTS waiting_message TEXT NOT NULL DEFAULT 'Estamos organizando el ingreso. Tu turno se habilitara pronto.';

CREATE TABLE IF NOT EXISTS waiting_room_visitors (
    id BIGSERIAL PRIMARY KEY,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    visitor_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'waiting',
    position_number INTEGER NOT NULL DEFAULT 0,
    access_token TEXT NOT NULL DEFAULT '',
    joined_at TEXT NOT NULL,
    admitted_at TEXT,
    expires_at TEXT,
    completed_at TEXT,
    abandoned_at TEXT,
    last_seen_at TEXT NOT NULL,
    error TEXT NOT NULL DEFAULT '',
    UNIQUE(event_id, visitor_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_waiting_room_access_token
    ON waiting_room_visitors(access_token) WHERE access_token <> '';

CREATE INDEX IF NOT EXISTS idx_waiting_room_event_status
    ON waiting_room_visitors(event_id, status, joined_at);
