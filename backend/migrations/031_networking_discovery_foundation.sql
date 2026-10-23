ALTER TABLE networking_intents ADD COLUMN discovery_completed INTEGER NOT NULL DEFAULT 0;
ALTER TABLE networking_intents ADD COLUMN discovery_diversity INTEGER NOT NULL DEFAULT 1;
ALTER TABLE networking_intents ADD COLUMN desired_functions_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE networking_intents ADD COLUMN desired_company_types_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE networking_intents ADD COLUMN discovery_objectives_json TEXT NOT NULL DEFAULT '[]';

CREATE TABLE IF NOT EXISTS networking_event_vocabulary_candidates (
    id BIGSERIAL PRIMARY KEY,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    dimension TEXT NOT NULL,
    raw_value TEXT NOT NULL,
    normalized_key TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'CANDIDATE',
    concept_code TEXT REFERENCES networking_taxonomy_concepts(code) ON DELETE SET NULL,
    source TEXT NOT NULL DEFAULT 'USER',
    provenance TEXT NOT NULL DEFAULT '',
    usage_count INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(event_id, dimension, normalized_key)
);

CREATE INDEX IF NOT EXISTS idx_networking_vocabulary_event_dimension ON networking_event_vocabulary_candidates(event_id, dimension, status);
