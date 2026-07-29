# BITORA V4.9 Backup Restore Report

Backup includes V4.9 communication tables in event bundles.

Restore behavior:
- IDs are remapped for templates, versions, segments, campaigns, recipients, messages, deliveries, automations and provider events.
- Campaigns are restored as `RESTORED_REVIEW`.
- Automations are restored as `PAUSED`.
- Live Mode is set to 0 for restored campaigns.
- Provider external event ids and idempotency keys are rewritten where uniqueness could collide.

Verifier result:
- Event backup and restore with V4.9 data: PASSED.
- External effects after restore: 0.
