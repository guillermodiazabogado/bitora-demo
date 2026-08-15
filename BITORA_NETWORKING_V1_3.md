# BITORA Networking V1.3 - Semantic Profile & Routing Foundation

## Reentry factual

- Starting branch: `chore/final-endurance-certification`.
- Starting HEAD: `4044da2 - feat: add networking profile readiness and completion`.
- Working tree at reentry: clean.
- Expected V1.2 checkpoint matched HEAD.
- Baseline PASS before edits:
  - Python compile for `server.py`, `backend/services/networking.py`, V1/V1.1/V1.2 verifiers.
  - `verificar_networking_v1_2.py`.
- Baseline known failure before and after V1.3:
  - `verificar_mvp.py` fails with `FALLO: La inscripcion publica no genero portal`.
- Additional broad check:
  - `verificar_integridad_bitora.py` fails at `QR anticipado no fue rechazado correctamente` on both V1.3 working tree and the clean `4044da2` worktree, so it is classified as pre-existing.

## Objective

V1.3 adds structured semantic profile data and routing foundations without recommendation, matching, candidate generation, participant search or directory browsing.

The system must represent:

- organization activity/industry;
- specialties;
- offers;
- seeks;
- interests/objectives;
- normalized function;
- normalized seniority;
- ownership/provenance;
- event-enabled vocabularies.

## Architecture decision

- Reuse `networking_taxonomy_concepts` as the stable concept catalog.
- Extend concept metadata with description, parent concept and aliases.
- Add `networking_event_taxonomy_concepts` for event-enabled vocabularies.
- Add `networking_semantic_classifications` for explicit classifications.
- Keep ownership explicit:
  - `ORGANIZATION` semantics for activity/specialty/corporate offers.
  - `PERSON` semantics for professional function/interests where needed.
  - `PARTICIPATION` semantics for event-specific offers/seeks/interests.
- V1 legacy `networking_classifications` remains compatible for function/seniority history; V1.3 semantic routing uses the new explicit table.
- Expose one authorized per-event taxonomy API:
  - `GET /api/networking/taxonomy`
  - `POST /api/networking/taxonomy`
- Directory listing from the static server is disabled; `/assets/` returns 404 instead of exposing a file listing.

## Controlled families

- `INDUSTRY`
- `SPECIALTY`
- `OFFER`
- `SEEK`
- `INTEREST`

Function and seniority remain compact normalized values in the existing participation model and are also available as seeded taxonomy concepts.

## ExecPlan

### Milestone 1 - Semantic schema and ownership

Goal: add stable semantic catalog extensions, event vocabulary and explicit classifications.

Visible outcome: repository can store semantic concepts without mixing person, organization and event participation meaning.

Boundary: `backend/services/networking.py`, migration `030`, backup table lists.

Invariants: stable identity != label, offer != seek, person semantics != organization semantics != participation semantics.

Tests: migration execution, V1.3 verifier.

PASS: concepts and classifications persist with owner/provenance.

Rollback: remove new tables/columns before consumers depend on them.

### Milestone 2 - Event vocabulary/configuration

Goal: enable different vocabularies per event.

Visible outcome: admin/API can enable concepts for Event A without affecting Event B.

Boundary: backend config/service plus small admin controls.

Invariants: new event uses data/configuration, not code.

Tests: event isolation and duplicate prevention.

PASS: same concept catalog can be scoped per event and disabled without deletion.

Rollback: remove event vocabulary endpoints/UI.

### Milestone 3 - Import normalization

Goal: resolve structured semantic import values deterministically.

Visible outcome: known values classify; unknown values produce diagnostics and are not silently mapped.

Boundary: import preview/import normalization only.

Invariants: valid import may be semantically incomplete, unknown concept is explicit, reimport is safe.

Tests: known concept, unknown concept, import twice, source update.

PASS: no duplicate classifications and no typo-based auto-classification.

Rollback: keep existing free-text import while removing semantic assignment hooks.

### Milestone 4 - Participant semantic completion

Goal: extend V1.2 completion with event-enabled semantic selections.

Visible outcome: participant can declare offers/seeks/interests and function with controlled values plus concise text.

Boundary: completion endpoint and Networking UI.

Invariants: user-declared semantic state survives source reimport.

Tests: completion, reimport preservation, readiness recalculation.

PASS: USER classifications remain after SOURCE reimport.

Rollback: remove semantic fields from completion while preserving stored data.

### Milestone 5 - Presentation/readiness integration

Goal: expose concise semantic facts and allow readiness keys to use structured concepts.

Visible outcome: profile cards show a small useful subset without becoming taxonomy dumps.

Boundary: profile payload, presentation, readiness evaluator.

Invariants: hidden organization/representative do not leak semantics.

Tests: Organization First, Person First, hidden org, restricted rep.

PASS: cards use permitted semantics only.

Rollback: stop rendering semantic summaries; keep storage.

### Milestone 6 - Regression/future contract

Goal: verify V1.3 and document V2 input contract.

Visible outcome: semantic profile projection is available per authorized profile, not as roster.

Boundary: docs/tests only unless critical fix required.

Invariants: no directory, no matching, QR/scan/contact unchanged, backup/restore safe.

PASS: broad regression and final adversarial review pass.

## Future V2 input contract

A future discovery engine may consume per-profile context:

- `event_id`
- `person_id`
- `organization_id`
- `participation_id`
- `function`
- `seniority`
- `offers`
- `seeks`
- `interests`
- `organization_activity`
- `specialties`
- `networking intent`
- `contact openness`
- privacy-filtered route availability

V1.3 does not generate candidates from this data.

## Plan review notes

- Semantic routing is a soft signal, never a hard exclusion rule.
- Unknown imports are diagnostics, not fuzzy matches.
- Participant-facing taxonomy controls must not expose event population.
- Admin tooling may configure vocabulary but must not become a public directory.

## Implemented behavior

- Event vocabularies are configured as data by enabling taxonomy concepts per event.
- Concept identity is the stable `code`; labels can change without changing identity.
- Explicit concept codes are not collapsed by duplicate labels; label-based reuse is only used for generated codes.
- Import preview resolves known semantic values deterministically and reports unknown values with `UNKNOWN_CONCEPT`.
- Import execution returns the same semantic diagnostics, so unresolved values are visible after import too.
- Source-owned semantic classifications are refreshed on source reimport.
- User-owned semantic classifications from onboarding/completion survive source reimport.
- User-owned semantic classifications are replaced only after new values resolve to known concepts; an unknown typo does not erase previous valid selections.
- Organization-owned semantics are hidden when organization visibility is hidden.
- Person-owned semantics are hidden when representative visibility is restricted.
- Event-participation semantics are hidden when the representative is restricted because they describe that participant's event intent.
- Organization First cards can show activity/specialty/offers where permitted.
- Person First cards can show function/interests/offers/seeks where permitted.
- Readiness can use semantic dimensions without changing ACTIVE/PASSIVE state.
- No directory, recommendation, matching, ranking or candidate endpoint was added.

## Independent review findings repaired

- P1 privacy leak: user-declared semantics could remain visible as participation-owned rows when representative/organization was hidden.
  - Repair: participation semantics require representative visibility; offers tied to an organization are stored as organization-owned; interests are stored as person-owned.
- P1 user data loss: unknown concept submission could delete prior USER selections before resolving replacements.
  - Repair: semantic sync resolves first and deletes/replaces only roles with resolved concepts.
- P2 import diagnostics: import execution dropped preview semantic diagnostics.
  - Repair: import rows now include `semantic.known` and `semantic.unknown`, with aggregate unknown counts.
- P2 taxonomy identity: explicit same-label/different-code concepts could be collapsed.
  - Repair: explicit `code` now controls identity; same-label reuse applies only to generated codes.
- P2 backup verification depth: V1.3 verifier checked existence only.
  - Repair: verifier now compares exact source/restored counts for event taxonomy and semantic classifications.
- P3 migration idempotence: raw SQL `ALTER TABLE ADD COLUMN` remains non-idempotent like earlier migrations; runtime schema guards are idempotent and app initialization was verified.

## Final verification commands

PASS:

- `python -m py_compile server.py backend/services/networking.py backend/services/backup.py verificar_networking_v1.py verificar_networking_v1_1.py verificar_networking_v1_2.py verificar_networking_v1_3.py`
- `python verificar_networking_v1_3.py`
- `python verificar_networking_v1_2.py`
- `python verificar_networking_v1_1.py`
- `python verificar_networking_v1.py`
- `python verificar_event_restore.py`
- `python verificar_backup_restore.py`
- `python verificar_auth_red.py`
- `python verificar_landing_config.py`
- App initialization on a temporary SQLite database creates `networking_event_taxonomy_concepts` and `networking_semantic_classifications`.

PRE_EXISTING FAIL:

- `python verificar_mvp.py` -> `FALLO: La inscripcion publica no genero portal`
- `python verificar_integridad_bitora.py` -> `QR anticipado no fue rechazado correctamente`

Not available:

- No `package.json` was present, so no repository-native frontend build/lint/typecheck command was available.

## Manual verification

Configure an event vocabulary:

1. Open Networking admin for an event.
2. Select or paste semantic concepts in `Vocabulario semantico`.
3. Save.
4. Confirm that another event can have a different vocabulary.

Import semantic values:

1. Add optional import fields such as `organization_activity`, `specialty_concepts`, `offer_concepts`, `seek_concepts`, `interest_concepts`, `function` and `seniority`.
2. Run preview first.
3. Correct any `UNKNOWN_CONCEPT` diagnostics by updating the import value or event vocabulary.
4. Import; repeated import must not duplicate classifications.

Participant completion:

1. Enter Networking with the participant token.
2. Complete onboarding/profile fields for offers, seeks and interests where the event requires or recommends them.
3. Reimport source data and confirm the user selections remain visible to the participant.

No directory/matching check:

1. Use only own profile, own QR, scan and contacts.
2. There is no participant-facing screen to browse all people by taxonomy.
3. `/api/networking/directory` and `/api/networking/recommendations` return 404 in the V1.3 verifier.
