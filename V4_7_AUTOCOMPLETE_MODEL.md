# BITORA V4.7 Autocomplete Model

Autocomplete is scoped by organization and, where applicable, event.

Supported endpoints:

- `GET /api/autocomplete/participants?event_id={id}&q={text}`
- `GET /api/autocomplete/speakers?event_id={id}&q={text}`
- `GET /api/autocomplete/organizations?event_id={id}&q={text}`
- `GET /api/autocomplete/cities?event_id={id}&q={text}`
- `GET /api/autocomplete/roles?event_id={id}&q={text}`

Participant results mask email unless `autocomplete.private.use` is granted.

Queries shorter than two normalized characters return an empty list.
