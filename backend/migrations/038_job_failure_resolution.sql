ALTER TABLE jobs ADD COLUMN resolved_at TEXT;

CREATE INDEX IF NOT EXISTS idx_jobs_unresolved_failures
    ON jobs(status, resolved_at, kind);
