ALTER TABLE networking_taxonomy_concepts ADD COLUMN description TEXT NOT NULL DEFAULT '';
ALTER TABLE networking_taxonomy_concepts ADD COLUMN parent_code TEXT NOT NULL DEFAULT '';
ALTER TABLE networking_taxonomy_concepts ADD COLUMN aliases_json TEXT NOT NULL DEFAULT '[]';

CREATE TABLE IF NOT EXISTS networking_event_taxonomy_concepts (
    id BIGSERIAL PRIMARY KEY,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    concept_code TEXT NOT NULL REFERENCES networking_taxonomy_concepts(code) ON DELETE CASCADE,
    enabled INTEGER NOT NULL DEFAULT 1,
    label_override TEXT NOT NULL DEFAULT '',
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(event_id, concept_code)
);

CREATE TABLE IF NOT EXISTS networking_semantic_classifications (
    id BIGSERIAL PRIMARY KEY,
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    owner_type TEXT NOT NULL,
    owner_id BIGINT NOT NULL,
    participation_id BIGINT REFERENCES networking_event_participations(id) ON DELETE CASCADE,
    concept_code TEXT NOT NULL REFERENCES networking_taxonomy_concepts(code) ON DELETE RESTRICT,
    semantic_role TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'USER',
    provenance TEXT NOT NULL DEFAULT '',
    visibility TEXT NOT NULL DEFAULT 'PUBLIC',
    free_text TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(event_id, owner_type, owner_id, concept_code, semantic_role, source)
);

CREATE INDEX IF NOT EXISTS idx_networking_event_taxonomy_event ON networking_event_taxonomy_concepts(event_id, enabled);
CREATE INDEX IF NOT EXISTS idx_networking_semantic_owner ON networking_semantic_classifications(event_id, owner_type, owner_id);
CREATE INDEX IF NOT EXISTS idx_networking_semantic_participation ON networking_semantic_classifications(participation_id);
