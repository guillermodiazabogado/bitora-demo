# BITORA Networking V2.1 - Discovery Rotation, Session Quality & Mobile UX

## Starting state

- Expected checkpoint verified: `be009a7 feat: add networking discovery engine`.
- Branch during implementation: `chore/final-endurance-certification`.
- Pre-existing unrelated work preserved: `R2_RESTORE_ISOLATED_VALIDATION.json` was dirty before V2.1 and was not touched.
- No `AGENTS.md` was present.

## Scope

V2.1 improves Discovery session feel without redesigning the V2 engine.

Preserved:

- Digital Credential;
- public QR/deep link;
- Golden Ticket;
- progressive onboarding;
- live event vocabulary;
- canonical Networking Contacts;
- deterministic relevance;
- bounded backend Discovery API;
- no public directory;
- no bilateral matching;
- no AI/ML/embeddings.

## Rotation lifecycle

Discovery now distinguishes:

1. Fresh candidates: eligible profiles with no prior Discovery shown/skipped/saved/recycled history for this participant in this event.
2. Recyclable skipped candidates: profiles the participant skipped earlier, only after fresh candidates are exhausted.
3. True exhaustion: no fresh and no safely recyclable candidates.

Saved/contacted profiles are excluded through the canonical `networking_contacts` table, no matter whether the contact came from Discovery, QR scan or another valid Networking contact path.

## Skip cooldown

Skip remains temporary: it does not mutate semantic preferences and does not permanently hide a participant.

V2.1 uses a deterministic cooldown:

- recent last 3 Discovery targets are excluded from immediate fresh/recycle selection;
- skipped candidates can recycle only after fresh supply is exhausted;
- recycled candidates are shown once per Discovery preference cycle;
- editing Discovery preferences starts a new preference cycle without deleting identity, contacts or history.

This avoids instant loops while keeping old skipped profiles available later.

## Organization sequencing

The sequencer tracks recent organizations from the last Discovery interactions and prefers other organizations when alternatives exist.

This affects order, not eligibility:

- multiple representatives remain distinct people;
- if only one organization remains, its representatives can still appear;
- ORGANIZATION_FIRST benefits most, but PERSON_FIRST also avoids needless adjacent organization repetition.

## Exploration sequencing

V2 event configuration is reused:

- `networking_discovery_enabled`
- `networking_discovery_batch_size`
- `networking_discovery_exploration_frequency`

No new organizer-facing ranking settings were added.

Aligned profiles remain primary. Exploration appears only when the participant allowed diversity and according to the configured frequency. Exploration receives a truthful reason: `Oportunidad fuera de tus preferencias`.

## Exhaustion recovery

V2.1 has three participant-facing states:

- fresh opportunities;
- reconsideration pass: `Ya viste las oportunidades nuevas. Te mostramos algunas que quizas quieras reconsiderar.`;
- true exhaustion: `Ya recorriste las oportunidades disponibles por ahora.`

Newly imported or externally registered participants automatically enter the fresh pool if they meet current eligibility/privacy rules. No deployment is required.

## Privacy and state

Privacy remains a hard gate before sequencing.

If a previously shown or skipped participant becomes hidden, revoked, non-active, non-discoverable or already contacted, they stop appearing. Current state wins over historical eligibility.

Discovery state remains event-specific. Skips and recycle history from one event do not affect another event.

## Mobile UX

Discovery UI now includes:

- loading state while fetching/saving/skipping;
- double-tap guard on Discovery actions;
- retry in empty/failure state;
- visible save confirmation: `Guardado en Mis Contactos`;
- `Ver perfil`;
- one-tap `Siguiente`;
- touch-friendly buttons;
- mobile action stacking under narrow widths;
- wording that avoids score/match/AI claims.

The frontend still renders one opportunity at a time and does not cache or download an event roster.

## Backup and restore

No new table was required.

V2.1 uses `networking_interaction_events` and `networking_contacts`, already covered by event backup/restore. The V2.1 verifier checks restored interaction and contact counts.

## Verification

PASS:

- `python -m py_compile server.py backend/services/networking.py verificar_networking_v2_1.py`
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

Inherited failures remain:

- `python verificar_mvp.py` -> `FALLO: La inscripcion publica no genero portal`
- `python verificar_integridad_bitora.py` -> `QR anticipado no fue rechazado correctamente`

No `package.json` exists, so there is no frontend build/lint/typecheck command in this repository.

## Manual verification

Fresh -> skip -> recycle:

1. Complete Discovery preferences for a participant.
2. Open Discovery and note the first profile.
3. Tap `Siguiente`.
4. Confirm the same profile does not immediately return.
5. Continue skipping fresh profiles.
6. After fresh exhaustion, previously skipped profiles may return in the reconsideration pass.

Organization diversity:

1. Import multiple representatives from one organization and at least one from another.
2. Skip a representative from the first organization.
3. If a relevant alternative organization exists, the next card should prefer that alternative.
4. If only one organization remains, its other representatives may still appear.

Exhaustion and new participant recovery:

1. Consume fresh and recycle candidates until true exhaustion.
2. Import or externally register a new eligible participant.
3. Open Discovery again.
4. The new participant should appear as fresh.

Mobile:

1. Open `/networking.html?token=<token>` at widths around 320, 360, 390 and 430 px.
2. Confirm Discovery actions stack safely and remain tappable.
3. Confirm loading, retry, save confirmation and empty state are visible.

## Known limitations

- Cooldown is a simple last-3-target rule, not a sophisticated session model.
- Recycle is one pass per Discovery preference cycle.
- Exact normalized matching remains the semantic limitation from V2.
- No browser screenshot automation was added; mobile verification is covered by static UI assertions and manual guidance.
