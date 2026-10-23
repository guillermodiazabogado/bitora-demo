# BITORA V4.7 Performance Report

Limits:

- History responses are capped at 200 entries.
- Autocomplete responses are capped at 25 entries.
- Short autocomplete queries return no rows.

Indexes reused:

- `idx_audit_logs_event_created`
- `idx_audit_logs_entity_created`

New index:

- `idx_duplicate_decisions_scope`

Future scaling can add normalized search columns or full-text indexes if the dataset grows beyond current operational needs.
