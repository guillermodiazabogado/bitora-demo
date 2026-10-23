# BITORA V4.7 History Architecture

The history layer is read-oriented and derives from the existing `audit_logs` table.

Main service:

`backend/services/history_autocomplete.py`

Endpoints:

- `GET /api/events/{event_id}/history`
- `GET /api/history/entities/{entity_type}/{entity_id}?event_id={event_id}`

The service validates that the event belongs to the active organization before reading. Normal responses include safe summaries only. Raw payload is returned only when the caller has `history.sensitive.read`.
