CREATE TABLE IF NOT EXISTS feature_flags (
    id BIGSERIAL PRIMARY KEY,
    flag_key TEXT NOT NULL,
    scope_type TEXT NOT NULL,
    scope_id BIGINT NOT NULL DEFAULT 0,
    enabled INTEGER NOT NULL DEFAULT 0,
    updated_by TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL,
    UNIQUE(flag_key, scope_type, scope_id)
);

CREATE TABLE IF NOT EXISTS attendance_records (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    participant_id BIGINT NOT NULL REFERENCES people(id) ON DELETE RESTRICT,
    accreditation_id BIGINT REFERENCES accreditations(id) ON DELETE SET NULL,
    activity_id BIGINT REFERENCES activities(id) ON DELETE SET NULL,
    attendance_type TEXT NOT NULL,
    status TEXT NOT NULL,
    source TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    recorded_by TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    correlation_id TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    invalidated_at TEXT,
    invalidated_by TEXT,
    invalidation_reason TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, idempotency_key)
);

CREATE TABLE IF NOT EXISTS attendance_events (
    id BIGSERIAL PRIMARY KEY,
    attendance_id BIGINT NOT NULL REFERENCES attendance_records(id) ON DELETE CASCADE,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    participant_id BIGINT NOT NULL REFERENCES people(id) ON DELETE RESTRICT,
    activity_id BIGINT REFERENCES activities(id) ON DELETE SET NULL,
    event_type TEXT NOT NULL,
    status TEXT NOT NULL,
    source TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    actor TEXT NOT NULL,
    idempotency_key TEXT NOT NULL DEFAULT '',
    correlation_id TEXT NOT NULL DEFAULT '',
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS attendance_corrections (
    id BIGSERIAL PRIMARY KEY,
    attendance_id BIGINT NOT NULL REFERENCES attendance_records(id) ON DELETE CASCADE,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    previous_status TEXT NOT NULL,
    new_status TEXT NOT NULL,
    previous_metadata_json TEXT NOT NULL DEFAULT '{}',
    new_metadata_json TEXT NOT NULL DEFAULT '{}',
    reason TEXT NOT NULL,
    corrected_by TEXT NOT NULL,
    corrected_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_feature_flags_lookup ON feature_flags(flag_key, scope_type, scope_id, enabled);
CREATE INDEX IF NOT EXISTS idx_attendance_records_org_event ON attendance_records(organization_id, event_id);
CREATE INDEX IF NOT EXISTS idx_attendance_records_event_participant ON attendance_records(event_id, participant_id);
CREATE INDEX IF NOT EXISTS idx_attendance_records_event_activity ON attendance_records(event_id, activity_id);
CREATE INDEX IF NOT EXISTS idx_attendance_records_participant_time ON attendance_records(participant_id, occurred_at);
CREATE INDEX IF NOT EXISTS idx_attendance_records_status ON attendance_records(status);
CREATE INDEX IF NOT EXISTS idx_attendance_records_created ON attendance_records(created_at);
CREATE INDEX IF NOT EXISTS idx_attendance_events_attendance ON attendance_events(attendance_id, created_at);
CREATE INDEX IF NOT EXISTS idx_attendance_events_event ON attendance_events(event_id, event_type, created_at);
CREATE INDEX IF NOT EXISTS idx_attendance_corrections_attendance ON attendance_corrections(attendance_id, corrected_at);
