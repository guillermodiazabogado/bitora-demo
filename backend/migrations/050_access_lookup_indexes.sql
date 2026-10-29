-- Hot-path lookup indexes for QR access validation.
--
-- The legacy token resolver normalizes with lower(token), which cannot use the
-- plain UNIQUE(token) index. The enterprise resolver filters by tenant/event,
-- credential type and legacy hash; including the hash avoids scanning every
-- credential in a large event. These indexes do not change authorization,
-- transaction isolation, anti-passback or idempotency semantics.

CREATE INDEX IF NOT EXISTS idx_accreditations_token_normalized
    ON accreditations(lower(token));

CREATE INDEX IF NOT EXISTS idx_enterprise_credentials_token_lookup
    ON enterprise_credentials(
        organization_id,
        event_id,
        credential_type,
        legacy_token_hash
    );
