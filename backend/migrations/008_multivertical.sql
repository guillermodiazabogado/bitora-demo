ALTER TABLE events
ADD COLUMN IF NOT EXISTS project_type TEXT NOT NULL DEFAULT 'conference';

UPDATE events
SET project_type = 'conference'
WHERE project_type IS NULL OR project_type = '';

CREATE INDEX IF NOT EXISTS idx_events_project_type_status
ON events (project_type, status);
