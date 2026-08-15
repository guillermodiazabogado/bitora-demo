# BITORA Networking V2.2 - Organizer Operations & Commercial Readiness

## Starting state

- Expected checkpoint verified: `7bb6583 feat: improve networking discovery rotation and mobile ux`.
- Branch during implementation: `chore/final-endurance-certification`.
- Pre-existing unrelated work preserved: `R2_RESTORE_ISOLATED_VALIDATION.json` was dirty before V2.2 and was not touched.
- No `AGENTS.md` was present.

## Scope

V2.2 makes Networking operable for event organizers without adding analytics complexity.

Preserved:

- Digital Credential;
- public QR/deep links;
- Golden Ticket;
- progressive Discovery onboarding;
- live vocabulary;
- canonical Networking Contacts;
- deterministic Discovery;
- V2.1 rotation/recycle;
- event isolation;
- anti-directory participant boundary;
- no AI/ML, no participant scoring, no leaderboards.

## ExecPlan

1. Reentry and baseline
   - Verify branch, HEAD, working tree and V2.1 regression suite.
   - Classify inherited failures.
   - Preserve unrelated dirty files.

2. Operational metrics service
   - Add one backend summary derived from canonical state.
   - No persisted counters and no new migration.
   - Source data: `networking_event_participations`, V1.2 readiness evaluator, `networking_contacts`, `networking_interaction_events`, taxonomy and vocabulary tables.

3. Prelaunch readiness and warnings
   - Add deterministic event status: `READY`, `NEEDS_ATTENTION`, `NOT_READY`.
   - Status is explainable through warning rows, not a hidden score.
   - Discovery disabled is informational, not event failure.

4. Organizer dashboard
   - Extend `networking-admin.html` with a compact operations panel.
   - UI renders only aggregates and warnings returned by the backend.
   - No frontend business-rule duplication.

5. Export and runbook
   - Add one-row CSV operational summary.
   - Export contains aggregate metrics only.
   - No private channels, public profile tokens, participant behavior timelines or roster rows.

6. Verification and review
   - Add `verificar_networking_v2_2.py`.
   - Run Networking regression, backup/restore and auth checks.
   - Run local adversarial and commercial reviews because subagent capacity was unavailable.

Rollback/recovery: V2.2 is additive. Revert the service methods, two admin endpoints, admin HTML section, verifier and this document. No migration rollback is needed.

## Operations service

Authoritative method:

- `NetworkingService.operations_summary(db, event_id)`

Admin endpoints:

- `GET /api/networking/operations?actor=Admin&event_id=<id>`
- `GET /api/networking/operations.csv?actor=Admin&event_id=<id>`

Both require the same admin/reporting authorization style used by Networking readiness. Participant/public actors receive 403 in non-login test mode.

## Metric definitions

- `participants.total`: EventParticipations for the event.
- `participants.active`: EventParticipations in `ACTIVE`; this is not readiness.
- `participants.ready`: profiles marked `READY` by the V1.2 readiness evaluator.
- `discovery.configured_participants`: participants with Discovery preferences completed.
- `discovery.users`: participants with Discovery interaction history.
- `discovery.profiles_shown`: `discovery_shown` plus `discovery_recycled`.
- `discovery.exhausted_users`: participants with recorded `discovery_exhausted` in the current Discovery preference cycle.
- `networking.contacts_total`: active canonical Networking contacts.
- `networking.scan_contact_events`: scan/QR contact events where history exists.
- `networking.discovery_saved_events`: Discovery save actions where history exists.
- `vocabulary.unresolved_candidates`: live vocabulary values still in `CANDIDATE`.

Historical note: old events without V2.2-era `discovery_exhausted` events may show zero exhausted users even if a user previously saw an empty state. V2.2 does not fabricate missing historical metrics.

## Warnings

Warnings are actionable and simple:

- `NO_PARTICIPANTS`
- `INCOMPLETE_PROFILES`
- `NO_ACTIVE_PARTICIPANTS`
- `DISCOVERY_DISABLED`
- `DISCOVERY_SMALL_POOL`
- `DISCOVERY_NOT_USED_YET`
- `DISCOVERY_EMPTY_VOCABULARY`
- `DISCOVERY_NO_OFFERS`
- `DISCOVERY_NO_SEEKS`
- `VOCABULARY_UNRESOLVED`

Severity is `INFO`, `WARNING` or `CRITICAL`. V2.2 currently uses warning/info states and reserves critical for future deterministic configuration failures.

## Discovery operations

V2.2 does not change the relevance engine.

It adds operational visibility for:

- Discovery enabled/disabled;
- configured participants;
- users with Discovery history;
- cards shown;
- skips;
- saves;
- exhaustion;
- discoverable pool size;
- blocked-by-state/privacy count;
- organizations represented.

Discovery disabled is reported as a valid configuration. Basic Networking still has value through credential, QR and contacts.

## Export

The CSV export is one event-level row.

It intentionally excludes:

- participant names;
- emails;
- phones;
- QR/public profile IDs;
- channel contents;
- per-participant click or skip timelines.

This prevents the export from becoming a participant-directory loophole.

## Admin dashboard

`networking-admin.html` now includes:

- overall operations status;
- warnings;
- participant totals;
- active/ready/incomplete counts;
- contact counts;
- QR and Discovery activity;
- exhaustion count;
- vocabulary health;
- CSV export action.

The dashboard uses existing event ID controls and links configuration, readiness and vocabulary in one coherent page.

## Event deployment runbook

1. Create/configure the event.
2. Set Networking presentation mode and readiness rules.
3. Import participants.
4. Preview/resolve structural import errors.
5. Open Networking Admin and load Operations.
6. Check incomplete profiles and contact-route warnings.
7. Configure/verify vocabulary.
8. Enable or disable Discovery intentionally.
9. Test public QR/deep link.
10. During the event, monitor active users, Discovery users, cards shown, contacts and exhaustion.
11. After the event, export the operational CSV summary.

## Privacy and authorization

- Operations endpoints are admin-only.
- Participant-facing APIs remain bounded and do not expose rosters.
- Metrics are aggregate and descriptive.
- The CSV export contains no private channel data.
- Hidden profiles may affect aggregate counts but are not revealed as identities or semantic labels.

## Backup and restore

No new table was added.

V2.2 derives metrics from tables already included in event backup/restore:

- Networking participations;
- intents;
- contacts;
- interaction events;
- taxonomy/vocabulary;
- semantic classifications.

The V2.2 verifier restores an event bundle and confirms contact and Discovery history metrics survive.

## Known limitations

- Discovery exhaustion is counted reliably after V2.2 records `discovery_exhausted`; older empty states are not reconstructed.
- Contact provenance is based on available interaction history. Old contacts without provenance are counted in total contacts but not forced into a source category.
- No cross-event BI, time-series charts, leaderboards, participant scores or ROI attribution.
- No browser screenshot automation was added for the admin panel; HTML presence and mobile-safe non-directory structure are covered by verifier assertions.

## Verification

PASS:

- `python -m py_compile server.py backend/services/networking.py verificar_networking_v2_2.py`
- `python verificar_networking_v2_2.py`

Broad regression should include:

- `python verificar_networking_v2_1.py`
- `python verificar_networking_v2.py`
- `python verificar_networking_v1_3.py`
- `python verificar_networking_v1_2.py`
- `python verificar_networking_v1_1.py`
- `python verificar_networking_v1.py`
- `python verificar_event_restore.py`
- `python verificar_backup_restore.py`
- `python verificar_auth_red.py`
- `python verificar_landing_config.py`

Inherited failures expected from baseline:

- `python verificar_mvp.py` -> `FALLO: La inscripcion publica no genero portal`
- `python verificar_integridad_bitora.py` -> `QR anticipado no fue rechazado correctamente`
