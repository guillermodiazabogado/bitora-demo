CREATE TABLE IF NOT EXISTS enterprise_entities (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    entity_type TEXT NOT NULL,
    legacy_table TEXT NOT NULL DEFAULT '',
    legacy_id BIGINT,
    external_key TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, event_id, entity_type, legacy_table, legacy_id, external_key)
);

CREATE TABLE IF NOT EXISTS enterprise_identities (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    entity_id BIGINT NOT NULL REFERENCES enterprise_entities(id) ON DELETE CASCADE,
    identity_type TEXT NOT NULL DEFAULT 'PROFILE',
    display_name TEXT NOT NULL DEFAULT '',
    identity_hash TEXT NOT NULL DEFAULT '',
    verification_status TEXT NOT NULL DEFAULT 'UNVERIFIED',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(entity_id, identity_type)
);

CREATE TABLE IF NOT EXISTS enterprise_credentials (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    entity_id BIGINT NOT NULL REFERENCES enterprise_entities(id) ON DELETE CASCADE,
    accreditation_id BIGINT REFERENCES accreditations(id) ON DELETE SET NULL,
    credential_type TEXT NOT NULL,
    legacy_token_hash TEXT NOT NULL DEFAULT '',
    token_hint TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    issued_at TEXT NOT NULL DEFAULT '',
    revoked_at TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, event_id, credential_type, accreditation_id)
);

CREATE TABLE IF NOT EXISTS enterprise_doors (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    zone_id BIGINT REFERENCES event_zones(id) ON DELETE SET NULL,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    door_type TEXT NOT NULL DEFAULT 'LOGICAL',
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, event_id, code)
);

CREATE TABLE IF NOT EXISTS enterprise_devices (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    device_uid TEXT NOT NULL,
    device_type TEXT NOT NULL DEFAULT 'GENERIC',
    status TEXT NOT NULL DEFAULT 'REGISTERED',
    last_seen_at TEXT,
    version TEXT NOT NULL DEFAULT '',
    dataset_revision TEXT NOT NULL DEFAULT '',
    sync_state TEXT NOT NULL DEFAULT 'NOT_CONFIGURED',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, event_id, device_uid)
);

CREATE TABLE IF NOT EXISTS enterprise_entitlements (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    entity_id BIGINT NOT NULL REFERENCES enterprise_entities(id) ON DELETE CASCADE,
    entitlement_type TEXT NOT NULL,
    scope_type TEXT NOT NULL DEFAULT 'EVENT',
    scope_id TEXT NOT NULL DEFAULT '',
    allocated INTEGER NOT NULL DEFAULT 0,
    consumed INTEGER NOT NULL DEFAULT 0,
    consumable INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    valid_from TEXT NOT NULL DEFAULT '',
    valid_until TEXT NOT NULL DEFAULT '',
    idempotency_key TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, event_id, entity_id, entitlement_type, scope_type, scope_id)
);

CREATE TABLE IF NOT EXISTS enterprise_rules (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    entitlement_id BIGINT REFERENCES enterprise_entitlements(id) ON DELETE CASCADE,
    rule_type TEXT NOT NULL,
    scope_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    valid_from TEXT NOT NULL DEFAULT '',
    valid_until TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS enterprise_domain_events (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    entity_id BIGINT REFERENCES enterprise_entities(id) ON DELETE SET NULL,
    device_id BIGINT REFERENCES enterprise_devices(id) ON DELETE SET NULL,
    event_type TEXT NOT NULL,
    correlation_id TEXT NOT NULL DEFAULT '',
    idempotency_key TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    occurred_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_enterprise_entities_scope ON enterprise_entities(organization_id, event_id, entity_type, status);
CREATE INDEX IF NOT EXISTS idx_enterprise_credentials_scope ON enterprise_credentials(organization_id, event_id, credential_type, status);
CREATE INDEX IF NOT EXISTS idx_enterprise_entitlements_scope ON enterprise_entitlements(organization_id, event_id, entity_id, entitlement_type, status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_enterprise_entitlements_idempotency ON enterprise_entitlements(organization_id, idempotency_key) WHERE idempotency_key <> '';
CREATE INDEX IF NOT EXISTS idx_enterprise_rules_scope ON enterprise_rules(organization_id, event_id, entitlement_id, rule_type, status);
CREATE INDEX IF NOT EXISTS idx_enterprise_doors_scope ON enterprise_doors(organization_id, event_id, zone_id, status);
CREATE INDEX IF NOT EXISTS idx_enterprise_devices_scope ON enterprise_devices(organization_id, event_id, status);
CREATE INDEX IF NOT EXISTS idx_enterprise_domain_events_scope ON enterprise_domain_events(organization_id, event_id, event_type, occurred_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_enterprise_domain_events_idempotency ON enterprise_domain_events(organization_id, idempotency_key) WHERE idempotency_key <> '';
