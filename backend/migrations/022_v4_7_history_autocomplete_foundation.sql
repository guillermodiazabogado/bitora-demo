CREATE TABLE IF NOT EXISTS duplicate_resolution_decisions (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_id BIGINT REFERENCES events(id) ON DELETE SET NULL,
    candidate_person_id BIGINT NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    decision TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    actor TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_duplicate_decisions_scope ON duplicate_resolution_decisions(organization_id, event_id, candidate_person_id);
CREATE INDEX IF NOT EXISTS idx_duplicate_decisions_created ON duplicate_resolution_decisions(created_at);
