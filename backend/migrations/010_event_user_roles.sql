CREATE TABLE IF NOT EXISTS user_event_roles (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    UNIQUE(user_id, event_id)
);

CREATE INDEX IF NOT EXISTS idx_user_event_roles_user_event
ON user_event_roles (user_id, event_id, active);

CREATE INDEX IF NOT EXISTS idx_user_event_roles_event_role
ON user_event_roles (event_id, role, active);
