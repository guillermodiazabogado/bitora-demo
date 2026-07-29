# BITORA V4.9 Security Report

Controls implemented:
- Feature flags off by default.
- Live Mode off by default.
- Event-scoped backend checks.
- RBAC enforced in HTTP routes.
- Safe variable catalog for templates.
- Escaped preview rendering.
- Consent and suppression filtering.
- Webhook signature validation for contract events.
- Idempotency for campaign messages and provider events.
- Restore moves campaigns/automations to safe states.

Secrets exposed: 0
Real communications sent by verifier: 0
