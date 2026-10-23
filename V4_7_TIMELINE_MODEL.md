# BITORA V4.7 Timeline Model

Timeline items contain:

- `id`
- `created_at`
- `actor`
- `action`
- `entity_type`
- `entity_id`
- `summary`

Sensitive payloads are omitted by default. The model is intentionally append-only because the canonical source is `audit_logs`.

Supported entity types:

- `event`
- `person`
- `accreditation`
- `activity`
- `attendance`
- `certificate`
- `survey`
- `speaker`
- `zone`
