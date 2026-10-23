# BITORA V4.7 Backup Restore Report

Event backup now includes:

- `duplicate_resolution_decisions` scoped by `event_id`.

Restore behavior:

- `event_id` is remapped by the generic restore path.
- `candidate_person_id` is remapped through the people map.
- Audit logs continue to be restored through the existing controlled audit restore behavior.

Validation:

- Event backup and restore were executed by `verificar_v4_7_history_autocomplete_foundation.py`.
- Restored event preserved audit history and one duplicate decision.
