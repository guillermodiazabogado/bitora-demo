# BITORA Networking V2 - Discovery Engine & Smart Contact Guide

## Starting state

- Starting checkpoint verified: `4ed6be1 feat: add networking credential and discovery foundation`.
- Branch during implementation: `chore/final-endurance-certification`.
- Baseline PASS before V2: `verificar_networking_v1_3.py`, `verificar_networking_v1_2.py`, `verificar_networking_v1_1.py`, `verificar_networking_v1.py`, event restore, backup restore, auth red and landing config.
- Inherited baseline failures remain outside Networking V2:
  - `verificar_mvp.py`: `FALLO: La inscripcion publica no genero portal`.
  - `verificar_integridad_bitora.py`: `QR anticipado no fue rechazado correctamente`.

## Product scope

V2 activates the Discovery experience prepared by V1.3.

The product is a small, explainable smart contact guide:

`Credential -> Golden Ticket -> Discovery Onboarding -> Discovery Stream`

It is not a public directory, bilateral match, chat, scheduler, CRM, score system, AI/ML ranking or embedding search.

## Event configuration

Migration `032_networking_discovery_engine.sql` adds:

- `events.networking_discovery_enabled`
- `events.networking_discovery_exploration_frequency`
- `events.networking_discovery_batch_size`
- index on `networking_interaction_events(event_id, actor_participation_id, event_type, target_participation_id)`

Defaults:

- Discovery enabled: yes.
- Batch size: 3, server-capped at 5.
- Exploration frequency: 4, bounded between 2 and 12.

Admin can configure these in the Networking admin page without algorithm weights or event-specific code.

## Candidate universe

Discovery requires authenticated participant context.

Candidates are event-local and bounded. The backend excludes:

- self;
- non-active target participation;
- non-discoverable targets;
- hidden public profiles;
- existing active contacts for that owner;
- targets already shown/skipped/saved by that owner in the same event.

This follows current Networking semantics, where public profile and scan/contact exchange require active profiles.

## Relevance model

The engine is deterministic and rule-based.

Internal relevance uses:

- strong signal: the user seeks something the candidate offers;
- medium signal: the candidate seeks something the user offers;
- medium signal: preferred sector/company type;
- medium signal: desired function;
- light signal: shared event objective/interest;
- exploration signal: valid opportunity outside preferences when diversity is enabled.

Internal score is never exposed to the participant. The UI receives human-readable reasons only, for example:

- `Ofrece algo que estas buscando`
- `Pertenece a un rubro que elegiste`
- `Trabaja en un area que queres contactar`
- `Oportunidad fuera de tus preferencias`

## Interaction history

V2 reuses `networking_interaction_events` for:

- `discovery_shown`
- `discovery_skipped`
- `discovery_saved`
- `discovery_profile_opened`
- `discovery_channel_opened`

Skip does not create a contact and does not mutate semantic preferences.

Save uses the canonical `networking_contacts` table. Repeated save is idempotent and the saved profile appears in existing My Contacts.

## UX

The credential remains the participant home.

Golden Ticket behavior:

- Discovery disabled: shows an honest unavailable state.
- Discovery not configured: opens progressive onboarding.
- Discovery ready: opens the live stream.

The stream displays one visible opportunity at a time with:

- adaptive profile card from existing presentation model;
- one safe explanation reason;
- permitted quick actions in the reused profile card;
- `Guardar contacto`;
- `Siguiente`;
- `Editar preferencias`;
- route back to My Contacts.

Empty state is truthful and offers preference editing or return to credential, never a roster fallback.

## Privacy

Privacy is applied before relevance.

Hidden profile/undiscoverable participants are excluded before scoring. Candidate reasons are derived from the already permitted presentation/semantic payload, so hidden organization or restricted representative data does not leak through explanations.

## Backup and restore

New Discovery configuration is stored on `events`, which is already included in event backup. Discovery history is stored in `networking_interaction_events`, already included in event backup/restore.

`verificar_networking_v2.py` verifies restored counts for contacts and interaction history plus Discovery config.

## Execution plan and review

Milestones executed:

1. Reentry and baseline classification.
2. Event Discovery configuration and migration.
3. Bounded backend candidate engine.
4. Skip/save/contact interaction integration.
5. Real Discovery stream UI.
6. Admin minimal configuration.
7. V2 verification script.
8. Regression and adversarial/product review.

Independent subagent review was attempted but unavailable because the thread agent limit was reached. A separate local adversarial pass checked:

- no roster/directory endpoint;
- no unbounded candidate limit;
- no participant-facing score;
- no AI/ML/embedding code path;
- privacy-first candidate filtering;
- canonical contact reuse;
- event-specific interaction/preference state.

## Test commands

PASS:

- `python -m py_compile server.py backend/services/networking.py backend/services/backup.py verificar_networking_v2.py`
- `python verificar_networking_v2.py`
- `python verificar_networking_v1_3.py`
- `python verificar_networking_v1_2.py`
- `python verificar_networking_v1_1.py`
- `python verificar_networking_v1.py`
- `python verificar_event_restore.py`
- `python verificar_backup_restore.py`
- `python verificar_auth_red.py`
- `python verificar_landing_config.py`

Inherited failures:

- `python verificar_mvp.py`
- `python verificar_integridad_bitora.py`

No `package.json` exists in this repository, so no frontend build/lint/typecheck command is available.

## Manual verification

Enable Discovery:

1. Open Networking admin.
2. Select an event.
3. Set Discovery to enabled.
4. Set cards per batch between 1 and 5.
5. Save configuration.

Participant flow:

1. Open `/networking.html?token=<owner-token>`.
2. Use the credential without completing Discovery.
3. Tap Golden Ticket.
4. Complete Discovery preferences.
5. Confirm a real opportunity card appears.
6. Tap `Siguiente`; the same card should not immediately repeat.
7. Tap `Guardar contacto`; the card should appear in My Contacts.

Direct seek/offer verification:

1. Configure a SEEK concept and an OFFER concept with the same user-facing label.
2. Give participant A the seek and participant B the offer.
3. Complete A's Discovery onboarding.
4. B should appear before unrelated valid profiles with reason `Ofrece algo que estas buscando`.

Diversity verification:

1. Complete Discovery with diversity disabled; stream should stay aligned with preferences.
2. Edit preferences and enable diversity; valid exploration profiles may appear after aligned profiles.

No-directory verification:

1. `/api/networking/directory` returns 404.
2. `/api/networking/recommendations` returns 404.
3. `/api/networking/discovery?limit=10000` still returns a server-capped small batch.

## Known limitations

- Discovery stops at exhaustion; skipped profiles are not reintroduced in V2.
- Relevance uses exact normalized label/code overlap and explicit vocabulary only.
- No meeting scheduling, chat, bilateral matching, compatibility score or AI is implemented.
- Organization repetition control is lightweight and only avoids immediate adjacent repetition where possible.
