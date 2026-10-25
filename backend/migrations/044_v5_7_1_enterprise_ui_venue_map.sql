CREATE TABLE IF NOT EXISTS enterprise_venues (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    address TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, code)
);

CREATE TABLE IF NOT EXISTS enterprise_venue_maps (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    venue_id BIGINT NOT NULL REFERENCES enterprise_venues(id) ON DELETE CASCADE,
    version TEXT NOT NULL,
    map_type TEXT NOT NULL DEFAULT 'SVG',
    asset_ref TEXT NOT NULL DEFAULT '',
    svg_text TEXT NOT NULL DEFAULT '',
    checksum TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, venue_id, version)
);

CREATE TABLE IF NOT EXISTS enterprise_venue_map_elements (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    venue_id BIGINT NOT NULL REFERENCES enterprise_venues(id) ON DELETE CASCADE,
    venue_map_id BIGINT NOT NULL REFERENCES enterprise_venue_maps(id) ON DELETE CASCADE,
    element_key TEXT NOT NULL,
    element_type TEXT NOT NULL,
    reference_table TEXT NOT NULL DEFAULT '',
    reference_id BIGINT,
    label TEXT NOT NULL DEFAULT '',
    geometry_json TEXT NOT NULL DEFAULT '{}',
    layer TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, venue_map_id, element_key)
);

CREATE TABLE IF NOT EXISTS enterprise_event_map_configurations (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    venue_id BIGINT NOT NULL REFERENCES enterprise_venues(id) ON DELETE CASCADE,
    venue_map_id BIGINT NOT NULL REFERENCES enterprise_venue_maps(id) ON DELETE CASCADE,
    mode TEXT NOT NULL DEFAULT 'AUTO',
    active_layers_json TEXT NOT NULL DEFAULT '[]',
    overrides_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, event_id)
);

CREATE INDEX IF NOT EXISTS idx_enterprise_venues_scope ON enterprise_venues(organization_id, status);
CREATE INDEX IF NOT EXISTS idx_enterprise_venue_maps_scope ON enterprise_venue_maps(organization_id, venue_id, status);
CREATE INDEX IF NOT EXISTS idx_enterprise_venue_elements_scope ON enterprise_venue_map_elements(organization_id, venue_map_id, element_type, layer, status);
CREATE INDEX IF NOT EXISTS idx_enterprise_event_map_scope ON enterprise_event_map_configurations(organization_id, event_id, status);
