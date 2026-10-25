CREATE TABLE IF NOT EXISTS enterprise_stands (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    company_id BIGINT NOT NULL REFERENCES enterprise_companies(id) ON DELETE CASCADE,
    zone_id BIGINT REFERENCES event_zones(id) ON DELETE SET NULL,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, event_id, company_id, code)
);

CREATE TABLE IF NOT EXISTS enterprise_lead_licenses (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    company_id BIGINT NOT NULL REFERENCES enterprise_companies(id) ON DELETE CASCADE,
    stand_id BIGINT REFERENCES enterprise_stands(id) ON DELETE SET NULL,
    max_users INTEGER NOT NULL DEFAULT 0,
    max_devices INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'PENDING',
    valid_from TEXT NOT NULL DEFAULT '',
    valid_until TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, event_id, company_id, stand_id)
);

CREATE TABLE IF NOT EXISTS enterprise_lead_consents (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    participant_entity_id BIGINT NOT NULL REFERENCES enterprise_entities(id) ON DELETE CASCADE,
    company_id BIGINT REFERENCES enterprise_companies(id) ON DELETE CASCADE,
    purpose TEXT NOT NULL DEFAULT 'LEAD_RETRIEVAL',
    policy_version TEXT NOT NULL DEFAULT 'v1',
    status TEXT NOT NULL DEFAULT 'GRANTED',
    granted_at TEXT,
    revoked_at TEXT,
    source TEXT NOT NULL DEFAULT '',
    fields_json TEXT NOT NULL DEFAULT '[]',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS enterprise_leads (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    company_id BIGINT NOT NULL REFERENCES enterprise_companies(id) ON DELETE CASCADE,
    stand_id BIGINT REFERENCES enterprise_stands(id) ON DELETE SET NULL,
    participant_entity_id BIGINT NOT NULL REFERENCES enterprise_entities(id) ON DELETE CASCADE,
    captured_by_user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    captured_by_device_id BIGINT REFERENCES enterprise_devices(id) ON DELETE SET NULL,
    captured_at TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT '',
    consent_id BIGINT REFERENCES enterprise_lead_consents(id) ON DELETE SET NULL,
    qualification TEXT NOT NULL DEFAULT 'UNQUALIFIED',
    follow_up_status TEXT NOT NULL DEFAULT 'NEW',
    assigned_user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    data_snapshot_json TEXT NOT NULL DEFAULT '{}',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, event_id, company_id, participant_entity_id)
);

CREATE TABLE IF NOT EXISTS enterprise_lead_interactions (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    company_id BIGINT NOT NULL REFERENCES enterprise_companies(id) ON DELETE CASCADE,
    lead_id BIGINT NOT NULL REFERENCES enterprise_leads(id) ON DELETE CASCADE,
    interaction_type TEXT NOT NULL,
    actor_user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    device_id BIGINT REFERENCES enterprise_devices(id) ON DELETE SET NULL,
    note TEXT NOT NULL DEFAULT '',
    tags_json TEXT NOT NULL DEFAULT '[]',
    idempotency_key TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    occurred_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS enterprise_lead_exports (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    company_id BIGINT NOT NULL REFERENCES enterprise_companies(id) ON DELETE CASCADE,
    exported_by TEXT NOT NULL DEFAULT '',
    lead_count INTEGER NOT NULL DEFAULT 0,
    fields_json TEXT NOT NULL DEFAULT '[]',
    policy_version TEXT NOT NULL DEFAULT 'v1',
    idempotency_key TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    UNIQUE(organization_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_enterprise_stands_scope ON enterprise_stands(organization_id, event_id, company_id, status);
CREATE INDEX IF NOT EXISTS idx_enterprise_lead_licenses_scope ON enterprise_lead_licenses(organization_id, event_id, company_id, status);
CREATE INDEX IF NOT EXISTS idx_enterprise_lead_consents_scope ON enterprise_lead_consents(organization_id, event_id, participant_entity_id, company_id, status);
CREATE INDEX IF NOT EXISTS idx_enterprise_leads_scope ON enterprise_leads(organization_id, event_id, company_id, qualification, follow_up_status);
CREATE INDEX IF NOT EXISTS idx_enterprise_lead_interactions_scope ON enterprise_lead_interactions(organization_id, event_id, company_id, lead_id, interaction_type);
CREATE UNIQUE INDEX IF NOT EXISTS idx_enterprise_lead_interactions_idempotency ON enterprise_lead_interactions(organization_id, idempotency_key) WHERE idempotency_key <> '';
