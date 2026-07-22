# BITORA Release Certification Report

Fecha: 2026-07-22

## Objetivo

Registrar el estado de certificacion despues de auditar y endurecer la etapa WhatsApp Cloud API Live.

## Estado actual

```text
Release global: NO APROBADA
Motivo: quedan gates live externos y pruebas prolongadas pendientes.
Google OAuth Live: PASSED
WhatsApp Live: NO CERTIFICADO
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

Google dentro de BSTF:

```text
google_oauth_http_flow: passed
google_oauth_state_security: passed
google_oauth_multitenant_isolation: passed
google_oauth_refresh_contract: passed
google_oauth_backup_restore: passed
google_oauth_multitenant_live: passed
google_oauth_live: passed
```

## Gates aun pendientes

Estos gates siguen pendientes y explican por que la Release global no se declara certificada:

```text
email_organization_live: omitted en esta corrida de contenedor por falta de evidencia local en ese entorno
whatsapp_organization_live: omitted
webhook_tenant_resolution_live: omitted
disaster_recovery_live: omitted
endurance_24h: omitted
upgrade_from_previous_version: omitted
```

Nota: Email Live ya fue certificado en una etapa anterior, pero la corrida actual dentro del contenedor no tenia la evidencia `email_multitenant_live` disponible en `output/live_integrations`. Debe reejecutarse o persistirse esa evidencia antes de una Release final completa.

## WhatsApp Cloud API

La auditoria de WhatsApp confirma que el flujo tecnico base ya existe:

```text
Proveedor Meta desacoplado: PASSED
Cola communication_queue: PASSED
Worker whatsapp.send: PASSED
Safe Mode WhatsApp: PASSED
Asignacion por organization_id/event_id/integration_id: PASSED
Webhook endpoint preparado: PASSED contract
```

La certificacion live sigue pendiente porque no se ejecuto todavia un envio real contra Meta ni se confirmo recepcion en telefono autorizado.

Se incorporo una correccion de certificacion:

```text
verificar_whatsapp_multitenant_live.py ahora exige:
- envio iniciado desde BITORA;
- job procesado por worker;
- message_id devuelto por Meta;
- Safe Mode activo;
- recepcion real confirmada o webhook delivered/read.
```

Estado:

```text
whatsapp_organization_live: OMITTED
webhook_tenant_resolution_live: OMITTED
WHATSAPP LIVE NO CERTIFICADO
```

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
- Certificar WhatsApp Live.
- Certificar webhooks tenant-aware live.
- Ejecutar Disaster Recovery live.
- Ejecutar Endurance 24 horas.
- Ejecutar upgrade desde version anterior.

## Decision tecnica

```text
GOOGLE OAUTH LIVE CERTIFICADO
RELEASE GLOBAL NO CERTIFICADA TODAVIA
```
