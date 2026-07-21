CREATE TABLE IF NOT EXISTS organizations (
    id BIGSERIAL PRIMARY KEY,
    public_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    legal_name TEXT NOT NULL DEFAULT '',
    trade_name TEXT NOT NULL DEFAULT '',
    tax_id TEXT NOT NULL DEFAULT '',
    contact_name TEXT NOT NULL DEFAULT '',
    contact_email TEXT NOT NULL DEFAULT '',
    contact_phone TEXT NOT NULL DEFAULT '',
    country TEXT NOT NULL DEFAULT 'AR',
    timezone TEXT NOT NULL DEFAULT 'America/Argentina/Buenos_Aires',
    locale TEXT NOT NULL DEFAULT 'es_AR',
    status TEXT NOT NULL DEFAULT 'active',
    plan TEXT NOT NULL DEFAULT 'standard',
    logo_data TEXT NOT NULL DEFAULT '',
    colors TEXT NOT NULL DEFAULT '{}',
    website TEXT NOT NULL DEFAULT '',
    general_email TEXT NOT NULL DEFAULT '',
    general_whatsapp TEXT NOT NULL DEFAULT '',
    signature TEXT NOT NULL DEFAULT '',
    terms_url TEXT NOT NULL DEFAULT '',
    privacy_url TEXT NOT NULL DEFAULT '',
    safe_mode_email INTEGER NOT NULL DEFAULT 1,
    safe_mode_whatsapp INTEGER NOT NULL DEFAULT 1,
    force_email_recipient TEXT NOT NULL DEFAULT '',
    force_whatsapp_recipient TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted_at TEXT
);

CREATE TABLE IF NOT EXISTS organization_users (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    invited_at TEXT,
    accepted_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, user_id)
);

ALTER TABLE events
    ADD COLUMN IF NOT EXISTS organization_id BIGINT REFERENCES organizations(id) ON DELETE RESTRICT;

CREATE TABLE IF NOT EXISTS organization_integrations (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    integration_type TEXT NOT NULL,
    name TEXT NOT NULL,
    mode TEXT NOT NULL DEFAULT 'platform_managed',
    status TEXT NOT NULL DEFAULT 'draft',
    configuration_encrypted TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    last_tested_at TEXT,
    last_test_status TEXT NOT NULL DEFAULT '',
    last_error_message_sanitized TEXT NOT NULL DEFAULT '',
    created_by TEXT NOT NULL DEFAULT '',
    updated_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    disabled_at TEXT
);

CREATE TABLE IF NOT EXISTS event_integrations (
    id BIGSERIAL PRIMARY KEY,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    channel TEXT NOT NULL,
    organization_integration_id BIGINT NOT NULL REFERENCES organization_integrations(id) ON DELETE RESTRICT,
    is_default INTEGER NOT NULL DEFAULT 0,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(event_id, channel)
);

ALTER TABLE communication_queue
    ADD COLUMN IF NOT EXISTS organization_id BIGINT REFERENCES organizations(id) ON DELETE SET NULL;

ALTER TABLE communication_queue
    ADD COLUMN IF NOT EXISTS integration_id BIGINT REFERENCES organization_integrations(id) ON DELETE SET NULL;

ALTER TABLE jobs
    ADD COLUMN IF NOT EXISTS organization_id BIGINT REFERENCES organizations(id) ON DELETE SET NULL;

ALTER TABLE jobs
    ADD COLUMN IF NOT EXISTS integration_id BIGINT REFERENCES organization_integrations(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_organizations_status ON organizations(status);
CREATE INDEX IF NOT EXISTS idx_organization_users_user ON organization_users(user_id, organization_id, status);
CREATE INDEX IF NOT EXISTS idx_events_organization_status ON events(organization_id, status);
CREATE INDEX IF NOT EXISTS idx_org_integrations_org_type ON organization_integrations(organization_id, integration_type, status);
CREATE INDEX IF NOT EXISTS idx_event_integrations_event_channel ON event_integrations(event_id, channel, enabled);
CREATE INDEX IF NOT EXISTS idx_communication_queue_org_channel ON communication_queue(organization_id, channel, status);

INSERT INTO organizations (public_id, name, legal_name, trade_name, status, plan, created_at, updated_at)
SELECT 'org_bitora_principal', 'BITORA Principal', 'BITORA Principal', 'BITORA', 'active', 'standard', CURRENT_TIMESTAMP::TEXT, CURRENT_TIMESTAMP::TEXT
WHERE NOT EXISTS (SELECT 1 FROM organizations WHERE public_id = 'org_bitora_principal');

UPDATE events
SET organization_id = (SELECT id FROM organizations WHERE public_id = 'org_bitora_principal')
WHERE organization_id IS NULL;

INSERT INTO organization_users (organization_id, user_id, role, status, accepted_at, created_at, updated_at)
SELECT
    (SELECT id FROM organizations WHERE public_id = 'org_bitora_principal'),
    u.id,
    CASE
        WHEN u.role = 'Super Admin' THEN 'organization_owner'
        WHEN u.role = 'Productor' THEN 'producer_admin'
        WHEN u.role = 'Soporte tecnico' THEN 'technical_support'
        ELSE 'event_operator'
    END,
    'active',
    CURRENT_TIMESTAMP::TEXT,
    CURRENT_TIMESTAMP::TEXT,
    CURRENT_TIMESTAMP::TEXT
FROM users u
WHERE NOT EXISTS (
    SELECT 1
    FROM organization_users ou
    WHERE ou.organization_id = (SELECT id FROM organizations WHERE public_id = 'org_bitora_principal')
      AND ou.user_id = u.id
);
