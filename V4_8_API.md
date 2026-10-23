# V4.8 API

- `GET /api/events/{event_id}/operations-center`
- `GET /api/events/{event_id}/operations-center/{readiness|metrics|alerts|incidents|tasks}`
- `POST/PATCH /api/events/{event_id}/operations-center/incidents[/{id}]`
- `POST/PATCH /api/events/{event_id}/operations-center/tasks[/{id}]`
- `POST /api/events/{event_id}/operations-center/alerts/{id}/{acknowledge|resolve}`

All routes require the feature flag, event ownership and the corresponding
RBAC permission.

