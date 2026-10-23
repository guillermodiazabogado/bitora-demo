CREATE TABLE IF NOT EXISTS attendance_rule_sets (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    activity_id BIGINT REFERENCES activities(id) ON DELETE SET NULL,
    name TEXT NOT NULL,
    scope_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'DRAFT',
    current_version_id BIGINT,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, event_id, scope_type, activity_id, name)
);

CREATE TABLE IF NOT EXISTS attendance_rule_set_versions (
    id BIGSERIAL PRIMARY KEY,
    rule_set_id BIGINT NOT NULL REFERENCES attendance_rule_sets(id) ON DELETE CASCADE,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    activity_id BIGINT REFERENCES activities(id) ON DELETE SET NULL,
    version_number INTEGER NOT NULL,
    configuration_json TEXT NOT NULL,
    configuration_hash TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'DRAFT',
    published_at TEXT,
    published_by TEXT,
    idempotency_key TEXT NOT NULL DEFAULT '',
    request_hash TEXT NOT NULL DEFAULT '',
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(rule_set_id, version_number),
    UNIQUE(rule_set_id, configuration_hash)
);

CREATE TABLE IF NOT EXISTS attendance_closures (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    activity_id BIGINT REFERENCES activities(id) ON DELETE SET NULL,
    scope_type TEXT NOT NULL,
    rule_set_version_id BIGINT NOT NULL REFERENCES attendance_rule_set_versions(id) ON DELETE RESTRICT,
    status TEXT NOT NULL,
    closed_at TEXT,
    closed_by TEXT NOT NULL,
    closure_reason TEXT NOT NULL DEFAULT '',
    cutoff_at TEXT NOT NULL,
    algorithm_version TEXT NOT NULL,
    snapshot_json TEXT NOT NULL DEFAULT '{}',
    snapshot_hash TEXT NOT NULL DEFAULT '',
    supersedes_closure_id BIGINT REFERENCES attendance_closures(id) ON DELETE SET NULL,
    reopened_at TEXT,
    reopened_by TEXT,
    reopening_reason TEXT,
    idempotency_key TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    correlation_id TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, idempotency_key)
);

CREATE TABLE IF NOT EXISTS attendance_evaluations (
    id BIGSERIAL PRIMARY KEY,
    closure_id BIGINT NOT NULL REFERENCES attendance_closures(id) ON DELETE CASCADE,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    activity_id BIGINT REFERENCES activities(id) ON DELETE SET NULL,
    participant_id BIGINT NOT NULL REFERENCES people(id) ON DELETE RESTRICT,
    accreditation_id BIGINT REFERENCES accreditations(id) ON DELETE SET NULL,
    result_status TEXT NOT NULL,
    attendance_percentage TEXT NOT NULL DEFAULT '0.00',
    attended_count INTEGER NOT NULL DEFAULT 0,
    required_count INTEGER NOT NULL DEFAULT 0,
    duration_minutes INTEGER NOT NULL DEFAULT 0,
    eligible INTEGER NOT NULL DEFAULT 0,
    failure_reasons_json TEXT NOT NULL DEFAULT '[]',
    calculation_details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    UNIQUE(closure_id, participant_id)
);

CREATE TABLE IF NOT EXISTS attendance_evaluation_items (
    id BIGSERIAL PRIMARY KEY,
    evaluation_id BIGINT NOT NULL REFERENCES attendance_evaluations(id) ON DELETE CASCADE,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    activity_id BIGINT REFERENCES activities(id) ON DELETE SET NULL,
    attendance_record_id BIGINT REFERENCES attendance_records(id) ON DELETE SET NULL,
    unit_key TEXT NOT NULL,
    status TEXT NOT NULL,
    weight TEXT NOT NULL DEFAULT '1.00',
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS attendance_eligibility_decisions (
    id BIGSERIAL PRIMARY KEY,
    closure_id BIGINT NOT NULL REFERENCES attendance_closures(id) ON DELETE CASCADE,
    evaluation_id BIGINT NOT NULL REFERENCES attendance_evaluations(id) ON DELETE CASCADE,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    participant_id BIGINT NOT NULL REFERENCES people(id) ON DELETE RESTRICT,
    automatic_result TEXT NOT NULL,
    effective_result TEXT NOT NULL,
    override_id BIGINT,
    status TEXT NOT NULL,
    reasons_json TEXT NOT NULL DEFAULT '[]',
    decided_at TEXT NOT NULL,
    decided_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(evaluation_id)
);

CREATE TABLE IF NOT EXISTS attendance_overrides (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    closure_id BIGINT NOT NULL REFERENCES attendance_closures(id) ON DELETE CASCADE,
    evaluation_id BIGINT NOT NULL REFERENCES attendance_evaluations(id) ON DELETE CASCADE,
    participant_id BIGINT NOT NULL REFERENCES people(id) ON DELETE RESTRICT,
    previous_effective_result TEXT NOT NULL,
    manual_result TEXT NOT NULL,
    reason TEXT NOT NULL,
    evidence_json TEXT NOT NULL DEFAULT '{}',
    idempotency_key TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    correlation_id TEXT NOT NULL DEFAULT '',
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(organization_id, idempotency_key)
);

CREATE TABLE IF NOT EXISTS attendance_reopenings (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    closure_id BIGINT NOT NULL REFERENCES attendance_closures(id) ON DELETE CASCADE,
    reason TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    correlation_id TEXT NOT NULL DEFAULT '',
    reopened_by TEXT NOT NULL,
    reopened_at TEXT NOT NULL,
    UNIQUE(organization_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_attendance_rule_sets_scope ON attendance_rule_sets(organization_id, event_id, scope_type, activity_id, status);
CREATE INDEX IF NOT EXISTS idx_attendance_rule_versions_set ON attendance_rule_set_versions(rule_set_id, status, version_number);
CREATE INDEX IF NOT EXISTS idx_attendance_closures_scope ON attendance_closures(organization_id, event_id, scope_type, activity_id, status);
CREATE INDEX IF NOT EXISTS idx_attendance_closures_rule_version ON attendance_closures(rule_set_version_id, status);
CREATE INDEX IF NOT EXISTS idx_attendance_evaluations_closure ON attendance_evaluations(closure_id, participant_id);
CREATE INDEX IF NOT EXISTS idx_attendance_eligibility_event_participant ON attendance_eligibility_decisions(event_id, participant_id, status);
CREATE INDEX IF NOT EXISTS idx_attendance_overrides_evaluation ON attendance_overrides(evaluation_id, created_at);
CREATE INDEX IF NOT EXISTS idx_attendance_reopenings_closure ON attendance_reopenings(closure_id, reopened_at);
