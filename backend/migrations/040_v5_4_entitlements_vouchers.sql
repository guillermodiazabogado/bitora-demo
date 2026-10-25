ALTER TABLE enterprise_entitlements ADD COLUMN source TEXT NOT NULL DEFAULT '';
ALTER TABLE enterprise_entitlements ADD COLUMN source_reference TEXT NOT NULL DEFAULT '';

CREATE TABLE IF NOT EXISTS enterprise_entitlement_types (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    consumable INTEGER NOT NULL DEFAULT 1,
    default_quantity INTEGER NOT NULL DEFAULT 1,
    offline_policy TEXT NOT NULL DEFAULT 'ONLINE_REQUIRED',
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, event_id, code)
);

CREATE TABLE IF NOT EXISTS enterprise_service_points (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    zone_id BIGINT REFERENCES event_zones(id) ON DELETE SET NULL,
    device_id BIGINT REFERENCES enterprise_devices(id) ON DELETE SET NULL,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    service_type TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, event_id, code)
);

CREATE TABLE IF NOT EXISTS enterprise_entitlement_consumptions (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    entity_id BIGINT REFERENCES enterprise_entities(id) ON DELETE SET NULL,
    credential_id BIGINT REFERENCES enterprise_credentials(id) ON DELETE SET NULL,
    entitlement_id BIGINT REFERENCES enterprise_entitlements(id) ON DELETE SET NULL,
    service_point_id BIGINT REFERENCES enterprise_service_points(id) ON DELETE SET NULL,
    device_id BIGINT REFERENCES enterprise_devices(id) ON DELETE SET NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    occurred_at TEXT NOT NULL,
    server_received_at TEXT NOT NULL,
    idempotency_key TEXT NOT NULL DEFAULT '',
    correlation_id TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT '',
    result TEXT NOT NULL,
    reason_code TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS enterprise_entitlement_adjustments (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    entitlement_id BIGINT NOT NULL REFERENCES enterprise_entitlements(id) ON DELETE CASCADE,
    quantity_delta INTEGER NOT NULL DEFAULT 0,
    reason TEXT NOT NULL DEFAULT '',
    actor TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS enterprise_entitlement_grant_batches (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    grant_id TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT '',
    source_reference TEXT NOT NULL DEFAULT '',
    entitlement_type TEXT NOT NULL,
    summary_json TEXT NOT NULL DEFAULT '{}',
    idempotency_key TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'COMPLETED',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, event_id, grant_id)
);

CREATE INDEX IF NOT EXISTS idx_enterprise_entitlement_types_scope ON enterprise_entitlement_types(organization_id, event_id, code, status);
CREATE INDEX IF NOT EXISTS idx_enterprise_service_points_scope ON enterprise_service_points(organization_id, event_id, code, status);
CREATE INDEX IF NOT EXISTS idx_enterprise_consumptions_scope ON enterprise_entitlement_consumptions(organization_id, event_id, entitlement_id, result, occurred_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_enterprise_consumptions_idempotency ON enterprise_entitlement_consumptions(organization_id, idempotency_key) WHERE idempotency_key <> '';
CREATE INDEX IF NOT EXISTS idx_enterprise_adjustments_scope ON enterprise_entitlement_adjustments(organization_id, event_id, entitlement_id, created_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_enterprise_grant_batches_idempotency ON enterprise_entitlement_grant_batches(organization_id, idempotency_key) WHERE idempotency_key <> '';
