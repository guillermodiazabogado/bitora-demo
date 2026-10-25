ALTER TABLE enterprise_devices ADD COLUMN display_name TEXT NOT NULL DEFAULT '';
ALTER TABLE enterprise_devices ADD COLUMN capabilities_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE enterprise_devices ADD COLUMN credential_hash TEXT NOT NULL DEFAULT '';
ALTER TABLE enterprise_devices ADD COLUMN credential_hint TEXT NOT NULL DEFAULT '';
ALTER TABLE enterprise_devices ADD COLUMN credential_rotated_at TEXT NOT NULL DEFAULT '';
ALTER TABLE enterprise_devices ADD COLUMN revoked_at TEXT;
ALTER TABLE enterprise_devices ADD COLUMN revoked_reason TEXT NOT NULL DEFAULT '';

CREATE TABLE IF NOT EXISTS enterprise_event_datasets (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    revision TEXT NOT NULL,
    dataset_type TEXT NOT NULL DEFAULT 'ACCESS_FULL',
    schema_version TEXT NOT NULL DEFAULT 'v5.2',
    checksum TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'CURRENT',
    generated_at TEXT NOT NULL,
    generated_by TEXT NOT NULL DEFAULT '',
    payload_json TEXT NOT NULL DEFAULT '{}',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    UNIQUE(organization_id, event_id, revision)
);

CREATE TABLE IF NOT EXISTS enterprise_edge_queue (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    device_id BIGINT NOT NULL REFERENCES enterprise_devices(id) ON DELETE CASCADE,
    operation_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    correlation_id TEXT NOT NULL,
    device_sequence INTEGER NOT NULL DEFAULT 0,
    operation_type TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    local_decision_json TEXT NOT NULL DEFAULT '{}',
    dataset_revision TEXT NOT NULL DEFAULT '',
    device_occurred_at TEXT NOT NULL,
    queued_at TEXT NOT NULL,
    server_received_at TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'PENDING',
    last_error TEXT NOT NULL DEFAULT '',
    server_result_json TEXT NOT NULL DEFAULT '{}',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, event_id, device_id, operation_id),
    UNIQUE(organization_id, idempotency_key)
);

CREATE TABLE IF NOT EXISTS enterprise_edge_reconciliations (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    device_id BIGINT REFERENCES enterprise_devices(id) ON DELETE SET NULL,
    queue_id BIGINT REFERENCES enterprise_edge_queue(id) ON DELETE SET NULL,
    operation_id TEXT NOT NULL DEFAULT '',
    local_decision TEXT NOT NULL DEFAULT '',
    server_decision TEXT NOT NULL DEFAULT '',
    conflict_type TEXT NOT NULL DEFAULT 'NO_CONFLICT',
    resolution TEXT NOT NULL DEFAULT '',
    correlation_id TEXT NOT NULL DEFAULT '',
    idempotency_key TEXT NOT NULL DEFAULT '',
    dataset_revision TEXT NOT NULL DEFAULT '',
    device_sequence INTEGER NOT NULL DEFAULT 0,
    clock_skew_seconds INTEGER NOT NULL DEFAULT 0,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    reconciled_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS enterprise_device_heartbeats (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    device_id BIGINT NOT NULL REFERENCES enterprise_devices(id) ON DELETE CASCADE,
    software_version TEXT NOT NULL DEFAULT '',
    dataset_revision TEXT NOT NULL DEFAULT '',
    queue_depth INTEGER NOT NULL DEFAULT 0,
    sync_status TEXT NOT NULL DEFAULT '',
    clock_skew_seconds INTEGER NOT NULL DEFAULT 0,
    received_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_enterprise_datasets_scope ON enterprise_event_datasets(organization_id, event_id, status, generated_at);
CREATE INDEX IF NOT EXISTS idx_enterprise_edge_queue_status ON enterprise_edge_queue(organization_id, event_id, device_id, status, queued_at);
CREATE INDEX IF NOT EXISTS idx_enterprise_reconciliations_scope ON enterprise_edge_reconciliations(organization_id, event_id, conflict_type, reconciled_at);
CREATE INDEX IF NOT EXISTS idx_enterprise_device_heartbeats_scope ON enterprise_device_heartbeats(organization_id, event_id, device_id, received_at);
