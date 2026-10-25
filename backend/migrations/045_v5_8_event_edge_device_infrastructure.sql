CREATE TABLE IF NOT EXISTS enterprise_event_edges (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    edge_uid TEXT NOT NULL,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PROVISIONING',
    cloud_connectivity TEXT NOT NULL DEFAULT 'UNKNOWN',
    event_operation_status TEXT NOT NULL DEFAULT 'DEGRADED',
    software_version TEXT NOT NULL DEFAULT '',
    protocol_version TEXT NOT NULL DEFAULT 'v5.8',
    credential_hash TEXT NOT NULL DEFAULT '',
    credential_hint TEXT NOT NULL DEFAULT '',
    credential_status TEXT NOT NULL DEFAULT 'ACTIVE',
    dataset_revision TEXT NOT NULL DEFAULT '',
    last_cloud_sync TEXT,
    last_seen TEXT,
    clock_status TEXT NOT NULL DEFAULT 'UNKNOWN',
    storage_status TEXT NOT NULL DEFAULT 'UNKNOWN',
    queue_depth INTEGER NOT NULL DEFAULT 0,
    health_json TEXT NOT NULL DEFAULT '{}',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, event_id, edge_uid)
);

CREATE TABLE IF NOT EXISTS enterprise_device_profiles (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    profile_key TEXT NOT NULL,
    revision INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    capabilities_json TEXT NOT NULL DEFAULT '[]',
    defaults_json TEXT NOT NULL DEFAULT '{}',
    dataset_subset_json TEXT NOT NULL DEFAULT '{}',
    offline_policy_json TEXT NOT NULL DEFAULT '{}',
    hardware_requirements_json TEXT NOT NULL DEFAULT '{}',
    ui_hints_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, event_id, profile_key, revision)
);

CREATE TABLE IF NOT EXISTS enterprise_device_pairing_codes (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    edge_id BIGINT REFERENCES enterprise_event_edges(id) ON DELETE SET NULL,
    profile_id BIGINT REFERENCES enterprise_device_profiles(id) ON DELETE SET NULL,
    pairing_code_hash TEXT NOT NULL,
    pairing_code_hint TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'PENDING',
    requested_device_type TEXT NOT NULL DEFAULT '',
    zone_id BIGINT,
    door_id BIGINT,
    expires_at TEXT NOT NULL,
    used_at TEXT,
    used_device_id BIGINT REFERENCES enterprise_devices(id) ON DELETE SET NULL,
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, event_id, pairing_code_hash)
);

CREATE TABLE IF NOT EXISTS enterprise_capability_execution_classes (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    capability TEXT NOT NULL,
    execution_class TEXT NOT NULL,
    certification_status TEXT NOT NULL DEFAULT 'FOUNDATION',
    policy_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, event_id, capability, execution_class)
);

CREATE TABLE IF NOT EXISTS enterprise_edge_checkpoints (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    edge_id BIGINT REFERENCES enterprise_event_edges(id) ON DELETE SET NULL,
    checkpoint_type TEXT NOT NULL,
    checkpoint_value TEXT NOT NULL,
    created_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_enterprise_event_edges_scope ON enterprise_event_edges(organization_id, event_id, status);
CREATE INDEX IF NOT EXISTS idx_enterprise_device_profiles_scope ON enterprise_device_profiles(organization_id, event_id, profile_key, status);
CREATE INDEX IF NOT EXISTS idx_enterprise_pairing_scope ON enterprise_device_pairing_codes(organization_id, event_id, status, expires_at);
CREATE INDEX IF NOT EXISTS idx_enterprise_capability_classes_scope ON enterprise_capability_execution_classes(organization_id, event_id, capability);
CREATE INDEX IF NOT EXISTS idx_enterprise_edge_checkpoints_scope ON enterprise_edge_checkpoints(organization_id, event_id, edge_id, created_at);
