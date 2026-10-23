# BITORA V4.9 Webhook Security

Provider events are accepted only when:
- event scope is known;
- message belongs to the same organization and event;
- external event id is present;
- signature matches when a secret is configured;
- duplicate provider events are idempotent.

The service stores minimized payload metadata. It does not store raw provider secrets or full external payloads.
