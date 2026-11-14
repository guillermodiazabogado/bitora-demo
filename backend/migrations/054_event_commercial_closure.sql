-- Formal, auditable event closure for the commercial end-to-end flow.
ALTER TABLE events ADD COLUMN IF NOT EXISTS closed_at TEXT;
ALTER TABLE events ADD COLUMN IF NOT EXISTS closed_by TEXT;
ALTER TABLE events ADD COLUMN IF NOT EXISTS closure_reason TEXT NOT NULL DEFAULT '';

CREATE INDEX IF NOT EXISTS idx_events_status_closed_at
    ON events(status, closed_at);
