CREATE TABLE IF NOT EXISTS analytics_v4_snapshots (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    snapshot_type TEXT NOT NULL DEFAULT 'EVENT_OVERVIEW',
    period_start TEXT NOT NULL DEFAULT '',
    period_end TEXT NOT NULL DEFAULT '',
    timezone TEXT NOT NULL DEFAULT 'UTC',
    filters_json TEXT NOT NULL DEFAULT '{}',
    metrics_json TEXT NOT NULL DEFAULT '{}',
    definitions_json TEXT NOT NULL DEFAULT '[]',
    quality_json TEXT NOT NULL DEFAULT '[]',
    source_tables_json TEXT NOT NULL DEFAULT '[]',
    snapshot_hash TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'READY',
    generated_by TEXT NOT NULL DEFAULT '',
    generated_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS analytics_v4_reports (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    snapshot_id BIGINT REFERENCES analytics_v4_snapshots(id) ON DELETE SET NULL,
    report_type TEXT NOT NULL DEFAULT 'EXECUTIVE',
    title TEXT NOT NULL,
    sections_json TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'DRAFT',
    created_by TEXT NOT NULL DEFAULT '',
    approved_by TEXT NOT NULL DEFAULT '',
    approved_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS analytics_v4_export_jobs (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    report_id BIGINT REFERENCES analytics_v4_reports(id) ON DELETE SET NULL,
    snapshot_id BIGINT REFERENCES analytics_v4_snapshots(id) ON DELETE SET NULL,
    export_format TEXT NOT NULL DEFAULT 'json',
    status TEXT NOT NULL DEFAULT 'PENDING',
    filters_json TEXT NOT NULL DEFAULT '{}',
    requested_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    completed_at TEXT,
    expires_at TEXT,
    row_count INTEGER NOT NULL DEFAULT 0,
    file_name TEXT NOT NULL DEFAULT '',
    content_type TEXT NOT NULL DEFAULT '',
    checksum TEXT NOT NULL DEFAULT '',
    storage_key TEXT NOT NULL DEFAULT '',
    error_message_sanitized TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS analytics_v4_saved_views (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    owner TEXT NOT NULL DEFAULT '',
    name TEXT NOT NULL,
    view_type TEXT NOT NULL DEFAULT 'dashboard',
    filters_json TEXT NOT NULL DEFAULT '{}',
    widgets_json TEXT NOT NULL DEFAULT '[]',
    is_default INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS analytics_v4_data_quality_issues (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    severity TEXT NOT NULL,
    code TEXT NOT NULL,
    title TEXT NOT NULL,
    details_json TEXT NOT NULL DEFAULT '{}',
    source TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'OPEN',
    detected_at TEXT NOT NULL,
    resolved_at TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS functional_closure_reviews (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    run_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'IN_REVIEW',
    coverage_json TEXT NOT NULL DEFAULT '[]',
    gates_json TEXT NOT NULL DEFAULT '[]',
    quality_json TEXT NOT NULL DEFAULT '[]',
    blockers_count INTEGER NOT NULL DEFAULT 0,
    approved_by TEXT NOT NULL DEFAULT '',
    approved_at TEXT,
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(event_id, run_id)
);

CREATE TABLE IF NOT EXISTS functional_closure_gate_results (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    closure_review_id BIGINT NOT NULL REFERENCES functional_closure_reviews(id) ON DELETE CASCADE,
    gate_key TEXT NOT NULL,
    status TEXT NOT NULL,
    evidence_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    UNIQUE(closure_review_id, gate_key)
);

CREATE TABLE IF NOT EXISTS functional_closure_findings (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    closure_review_id BIGINT NOT NULL REFERENCES functional_closure_reviews(id) ON DELETE CASCADE,
    severity TEXT NOT NULL DEFAULT 'INFO',
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'OPEN',
    owner TEXT NOT NULL DEFAULT '',
    due_at TEXT,
    resolved_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS functional_closure_actions (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    closure_review_id BIGINT NOT NULL REFERENCES functional_closure_reviews(id) ON DELETE CASCADE,
    finding_id BIGINT REFERENCES functional_closure_findings(id) ON DELETE SET NULL,
    action_type TEXT NOT NULL DEFAULT 'MANUAL_REVIEW',
    status TEXT NOT NULL DEFAULT 'PENDING',
    actor TEXT NOT NULL DEFAULT '',
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_analytics_v4_snapshots_event
ON analytics_v4_snapshots (organization_id, event_id, generated_at);

CREATE INDEX IF NOT EXISTS idx_analytics_v4_reports_event
ON analytics_v4_reports (organization_id, event_id, status, updated_at);

CREATE INDEX IF NOT EXISTS idx_analytics_v4_exports_event
ON analytics_v4_export_jobs (organization_id, event_id, status, created_at);

CREATE INDEX IF NOT EXISTS idx_analytics_v4_quality_event
ON analytics_v4_data_quality_issues (organization_id, event_id, severity, status);

CREATE INDEX IF NOT EXISTS idx_functional_closure_reviews_event
ON functional_closure_reviews (organization_id, event_id, status, updated_at);

CREATE INDEX IF NOT EXISTS idx_functional_closure_findings_review
ON functional_closure_findings (closure_review_id, severity, status);
