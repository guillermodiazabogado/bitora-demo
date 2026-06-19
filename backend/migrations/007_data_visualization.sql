CREATE TABLE IF NOT EXISTS visualization_layouts (
    id BIGSERIAL PRIMARY KEY,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    owner TEXT NOT NULL,
    name TEXT NOT NULL,
    dashboard TEXT NOT NULL DEFAULT 'operational',
    period TEXT NOT NULL DEFAULT 'event',
    widgets TEXT NOT NULL DEFAULT '',
    mode TEXT NOT NULL DEFAULT 'monitor',
    is_default INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_visualization_layouts_event_owner
ON visualization_layouts (event_id, owner, updated_at);
