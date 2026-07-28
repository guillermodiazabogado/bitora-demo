# BITORA Final Staging Integrations Revalidation Report

Fecha: 2026-07-28 13:28:08 -03:00

Identificador de corrida:

```text
FINAL-STAGING-REVALIDATION-20260728-1328
```

Commit:

```text
87252c97429d44b1149737c873285a308d96f095
```

## Resultado Consolidado

```text
FINAL STAGING INTEGRATIONS REVALIDATION: PASSED
```

La revalidacion se ejecuto sobre el mismo staging final donde ya estaban certificados WhatsApp Live y Webhooks Live.

## Email Live

```text
email_multitenant_live: PASSED
email_organization_live: PASSED en BSTF
Proveedor: Resend
Modo: live
job_id: 38
queue_id: 187
organization_id: 1
event_id: 175
integration_id: 41
message_id: a8fe10***7d2350
Safe Mode: PASSED
Auditoria: PASSED
Cruces multi-tenant: 0
Destinatarios no autorizados: 0
Secretos expuestos: 0
```

Nota: la prueba live valida envio real aceptado por Resend, cola, worker, Safe Mode y auditoria. La confirmacion historica de bandeja real ya consta en `EMAIL_LIVE_CERTIFICATION_REPORT.md`.

## Google OAuth Live

```text
google_oauth_multitenant_live: PASSED
google_oauth_live: PASSED en BSTF
Proveedor: Google OAuth
organization_id: 3
integration_id: 5
Cuenta: gui***@gmail.com
Userinfo live: PASSED
Refresh live: PASSED
Refresh antes de userinfo por access token vencido: PASSED
Token encryption: PASSED
Auditoria: PASSED
Cruces multi-tenant: 0
Tokens expuestos: 0
```

La revalidacion detecto access token vencido y ejecuto refresh real con refresh token cifrado antes de userinfo. Eso refleja el comportamiento esperado de una integracion OAuth persistente.

## WhatsApp Live

```text
whatsapp_multitenant_live: PASSED
whatsapp_organization_live: PASSED en BSTF
Proveedor: Meta Cloud API
job_id: 39
queue_id: 188
organization_id: 1
event_id: 177
integration_id: 43
message_id: wamid***xNgA=
Safe Mode: PASSED
Destinatario forzado: PASSED
Recepcion confirmada: PASSED
Auditoria: PASSED
Cruces multi-tenant: 0
Duplicados atribuibles a BITORA: 0
Tokens expuestos: 0
```

## WhatsApp Webhook Live

```text
webhooks_multitenant_live: PASSED
webhook_tenant_resolution_live: PASSED en BSTF
Proveedor tunel: Cloudflare Tunnel temporal
Meta challenge: PASSED
Meta POST real: PASSED
Evento recibido: delivered
job_id: 37
queue_id: 186
organization_id: 1
event_id: 174
integration_id: 40
message_id: wamid***3MwA=
Firma X-Hub-Signature-256: PASSED
Tenant resolution: PASSED
Message state update: PASSED
Idempotencia: PASSED
Auditoria: PASSED
Cruces multi-tenant: 0
Firmas invalidas aceptadas: 0
Secretos expuestos: 0
```

## Convivencia

```text
Cruces entre integraciones: 0
Cruces multi-tenant: 0
Jobs duplicados: 0
Auditorias contradictorias: 0
Safe Mode: PASSED
Secretos expuestos: 0
```

## BSTF Release

Resultado de la corrida `run_bitora_supertest.py --release`:

```text
approved: false
weighted_average: 70.1
email_organization_live: PASSED
google_oauth_live: PASSED
whatsapp_organization_live: PASSED
webhook_tenant_resolution_live: PASSED
```

La Release global no se declara aprobada porque quedaron fallas/omisiones fuera de esta etapa:

```text
seguridad_basica: FAILED
multievent_isolation_20_events: FAILED
backup_multitenant_live: OMITTED
restore_multitenant_live: OMITTED
disaster_recovery_live: OMITTED
endurance_24h: OMITTED
upgrade_from_previous_version: OMITTED
```

## Decision De Esta Etapa

```text
FINAL STAGING INTEGRATIONS REVALIDATION: PASSED
BITORA RELEASE FINAL: NO DECLARADA
```

## Proximo Paso

```text
Upgrade Certification desde version anterior
```
