# BITORA v1.0.0-rc.1 Release Notes

## Identificacion

```text
Version: bitora-v1.0.0-rc.1
Tipo: Release Candidate
Runtime certificado: 3e82a6ae0deddf64fd77ba16fb4721b21902b9b2
Fecha: 2026-07-28
Rama: main
```

## Estado

```text
Release Candidate: AUTHORIZED
Stable Release: NOT CERTIFIED
Endurance 24h: DEFERRED
```

## Alcance Funcional

Incluye nucleo multitenant, usuarios y permisos, comunicaciones, Email Live, Google OAuth Live, WhatsApp Live, Webhooks Live, Backup Multitenant Live, Restore Multitenant Live, Disaster Recovery Live y Upgrade From Previous Version.

## Certificaciones Aprobadas

```text
seguridad_basica
multievent_isolation_20_events
email_organization_live
google_oauth_live
whatsapp_organization_live
webhook_tenant_resolution_live
backup_multitenant_live
restore_multitenant_live
disaster_recovery_live
upgrade_from_previous_version
```

## Gate Pendiente

```text
endurance_24h: DEFERRED
```

Condicion para Release estable: ejecutar y aprobar Endurance 24h sobre el commit estable final congelado.

## Uso Autorizado

- Staging.
- QA.
- Pruebas internas.
- Pilotos controlados.
- Eventos supervisados.
- Demostraciones controladas.

## Uso No Autorizado

- Declarar Release estable certificada.
- Operacion critica sin monitoreo.
- Despliegue definitivo sin respaldo y runbooks.
- Eliminar evidencias.
- Mover o reemplazar el tag RC.

## Riesgos Residuales

- Estabilidad continua de 24 horas no certificada.
- Degradacion sostenida aun no medida.
- Cambios posteriores pueden exigir recertificacion parcial o completa.
