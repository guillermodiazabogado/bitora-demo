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
