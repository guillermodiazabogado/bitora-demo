CREATE TABLE IF NOT EXISTS role_permissions (
    id SERIAL PRIMARY KEY,
    role TEXT NOT NULL,
    module TEXT NOT NULL,
    allowed INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    UNIQUE(role, module)
);

CREATE TABLE IF NOT EXISTS role_action_permissions (
    id SERIAL PRIMARY KEY,
    role TEXT NOT NULL,
    action TEXT NOT NULL,
    allowed INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    UNIQUE(role, action)
);
