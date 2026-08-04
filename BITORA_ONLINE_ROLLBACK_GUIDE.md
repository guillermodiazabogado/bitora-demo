# BITORA Online Rollback Guide

Fecha: 2026-08-04

## Estrategia

Rollback online debe priorizar:

1. Detener despliegue defectuoso.
2. Mantener Safe Mode ON.
3. Mantener Live Mode OFF.
4. Volver a imagen anterior si no hubo migracion irreversible.
5. Restaurar backup si la migracion o datos quedaron comprometidos.

## Prohibiciones

- No ejecutar rollback destructivo en produccion sin backup.
- No reactivar workers externos antes de validar datos.
- No reintentar comunicaciones historicas automaticamente.

## Validacion posterior

- Health.
- Login.
- RBAC.
- Multitenant.
- Storage.
- Jobs.
- Auditoria.
