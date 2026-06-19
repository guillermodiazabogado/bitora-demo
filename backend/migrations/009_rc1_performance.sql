CREATE INDEX IF NOT EXISTS idx_access_logs_event_result_created
    ON access_logs (event_id, result, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_accreditations_event_checked_status
    ON accreditations (event_id, checked_in_at, status);

CREATE INDEX IF NOT EXISTS idx_communication_queue_status_scheduled
    ON communication_queue (status, scheduled_at, id);

CREATE INDEX IF NOT EXISTS idx_audit_logs_entity_created
    ON audit_logs (entity_type, entity_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_activities_event_status_start
    ON activities (event_id, status, starts_at);

CREATE INDEX IF NOT EXISTS idx_captation_event_action_created
    ON captation_events (event_id, action, created_at DESC);
