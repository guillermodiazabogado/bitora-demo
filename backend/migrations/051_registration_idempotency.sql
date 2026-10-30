-- Durable, event-scoped idempotency for public and reception registrations.
-- The claim and the registration domain changes are committed atomically.

CREATE TABLE IF NOT EXISTS registration_idempotency (
    event_id BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    key_hash TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    accreditation_id BIGINT REFERENCES accreditations(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'PENDING',
    response_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    completed_at TEXT,
    PRIMARY KEY(event_id, key_hash),
    CHECK (length(key_hash) = 64),
    CHECK (length(request_hash) = 64),
    CHECK (status IN ('PENDING', 'COMPLETED')),
    CHECK (
        (status = 'PENDING' AND accreditation_id IS NULL AND completed_at IS NULL)
        OR
        (status = 'COMPLETED' AND accreditation_id IS NOT NULL AND completed_at IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_registration_idempotency_accreditation
    ON registration_idempotency(accreditation_id);
