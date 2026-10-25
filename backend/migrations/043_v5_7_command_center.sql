CREATE TABLE IF NOT EXISTS enterprise_alert_rules (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    rule_key TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'WARNING',
    threshold_value REAL NOT NULL DEFAULT 0,
    enabled INTEGER NOT NULL DEFAULT 1,
    config_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, event_id, rule_key)
);

CREATE TABLE IF NOT EXISTS enterprise_operational_alerts (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    alert_key TEXT NOT NULL,
    alert_type TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'WARNING',
    status TEXT NOT NULL DEFAULT 'OPEN',
    source TEXT NOT NULL DEFAULT 'command_center',
    title TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT '',
    metric_value REAL NOT NULL DEFAULT 0,
    entity_ref TEXT NOT NULL DEFAULT '',
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    acknowledged_at TEXT,
    acknowledged_by TEXT NOT NULL DEFAULT '',
    resolved_at TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_enterprise_alert_rules_scope ON enterprise_alert_rules(organization_id, event_id, enabled);
CREATE INDEX IF NOT EXISTS idx_enterprise_operational_alerts_scope ON enterprise_operational_alerts(organization_id, event_id, status, severity);
CREATE INDEX IF NOT EXISTS idx_enterprise_operational_alerts_key ON enterprise_operational_alerts(organization_id, event_id, alert_key, status);
