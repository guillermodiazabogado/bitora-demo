CREATE TABLE IF NOT EXISTS enterprise_access_events (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    entity_id BIGINT REFERENCES enterprise_entities(id) ON DELETE SET NULL,
    credential_id BIGINT REFERENCES enterprise_credentials(id) ON DELETE SET NULL,
    accreditation_id BIGINT REFERENCES accreditations(id) ON DELETE SET NULL,
    door_id BIGINT REFERENCES enterprise_doors(id) ON DELETE SET NULL,
    zone_id BIGINT REFERENCES event_zones(id) ON DELETE SET NULL,
    device_id BIGINT REFERENCES enterprise_devices(id) ON DELETE SET NULL,
    direction TEXT NOT NULL,
    decision TEXT NOT NULL,
    reason_code TEXT NOT NULL,
    previous_state TEXT NOT NULL DEFAULT 'OUTSIDE',
    proposed_state TEXT NOT NULL DEFAULT 'OUTSIDE',
    previous_zone_id BIGINT,
    proposed_zone_id BIGINT,
    correlation_id TEXT NOT NULL DEFAULT '',
    idempotency_key TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT 'shadow',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    occurred_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS enterprise_access_state_snapshots (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    entity_id BIGINT NOT NULL REFERENCES enterprise_entities(id) ON DELETE CASCADE,
    credential_id BIGINT REFERENCES enterprise_credentials(id) ON DELETE SET NULL,
    accreditation_id BIGINT REFERENCES accreditations(id) ON DELETE SET NULL,
    current_state TEXT NOT NULL DEFAULT 'OUTSIDE',
    current_zone_id BIGINT REFERENCES event_zones(id) ON DELETE SET NULL,
    last_access_event_id BIGINT REFERENCES enterprise_access_events(id) ON DELETE SET NULL,
    last_decision TEXT NOT NULL DEFAULT '',
    last_reason_code TEXT NOT NULL DEFAULT '',
    last_direction TEXT NOT NULL DEFAULT '',
    last_door_id BIGINT REFERENCES enterprise_doors(id) ON DELETE SET NULL,
    last_device_id BIGINT REFERENCES enterprise_devices(id) ON DELETE SET NULL,
    last_transition_at TEXT NOT NULL DEFAULT '',
    next_allowed_at TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, event_id, entity_id)
);

CREATE TABLE IF NOT EXISTS enterprise_credential_revocations (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    credential_id BIGINT NOT NULL REFERENCES enterprise_credentials(id) ON DELETE CASCADE,
    accreditation_id BIGINT REFERENCES accreditations(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    reason_code TEXT NOT NULL DEFAULT 'REVOKED',
    reason TEXT NOT NULL DEFAULT '',
    actor TEXT NOT NULL DEFAULT '',
    revoked_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    UNIQUE(organization_id, event_id, credential_id, status)
);

CREATE TABLE IF NOT EXISTS enterprise_access_comparisons (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    entity_id BIGINT REFERENCES enterprise_entities(id) ON DELETE SET NULL,
    credential_id BIGINT REFERENCES enterprise_credentials(id) ON DELETE SET NULL,
    accreditation_id BIGINT REFERENCES accreditations(id) ON DELETE SET NULL,
    access_event_id BIGINT REFERENCES enterprise_access_events(id) ON DELETE SET NULL,
    v4_result TEXT NOT NULL,
    v4_reason TEXT NOT NULL DEFAULT '',
    v5_decision TEXT NOT NULL,
    v5_reason_code TEXT NOT NULL,
    comparison TEXT NOT NULL,
    classification TEXT NOT NULL DEFAULT '',
    correlation_id TEXT NOT NULL DEFAULT '',
    idempotency_key TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_enterprise_access_events_scope ON enterprise_access_events(organization_id, event_id, entity_id, occurred_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_enterprise_access_events_idempotency ON enterprise_access_events(organization_id, idempotency_key) WHERE idempotency_key <> '';
CREATE INDEX IF NOT EXISTS idx_enterprise_access_state_scope ON enterprise_access_state_snapshots(organization_id, event_id, current_state, current_zone_id);
CREATE INDEX IF NOT EXISTS idx_enterprise_revocations_scope ON enterprise_credential_revocations(organization_id, event_id, credential_id, status);
CREATE INDEX IF NOT EXISTS idx_enterprise_access_comparisons_scope ON enterprise_access_comparisons(organization_id, event_id, comparison, created_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_enterprise_access_comparisons_idempotency ON enterprise_access_comparisons(organization_id, idempotency_key) WHERE idempotency_key <> '';
