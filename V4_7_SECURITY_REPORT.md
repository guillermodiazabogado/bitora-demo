# BITORA V4.7 Security Report

Controls implemented:

- Feature flag disabled by default.
- Event ownership validation before history and autocomplete.
- Entity type allowlist.
- Private data hidden unless permission is present.
- Duplicate decisions are scoped to organization and event.
- Raw audit payload is not returned unless explicitly requested by a privileged caller.
- Backup/restore remaps `candidate_person_id`.

Validation:

- `verificar_v4_7_history_autocomplete_foundation.py`: PASSED.
- Secret scan: no findings during implementation validation.
