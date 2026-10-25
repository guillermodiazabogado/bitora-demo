CREATE TABLE IF NOT EXISTS enterprise_companies (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    company_type TEXT NOT NULL DEFAULT 'EXHIBITOR',
    tax_id TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, name)
);

CREATE TABLE IF NOT EXISTS enterprise_company_event_participation (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    company_id BIGINT NOT NULL REFERENCES enterprise_companies(id) ON DELETE CASCADE,
    entity_id BIGINT REFERENCES enterprise_entities(id) ON DELETE SET NULL,
    role_type TEXT NOT NULL DEFAULT 'EXHIBITOR',
    status TEXT NOT NULL DEFAULT 'INVITED',
    approval_mode TEXT NOT NULL DEFAULT 'AUTO_APPROVE',
    valid_from TEXT NOT NULL DEFAULT '',
    valid_until TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, event_id, company_id)
);

CREATE TABLE IF NOT EXISTS enterprise_delegations (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    company_id BIGINT REFERENCES enterprise_companies(id) ON DELETE CASCADE,
    participation_id BIGINT REFERENCES enterprise_company_event_participation(id) ON DELETE CASCADE,
    entity_id BIGINT REFERENCES enterprise_entities(id) ON DELETE SET NULL,
    name TEXT NOT NULL,
    delegation_type TEXT NOT NULL DEFAULT 'GENERAL',
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, event_id, company_id, name)
);

CREATE TABLE IF NOT EXISTS enterprise_delegation_members (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    company_id BIGINT NOT NULL REFERENCES enterprise_companies(id) ON DELETE CASCADE,
    delegation_id BIGINT REFERENCES enterprise_delegations(id) ON DELETE SET NULL,
    person_id BIGINT REFERENCES people(id) ON DELETE SET NULL,
    accreditation_id BIGINT REFERENCES accreditations(id) ON DELETE SET NULL,
    entity_id BIGINT REFERENCES enterprise_entities(id) ON DELETE SET NULL,
    member_role TEXT NOT NULL DEFAULT 'GUEST',
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    source TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    joined_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, event_id, company_id, delegation_id, person_id, member_role)
);

CREATE TABLE IF NOT EXISTS enterprise_company_users (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    company_id BIGINT NOT NULL REFERENCES enterprise_companies(id) ON DELETE CASCADE,
    user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    email TEXT NOT NULL DEFAULT '',
    role TEXT NOT NULL DEFAULT 'VIEWER',
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    permissions_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, event_id, company_id, email)
);

CREATE TABLE IF NOT EXISTS enterprise_company_quotas (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    company_id BIGINT NOT NULL REFERENCES enterprise_companies(id) ON DELETE CASCADE,
    delegation_id BIGINT REFERENCES enterprise_delegations(id) ON DELETE CASCADE,
    quota_type TEXT NOT NULL DEFAULT 'TOTAL',
    allocated INTEGER NOT NULL DEFAULT 0,
    reserved INTEGER NOT NULL DEFAULT 0,
    consumed INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, event_id, company_id, delegation_id, quota_type)
);

CREATE TABLE IF NOT EXISTS enterprise_invitations (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    company_id BIGINT NOT NULL REFERENCES enterprise_companies(id) ON DELETE CASCADE,
    delegation_id BIGINT REFERENCES enterprise_delegations(id) ON DELETE SET NULL,
    invitation_token_hash TEXT NOT NULL,
    token_hint TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    quota_type TEXT NOT NULL DEFAULT 'TOTAL',
    status TEXT NOT NULL DEFAULT 'PENDING',
    expires_at TEXT NOT NULL DEFAULT '',
    revoked_at TEXT,
    completed_at TEXT,
    person_id BIGINT REFERENCES people(id) ON DELETE SET NULL,
    accreditation_id BIGINT REFERENCES accreditations(id) ON DELETE SET NULL,
    idempotency_key TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, invitation_token_hash)
);

CREATE TABLE IF NOT EXISTS enterprise_approval_requests (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    company_id BIGINT NOT NULL REFERENCES enterprise_companies(id) ON DELETE CASCADE,
    delegation_id BIGINT REFERENCES enterprise_delegations(id) ON DELETE SET NULL,
    person_id BIGINT REFERENCES people(id) ON DELETE SET NULL,
    accreditation_id BIGINT REFERENCES accreditations(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'SUBMITTED',
    reviewer TEXT NOT NULL DEFAULT '',
    reason TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT '',
    submitted_at TEXT NOT NULL,
    reviewed_at TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS enterprise_import_jobs (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    company_id BIGINT NOT NULL REFERENCES enterprise_companies(id) ON DELETE CASCADE,
    delegation_id BIGINT REFERENCES enterprise_delegations(id) ON DELETE SET NULL,
    import_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PREVIEW',
    file_name TEXT NOT NULL DEFAULT '',
    summary_json TEXT NOT NULL DEFAULT '{}',
    errors_json TEXT NOT NULL DEFAULT '[]',
    idempotency_key TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, event_id, company_id, import_id)
);

CREATE INDEX IF NOT EXISTS idx_enterprise_companies_scope ON enterprise_companies(organization_id, status, company_type);
CREATE INDEX IF NOT EXISTS idx_enterprise_company_participation_scope ON enterprise_company_event_participation(organization_id, event_id, company_id, status);
CREATE INDEX IF NOT EXISTS idx_enterprise_delegations_scope ON enterprise_delegations(organization_id, event_id, company_id, status);
CREATE INDEX IF NOT EXISTS idx_enterprise_delegation_members_scope ON enterprise_delegation_members(organization_id, event_id, company_id, delegation_id, status);
CREATE INDEX IF NOT EXISTS idx_enterprise_company_users_scope ON enterprise_company_users(organization_id, event_id, company_id, role, status);
CREATE INDEX IF NOT EXISTS idx_enterprise_company_quotas_scope ON enterprise_company_quotas(organization_id, event_id, company_id, delegation_id, quota_type);
CREATE INDEX IF NOT EXISTS idx_enterprise_invitations_scope ON enterprise_invitations(organization_id, event_id, company_id, status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_enterprise_invitations_idempotency ON enterprise_invitations(organization_id, idempotency_key) WHERE idempotency_key <> '';
CREATE INDEX IF NOT EXISTS idx_enterprise_approval_requests_scope ON enterprise_approval_requests(organization_id, event_id, company_id, status);
CREATE INDEX IF NOT EXISTS idx_enterprise_import_jobs_scope ON enterprise_import_jobs(organization_id, event_id, company_id, status);
