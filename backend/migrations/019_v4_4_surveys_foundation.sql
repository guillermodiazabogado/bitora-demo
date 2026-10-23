CREATE TABLE IF NOT EXISTS survey_types (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT REFERENCES events(id) ON DELETE CASCADE,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, event_id, code)
);

CREATE TABLE IF NOT EXISTS surveys (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    survey_type_id BIGINT NOT NULL REFERENCES survey_types(id) ON DELETE RESTRICT,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'DRAFT',
    response_mode TEXT NOT NULL DEFAULT 'IDENTIFIED',
    access_policy TEXT NOT NULL DEFAULT 'EVENT_PARTICIPANTS',
    duplicate_policy TEXT NOT NULL DEFAULT 'ONE_PER_PARTICIPANT',
    current_version_id BIGINT,
    opens_at TEXT,
    closes_at TEXT,
    created_by TEXT NOT NULL DEFAULT '',
    archived_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, event_id, name)
);

CREATE TABLE IF NOT EXISTS survey_versions (
    id BIGSERIAL PRIMARY KEY,
    survey_id BIGINT NOT NULL REFERENCES surveys(id) ON DELETE CASCADE,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    instructions TEXT NOT NULL DEFAULT '',
    content_hash TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'DRAFT',
    published_at TEXT,
    published_by TEXT NOT NULL DEFAULT '',
    created_by TEXT NOT NULL DEFAULT '',
    idempotency_key TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(survey_id, version_number),
    UNIQUE(survey_id, content_hash)
);

CREATE TABLE IF NOT EXISTS survey_questions (
    id BIGSERIAL PRIMARY KEY,
    version_id BIGINT NOT NULL REFERENCES survey_versions(id) ON DELETE CASCADE,
    survey_id BIGINT NOT NULL REFERENCES surveys(id) ON DELETE CASCADE,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    question_key TEXT NOT NULL,
    prompt TEXT NOT NULL,
    question_type TEXT NOT NULL,
    required INTEGER NOT NULL DEFAULT 0,
    sort_order INTEGER NOT NULL DEFAULT 0,
    config_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    UNIQUE(version_id, question_key)
);

CREATE TABLE IF NOT EXISTS survey_question_options (
    id BIGSERIAL PRIMARY KEY,
    question_id BIGINT NOT NULL REFERENCES survey_questions(id) ON DELETE CASCADE,
    version_id BIGINT NOT NULL REFERENCES survey_versions(id) ON DELETE CASCADE,
    survey_id BIGINT NOT NULL REFERENCES surveys(id) ON DELETE CASCADE,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    option_key TEXT NOT NULL,
    label TEXT NOT NULL,
    value TEXT NOT NULL DEFAULT '',
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    UNIQUE(question_id, option_key)
);

CREATE TABLE IF NOT EXISTS survey_assignments (
    id BIGSERIAL PRIMARY KEY,
    survey_id BIGINT NOT NULL REFERENCES surveys(id) ON DELETE CASCADE,
    version_id BIGINT NOT NULL REFERENCES survey_versions(id) ON DELETE RESTRICT,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    activity_id BIGINT REFERENCES activities(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'DRAFT',
    access_mode TEXT NOT NULL DEFAULT 'EVENT_PARTICIPANTS',
    opens_at TEXT,
    closes_at TEXT,
    closed_at TEXT,
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS survey_access_tokens (
    id BIGSERIAL PRIMARY KEY,
    assignment_id BIGINT NOT NULL REFERENCES survey_assignments(id) ON DELETE CASCADE,
    survey_id BIGINT NOT NULL REFERENCES surveys(id) ON DELETE CASCADE,
    version_id BIGINT NOT NULL REFERENCES survey_versions(id) ON DELETE CASCADE,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    participant_id BIGINT REFERENCES people(id) ON DELETE SET NULL,
    anonymous_subject_hash TEXT NOT NULL,
    token_hash TEXT NOT NULL,
    token_hint TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    expires_at TEXT,
    used_at TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(token_hash)
);

CREATE TABLE IF NOT EXISTS survey_response_sessions (
    id BIGSERIAL PRIMARY KEY,
    assignment_id BIGINT NOT NULL REFERENCES survey_assignments(id) ON DELETE CASCADE,
    survey_id BIGINT NOT NULL REFERENCES surveys(id) ON DELETE CASCADE,
    version_id BIGINT NOT NULL REFERENCES survey_versions(id) ON DELETE RESTRICT,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    response_mode TEXT NOT NULL,
    participant_id BIGINT REFERENCES people(id) ON DELETE SET NULL,
    anonymous_subject_hash TEXT NOT NULL DEFAULT '',
    token_hash TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'IN_PROGRESS',
    started_at TEXT NOT NULL,
    submitted_at TEXT,
    idempotency_key TEXT NOT NULL,
    request_hash TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organization_id, idempotency_key)
);

CREATE TABLE IF NOT EXISTS survey_answers (
    id BIGSERIAL PRIMARY KEY,
    session_id BIGINT NOT NULL REFERENCES survey_response_sessions(id) ON DELETE CASCADE,
    assignment_id BIGINT NOT NULL REFERENCES survey_assignments(id) ON DELETE CASCADE,
    survey_id BIGINT NOT NULL REFERENCES surveys(id) ON DELETE CASCADE,
    version_id BIGINT NOT NULL REFERENCES survey_versions(id) ON DELETE CASCADE,
    question_id BIGINT NOT NULL REFERENCES survey_questions(id) ON DELETE CASCADE,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    answer_text TEXT,
    answer_number REAL,
    answer_bool INTEGER,
    created_at TEXT NOT NULL,
    UNIQUE(session_id, question_id)
);

CREATE TABLE IF NOT EXISTS survey_answer_options (
    id BIGSERIAL PRIMARY KEY,
    answer_id BIGINT NOT NULL REFERENCES survey_answers(id) ON DELETE CASCADE,
    session_id BIGINT NOT NULL REFERENCES survey_response_sessions(id) ON DELETE CASCADE,
    option_id BIGINT NOT NULL REFERENCES survey_question_options(id) ON DELETE CASCADE,
    question_id BIGINT NOT NULL REFERENCES survey_questions(id) ON DELETE CASCADE,
    survey_id BIGINT NOT NULL REFERENCES surveys(id) ON DELETE CASCADE,
    version_id BIGINT NOT NULL REFERENCES survey_versions(id) ON DELETE CASCADE,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    UNIQUE(answer_id, option_id)
);

CREATE INDEX IF NOT EXISTS idx_survey_types_scope ON survey_types(organization_id, event_id, status);
CREATE INDEX IF NOT EXISTS idx_surveys_scope ON surveys(organization_id, event_id, status);
CREATE INDEX IF NOT EXISTS idx_survey_versions_survey ON survey_versions(survey_id, status, version_number);
CREATE INDEX IF NOT EXISTS idx_survey_questions_version ON survey_questions(version_id, sort_order);
CREATE INDEX IF NOT EXISTS idx_survey_options_question ON survey_question_options(question_id, sort_order);
CREATE INDEX IF NOT EXISTS idx_survey_assignments_event ON survey_assignments(organization_id, event_id, status);
CREATE INDEX IF NOT EXISTS idx_survey_access_tokens_hash ON survey_access_tokens(token_hash, status);
CREATE INDEX IF NOT EXISTS idx_survey_sessions_event ON survey_response_sessions(organization_id, event_id, survey_id, status);
CREATE INDEX IF NOT EXISTS idx_survey_sessions_participant ON survey_response_sessions(assignment_id, participant_id, status);
CREATE INDEX IF NOT EXISTS idx_survey_answers_session ON survey_answers(session_id, question_id);
CREATE INDEX IF NOT EXISTS idx_survey_answer_options_session ON survey_answer_options(session_id, option_id);
