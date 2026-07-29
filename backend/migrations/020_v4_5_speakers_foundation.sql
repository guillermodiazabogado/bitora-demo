CREATE TABLE IF NOT EXISTS speaker_profiles (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    public_id TEXT NOT NULL,
    display_name TEXT NOT NULL,
    first_name TEXT NOT NULL DEFAULT '',
    last_name TEXT NOT NULL DEFAULT '',
    professional_name TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL DEFAULT '',
    position TEXT NOT NULL DEFAULT '',
    company TEXT NOT NULL DEFAULT '',
    short_bio TEXT NOT NULL DEFAULT '',
    long_bio TEXT NOT NULL DEFAULT '',
    photo_storage_key TEXT NOT NULL DEFAULT '',
    country TEXT NOT NULL DEFAULT '',
    city TEXT NOT NULL DEFAULT '',
    links_json TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'DRAFT',
    visibility TEXT NOT NULL DEFAULT 'EVENT',
    current_version_id BIGINT,
    created_by TEXT NOT NULL DEFAULT '',
    archived_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, public_id)
);

CREATE TABLE IF NOT EXISTS speaker_private_details (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    speaker_profile_id BIGINT NOT NULL REFERENCES speaker_profiles(id) ON DELETE CASCADE,
    email TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    document_id TEXT NOT NULL DEFAULT '',
    internal_notes TEXT NOT NULL DEFAULT '',
    technical_needs TEXT NOT NULL DEFAULT '',
    logistics_notes TEXT NOT NULL DEFAULT '',
    documentation_status TEXT NOT NULL DEFAULT 'PENDING',
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, speaker_profile_id)
);

CREATE TABLE IF NOT EXISTS speaker_profile_versions (
    id BIGSERIAL PRIMARY KEY,
    speaker_profile_id BIGINT NOT NULL REFERENCES speaker_profiles(id) ON DELETE CASCADE,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    snapshot_json TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PUBLISHED',
    published_at TEXT,
    published_by TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    UNIQUE(speaker_profile_id, version_number)
);

CREATE TABLE IF NOT EXISTS speaker_event_assignments (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    speaker_profile_id BIGINT NOT NULL REFERENCES speaker_profiles(id) ON DELETE CASCADE,
    roles_json TEXT NOT NULL DEFAULT '["SPEAKER"]',
    status TEXT NOT NULL DEFAULT 'INVITED',
    visibility TEXT NOT NULL DEFAULT 'PUBLIC',
    internal_notes TEXT NOT NULL DEFAULT '',
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, event_id, speaker_profile_id)
);

CREATE TABLE IF NOT EXISTS speaker_activity_assignments (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    activity_id BIGINT NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
    speaker_profile_id BIGINT NOT NULL REFERENCES speaker_profiles(id) ON DELETE CASCADE,
    role TEXT NOT NULL DEFAULT 'SPEAKER',
    status TEXT NOT NULL DEFAULT 'INVITED',
    visibility TEXT NOT NULL DEFAULT 'PUBLIC',
    sort_order INTEGER NOT NULL DEFAULT 0,
    starts_at TEXT,
    ends_at TEXT,
    internal_notes TEXT NOT NULL DEFAULT '',
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, event_id, activity_id, speaker_profile_id, role)
);

CREATE TABLE IF NOT EXISTS speaker_documents (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    speaker_profile_id BIGINT NOT NULL REFERENCES speaker_profiles(id) ON DELETE CASCADE,
    document_type TEXT NOT NULL,
    filename TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    storage_key TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    size_bytes BIGINT NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'PENDING',
    visibility TEXT NOT NULL DEFAULT 'PRIVATE',
    uploaded_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS speaker_access_tokens (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    speaker_profile_id BIGINT NOT NULL REFERENCES speaker_profiles(id) ON DELETE CASCADE,
    scope TEXT NOT NULL DEFAULT 'PROFILE_SELF_SERVICE',
    token_hash TEXT NOT NULL UNIQUE,
    token_hint TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    expires_at TEXT,
    used_at TEXT,
    revoked_at TEXT,
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_speaker_profiles_scope ON speaker_profiles(organization_id, status, visibility);
CREATE INDEX IF NOT EXISTS idx_speaker_private_profile ON speaker_private_details(organization_id, speaker_profile_id);
CREATE INDEX IF NOT EXISTS idx_speaker_versions_profile ON speaker_profile_versions(speaker_profile_id, version_number);
CREATE INDEX IF NOT EXISTS idx_speaker_event_assignments_event ON speaker_event_assignments(organization_id, event_id, status);
CREATE INDEX IF NOT EXISTS idx_speaker_activity_assignments_event ON speaker_activity_assignments(organization_id, event_id, activity_id, status);
CREATE INDEX IF NOT EXISTS idx_speaker_documents_event ON speaker_documents(organization_id, event_id, speaker_profile_id);
CREATE INDEX IF NOT EXISTS idx_speaker_access_tokens_hash ON speaker_access_tokens(token_hash, status);
