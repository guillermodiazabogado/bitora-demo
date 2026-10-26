# BITORA Enterprise API contracts

All administrative routes require an authenticated session, event assignment,
the listed RBAC action and CSRF validation. Device offline routes use
`Authorization: Bearer <device-secret>` and never accept the secret from the
response body. Organization and event identifiers are checked together.

## Event Edge and devices

- `POST /api/events/{event_id}/edge/readiness` — `edge.read`.
- `POST /api/events/{event_id}/edge/profiles` — `edge.provision`.
- `POST /api/events/{event_id}/edge/provision` — `edge.provision`; returns the
  Edge secret once.
- `POST /api/events/{event_id}/edge/pairing-code` — `edge.pairing.manage`.
- `POST /api/events/{event_id}/edge/dataset` — `edge.datasets.manage`.
- `POST /api/events/{event_id}/edge/dataset-activate` —
  `edge.datasets.manage`.
- `POST /api/events/{event_id}/devices/pair` — one-time pairing code, persistent
  rate limit.
- `POST /api/events/{event_id}/devices/{device_id}/heartbeat` — device Bearer.
- `POST /api/events/{event_id}/devices/{device_id}/sync` — device Bearer, at
  most 250 operations.

## Vouchers

- `POST /api/organizations/{org_id}/events/{event_id}/vouchers/assignments` —
  `vouchers.manage`, idempotency key required.
- `POST /api/organizations/{org_id}/events/{event_id}/vouchers/consumptions` —
  `vouchers.consume`, idempotency key required.
- `GET /api/organizations/{org_id}/events/{event_id}/vouchers/participants/current`
  — `vouchers.read`, credential supplied through `X-Credential-Token` to avoid
  URL/log disclosure.
- `GET /api/organizations/{org_id}/events/{event_id}/vouchers/report` —
  `vouchers.read`.

## Lead Retrieval

- `POST /api/v5/organizations/{org_id}/events/{event_id}/leads/captures` —
  `leads.capture`, consent and idempotency required.
- `POST /api/v5/organizations/{org_id}/events/{event_id}/leads/offline-sync` —
  device Bearer and consent evidence required.
- `GET /api/v5/organizations/{org_id}/events/{event_id}/companies/{company_id}/leads`
  — `leads.read`.
- `POST /api/v5/organizations/{org_id}/events/{event_id}/companies/{company_id}/leads/export`
  — `leads.export`, idempotency required.

## Vehicle logistics

- `POST /api/v5/organizations/{org_id}/events/{event_id}/vehicles/access` —
  `vehicles.access`, idempotency and anti-passback.
- `POST /api/v5/organizations/{org_id}/events/{event_id}/vehicles/offline-sync`
  — device Bearer.
- `GET /api/v5/organizations/{org_id}/events/{event_id}/vehicles/dashboard` —
  `vehicles.read`.
- `POST /api/v5/organizations/{org_id}/events/{event_id}/vehicles/import-preview`
  — `vehicles.import`; preview only, without writes.

Secrets, credential hashes, raw dataset payloads and internal metadata are
excluded from administrative responses.
