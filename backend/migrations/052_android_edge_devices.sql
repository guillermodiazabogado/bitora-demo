CREATE TABLE IF NOT EXISTS android_pairings (
    code_hash TEXT PRIMARY KEY,
    pairing_code TEXT NOT NULL,
    nonce_hash TEXT NOT NULL,
    device_kind TEXT NOT NULL,
    requested_profile TEXT NOT NULL,
    software_version TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'PENDING',
    organization_id BIGINT REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT REFERENCES events(id) ON DELETE CASCADE,
    event_name TEXT NOT NULL DEFAULT '',
    profile TEXT NOT NULL DEFAULT '',
    scope TEXT NOT NULL DEFAULT '',
    capabilities_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    expires_at_epoch BIGINT NOT NULL,
    approved_at TEXT,
    used_device_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_android_pairings_status ON android_pairings(status, expires_at_epoch);

CREATE TABLE IF NOT EXISTS android_devices (
    device_id TEXT PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    event_name TEXT NOT NULL DEFAULT '',
    profile TEXT NOT NULL,
    scope TEXT NOT NULL,
    capabilities_json TEXT NOT NULL DEFAULT '[]',
    credential_hash TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    software_version TEXT NOT NULL DEFAULT '',
    dataset_revision TEXT NOT NULL DEFAULT '',
    telemetry_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    last_seen_at TEXT,
    revoked_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_android_devices_event ON android_devices(organization_id, event_id, status);

CREATE TABLE IF NOT EXISTS android_edge_operations (
    operation_id TEXT PRIMARY KEY,
    device_id TEXT NOT NULL REFERENCES android_devices(device_id) ON DELETE CASCADE,
    idempotency_key TEXT NOT NULL,
    operation_type TEXT NOT NULL,
    correlation_id TEXT NOT NULL DEFAULT '',
    sequence_number BIGINT NOT NULL DEFAULT 0,
    payload_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'ACKNOWLEDGED',
    created_at TEXT NOT NULL,
    UNIQUE(device_id, idempotency_key)
);

