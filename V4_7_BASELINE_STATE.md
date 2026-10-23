# BITORA V4.7 Baseline State

Branch: `feature/v4.7-history-autocomplete-foundation`

V4.7 starts after V4.5 Speakers and V4.6 Zone Permissions were merged into `develop/v4`.

Scope:
- Human-readable history over existing audit logs.
- Tenant-aware autocomplete for participants, speakers and controlled value lists.
- Duplicate candidate detection and decision recording.
- No replacement of the canonical audit log.
- Feature flag disabled by default: `BITORA_HISTORY_AUTOCOMPLETE_V4_ENABLED=false`.

Runtime changes are limited to the V4.7 domain service, endpoints, one metadata table, backup/restore mapping, and a minimal admin page.
