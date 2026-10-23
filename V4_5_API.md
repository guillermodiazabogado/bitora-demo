# BITORA V4.5 - API

Endpoints administrativos:

- `GET /api/speakers?event_id={id}`
- `GET /api/speakers/{speaker_id}?event_id={id}`
- `POST /api/speakers`
- `PATCH/POST /api/speakers/{speaker_id}`
- `POST /api/speakers/{speaker_id}/publish`
- `POST /api/speakers/{speaker_id}/archive`
- `POST /api/events/{event_id}/speakers`
- `POST /api/events/{event_id}/speakers/{speaker_id}/activities`
- `POST /api/speakers/{speaker_id}/access-token`
- `POST /api/speakers/{speaker_id}/documents`

Endpoints publicos:

- `GET /api/public/events/{event_id}/speakers`
- `GET /api/public/speakers/{public_id}`
- `GET /api/public/speakers/access/{token}`
- `POST /api/public/speakers/access/{token}/update`
