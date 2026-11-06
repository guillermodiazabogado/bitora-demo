CREATE TABLE IF NOT EXISTS android_edge_credentials (
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    accreditation_id BIGINT NOT NULL REFERENCES accreditations(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (event_id, token_hash),
    UNIQUE (event_id, accreditation_id)
);

CREATE INDEX IF NOT EXISTS idx_android_edge_credentials_accreditation
    ON android_edge_credentials(accreditation_id);

CREATE TABLE IF NOT EXISTS android_service_entitlements (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    accreditation_id BIGINT NOT NULL REFERENCES accreditations(id) ON DELETE CASCADE,
    entitlement_type TEXT NOT NULL,
    service_point TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    quantity INTEGER NOT NULL DEFAULT 1,
    consumed_quantity INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(event_id, accreditation_id, entitlement_type, service_point)
);

CREATE INDEX IF NOT EXISTS idx_android_service_entitlements_event
    ON android_service_entitlements(event_id, status);

CREATE TABLE IF NOT EXISTS android_service_consumptions (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    entitlement_id BIGINT NOT NULL REFERENCES android_service_entitlements(id) ON DELETE CASCADE,
    accreditation_id BIGINT NOT NULL REFERENCES accreditations(id) ON DELETE CASCADE,
    device_id TEXT NOT NULL REFERENCES android_devices(device_id) ON DELETE CASCADE,
    operation_id TEXT NOT NULL REFERENCES android_edge_operations(operation_id) ON DELETE CASCADE,
    quantity INTEGER NOT NULL DEFAULT 1,
    service_point TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(operation_id)
);

CREATE TABLE IF NOT EXISTS android_lead_participants (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    accreditation_id BIGINT NOT NULL REFERENCES accreditations(id) ON DELETE CASCADE,
    consent_status TEXT NOT NULL DEFAULT 'GRANTED',
    source TEXT NOT NULL DEFAULT 'admin',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(event_id, accreditation_id)
);

CREATE INDEX IF NOT EXISTS idx_android_lead_participants_event
    ON android_lead_participants(event_id, consent_status);

CREATE TABLE IF NOT EXISTS android_lead_captures (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    accreditation_id BIGINT NOT NULL REFERENCES accreditations(id) ON DELETE CASCADE,
    device_id TEXT NOT NULL REFERENCES android_devices(device_id) ON DELETE CASCADE,
    operation_id TEXT NOT NULL REFERENCES android_edge_operations(operation_id) ON DELETE CASCADE,
    consent_verified INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    UNIQUE(event_id, device_id, accreditation_id),
    UNIQUE(operation_id)
);

CREATE TABLE IF NOT EXISTS android_vehicle_permits (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    permit_token TEXT NOT NULL UNIQUE,
    token_hash TEXT NOT NULL,
    display_label TEXT NOT NULL,
    checkpoint TEXT NOT NULL DEFAULT 'logistics-main',
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(event_id, token_hash)
);

CREATE INDEX IF NOT EXISTS idx_android_vehicle_permits_event
    ON android_vehicle_permits(event_id, status);

CREATE TABLE IF NOT EXISTS android_vehicle_access (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    permit_id BIGINT REFERENCES android_vehicle_permits(id) ON DELETE SET NULL,
    device_id TEXT NOT NULL REFERENCES android_devices(device_id) ON DELETE CASCADE,
    operation_id TEXT NOT NULL REFERENCES android_edge_operations(operation_id) ON DELETE CASCADE,
    checkpoint TEXT NOT NULL,
    decision TEXT NOT NULL,
    reason_code TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    UNIQUE(operation_id)
);

CREATE INDEX IF NOT EXISTS idx_android_vehicle_access_event
    ON android_vehicle_access(event_id, created_at DESC);
