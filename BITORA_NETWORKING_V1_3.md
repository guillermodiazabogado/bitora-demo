# BITORA Networking V1.3 - Digital Credential, Live Event Vocabulary & Discovery Foundation

## Reentry factual

- Starting branch: `chore/final-endurance-certification`.
- Expected checkpoint in superseding spec: `4044da2 - feat: add networking profile readiness and completion`.
- Actual starting HEAD: `7ca7fe9 - feat: add networking semantic profile foundation`.
- Working tree at reentry: clean.
- No `AGENTS.md` found.
- No `package.json` found; no repository-native frontend build/lint/typecheck command available.

Baseline before new edits:

- PASS `py_compile` for Networking/server/backup modules.
- PASS `verificar_networking_v1_3.py` from the earlier semantic V1.3.
- PASS `verificar_networking_v1_2.py`.
- PRE_EXISTING FAIL `verificar_mvp.py`: `FALLO: La inscripcion publica no genero portal`.

## Product decision

This file documents the superseding V1.3 scope:

`DIGITAL CREDENTIAL -> CONTACT EXCHANGE -> DISCOVERY`

V1.3 does not implement a final recommendation engine, ranking, compatibility score, public directory, participant browser, swipes, chat, meetings or AI/ML inference.

## Architecture

### Digital Credential

- The participant home in `networking.html` is now a mobile event credential.
- The credential shows event identity, participant/organization hierarchy, public Networking QR and Level 1 actions.
- It respects V1.1 presentation hierarchy and V1 privacy filtering.
- Credential/contact exchange does not require Discovery onboarding.

### Public QR and deep link

- `/api/networking/qr.svg?profile_id=NET-...` now encodes an absolute web link to `/n/NET-...`.
- `/n/NET-...` serves `networking-public.html`.
- The public page resolves `/api/networking/profile` and shows only permitted data.
- Public profile token remains non-authenticating; owner access still requires owner token/accreditation token.
- Authenticated users can save the scanned profile through the existing `/api/networking/scan` path.
- Logged-out users can view the public profile and continue to login/registration while preserving `return_profile`.

### Golden Ticket

- The credential includes a distinctive Golden Ticket button.
- First use opens progressive Discovery onboarding.
- Completed state opens a truthful Discovery shell: no fake recommendations.
- Discovery state is stored separately from ACTIVE/PASSIVE and basic profile readiness.

### Discovery preferences

Stored in `networking_intents`:

- `discovery_completed`
- `discovery_diversity`
- `desired_functions_json`
- `desired_company_types_json`
- `discovery_objectives_json`

This keeps Discovery preferences event-specific.

### Live Event Vocabulary

V1.3 reuses the earlier semantic foundation:

- `networking_taxonomy_concepts`
- `networking_event_taxonomy_concepts`
- `networking_semantic_classifications`

It adds:

- `networking_event_vocabulary_candidates`

The live vocabulary is built from:

- configured event taxonomy;
- source import declarations;
- external registration declarations;
- user onboarding/completion declarations;
- Discovery onboarding declarations.

Raw/new values are preserved as event candidates. They are not silently mapped to unrelated canonical concepts. Deterministic normalization trims/cases and removes accents for obvious duplicates.

Anonymous users can only see configured vocabulary. Live candidates are returned only with participant token context or admin actor context, so raw market intent is not exposed publicly.

## Semantic ownership

- Organization: industry/activity, specialty, organization offers.
- Person: function, seniority, person interests.
- EventParticipation: event-specific seeks and Discovery preferences.

Offer and seek remain directionally distinct.

## Admin operations

`networking-admin.html` now exposes:

- configured semantic vocabulary;
- live vocabulary counts by dimension;
- import readiness diagnostics.

It does not expose participant roster browsing.

## Final review repairs

- Live vocabulary candidates were restricted from anonymous access.
- Public profile now honors `profile_visible` for non-owner viewers.
- Discovery company-type step now uses `COMPANY_TYPE` with industry fallback.
- The verifier asserts that anonymous vocabulary does not expose uncurated candidates.

Commercial review outcome:

- PASS: the story is explainable as `credential -> contact exchange -> Golden Ticket`.
- PASS: no fake recommendations or heavy matching were introduced.
- PARTIAL: admin taxonomy setup still uses JSON and readiness keys; this is acceptable for foundation but should be simplified with presets in a later commercial polish.
- PARTIAL: owner tokens can still appear in post-registration URLs as inherited architecture; QR public links are separated from owner tokens, but token handling can be improved in a later security polish.

## Migrations

- `030_networking_semantic_profile.sql`: semantic taxonomy/classification foundation from earlier V1.3.
- `031_networking_discovery_foundation.sql`: Discovery preference columns and event vocabulary candidates.

Runtime schema guards were added for existing SQLite databases.

## Future V2 Discovery contract

A future simple Discovery engine may consume:

- event id;
- participant id;
- person id;
- organization id;
- presentation mode;
- basic readiness;
- discovery readiness;
- offers;
- seeks;
- organization activity/industry;
- specialties;
- desired company types;
- desired functions;
- objectives/interests;
- function;
- seniority;
- contact openness;
- privacy-filtered route availability;
- diversity preference.

V1.3 does not generate candidates from this data.

## Verification

PASS:

- `python -m py_compile server.py backend/services/networking.py backend/services/backup.py verificar_networking_v1_3.py`
- `python verificar_networking_v1_3.py`
- `python verificar_networking_v1_2.py`
- `python verificar_networking_v1_1.py`
- `python verificar_networking_v1.py`
- `python verificar_event_restore.py`
- `python verificar_backup_restore.py`
- `python verificar_auth_red.py`
- `python verificar_landing_config.py`
- App initialization on a temporary SQLite database creates Discovery/vocabulary schema.

PRE_EXISTING FAIL:

- `python verificar_mvp.py` -> `FALLO: La inscripcion publica no genero portal`
- `python verificar_integridad_bitora.py` -> `QR anticipado no fue rechazado correctamente`

## Manual checks

Credential with a normal phone:

1. Open a participant credential in `/networking.html?token=...`.
2. Scan the visible QR with a normal camera.
3. The camera opens `/n/NET-...`.
4. The public profile displays permitted data only.

Activate Discovery:

1. Tap Golden Ticket.
2. Answer the progressive questions.
3. Confirm the Golden Ticket changes to ready.
4. Re-enter later; it opens the Discovery-ready shell.

New category becomes selectable:

1. Import or declare a new value such as `Geotecnia aplicada`.
2. Open admin `Vocabulario vivo` or participant Golden Ticket.
3. Confirm the value appears as an event candidate without code changes.

No directory/matching:

1. `/api/networking/directory` returns 404.
2. `/api/networking/recommendations` returns 404.
3. Participant UI exposes credential, scan, contacts and Discovery onboarding/shell only.

## Known limitations

- Discovery stream/recommendation engine is intentionally not implemented.
- Admin vocabulary normalization is still intentionally lightweight; no ontology platform.
- Raw candidates are preserved event-locally and need later admin resolution if organizers want canonical governance.
- Mobile verification was performed through responsive CSS/static checks and API/E2E script coverage; no browser-driven visual screenshot suite exists in the repository.
