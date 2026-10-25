CREATE TABLE IF NOT EXISTS enterprise_vehicles (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    entity_id BIGINT REFERENCES enterprise_entities(id) ON DELETE SET NULL,
    plate TEXT NOT NULL,
    normalized_plate TEXT NOT NULL,
    vehicle_type TEXT NOT NULL DEFAULT 'CAR',
    make TEXT NOT NULL DEFAULT '',
    model TEXT NOT NULL DEFAULT '',
    color TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, normalized_plate)
);

CREATE TABLE IF NOT EXISTS enterprise_vehicle_event_participation (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    vehicle_id BIGINT NOT NULL REFERENCES enterprise_vehicles(id) ON DELETE CASCADE,
    company_id BIGINT REFERENCES enterprise_companies(id) ON DELETE SET NULL,
    driver_entity_id BIGINT REFERENCES enterprise_entities(id) ON DELETE SET NULL,
    purpose TEXT NOT NULL DEFAULT 'SERVICE',
    status TEXT NOT NULL DEFAULT 'PENDING',
    valid_from TEXT NOT NULL DEFAULT '',
    valid_until TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, event_id, vehicle_id)
);

CREATE TABLE IF NOT EXISTS enterprise_logistics_destinations (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    zone_id BIGINT REFERENCES event_zones(id) ON DELETE SET NULL,
    stand_id BIGINT REFERENCES enterprise_stands(id) ON DELETE SET NULL,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    capacity INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, event_id, code)
);

CREATE TABLE IF NOT EXISTS enterprise_vehicle_access_slots (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    vehicle_id BIGINT NOT NULL REFERENCES enterprise_vehicles(id) ON DELETE CASCADE,
    company_id BIGINT REFERENCES enterprise_companies(id) ON DELETE SET NULL,
    driver_entity_id BIGINT REFERENCES enterprise_entities(id) ON DELETE SET NULL,
    gate_id BIGINT REFERENCES enterprise_doors(id) ON DELETE SET NULL,
    destination_id BIGINT REFERENCES enterprise_logistics_destinations(id) ON DELETE SET NULL,
    purpose TEXT NOT NULL DEFAULT 'SERVICE',
    valid_from TEXT NOT NULL DEFAULT '',
    valid_until TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'PENDING',
    entry_limit INTEGER NOT NULL DEFAULT 1,
    entries_used INTEGER NOT NULL DEFAULT 0,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS enterprise_vehicle_access_events (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    vehicle_id BIGINT REFERENCES enterprise_vehicles(id) ON DELETE SET NULL,
    driver_entity_id BIGINT REFERENCES enterprise_entities(id) ON DELETE SET NULL,
    company_id BIGINT REFERENCES enterprise_companies(id) ON DELETE SET NULL,
    slot_id BIGINT REFERENCES enterprise_vehicle_access_slots(id) ON DELETE SET NULL,
    gate_id BIGINT REFERENCES enterprise_doors(id) ON DELETE SET NULL,
    destination_id BIGINT REFERENCES enterprise_logistics_destinations(id) ON DELETE SET NULL,
    device_id BIGINT REFERENCES enterprise_devices(id) ON DELETE SET NULL,
    direction TEXT NOT NULL,
    decision TEXT NOT NULL,
    reason_code TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    server_received_at TEXT NOT NULL,
    correlation_id TEXT NOT NULL DEFAULT '',
    idempotency_key TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS enterprise_vehicle_state_snapshots (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    vehicle_id BIGINT NOT NULL REFERENCES enterprise_vehicles(id) ON DELETE CASCADE,
    current_state TEXT NOT NULL DEFAULT 'OUTSIDE',
    current_destination_id BIGINT REFERENCES enterprise_logistics_destinations(id) ON DELETE SET NULL,
    entered_at TEXT,
    last_event_id BIGINT REFERENCES enterprise_vehicle_access_events(id) ON DELETE SET NULL,
    last_gate_id BIGINT REFERENCES enterprise_doors(id) ON DELETE SET NULL,
    last_device_id BIGINT REFERENCES enterprise_devices(id) ON DELETE SET NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, event_id, vehicle_id)
);

CREATE TABLE IF NOT EXISTS enterprise_vehicle_import_jobs (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    import_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PREVIEW',
    summary_json TEXT NOT NULL DEFAULT '{}',
    errors_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, event_id, import_id)
);

CREATE INDEX IF NOT EXISTS idx_enterprise_vehicles_scope ON enterprise_vehicles(organization_id, normalized_plate, status);
CREATE INDEX IF NOT EXISTS idx_enterprise_vehicle_participation_scope ON enterprise_vehicle_event_participation(organization_id, event_id, vehicle_id, status);
CREATE INDEX IF NOT EXISTS idx_enterprise_vehicle_slots_scope ON enterprise_vehicle_access_slots(organization_id, event_id, vehicle_id, status, valid_from);
CREATE UNIQUE INDEX IF NOT EXISTS idx_enterprise_vehicle_events_idempotency ON enterprise_vehicle_access_events(organization_id, idempotency_key) WHERE idempotency_key <> '';
CREATE INDEX IF NOT EXISTS idx_enterprise_vehicle_state_scope ON enterprise_vehicle_state_snapshots(organization_id, event_id, current_state);
