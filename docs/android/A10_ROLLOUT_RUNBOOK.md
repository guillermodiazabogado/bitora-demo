# Android A10 Rollout Runbook

This runbook begins only after the production URL, signing identity, Admin
pairing service and application ownership are supplied. It does not authorize a
production deployment by itself.

## Release gates

1. All JVM tests, phase verifiers, debug/release builds, lint and R8 pass.
2. Instrumented recovery tests pass on API 26 and API 35.
3. Release APKs are signed by CI from protected secrets and their SHA-256 hashes
   are recorded with the release candidate.
4. The configured production endpoint passes the stable HTTPS endpoint policy.
5. Operation and Display are paired only to a non-production pilot event first.

## Pilot rings

| Ring | Scope | Minimum observation | Promotion gate |
| --- | --- | --- | --- |
| 0 | Internal QA, 2 devices per app | 4 hours | No crash, pairing or sync blocker |
| 1 | One venue, 10% of devices | 1 event shift | Error and queue thresholds remain green |
| 2 | One venue, 50% of devices | 1 event shift | No unresolved severity-1/2 incident |
| 3 | Approved fleet | 24 hours | Operations owner signs off |

Promotion is manual. Never promote while an offline queue is growing or an
event is actively admitting attendees.

## Telemetry contract

Emit operational metadata only. Do not emit credential tokens, QR payloads,
participant fields or raw operation payloads.

- App identity, version, build type and device ID
- Event ID, profile and scope identifier
- Pairing state and Edge connectivity state
- Dataset revision, age and verification result
- Background worker state, retry class and duration
- Queue depth, oldest queued age, acknowledged count and conflict count
- Crash-free sessions and startup duration

Required alerts:

- Heartbeat absent for 20 minutes during an active event
- Dataset invalid, expired or more than two revisions behind
- Queue depth above 100 or oldest operation above 10 minutes
- Background retries continuing for 15 minutes
- Crash-free sessions below 99.5% in a pilot ring

## Rollback triggers

Stop promotion and roll back when any of these occurs:

- Pairing or identity loss on more than one pilot device
- Signed dataset rejection caused by the release candidate
- Acknowledged operations are duplicated or lost
- Queue depth continues increasing after connectivity returns
- Crash rate exceeds 0.5% or a severity-1 operational workflow fails

## Rollback procedure

1. Freeze the active rollout ring in the MDM/private store.
2. Preserve server logs, app version, device IDs, dataset revisions and queue
   metrics. Never collect credential tokens or participant data.
3. Reassign the prior signed APK version to the affected ring.
4. Keep device app data during downgrade so encrypted identity and pending
   operations remain available. Do not clear storage unless incident command
   explicitly approves it.
5. Confirm the prior version reconnects, receives the current signed dataset and
   drains the queue idempotently.
6. Resume promotion only after root cause, fix and a new pilot pass are recorded.

## Distribution controls

- Use managed private distribution, not a public store listing, for the pilot.
- Restrict installs and updates to managed event devices.
- Keep signing keys and passwords in protected CI/MDM secret storage.
- Record APK hash, version code, signer fingerprint, rollout ring and operator.
- Maintain the immediately previous signed version as the rollback candidate.
