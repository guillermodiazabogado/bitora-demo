CREATE TABLE IF NOT EXISTS technical_logs (
    id BIGSERIAL PRIMARY KEY,
    level TEXT NOT NULL DEFAULT 'info',
    module TEXT NOT NULL DEFAULT 'system',
    message TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT '',
    request_path TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_technical_logs_created
    ON technical_logs(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_technical_logs_level_module
    ON technical_logs(level, module, created_at DESC);
