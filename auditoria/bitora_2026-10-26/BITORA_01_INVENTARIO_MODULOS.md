# BITORA — Inventario de módulos

## Tecnologías y puntos de entrada

- Backend: Python, servidor HTTP de biblioteca estándar, `server.py`.
- Persistencia: SQLite y adaptador/pool PostgreSQL.
- Frontend: HTML, CSS y JavaScript sin framework.
- Procesos: servidor embebido, worker y simulador.
- Almacenamiento: local y S3/R2 mediante boto3.
- Despliegue: Docker, Render y documentación Railway.
- Dependencias: Pillow, ReportLab, psycopg, cryptography y boto3.

## Inventario funcional

| Dominio | Implementación localizada | Estado auditado |
|---|---|---|
| Eventos y configuración | `server.py`, repositorio de eventos, UI administrativa | IMPLEMENTADA SIN VALIDACIÓN |
| Participantes e inscripción | Repositorios, `/api/register`, formularios públicos | IMPLEMENTADA SIN VALIDACIÓN |
| Credencial y QR | Servicios `qr.py`, `qrcodegen.py`, exportaciones SVG/PNG/PDF | IMPLEMENTADA SIN VALIDACIÓN |
| Reservas/lista de espera | Servicios y repositorios dedicados | IMPLEMENTADA SIN VALIDACIÓN |
| Recepción y acreditación | UI y endpoint `/api/validate` | PARCIAL |
| Accesos V5.1 | `access_state_engine.py` | PARCIAL: shadow |
| Certificados V4.3 | `certificates.py`, migración 018 | IMPLEMENTADA SIN VALIDACIÓN |
| Encuestas V4.4 | `surveys.py`, migración 019 | IMPLEMENTADA SIN VALIDACIÓN |
| Speakers y zonas | Servicios y pantallas dedicadas | IMPLEMENTADA SIN VALIDACIÓN |
| Networking | `networking.py` y cuatro interfaces web | IMPLEMENTADA SIN VALIDACIÓN |
| Comunicaciones | Email, WhatsApp, automatización, webhooks | PARCIAL/BLOQUEADA |
| Empresas/delegaciones | `company_delegation.py`, migración 039 | PARCIAL |
| Vouchers | `entitlements_vouchers.py`, migración 040 | PARCIAL |
| Lead Retrieval | `lead_retrieval.py`, migración 041 | PARCIAL |
| Logística vehicular | `vehicle_logistics.py`, migración 042 | PARCIAL |
| Command Center | `command_center.py`, migración 043, endpoint y UI | IMPLEMENTADA SIN VALIDACIÓN |
| Venue Map | `venue_map.py`, migración 044 | PARCIAL |
| Device/Edge | `edge_sync.py`, `event_edge.py`, migraciones 038/045 | PARCIAL/BLOQUEADA |
| Backups | `backup.py`, storage local/S3 | IMPLEMENTADA SIN VALIDACIÓN |
| Android | Directorio sin archivos | NO IMPLEMENTADA |

## Configuración pendiente para operación real

- Runtime Python reproducible.
- PostgreSQL externo y conjunto completo de migraciones.
- Almacenamiento S3/R2 y restauración aislada.
- Secretos de sesiones, encuestas, speakers e integraciones.
- Proveedores reales de email y WhatsApp.
- Cliente Edge y dispositivos físicos.
- Observabilidad y almacén compartido de sesiones.
