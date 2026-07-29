CREATE TABLE IF NOT EXISTS communication_v4_templates (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    channel TEXT NOT NULL,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'DRAFT',
    current_version_id BIGINT,
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    archived_at TEXT
);

CREATE TABLE IF NOT EXISTS communication_v4_template_versions (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    template_id BIGINT NOT NULL REFERENCES communication_v4_templates(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    subject TEXT NOT NULL DEFAULT '',
    content TEXT NOT NULL DEFAULT '',
    variables_json TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'DRAFT',
    content_hash TEXT NOT NULL,
    approved_by TEXT NOT NULL DEFAULT '',
    approved_at TEXT,
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    UNIQUE(template_id, version_number),
    UNIQUE(template_id, content_hash)
);

CREATE TABLE IF NOT EXISTS communication_v4_segments (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    rules_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    archived_at TEXT
);

CREATE TABLE IF NOT EXISTS communication_v4_campaigns (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    channel TEXT NOT NULL,
    template_id BIGINT NOT NULL REFERENCES communication_v4_templates(id) ON DELETE RESTRICT,
    template_version_id BIGINT NOT NULL REFERENCES communication_v4_template_versions(id) ON DELETE RESTRICT,
    segment_id BIGINT NOT NULL REFERENCES communication_v4_segments(id) ON DELETE RESTRICT,
    status TEXT NOT NULL DEFAULT 'DRAFT',
    safe_mode INTEGER NOT NULL DEFAULT 1,
    live_mode INTEGER NOT NULL DEFAULT 0,
    recipient_count INTEGER NOT NULL DEFAULT 0,
    excluded_count INTEGER NOT NULL DEFAULT 0,
    sent_count INTEGER NOT NULL DEFAULT 0,
    snapshot_hash TEXT NOT NULL DEFAULT '',
    scheduled_at TEXT,
    approved_by TEXT NOT NULL DEFAULT '',
    approved_at TEXT,
    started_at TEXT,
    completed_at TEXT,
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS communication_v4_campaign_recipients (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    campaign_id BIGINT NOT NULL REFERENCES communication_v4_campaigns(id) ON DELETE CASCADE,
    person_id BIGINT NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    accreditation_id BIGINT REFERENCES accreditations(id) ON DELETE SET NULL,
    channel TEXT NOT NULL,
    recipient TEXT NOT NULL,
    original_recipient TEXT NOT NULL DEFAULT '',
    consent_status TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'READY',
    message_id BIGINT,
    idempotency_key TEXT NOT NULL,
    snapshot_hash TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    UNIQUE(idempotency_key)
);

CREATE TABLE IF NOT EXISTS communication_v4_messages (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    campaign_id BIGINT REFERENCES communication_v4_campaigns(id) ON DELETE SET NULL,
    campaign_recipient_id BIGINT REFERENCES communication_v4_campaign_recipients(id) ON DELETE SET NULL,
    person_id BIGINT REFERENCES people(id) ON DELETE SET NULL,
    accreditation_id BIGINT REFERENCES accreditations(id) ON DELETE SET NULL,
    channel TEXT NOT NULL,
    recipient TEXT NOT NULL,
    subject TEXT NOT NULL DEFAULT '',
    content TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'created',
    provider TEXT NOT NULL DEFAULT '',
    provider_message_id TEXT NOT NULL DEFAULT '',
    idempotency_key TEXT NOT NULL,
    correlation_id TEXT NOT NULL DEFAULT '',
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(idempotency_key)
);

CREATE TABLE IF NOT EXISTS communication_v4_deliveries (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    message_id BIGINT NOT NULL REFERENCES communication_v4_messages(id) ON DELETE CASCADE,
    channel TEXT NOT NULL,
    provider TEXT NOT NULL DEFAULT '',
    provider_message_id TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'accepted',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS communication_v4_attempts (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    message_id BIGINT NOT NULL REFERENCES communication_v4_messages(id) ON DELETE CASCADE,
    delivery_id BIGINT REFERENCES communication_v4_deliveries(id) ON DELETE SET NULL,
    attempt_number INTEGER NOT NULL,
    status TEXT NOT NULL,
    error_code TEXT NOT NULL DEFAULT '',
    error_message_sanitized TEXT NOT NULL DEFAULT '',
    retryable INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS communication_v4_consents (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT REFERENCES events(id) ON DELETE CASCADE,
    person_id BIGINT NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    channel TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'granted',
    source TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, person_id, channel)
);

CREATE TABLE IF NOT EXISTS communication_v4_suppressions (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT REFERENCES events(id) ON DELETE CASCADE,
    channel TEXT NOT NULL,
    recipient TEXT NOT NULL,
    normalized_recipient TEXT NOT NULL,
    reason TEXT NOT NULL,
    scope TEXT NOT NULL DEFAULT 'event',
    active INTEGER NOT NULL DEFAULT 1,
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS communication_v4_unsubscribes (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT REFERENCES events(id) ON DELETE CASCADE,
    person_id BIGINT REFERENCES people(id) ON DELETE SET NULL,
    channel TEXT NOT NULL,
    recipient TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS communication_v4_automations (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    trigger_type TEXT NOT NULL,
    channel TEXT NOT NULL,
    template_id BIGINT REFERENCES communication_v4_templates(id) ON DELETE SET NULL,
    segment_id BIGINT REFERENCES communication_v4_segments(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'DRAFT',
    safe_mode INTEGER NOT NULL DEFAULT 1,
    limits_json TEXT NOT NULL DEFAULT '{}',
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS communication_v4_automation_runs (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    automation_id BIGINT NOT NULL REFERENCES communication_v4_automations(id) ON DELETE CASCADE,
    trigger_payload_minimized TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'pending',
    campaign_id BIGINT REFERENCES communication_v4_campaigns(id) ON DELETE SET NULL,
    idempotency_key TEXT NOT NULL,
    created_at TEXT NOT NULL,
    completed_at TEXT,
    UNIQUE(idempotency_key)
);

CREATE TABLE IF NOT EXISTS communication_v4_provider_events (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    external_event_id TEXT NOT NULL,
    message_id BIGINT REFERENCES communication_v4_messages(id) ON DELETE SET NULL,
    provider_message_id TEXT NOT NULL DEFAULT '',
    event_type TEXT NOT NULL,
    payload_minimized TEXT NOT NULL DEFAULT '{}',
    signature_valid INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    UNIQUE(provider, external_event_id)
);

CREATE TABLE IF NOT EXISTS communication_v4_approvals (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    campaign_id BIGINT REFERENCES communication_v4_campaigns(id) ON DELETE SET NULL,
    approval_type TEXT NOT NULL,
    status TEXT NOT NULL,
    actor TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_comm_v4_templates_scope ON communication_v4_templates(organization_id, event_id, channel, status);
CREATE INDEX IF NOT EXISTS idx_comm_v4_segments_scope ON communication_v4_segments(organization_id, event_id, status);
CREATE INDEX IF NOT EXISTS idx_comm_v4_campaigns_scope ON communication_v4_campaigns(organization_id, event_id, status);
CREATE INDEX IF NOT EXISTS idx_comm_v4_recipients_campaign ON communication_v4_campaign_recipients(campaign_id, status);
CREATE INDEX IF NOT EXISTS idx_comm_v4_messages_scope ON communication_v4_messages(organization_id, event_id, campaign_id, status);
CREATE INDEX IF NOT EXISTS idx_comm_v4_deliveries_provider ON communication_v4_deliveries(provider, provider_message_id);
CREATE INDEX IF NOT EXISTS idx_comm_v4_suppressions_lookup ON communication_v4_suppressions(organization_id, channel, normalized_recipient, active);
CREATE INDEX IF NOT EXISTS idx_comm_v4_automations_scope ON communication_v4_automations(organization_id, event_id, status, trigger_type);
