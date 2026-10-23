# BITORA Networking V1.2 - Profile Completeness & Event Readiness

## Reentry factual

- Starting branch: `chore/final-endurance-certification`.
- Starting HEAD: `c688148 - feat: add event-configurable networking profile hierarchy`.
- Working tree at reentry: clean.
- Expected V1.1 checkpoint matched HEAD.
- Baseline PASS before edits:
  - Python compile for `server.py`, `backend/services/networking.py`, `verificar_networking_v1.py`, `verificar_networking_v1_1.py`.
  - `verificar_networking_v1_1.py`.
  - `verificar_networking_v1.py`.
- Baseline known failure before edits:
  - `verificar_mvp.py` -> `FALLO: La inscripcion publica no genero portal`.

## Objective

V1.2 adds event-specific profile readiness without implementing matching, search, directories or recommendations.

The system must distinguish:

- technical profile validity;
- participation lifecycle (`PASSIVE` / `ACTIVE`);
- event-specific readiness (`INCOMPLETE` / `READY`).

Readiness is deterministic, explainable and derived from current effective profile data plus event configuration.

## Architecture decision

- Event configuration stores controlled readiness dimensions:
  - `events.networking_readiness_required`
  - `events.networking_readiness_recommended`
- Empty event readiness config uses deterministic defaults from `networking_profile_mode`.
- One backend evaluator owns readiness rules and returns:
  - status;
  - completed/relevant counts;
  - missing required keys;
  - missing recommended keys;
  - next actions.
- Participant-completed fields that should survive source reimport are stored as explicit Networking-owned overrides in `networking_intents`.
- Readiness uses permitted effective presentation data. Hidden data does not satisfy contactability.

## Controlled readiness dimensions

- `person.identity`
- `person.role`
- `person.bio`
- `organization.identity`
- `organization.activity`
- `organization.description`
- `networking.intent`
- `networking.offers_seeks`
- `contact.permitted_route`
- `contact.organization_route`

## Default rules

### Organization First

Required:

- `organization.identity`
- `organization.activity`
- `networking.intent`
- `networking.offers_seeks`
- `contact.permitted_route`

Recommended:

- `organization.description`
- `person.identity`
- `person.role`
- `contact.organization_route`

### Person First

Required:

- `person.identity`
- `person.role`
- `person.bio`
- `networking.intent`
- `contact.permitted_route`

Recommended:

- `organization.identity`
- `networking.offers_seeks`

### AUTO

Uses the repository fallback already defined by V1.1: `PERSON_FIRST`.

## ExecPlan

### Milestone 1 - Readiness domain/configuration

Goal: persist controlled readiness config per event and add the shared evaluator.

User-visible result: old and new events return readiness in profile payloads.

Boundary: `backend/services/networking.py`, migration `029`, config API.

Invariants: valid != ready, ACTIVE != ready, event-specific readiness, event isolation.

Tests: new V1.2 verifier, V1/V1.1 regressions.

PASS: two events can produce different readiness using data only.

Rollback: remove migration columns and evaluator call sites before any frontend dependency.

### Milestone 2 - Import diagnostics

Goal: preview valid-but-incomplete rows separately from structural errors.

User-visible result: admin preview shows valid, invalid, complete, incomplete and common gaps.

Boundary: import preview only; no import mutation during validation.

Invariants: valid incomplete rows import; invalid rows do not mutate.

Tests: valid complete, valid incomplete, invalid, repeated preview/import twice.

PASS: readiness diagnostics do not reject valid rows.

Rollback: revert preview additions without changing import execution.

### Milestone 3 - Participant completion/onboarding

Goal: participant can fill missing relevant fields without a CRM-size form.

User-visible result: own profile shows readiness and compact completion fields.

Boundary: onboarding endpoint, new completion endpoint, networking UI.

Invariants: first use still required, reimport preserves Networking-owned completion fields.

Tests: PASSIVE+READY, ACTIVE+INCOMPLETE, completion to READY, reimport preservation.

PASS: completion changes derived readiness without altering participation lifecycle incorrectly.

Rollback: remove completion endpoint/UI while keeping evaluator intact.

### Milestone 4 - Admin readiness operations

Goal: expose event readiness counts and participant gaps.

User-visible result: admin can see total/passive/active/ready/incomplete and common missing categories.

Boundary: admin endpoint and admin UI only.

Invariants: no public directory; no hidden channel values exposed.

Tests: summary counts, event isolation, hidden channels excluded from contactability.

PASS: admin sees operational gaps, not private channel payloads.

Rollback: remove admin summary route/UI.

### Milestone 5 - External participants/regression

Goal: external registration enters the same readiness pipeline and V1/V1.1 continue passing.

User-visible result: Organization First registration can provide useful corporate data; Person First avoids extra code forks.

Boundary: external registration UI hints, no alternate domain.

Invariants: imported/external same architecture, QR/scan/contact unchanged, backup/restore unaffected.

Tests: V1.2 verifier plus V1/V1.1/event restore/backup restore/auth/MVP baseline classification.

PASS: broad regression complete with only known MVP baseline failure if still present.

Rollback: revert V1.2 frontend hints; backend remains generic.

## Plan review notes

- No recommendation or matching behavior is allowed.
- Readiness percent is a transparent field-completion metric only.
- Hidden data can be used to tell that something is missing, but never to mark a profile externally contactable or to display private values.
- Event config is controlled lists of known keys, not scripts or custom arbitrary fields.

## Implemented state

- Migration: `backend/migrations/029_networking_profile_readiness.sql`.
- Runtime schema guard: `NetworkingService.ensure_v1_2_schema`.
- Event config:
  - `events.networking_readiness_required`
  - `events.networking_readiness_recommended`
- User-completed, Networking-owned overrides:
  - `networking_intents.completed_title`
  - `networking_intents.completed_function`
  - `networking_intents.completed_seniority`
  - `networking_intents.completed_organization_activity`
  - `networking_intents.completed_organization_specialty`
  - `networking_intents.completed_organization_description`
- Backend evaluator:
  - `evaluate_profile_readiness`
  - `evaluate_import_readiness`
  - `readiness_summary`
- Participant completion endpoint:
  - `POST /api/networking/complete-profile`
- Admin readiness endpoint:
  - `GET /api/networking/readiness?actor=Admin&event_id=ID`
  - By default returns aggregate summary only.
  - `include_participants=1` returns only incomplete profiles, without `public_profile_id` and without channel values.
- Secured-mode admin routes use `require_event_permission` instead of trusting `actor` from the URL/body.

## Operating notes

Configure event readiness from `/networking-admin.html`:

1. Load the event configuration.
2. Choose Organization First / Person First / Auto.
3. Optionally enter comma-separated readiness keys in required/recommended fields.
4. Save.

If required/recommended fields are blank, the system uses the deterministic defaults for the profile mode.

Preview an import with `/api/networking/import/preview`. Valid-but-incomplete rows are reported separately from structurally invalid rows. Mixed imports process valid rows and report invalid rows.

Participants see readiness on their own Networking screen after activation and can fill compact missing data through the profile completion form.

## Final verification

PASS:

- `py_compile` for `server.py`, `backend/services/networking.py`, V1/V1.1/V1.2 verifiers and related regression scripts.
- `verificar_networking_v1_2.py`
- `verificar_networking_v1_1.py`
- `verificar_networking_v1.py`
- `verificar_event_restore.py`
- `verificar_backup_restore.py`
- `verificar_auth_red.py`
- SQLite execution check for migration `029_networking_profile_readiness.sql`.

Known baseline failure, unchanged:

- `verificar_mvp.py` -> `FALLO: La inscripcion publica no genero portal`.

## Non-blocking limitations

- Readiness dimensions are intentionally small and controlled. There is no arbitrary form builder.
- Structured taxonomy remains the V1 function/seniority foundation plus explicit offers/seeks text; no matching, ranking or semantic inference was added.
- The admin readiness list is limited to incomplete profiles and omits public profile IDs/channel values to avoid creating a directory surface.
