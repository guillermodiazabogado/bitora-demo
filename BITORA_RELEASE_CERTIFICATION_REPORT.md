# BITORA Release Certification Report

Fecha: 2026-07-28

## Objetivo

Registrar el estado de certificacion despues de ejecutar WhatsApp Cloud API Live desde BITORA.

## Estado actual

```text
Release global: NO APROBADA
Motivo: quedan gates live externos y pruebas prolongadas pendientes.
Google OAuth Live: PASSED
WhatsApp Live: PASSED
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
whatsapp_organization_live: passed
stdout_tail: Evidencia live aprobada.
exit_code: 0
```

## Gates aun pendientes

Estos gates siguen pendientes y explican por que la Release global no se declara certificada:

```text
email_organization_live: omitted en esta corrida de contenedor por falta de evidencia local en ese entorno
google_oauth_live: omitted en esta corrida de contenedor por falta de evidencia local en ese entorno
webhook_tenant_resolution_live: omitted
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

Webhook endpoint preparado:

```text
webhook_tenant_resolution_live: OMITTED
```

Motivo: no se recibio webhook live `delivered/read` en una URL publica de BITORA durante esta etapa.

## Seguridad

```text
Secretos versionados: 0
Tokens OAuth expuestos: 0
Authorization code en logs nuevos: redacted
Tokens WhatsApp expuestos: 0
Datos personales en reportes: enmascarados
```

## Riesgos pendientes

- Rotar el Client Secret de Google antes de uso prolongado o productivo.
- Reejecutar Email Live en el mismo entorno de certificacion final.
- Certificar webhooks tenant-aware live.
- Ejecutar Disaster Recovery live.
- Ejecutar Endurance 24 horas.
- Ejecutar upgrade desde version anterior.

## Decision tecnica

```text
GOOGLE OAUTH LIVE CERTIFICADO
WHATSAPP LIVE CERTIFICADO
RELEASE GLOBAL NO CERTIFICADA TODAVIA
```
