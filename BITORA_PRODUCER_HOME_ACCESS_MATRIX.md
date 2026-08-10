# BITORA Producer Home Access Matrix

Branch: feature/v4.0.2-producer-permissions-polish
Purpose: align Producer Home cards with effective event permissions. The Home visual does not grant access; backend RBAC remains authoritative.

| Card | Route/View | Required module | Required action | Feature flag / event dependency | Backend protection | Status |
|---|---|---:|---:|---|---|---|
| Panel de Control | `#dashboard` | `dashboard` | n/a | active event | event access + dashboard APIs | CORRECT |
| Inscripciones | `#register` | `register` | n/a | project `registration` | event access + registration APIs | CORRECT |
| Recepcion | `#reception` | `reception` | n/a | project `reception` | event access + accreditation APIs | CORRECT |
| Acceso | `#access` | `access` | n/a | project `access` | event access + access APIs | CORRECT |
| Asistencia | `/attendance-closure.html` | n/a | `attendance.read` | `attendance_closure_eligibility_v4_enabled` + `activities_enabled` | `/api/events/{id}/attendance*` RBAC + feature checks | CORRECT |
| Actividades | `#agenda` | `agenda` | n/a | project `agenda` + `activities_enabled` | event access + agenda APIs | CORRECT |
| Speakers | `/speakers-v4.html` | `speakers` | `speakers.read` | `speakers_v4_enabled` | speakers endpoints require feature + event permission | CORRECT |
| Certificados | `/certificates-v4.html` | `certificates` | `certificates.read` | `certificates_v4_enabled` | certificate endpoints require feature + event permission | CORRECT |
| Encuestas | `/surveys-v4.html` | `surveys` | `surveys.read` | `surveys_v4_enabled` | survey endpoints require feature + event permission | CORRECT |
| Comunicaciones | `#communications` | `communications` | `communications.view` | `communications_automation_v4_enabled` | communication endpoints require feature + event permission | CORRECT |
| Operations Center | `/operations-center-v4.html` | n/a | `operations_center.read` | `operations_center_v4_enabled` | operations endpoints require feature + event permission | CORRECT |
| Analytics | `/analytics-v4.html` | n/a | `analytics.read` | `analytics_v4_enabled` | analytics endpoints require feature + event permission | CORRECT |

Notes:
- Event features and V4 feature flags are separate from RBAC.
- Cards with both module and action now require both.
- Cards with direct V4 pages now require the same feature flag family as their backend APIs.
- Direct URLs remain subject to backend/session/RBAC checks; hiding a card is not a security boundary.
