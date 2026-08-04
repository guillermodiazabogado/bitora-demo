# BITORA Render Staging Deployment Guide

Estado: `READY FOR HOSTING APPROVAL`

## Objetivo

Mantener y completar `bitora-staging` en Render usando Docker y PostgreSQL real, sin activar produccion, sin ejecutar Endurance 24h y sin habilitar comunicaciones live.

## Blueprint

Archivo: `render.yaml`

Recursos definidos:

- Web service: `bitora-staging`
- Database: `bitora-staging-postgres`
- Branch: `deployment/v4-online`
- Runtime: Docker
- Health check: `/health`
- Readiness check operativo: `/ready`

## Variables no secretas clave

- `APP_ENV=staging`
- `BITORA_ENV=staging`
- `QR_DB_ENGINE=postgres`
- `BASE_URL=https://bitora-staging.onrender.com`
- `BITORA_PUBLIC_URL=https://bitora-staging.onrender.com`
- `HTTPS_REQUIRED=true`
- `QR_REQUIRE_LOGIN=true`
- `BITORA_SAFE_MODE=true`
- `BITORA_LIVE_MODE=false`
- `BITORA_COMMUNICATIONS_LIVE_MODE_ENABLED=false`
- `EMAIL_ENABLED=false`
- `WHATSAPP_ENABLED=false`

## Variables secretas

Render debe generarlas o pedirlas en dashboard. No se versionan:

- `SECRET_KEY`
- `SESSION_SECRET`
- `BITORA_INTEGRATION_ENCRYPTION_KEY`
- `BITORA_HEALTH_TOKEN`
- `BITORA_ADMIN_BOOTSTRAP_USER`
- `BITORA_ADMIN_BOOTSTRAP_PASSWORD`

## Pasos en Render

1. Abrir Render Dashboard.
2. Crear Blueprint desde GitHub.
3. Seleccionar repo `guillermodiazabogado/bitora-demo`.
4. Seleccionar rama `deployment/v4-online`.
5. Confirmar archivo `render.yaml`.
6. Revisar que el servicio sea `bitora-staging`.
7. Revisar que la base sea `bitora-staging-postgres`.
8. Cargar `BITORA_ADMIN_BOOTSTRAP_USER`.
9. Cargar `BITORA_ADMIN_BOOTSTRAP_PASSWORD` con al menos 12 caracteres y no trivial.
10. Confirmar costos si Render exige plan pago.
11. Crear/sincronizar Blueprint.
12. Esperar build y deploy.
13. Validar `/health`.
14. Validar `/ready`.

## Estado actual Render

El Blueprint ya fue creado y sincronizado.

Recursos actuales:

- Blueprint: `bitora-v4-staging`
- Web service: `bitora-staging`
- Web service ID: `srv-d9p5pn6gekts73f8u24g`
- PostgreSQL: `bitora-staging-postgres`
- URL publica: `https://bitora-staging.onrender.com`
- Plan web actual: `Free`

Validaciones ejecutadas:

- HTTPS: PASSED
- `/health`: PARTIAL, `backup=missing`
- `/ready`: PARTIAL, warning de storage persistente
- Login online: PASSED
- UI online: PASSED
- Safe Mode: ON
- Live Mode: OFF

## Bloqueo de disco persistente

Render informa que Persistent Disks no estan disponibles en instancias Free. Para certificar staging online completo, se debe aprobar una de estas opciones:

1. upgrade a un plan Render con Persistent Disk;
2. storage externo persistente compatible;
3. mantener el entorno como demo online no certificada.

No mergear PR `#12` hasta completar:

- storage persistente;
- backup remoto;
- restore remoto aislado;
- restart persistence.

## Validaciones post-deploy

- La respuesta debe declarar `env: staging`.
- `QR_DB_ENGINE` debe ser PostgreSQL.
- `/ready` debe tener `configuration=true`, `database=true`, `migrations=true`, `storage=true`, `safe_mode=true`, `live_mode_off=true`.
- No debe existir salida que muestre PINs demo.
- No debe quedar Live Mode activo.

## No hacer

- No usar `bitora-demo.onrender.com` como evidencia de staging V4.
- No activar Email/WhatsApp live en este sprint.
- No crear `bitora-v4.0.0` nuevo ni mover tags.
- No ejecutar Endurance.
- No desplegar produccion.
