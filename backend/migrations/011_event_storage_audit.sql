ALTER TABLE audit_logs
    ADD COLUMN IF NOT EXISTS event_id BIGINT REFERENCES events(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_audit_logs_event_created
    ON audit_logs (event_id, created_at DESC);
