# BITORA Storage Architecture Report

Staging: https://bitora-staging.onrender.com  
Commit auditado: 24f891ff767c1d92bcdd7edb81c71e87caf8ab67  
Fecha: 2026-08-11

## Estado observado

`/health` reporta:

- Environment: staging
- Database: online
- Jobs: ok, pending 0, failed 0
- Storage backend: local
- Storage ready: true
- Backup: missing

`/ready` reporta:

- Configuration: true
- Database: true
- Migrations: true
- Storage: true
- Safe Mode: true
- Live Mode OFF: true
- Warning: Storage local requiere disco persistente y backup externo

## Topologia actual

| Componente | Estado |
| --- | --- |
| PostgreSQL | Persistente en Render Postgres |
| Filesystem local | Ephemeral en el contenedor web |
| Certificados/PDF | Generados en storage local configurado |
| Backups | Ruta configurada, pero health reporta backup missing |
| Uploads/exports | Dependientes de storage local si se generan |
| Secrets | Variables de entorno, no deben respaldarse en artefactos |

## Riesgo principal

El staging actual puede operar, pero el storage de archivos no esta certificado como persistente entre reinicios/redeploys porque Render no tiene Persistent Disk declarado en `render.yaml`.

## Bloqueo

Persistent storage final queda bloqueado por aprobacion de hosting si Render requiere habilitar Persistent Disk o storage externo pago.

Estado: PERSISTENCE BLOCKED BY HOSTING APPROVAL

## Confirmacion externa

Documentacion oficial de Render:

- Los Persistent Disks preservan solo los datos escritos bajo el mount path configurado.
- Los servicios web gratis no pueden adjuntar Persistent Disk para preservar cambios locales del filesystem.

Por eso, con el plan actual observado, el almacenamiento local de `/bitora/storage` y `/bitora/backups` no puede certificarse como persistente.

## Accion recomendada

Antes de certificar persistencia:

1. Habilitar Persistent Disk en Render o configurar storage externo autorizado.
2. Montar rutas separadas para storage y backups.
3. Reiniciar staging.
4. Verificar `/health` sin `backup=missing`.
5. Ejecutar backup real.
6. Restaurar en entorno aislado.
7. Validar certificados, archivos y checksums.
