CREATE TABLE IF NOT EXISTS networking_organizations (
    id BIGSERIAL PRIMARY KEY,
    canonical_key TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    website TEXT NOT NULL DEFAULT '',
    logo_url TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    visibility TEXT NOT NULL DEFAULT 'VISIBLE',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS networking_event_participations (
    id BIGSERIAL PRIMARY KEY,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    person_id BIGINT NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    accreditation_id BIGINT REFERENCES accreditations(id) ON DELETE SET NULL,
    organization_id BIGINT REFERENCES networking_organizations(id) ON DELETE SET NULL,
    source_system TEXT NOT NULL DEFAULT 'BITORA',
    source_external_id TEXT NOT NULL DEFAULT '',
    source_fingerprint TEXT NOT NULL DEFAULT '',
    participation_state TEXT NOT NULL DEFAULT 'PASSIVE',
    public_profile_id TEXT NOT NULL UNIQUE,
    owner_token_hash TEXT NOT NULL DEFAULT '',
    owner_token_hint TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL DEFAULT '',
    normalized_function TEXT NOT NULL DEFAULT 'OTHER',
    normalized_seniority TEXT NOT NULL DEFAULT 'PROFESSIONAL',
    profile_photo_url TEXT NOT NULL DEFAULT '',
    organization_logo_url TEXT NOT NULL DEFAULT '',
    source_payload_json TEXT NOT NULL DEFAULT '{}',
    imported_at TEXT NOT NULL DEFAULT '',
    onboarded_at TEXT,
    revoked_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(event_id, person_id),
    UNIQUE(event_id, source_system, source_external_id)
);

CREATE TABLE IF NOT EXISTS networking_intents (
    id BIGSERIAL PRIMARY KEY,
    participation_id BIGINT NOT NULL UNIQUE REFERENCES networking_event_participations(id) ON DELETE CASCADE,
    modes_json TEXT NOT NULL DEFAULT '[]',
    direction TEXT NOT NULL DEFAULT 'BOTH',
    contact_openness TEXT NOT NULL DEFAULT 'CONNECT_FIRST',
    discoverable INTEGER NOT NULL DEFAULT 0,
    profile_visible INTEGER NOT NULL DEFAULT 0,
    channels_visible_default TEXT NOT NULL DEFAULT 'CONTACTS',
    representative_visible INTEGER NOT NULL DEFAULT 1,
    bio TEXT NOT NULL DEFAULT '',
    offers_text TEXT NOT NULL DEFAULT '',
    seeks_text TEXT NOT NULL DEFAULT '',
    interests_text TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS networking_contact_channels (
    id BIGSERIAL PRIMARY KEY,
    participation_id BIGINT NOT NULL REFERENCES networking_event_participations(id) ON DELETE CASCADE,
    channel_type TEXT NOT NULL,
    label TEXT NOT NULL DEFAULT '',
    value TEXT NOT NULL,
    url TEXT NOT NULL DEFAULT '',
    visibility TEXT NOT NULL DEFAULT 'CONTACTS',
    source TEXT NOT NULL DEFAULT 'import',
    updated_at TEXT NOT NULL,
    UNIQUE(participation_id, channel_type, value)
);

CREATE TABLE IF NOT EXISTS networking_taxonomy_concepts (
    id BIGSERIAL PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    concept_type TEXT NOT NULL,
    label TEXT NOT NULL,
    taxonomy_version TEXT NOT NULL DEFAULT 'v1',
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS networking_classifications (
    id BIGSERIAL PRIMARY KEY,
    participation_id BIGINT NOT NULL REFERENCES networking_event_participations(id) ON DELETE CASCADE,
    concept_code TEXT NOT NULL REFERENCES networking_taxonomy_concepts(code) ON DELETE RESTRICT,
    source TEXT NOT NULL DEFAULT 'declared',
    provenance TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    UNIQUE(participation_id, concept_code, source)
);

CREATE TABLE IF NOT EXISTS networking_contacts (
    id BIGSERIAL PRIMARY KEY,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    owner_participation_id BIGINT NOT NULL REFERENCES networking_event_participations(id) ON DELETE CASCADE,
    target_participation_id BIGINT NOT NULL REFERENCES networking_event_participations(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(owner_participation_id, target_participation_id)
);

CREATE TABLE IF NOT EXISTS networking_interaction_events (
    id BIGSERIAL PRIMARY KEY,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    actor_participation_id BIGINT REFERENCES networking_event_participations(id) ON DELETE SET NULL,
    target_participation_id BIGINT REFERENCES networking_event_participations(id) ON DELETE SET NULL,
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_networking_participations_event_state ON networking_event_participations(event_id, participation_state);
CREATE INDEX IF NOT EXISTS idx_networking_participations_public ON networking_event_participations(public_profile_id);
CREATE INDEX IF NOT EXISTS idx_networking_channels_participation ON networking_contact_channels(participation_id);
CREATE INDEX IF NOT EXISTS idx_networking_contacts_owner ON networking_contacts(owner_participation_id, status);
