# BITORA Networking V2.4 - Production Certification & Event Pilot Hardening

## Starting State

- Expected checkpoint verified: `d585a63 feat: add networking event launch and branding readiness`.
- Branch during certification: `chore/final-endurance-certification`.
- Pre-existing unrelated work preserved: `R2_RESTORE_ISOLATED_VALIDATION.json`.
- No `AGENTS.md` was present.

V2.4 is a hardening/certification milestone. It does not add a new product layer and does not change the V2 Discovery relevance model.

## Certification Scope

Certified software-side areas:

- participant credential/session access;
- public Networking QR/deep-link profile;
- contact creation/idempotency;
- My Contacts canonical contact state;
- Discovery onboarding, next/skip/save and V2.1 recycle behavior;
- current privacy/state override of historical Discovery history;
- event isolation and prelaunch/disabled public gating;
- organizer operations/export safety;
- populated backup/restore;
- fresh/init migration idempotency;
- static `frontend/` and `static/` Networking asset parity;
- modest concurrent event-pilot use on SQLite.

Out of scope remains unchanged: no AI/ML, no new ranking model, no CRM, no chat, no scheduling, no billing, no public directory, no BI platform.

## Hardening Change

Operational CSV export now neutralizes spreadsheet formula injection for event-controlled text fields. Values beginning with `=`, `+`, `-` or `@` are prefixed with an apostrophe before export.

This affects only CSV output and does not change admin dashboard or participant behavior.

## Certification Harness

New verifiers:

- `verificar_networking_v2_4.py`
- `verificar_networking_pilot.py`

`verificar_networking_v2_4.py` validates security/state/restore behavior on isolated temporary SQLite state.

`verificar_networking_pilot.py` creates a deterministic medium-event fixture:

- 501 Networking EventParticipations including owner;
- 500 imported candidates;
- approximately 80 organizations;
- mixed organization activity, function, offer/seek and channel data;
- event brand/public URL/launch config;
- active Discovery owner;
- bounded concurrent reads/writes.

## Automated Evidence

Latest local V2.4 verifier:

```text
OK: networking V2.4 certification hardening
{"contacts": 1, "credential_concurrency_seconds": 0.098, "interactions": 23, "participants_event": 5, "public_profile_concurrency_seconds": 0.22, "restored_event_id": 6, "scan_race_seconds": 0.225, "skip_race_seconds": 1.334}
```

Latest pilot load verifier:

```text
OK: networking pilot 500 load
{"credential": {"count": 50, "max_ms": 236.2, "median_ms": 124.6, "min_ms": 28.8, "p95_ms": 156.2}, "db": "sqlite", "discovery_next": {"count": 100, "max_ms": 3301.3, "median_ms": 2921.6, "min_ms": 2143.4, "p95_ms": 3224.2}, "duplicate_contacts": 0, "duplicate_scan": {"count": 40, "max_ms": 424.1, "median_ms": 221.1, "min_ms": 23.9, "p95_ms": 414.7}, "errors": 0, "import_seconds": 0.621, "journal_mode": "wal", "operations_summary_ms": 463.5, "organizations_estimated": 80, "participants": 501, "public_profile": {"count": 100, "max_ms": 532.8, "median_ms": 208.2, "min_ms": 104.9, "p95_ms": 331.6}}
```

These are certification observations, not a production SLA.

## Concurrency And Idempotency

Verified:

- 20 concurrent owner credential/session reads complete without state corruption.
- 40 concurrent public profile reads complete safely.
- 20 concurrent duplicate QR saves create exactly one logical `networking_contacts` row.
- QR save and Discovery save against the same target converge on the same canonical contact.
- 12 concurrent duplicate skip actions record one useful skip and do not immediately return the skipped profile.
- Retry-style repeated contact/save calls return the existing canonical contact.

The current SQLite configuration uses WAL mode and `busy_timeout = 30000`. Mutating Networking API routes are serialized by the application `DB_LOCK` and use explicit transactions.

## QR And Auth Security

Automated checks verify:

- Networking QR resolves to the configured event public URL via `NetworkingService.public_profile_link`.
- QR SVG is generated structurally with quiet-zone-capable SVG rendering.
- Public profile ID cannot authenticate an owner session.
- Public profile response does not include owner token hints or private email.
- malformed/random public profile IDs return safe 404 responses.
- prelaunch public profile access returns `NOT_LIVE`.
- disabled Networking blocks new public profile access without deleting state.

## Inherited Failure Classification

### `verificar_integridad_bitora.py`

Failure:

```text
QR anticipado no fue rechazado correctamente
```

Classification: `NETWORKING_IRRELEVANT_LEGACY`.

Evidence: the failing assertion exercises legacy accreditation/activity access validation through `/api/validate` using registration/access QR tokens and activity access windows. Networking QR uses event-participation public profile IDs (`NET-*`), `/api/networking/profile`, `/api/networking/qr.svg`, and private owner tokens for authentication. The shared QR rendering helper only draws SVG modules; it does not share authentication semantics. V2.4 reverified that public Networking QR cannot authenticate the owner.

### `verificar_mvp.py`

Failure:

```text
FALLO: La inscripcion publica no genero portal
```

Classification: `NETWORKING_IRRELEVANT_LEGACY`.

Evidence: the failing path is legacy public event registration and `/p.html` portal generation from `/api/register`. Networking external participants use `/api/networking/external-register`, canonical Person/Organization/EventParticipation records, private owner token issuance and the same Networking onboarding/contact architecture. V2.4 verified concurrent external Networking registrations and did not depend on legacy portal creation.

If either legacy issue is later shown to be part of a deployed Networking event path, it must be reclassified before launch.

## Backup And Restore

Automated restore uses a deliberately populated event with:

- event launch/brand config;
- participants;
- contact;
- Discovery preferences and interaction history;
- live vocabulary candidates.

The restored event preserves counts and launch state. Large-event restore can be slower; V2.4 keeps the routine verifier smaller and uses the pilot script for medium-event load evidence.

## Degradation Model

Production-critical core:

1. event resolution;
2. authentication;
3. Digital Credential;
4. public QR profile;
5. contact creation;
6. privacy;
7. database integrity.

Discovery is valuable but can be disabled while preserving credential/QR/contact flows. Networking launch can also be disabled and re-enabled without deleting contacts, preferences, interactions or profile tokens.

## Manual Certification Matrix

Not executed in Codex/local environment:

- Android standard-camera QR scan: `MANUAL REQUIRED`.
- iPhone standard-camera QR scan: `MANUAL REQUIRED`.
- External HTTPS hostname from a non-local network: `MANUAL REQUIRED`.
- Credential branding with real event assets: `MANUAL REQUIRED`.
- Public profile branding with real event assets: `MANUAL REQUIRED`.
- Discovery branding with real event assets: `MANUAL REQUIRED`.
- Two-device scan -> login/register -> return -> save contact: `MANUAL REQUIRED`.
- Admin launch -> participant live access on deployed host: `MANUAL REQUIRED`.
- Emergency disable from deployed admin while a participant device is active: `MANUAL REQUIRED`.

Do not mark the pilot complete until these have been executed in staging/production-like infrastructure.

## Pilot Runbook

Before event:

1. Configure event name, brand color/logo and public Networking base URL.
2. Import participants and inspect V2.2 operations dashboard.
3. Resolve blocking launch checks.
4. Enable or intentionally disable Discovery.
5. Run automated smoke/certification commands on the target build.
6. Take a backup.
7. Run real-camera QR certification with two devices.
8. Verify public HTTPS host from outside the local network.
9. Launch Networking.

During event:

1. Keep admin login available.
2. Monitor operations dashboard for contacts, Discovery usage and exhaustion.
3. Spot-check credential, QR scan and Discovery from a participant device.
4. If Discovery is unstable, disable Discovery first and preserve Basic Networking.
5. If core Networking is unsafe, disable Networking launch state and preserve all data.
6. Take a backup checkpoint if operationally appropriate.

After event:

1. Export operational summary.
2. Take final backup.
3. Verify restore if the event data must be archived/moved.
4. Disable or close public access according to event policy.

## Incident Playbook

Public URL broken:

- Check launch readiness public URL result.
- Verify HTTPS/DNS outside local network.
- Do not regenerate participant profile tokens unless there is a separate security reason.

Discovery unavailable:

- Disable Discovery in Networking config.
- Confirm Credential, QR and Contacts still work.
- Re-enable Discovery after fix; preferences/history remain intact.

Networking unsafe:

- Use Networking disable/launch control.
- Confirm public profile shows safe unavailable state.
- Preserve data and re-enable after fix.

DB/data concern:

- Stop risky writes if needed by disabling Networking.
- Take a backup before manual investigation.
- Restore only into an isolated environment until verified.

Bad import:

- Reimport with corrected source data.
- Confirm contacts, Discovery preferences and interaction history remain.

## Known Non-Blocking Limitations

- Real-device QR and public-host/TLS checks require staging/production environment and were not executed locally.
- SQLite pilot evidence is acceptable for modest local certification but is not a formal high-scale production SLA.
- Discovery candidate retrieval is the slowest certified path in the 500-participant SQLite load (`p95_ms` around 3224 ms for 100 concurrent requests). It completed without errors or data corruption; larger commercial pilots should monitor this path.
- V2.4 does not add offline-first behavior. Poor connectivity relies on retry/idempotent backend behavior and existing UI retry/error states.
- Legacy accreditation QR/activity and MVP portal failures remain inherited and classified as Networking-irrelevant based on current route/domain separation.

## Commands

```powershell
& 'C:\Users\Noxie-PC\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m py_compile server.py backend\services\networking.py verificar_networking_v2_4.py verificar_networking_pilot.py
& 'C:\Users\Noxie-PC\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' verificar_networking_v2_4.py
& 'C:\Users\Noxie-PC\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' verificar_networking_pilot.py
& 'C:\Users\Noxie-PC\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' verificar_networking_v2_3.py
& 'C:\Users\Noxie-PC\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' verificar_networking_v2_2.py
& 'C:\Users\Noxie-PC\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' verificar_networking_v2_1.py
& 'C:\Users\Noxie-PC\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' verificar_networking_v2.py
```
