CREATE TABLE IF NOT EXISTS operations_center_alerts (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    alert_type TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'MEDIUM',
    status TEXT NOT NULL DEFAULT 'OPEN',
    source TEXT NOT NULL DEFAULT '',
    dedupe_key TEXT NOT NULL,
    message TEXT NOT NULL,
    entity_type TEXT NOT NULL DEFAULT '',
    entity_id BIGINT,
    correlation_id TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL,
    acknowledged_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ,
    actor TEXT NOT NULL DEFAULT ''
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_operations_alert_open ON operations_center_alerts(organization_id, event_id, dedupe_key, status);
CREATE INDEX IF NOT EXISTS idx_operations_alert_scope ON operations_center_alerts(organization_id, event_id, status, created_at);

CREATE TABLE IF NOT EXISTS operations_center_incidents (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT 'GENERAL',
    severity TEXT NOT NULL DEFAULT 'MEDIUM',
    status TEXT NOT NULL DEFAULT 'OPEN',
    reporter TEXT NOT NULL DEFAULT '',
    assignee TEXT NOT NULL DEFAULT '',
    related_entity TEXT NOT NULL DEFAULT '',
    resolution TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    resolved_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_operations_incident_scope ON operations_center_incidents(organization_id, event_id, status, created_at);

CREATE TABLE IF NOT EXISTS operations_center_tasks (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    priority TEXT NOT NULL DEFAULT 'MEDIUM',
    status TEXT NOT NULL DEFAULT 'OPEN',
    assignee TEXT NOT NULL DEFAULT '',
    due_at TIMESTAMPTZ,
    alert_id BIGINT REFERENCES operations_center_alerts(id) ON DELETE SET NULL,
    incident_id BIGINT REFERENCES operations_center_incidents(id) ON DELETE SET NULL,
    created_by TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_operations_task_scope ON operations_center_tasks(organization_id, event_id, status, due_at);
