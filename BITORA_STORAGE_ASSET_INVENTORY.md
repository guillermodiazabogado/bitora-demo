# BITORA Storage Asset Inventory

Fecha: 2026-08-11

| Asset type | Current path/key | Must persist? | Can be regenerated? | Current backup | Target storage |
| --- | --- | --- | --- | --- | --- |
| PostgreSQL structured data | Render Postgres | Yes | No | Provider/backup flow | PostgreSQL, not R2 |
| Certificates PDF | `events/{event_id}/certificates/*` | Yes | Partially | Event/full backup | Cloudflare R2 |
| Speaker attachments | `events/{event_id}/attachments/*` | Yes | No | Event/full backup | Cloudflare R2 |
| Event uploads | `events/{event_id}/uploads/*` | Yes | No | Event/full backup | Cloudflare R2 |
| Event exports | `events/{event_id}/exports/*` | Useful | Yes | Event/full backup | Cloudflare R2 when persistent |
| QR/generated credentials | `events/{event_id}/qr/*` and DB metadata | Yes | Partially | Event/full backup | Cloudflare R2 |
| Full backup bundles | `backups/*` | Yes | No | Self-contained | Cloudflare R2 |
| Event backup bundles | `backups/*` | Yes | No | Self-contained | Cloudflare R2 |
| Temporary runtime files | local temp | No | Yes | No | Local ephemeral |
| Cache | memory/local | No | Yes | No | Local/memory |
| Endurance artifacts | `artifacts/` local ignored | No for runtime | N/A | No | Local only, not Git |
| Logs crudos | Render logs/local ignored | Operational | N/A | No | Render/log backend |

## Clasificacion

MUST PERSIST:

- certificados;
- uploads;
- adjuntos;
- backups;
- assets generados con valor probatorio.

EPHEMERAL OK:

- cache;
- temporales;
- artifacts locales de pruebas;
- archivos intermedios regenerables.

REGENERABLE:

- algunos exports;
- previews;
- caches;
- representaciones derivadas de DB.
