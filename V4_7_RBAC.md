# BITORA V4.7 RBAC

New permissions:

- `history.read`
- `history.sensitive.read`
- `autocomplete.use`
- `autocomplete.private.use`
- `duplicates.read`
- `duplicates.resolve`
- `history.audit.read`

Initial assignment:

- Super Admin: full access.
- Productor: full V4.7 access.
- Coordinador: safe history/autocomplete and duplicate review.
- Visualizador: safe history/autocomplete only.

Backend permission checks are mandatory. UI visibility is not treated as authorization.
