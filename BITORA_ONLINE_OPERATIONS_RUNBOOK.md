# BITORA Online Operations Runbook

Fecha: 2026-08-04

## Operacion diaria

- Verificar health.
- Revisar logs.
- Revisar jobs fallidos.
- Confirmar backup reciente.
- Confirmar Safe Mode segun entorno.

## Incidentes

Ante duda:

1. Pausar comunicaciones.
2. Pausar workers externos.
3. Tomar backup.
4. Revisar auditoria.
5. Validar aislamiento.
6. Restaurar solo desde artefactos verificados.

## Integraciones

Las integraciones live se mantienen tenant-aware. No compartir tokens entre organizaciones.

## Endurance

`endurance_24h` queda diferido a prompt posterior.
# Render staging operations update - 2026-08-04

## Estado actual

`READY FOR HOSTING CREDENTIALS`

## Primer despliegue Render

1. Sincronizar `render.yaml` desde la rama `deployment/v4-online`.
2. Confirmar `bitora-staging-postgres`.
3. Confirmar `bitora-staging`.
4. Cargar `BITORA_ADMIN_BOOTSTRAP_USER`.
5. Cargar `BITORA_ADMIN_BOOTSTRAP_PASSWORD`.
6. No habilitar Email/WhatsApp live.
7. Validar `/health`.
8. Validar `/ready`.
9. Ejecutar smoke remoto.
10. Generar backup de PostgreSQL.

## Controles de seguridad

- No usar `bitora-demo.onrender.com` como staging V4.
- No cargar `.env` en Git.
- No activar Live Mode.
- No ejecutar Endurance.
- No desplegar produccion.
