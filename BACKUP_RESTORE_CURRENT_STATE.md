# BACKUP_RESTORE_CURRENT_STATE

Fecha: 2026-07-28T18:27:05+00:00

Commit: 8fb67e53973321e5ada7762546ad119eb0d9ada4

Topologia evaluada:

- Staging Docker local.
- PostgreSQL: contenedor `bitora-staging-postgres`.
- App: contenedor `bitora-staging-app`.
- Worker: contenedor `bitora-staging-worker`.
- Storage persistente: volumen Docker montado en `/bitora/storage`.
- Backups: volumen Docker montado en `/bitora/backups` y `/bitora/pgbackups`.

Estado previo:

- Backup BDF existente: dump SQL simple sobre staging principal.
- Restore BDF existente: restauracion destructiva sobre staging principal.
- Brecha detectada: faltaba restauracion aislada con comparacion de manifiestos y storage.

Propuesta aplicada:

- Dataset multitenant real identificado por `BACKUP-RESTORE-LIVE-20260728-182640`.
- Backup PostgreSQL real con `pg_dump -Fc`.
- Backup de storage real con `tar.gz`.
- Restore en base PostgreSQL aislada.
- Restore de storage en ruta aislada.
- Validacion por manifiestos pre/post.

Secretos: no se imprimen ni se escriben en reportes.
