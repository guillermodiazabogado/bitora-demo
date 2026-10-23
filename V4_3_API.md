# V4.3 API

Endpoints implementados:

- `GET /api/certificate-types?event_id=...`
- `POST /api/certificate-types`
- `GET /api/certificate-templates?event_id=...`
- `POST /api/certificate-templates`
- `POST /api/certificate-templates/{template_id}/versions`
- `POST /api/certificate-templates/{template_id}/versions/{version_id}/publish`
- `POST /api/certificate-templates/{template_id}/versions/{version_id}/preview`
- `GET /api/events/{event_id}/certificates`
- `GET /api/events/{event_id}/certificates/{issuance_id}`
- `GET /api/events/{event_id}/certificates/{issuance_id}/download`
- `POST /api/events/{event_id}/certificates/issue`
- `POST /api/events/{event_id}/certificates/batches`
- `POST /api/events/{event_id}/certificates/{issuance_id}/revoke`
- `POST /api/events/{event_id}/certificates/{issuance_id}/reissue`
- `GET /api/public/certificates/verify/{token}`
