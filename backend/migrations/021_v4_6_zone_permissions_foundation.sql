CREATE TABLE IF NOT EXISTS event_zones (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    parent_zone_id BIGINT REFERENCES event_zones(id) ON DELETE SET NULL,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    capacity INTEGER,
    access_mode TEXT NOT NULL DEFAULT 'QR',
    valid_from TEXT,
    valid_until TEXT,
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, event_id, code)
);

CREATE TABLE IF NOT EXISTS zone_access_assignments (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    zone_id BIGINT NOT NULL REFERENCES event_zones(id) ON DELETE CASCADE,
    person_id BIGINT NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    accreditation_id BIGINT NOT NULL REFERENCES accreditations(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    valid_from TEXT,
    valid_until TEXT,
    source TEXT NOT NULL DEFAULT 'manual',
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, event_id, zone_id, person_id, accreditation_id)
);

CREATE TABLE IF NOT EXISTS zone_access_validations (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    zone_id BIGINT NOT NULL REFERENCES event_zones(id) ON DELETE CASCADE,
    person_id BIGINT REFERENCES people(id) ON DELETE SET NULL,
    accreditation_id BIGINT REFERENCES accreditations(id) ON DELETE SET NULL,
    decision TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    actor TEXT NOT NULL DEFAULT '',
    idempotency_key TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    UNIQUE(organization_id, idempotency_key)
);

CREATE TABLE IF NOT EXISTS zone_access_overrides (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    zone_id BIGINT NOT NULL REFERENCES event_zones(id) ON DELETE CASCADE,
    person_id BIGINT NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    accreditation_id BIGINT NOT NULL REFERENCES accreditations(id) ON DELETE CASCADE,
    override_type TEXT NOT NULL,
    reason TEXT NOT NULL,
    valid_until TEXT,
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_event_zones_scope ON event_zones(organization_id, event_id, status);
CREATE INDEX IF NOT EXISTS idx_zone_assignments_zone ON zone_access_assignments(organization_id, event_id, zone_id, status);
CREATE INDEX IF NOT EXISTS idx_zone_validations_event ON zone_access_validations(organization_id, event_id, zone_id, decision);
CREATE INDEX IF NOT EXISTS idx_zone_overrides_zone ON zone_access_overrides(organization_id, event_id, zone_id);
