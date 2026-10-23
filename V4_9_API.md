# BITORA V4.9 API

Routes are event-scoped:

- `GET /api/events/{event_id}/communications-v4`
- `GET /api/events/{event_id}/communications-v4/templates`
- `GET /api/events/{event_id}/communications-v4/segments`
- `GET /api/events/{event_id}/communications-v4/campaigns`
- `GET /api/events/{event_id}/communications-v4/recipients`
- `GET /api/events/{event_id}/communications-v4/messages`
- `GET /api/events/{event_id}/communications-v4/deliveries`
- `GET /api/events/{event_id}/communications-v4/automations`
- `POST /api/events/{event_id}/communications-v4/templates`
- `POST /api/events/{event_id}/communications-v4/templates/{template_id}/update`
- `POST /api/events/{event_id}/communications-v4/templates/{template_id}/approve`
- `POST /api/events/{event_id}/communications-v4/templates/{template_id}/preview`
- `POST /api/events/{event_id}/communications-v4/segments`
- `POST /api/events/{event_id}/communications-v4/segments/{segment_id}/preview`
- `POST /api/events/{event_id}/communications-v4/campaigns`
- `POST /api/events/{event_id}/communications-v4/campaigns/{campaign_id}/validate`
- `POST /api/events/{event_id}/communications-v4/campaigns/{campaign_id}/approve`
- `POST /api/events/{event_id}/communications-v4/campaigns/{campaign_id}/execute`
- `POST /api/events/{event_id}/communications-v4/campaigns/{campaign_id}/enqueue`
- `POST /api/events/{event_id}/communications-v4/automations`
- `POST /api/events/{event_id}/communications-v4/automations/{automation_id}/activate`
- `POST /api/events/{event_id}/communications-v4/automations/{automation_id}/pause`
