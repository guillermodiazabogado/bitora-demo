# BITORA V4.7 API

History:

- `GET /api/events/{event_id}/history`
- `GET /api/history/entities/{entity_type}/{entity_id}?event_id={event_id}`

Autocomplete:

- `GET /api/autocomplete/participants?event_id={event_id}&q={text}`
- `GET /api/autocomplete/speakers?event_id={event_id}&q={text}`
- `GET /api/autocomplete/organizations?event_id={event_id}&q={text}`
- `GET /api/autocomplete/cities?event_id={event_id}&q={text}`
- `GET /api/autocomplete/roles?event_id={event_id}&q={text}`

Duplicates:

- `GET /api/duplicate-candidates?event_id={event_id}&email={email}`
- `POST /api/duplicate-candidates/{person_id}/confirm`
- `POST /api/duplicate-candidates/{person_id}/dismiss`

Write bodies for duplicate decisions include:

```json
{
  "event_id": 1,
  "reason": "Coincidencia verificada"
}
```
