# BITORA V4.9 Retry And Idempotency

Campaign recipient idempotency key:

`campaign:{campaign_id}:person:{person_id}:channel:{channel}:version:{template_version_id}`

Guarantees:
- A recipient is not sent twice for the same campaign/channel/version.
- A repeated execution returns skipped recipients instead of duplicating messages.
- Provider events are unique by provider and external event id.
- Restore rewrites idempotency keys where needed to avoid collisions.
