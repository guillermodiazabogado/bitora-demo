CREATE TABLE IF NOT EXISTS certificate_types (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    event_id BIGINT REFERENCES events(id) ON DELETE CASCADE,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    kind TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    requires_eligibility INTEGER NOT NULL DEFAULT 1,
    requires_closure INTEGER NOT NULL DEFAULT 1,
    allow_override INTEGER NOT NULL DEFAULT 1,
    allow_batch INTEGER NOT NULL DEFAULT 1,
    allow_reissue INTEGER NOT NULL DEFAULT 1,
    requires_numbering INTEGER NOT NULL DEFAULT 1,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, event_id, code)
);

CREATE TABLE IF NOT EXISTS certificate_templates (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    event_id BIGINT REFERENCES events(id) ON DELETE CASCADE,
    certificate_type_id BIGINT NOT NULL REFERENCES certificate_types(id) ON DELETE RESTRICT,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'DRAFT',
    current_version_id BIGINT,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, event_id, name)
);

CREATE TABLE IF NOT EXISTS certificate_template_versions (
    id BIGSERIAL PRIMARY KEY,
    template_id BIGINT NOT NULL REFERENCES certificate_templates(id) ON DELETE CASCADE,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    event_id BIGINT REFERENCES events(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    content_schema TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    renderer_version TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'DRAFT',
    published_at TEXT,
    published_by TEXT,
    idempotency_key TEXT NOT NULL DEFAULT '',
    request_hash TEXT NOT NULL DEFAULT '',
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(template_id, version_number),
    UNIQUE(template_id, content_hash)
);

CREATE TABLE IF NOT EXISTS certificate_number_sequences (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    event_id BIGINT REFERENCES events(id) ON DELETE CASCADE,
    scope_key TEXT NOT NULL,
    next_value BIGINT NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, scope_key)
);

CREATE TABLE IF NOT EXISTS certificate_batches (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    certificate_type_id BIGINT NOT NULL REFERENCES certificate_types(id) ON DELETE RESTRICT,
    template_version_id BIGINT NOT NULL REFERENCES certificate_template_versions(id) ON DELETE RESTRICT,
    status TEXT NOT NULL DEFAULT 'DRAFT',
    total_count INTEGER NOT NULL DEFAULT 0,
    success_count INTEGER NOT NULL DEFAULT 0,
    failure_count INTEGER NOT NULL DEFAULT 0,
    idempotency_key TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    correlation_id TEXT NOT NULL DEFAULT '',
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, idempotency_key)
);

CREATE TABLE IF NOT EXISTS certificate_issuances (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    participant_id BIGINT NOT NULL REFERENCES people(id) ON DELETE RESTRICT,
    certificate_type_id BIGINT NOT NULL REFERENCES certificate_types(id) ON DELETE RESTRICT,
    template_version_id BIGINT NOT NULL REFERENCES certificate_template_versions(id) ON DELETE RESTRICT,
    eligibility_decision_id BIGINT REFERENCES attendance_eligibility_decisions(id) ON DELETE RESTRICT,
    attendance_closure_id BIGINT REFERENCES attendance_closures(id) ON DELETE RESTRICT,
    evaluation_id BIGINT REFERENCES attendance_evaluations(id) ON DELETE RESTRICT,
    batch_id BIGINT REFERENCES certificate_batches(id) ON DELETE SET NULL,
    certificate_number TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING',
    issued_at TEXT,
    issued_by TEXT NOT NULL DEFAULT '',
    idempotency_key TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    correlation_id TEXT NOT NULL DEFAULT '',
    supersedes_issuance_id BIGINT REFERENCES certificate_issuances(id) ON DELETE SET NULL,
    logical_hash TEXT NOT NULL DEFAULT '',
    failure_code TEXT NOT NULL DEFAULT '',
    failure_message TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, event_id, certificate_number),
    UNIQUE(organization_id, idempotency_key)
);

CREATE TABLE IF NOT EXISTS certificate_documents (
    id BIGSERIAL PRIMARY KEY,
    issuance_id BIGINT NOT NULL REFERENCES certificate_issuances(id) ON DELETE RESTRICT,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    storage_key TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    file_size BIGINT NOT NULL DEFAULT 0,
    sha256_hash TEXT NOT NULL,
    logical_hash TEXT NOT NULL DEFAULT '',
    renderer_version TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(issuance_id)
);

CREATE TABLE IF NOT EXISTS certificate_verification_tokens (
    id BIGSERIAL PRIMARY KEY,
    issuance_id BIGINT NOT NULL REFERENCES certificate_issuances(id) ON DELETE RESTRICT,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL,
    token_hint TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    created_at TEXT NOT NULL,
    UNIQUE(token_hash),
    UNIQUE(issuance_id)
);

CREATE TABLE IF NOT EXISTS certificate_revocations (
    id BIGSERIAL PRIMARY KEY,
    issuance_id BIGINT NOT NULL REFERENCES certificate_issuances(id) ON DELETE RESTRICT,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    reason TEXT NOT NULL,
    revoked_at TEXT NOT NULL,
    revoked_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(issuance_id)
);

CREATE TABLE IF NOT EXISTS certificate_reissuances (
    id BIGSERIAL PRIMARY KEY,
    previous_issuance_id BIGINT NOT NULL REFERENCES certificate_issuances(id) ON DELETE RESTRICT,
    new_issuance_id BIGINT NOT NULL REFERENCES certificate_issuances(id) ON DELETE RESTRICT,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    reason TEXT NOT NULL DEFAULT '',
    reissued_by TEXT NOT NULL,
    reissued_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(previous_issuance_id, new_issuance_id)
);

CREATE INDEX IF NOT EXISTS idx_certificate_types_scope ON certificate_types(organization_id, event_id, status);
CREATE INDEX IF NOT EXISTS idx_certificate_templates_scope ON certificate_templates(organization_id, event_id, status);
CREATE INDEX IF NOT EXISTS idx_certificate_template_versions_template ON certificate_template_versions(template_id, status, version_number);
CREATE INDEX IF NOT EXISTS idx_certificate_batches_event_status ON certificate_batches(organization_id, event_id, status);
CREATE INDEX IF NOT EXISTS idx_certificate_issuances_event_participant ON certificate_issuances(organization_id, event_id, participant_id, status);
CREATE INDEX IF NOT EXISTS idx_certificate_issuances_batch ON certificate_issuances(batch_id, status);
CREATE INDEX IF NOT EXISTS idx_certificate_documents_issuance ON certificate_documents(issuance_id);
CREATE INDEX IF NOT EXISTS idx_certificate_verification_token_hash ON certificate_verification_tokens(token_hash, status);
CREATE INDEX IF NOT EXISTS idx_certificate_revocations_issuance ON certificate_revocations(issuance_id);
