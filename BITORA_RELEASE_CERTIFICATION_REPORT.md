# BITORA Release Certification Report

Fecha: 2026-07-28

## Objetivo

Registrar el estado de certificacion despues de ejecutar WhatsApp Cloud API Live y Meta WhatsApp Webhooks Live desde BITORA.

## Estado actual

```text
Release global: NO APROBADA
Motivo: quedan gates live externos y pruebas prolongadas pendientes.
Google OAuth Live: PASSED
WhatsApp Live: PASSED
WhatsApp Webhook Live: PASSED
```

## Entorno BDF local

```text
Docker: PASSED
Docker Compose: PASSED
PostgreSQL: PASSED
Aplicacion BITORA: PASSED
Worker separado: PASSED
Monitor: PASSED
Storage persistente: PASSED
Safe Mode: PASSED
Backup local: PASSED
Restore local: PASSED
Health: PASSED
```

## Google OAuth Live

La etapa Google OAuth Live fue ejecutada y certificada despues de conectar una aplicacion Google Cloud de staging.

Resultado:

```text
google_oauth_live: PASSED
google_oauth_multitenant_live: PASSED
```

Evidencia:

```text
OAuth iniciado desde BITORA: PASSED
Consentimiento Google real: PASSED
Callback real: PASSED
Userinfo live: PASSED
Refresh live: PASSED
Revocacion/desconexion: PASSED
Reconexion: PASSED
Auditoria: PASSED
tokens_exposed: 0
cross_event_assignments: 0
account_email_masked: gui***@gmail.com
```

## Correcciones incorporadas

```text
Scope normalization para Google: PASSED
Sanitizacion de callback OAuth en logs: PASSED
Verificador live Google actualizado contra esquema real PostgreSQL: PASSED
```

## BSTF Release ejecutado

Comando ejecutado dentro del contenedor staging:

```text
python run_bitora_supertest.py --release
```

Resultado general:

```text
approved: false
weighted_average: 70.1
```

WhatsApp dentro de BSTF:

```text
whatsapp_organization_live: omitted en esta corrida por falta de evidencia local `whatsapp_multitenant_live`
webhook_tenant_resolution_live: passed
webhooks_multitenant_live: passed
```

## WhatsApp Webhooks Live

La etapa Meta WhatsApp Webhooks Live fue ejecutada contra Meta usando una URL publica temporal de Cloudflare Tunnel apuntando solo al endpoint webhook de BITORA.

Resultado:

```text
webhook_tenant_resolution_live: PASSED
Meta challenge: PASSED
Meta POST real: PASSED
Firma X-Hub-Signature-256: PASSED
Evento recibido: delivered
Tenant resolution: PASSED
Estado actualizado: PASSED
Auditoria: PASSED
Idempotencia: PASSED
Cruces multi-tenant: 0
Firmas invalidas aceptadas: 0
Secretos expuestos: 0
```

Evidencia sanitizada:

```text
message_id: wamid***DNAA=
job_id: 23
queue_id: 165
organization_id: 1
event_id: 147
integration_id: 30
evidence_file: output/live_integrations/webhooks_multitenant_live.json
```

## Gates aun pendientes

Estos gates siguen pendientes y explican por que la Release global no se declara certificada:

```text
email_organization_live: omitted en esta corrida de contenedor por falta de evidencia local en ese entorno
google_oauth_live: omitted en esta corrida de contenedor por falta de evidencia local en ese entorno
disaster_recovery_live: omitted
endurance_24h: omitted
upgrade_from_previous_version: omitted
```

Nota: Email Live y Google OAuth Live fueron certificados en etapas anteriores, pero la corrida actual dentro del contenedor no tenia esas evidencias disponibles en `output/live_integrations`. Deben reejecutarse o persistirse antes de una Release final completa.

## WhatsApp Cloud API

La etapa WhatsApp Cloud API Live fue ejecutada contra Meta desde el flujo real de BITORA.

```text
Proveedor Meta desacoplado: PASSED
Cola communication_queue: PASSED
Worker whatsapp.send: PASSED
Safe Mode WhatsApp: PASSED
Asignacion por organization_id/event_id/integration_id: PASSED
Meta message_id: PASSED
Recepcion real en telefono autorizado: PASSED
Auditoria: PASSED
Cruces multi-tenant: 0
Destinatarios no autorizados: 0
Tokens expuestos: 0
Duplicados atribuibles a BITORA: 0
```

Evidencia sanitizada:

```text
whatsapp_organization_live: PASSED
message_id: wamid***1QwA=
job_id: 12
queue_id: 147
organization_id: 1
event_id: 124
integration_id: 24
receipt_source: manual_operator_confirmation
```

Nota: en la corrida BSTF posterior a webhooks, `whatsapp_organization_live` figura omitido porque el runner espera evidencia en un archivo distinto al generado durante la certificacion manual anterior. La certificacion live original de WhatsApp se mantiene documentada arriba, pero debe persistirse o reejecutarse para una Release final completamente limpia.

## Seguridad

```text
Secretos versionados: 0
Tokens OAuth expuestos: 0
Authorization code en logs nuevos: redacted
Tokens WhatsApp expuestos: 0
Datos personales en reportes: enmascarados
Webhook payloads completos en reportes: 0
```

## Riesgos pendientes

- Rotar el Client Secret de Google antes de uso prolongado o productivo.
- Reejecutar Email Live en el mismo entorno de certificacion final.
- Ejecutar Disaster Recovery live.
- Ejecutar Endurance 24 horas.
- Ejecutar upgrade desde version anterior.

## Decision tecnica

```text
GOOGLE OAUTH LIVE CERTIFICADO
WHATSAPP LIVE CERTIFICADO
WHATSAPP WEBHOOK LIVE CERTIFICADO
RELEASE GLOBAL NO CERTIFICADA TODAVIA
```
