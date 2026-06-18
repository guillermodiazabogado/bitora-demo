CREATE TABLE IF NOT EXISTS simulator_state (
    event_id BIGINT PRIMARY KEY REFERENCES events(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'stopped',
    mode TEXT NOT NULL DEFAULT 'medium',
    scenario TEXT NOT NULL DEFAULT 'congress',
    participants_active INTEGER NOT NULL DEFAULT 100,
    accesses_per_minute INTEGER NOT NULL DEFAULT 30,
    rejections_per_minute INTEGER NOT NULL DEFAULT 3,
    simulated_errors INTEGER NOT NULL DEFAULT 1,
    average_occupancy INTEGER NOT NULL DEFAULT 55,
    active_terminals INTEGER NOT NULL DEFAULT 10,
    speed REAL NOT NULL DEFAULT 1,
    updated_by TEXT NOT NULL DEFAULT 'system',
    updated_at TEXT NOT NULL
);
