# V4.2 API

## Reglas

- `GET /api/events/{event_id}/attendance-rule-sets`
- `POST /api/events/{event_id}/attendance-rule-sets`
- `POST /api/events/{event_id}/attendance-rule-sets/{rule_set_id}/versions`
- `POST /api/events/{event_id}/attendance-rule-sets/{rule_set_id}/versions/{version_id}/publish`

## Cierres

- `GET /api/events/{event_id}/attendance-closures`
- `POST /api/events/{event_id}/attendance-closures`
- `GET /api/events/{event_id}/attendance-closures/{closure_id}`
- `POST /api/events/{event_id}/attendance-closures/{closure_id}/reopen`
- `GET /api/events/{event_id}/attendance-closures/{closure_id}/evaluations`

## Elegibilidad

- `GET /api/events/{event_id}/participants/{participant_id}/eligibility`
- `POST /api/events/{event_id}/participants/{participant_id}/eligibility/override`

Todas las escrituras sensibles usan idempotency key.

## UI QA

Pantalla minima:

- `/attendance-closure.html`

No es un dashboard final ni reemplaza QA backend.
