# BITORA V5.7.1 Enterprise UI + Venue Map Report

## Architecture

V5.7.1 adds an Enterprise UI foundation and reusable Venue Map model on top of V5.7 Command Center. It is additive and feature-flagged. It does not change V4 contracts or V5 access authority.

## Design System

Centralized tokens and component rules were added:

- `V5_7_1_DESIGN_SYSTEM.css`
- `V5_7_1_DESIGN_SYSTEM.md`

## Venue Model

New concepts:

- Enterprise Venue;
- Venue Map;
- Venue Map Element;
- Event Map Configuration.

Venue maps can be reused across events while event configurations keep event-specific overlays and active layers separate.

## Map Architecture

The map foundation supports:

- sanitized SVG text or asset reference;
- clickable overlays;
- layer model;
- projected/access/camera occupancy semantics;
- PRE_EVENT / LIVE / POST_EVENT modes.

## PRE/LIVE/POST

Modes:

- PRE_EVENT: projected demand and readiness;
- LIVE: real access flow and operational alerts;
- POST_EVENT: analysis foundation.

## Security

SVG sanitization rejects:

- scripts;
- JavaScript URLs;
- inline event handlers;
- foreignObject;
- oversize SVG payloads.

## Privacy

The Command Center overview remains aggregated and does not expose QR tokens, emails or device secrets.

## Performance

Measured locally in SQLite temp DB by `verificar_v5_7_1_enterprise_ui_venue_map.py`.

## Tests

Verifier:

- `verificar_v5_7_1_enterprise_ui_venue_map.py`

## Visual Review

Artifacts:

- `V5_7_1_PRE_EVENT_DESKTOP.html`
- `V5_7_1_LIVE_DESKTOP.html`
- `V5_7_1_LIVE_CRITICAL_ALERT.html`
- `V5_7_1_MAP_SELECTED_ZONE.html`
- `V5_7_1_DEVICES_VISUAL.html`
- `V5_7_1_TABLET.html`
- `V5_7_1_MOBILE_SUMMARY.html`

## Known Gaps

- Real uploaded map UI is not yet exposed in admin routes.
- Camera occupancy source is still unavailable unless configured later.
- Icons are represented by component mappings/design rules, not a bundled icon package.

## Rollback

Disable:

- `enterprise_ui_v5_7_1`
- `venue_map_v5_7_1`

V4/V5.7 remains operational.
