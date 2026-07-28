# BACKUP_RESTORE_RUNBOOK

## Proposito

Certificar backup y restore multitenant en staging sin afectar el staging activo ni disparar integraciones externas.

## Prerrequisitos

- Docker y Docker Compose activos.
- `deployment/staging/.env.staging` configurado con `APP_ENV=staging`.
- PostgreSQL de staging saludable.
- App y worker saludables.
- Safe Mode activo.

## Comando De Certificacion

```bash
python deployment/scripts/certify_backup_restore_live.py
```

## Flujo

1. Crear dataset multitenant con 4 organizaciones, 20 eventos y 1.000 participantes.
2. Generar manifiesto pre-backup.
3. Ejecutar `pg_dump -Fc` desde el contenedor PostgreSQL.
4. Empaquetar storage persistente.
5. Restaurar la base en una base PostgreSQL nueva y aislada.
6. Restaurar storage en una ruta aislada.
7. Ejecutar validacion post-restore.
8. Escribir evidencia para BSTF.

## Seguridad Operativa

- No restaurar sobre staging principal.
- No versionar dumps, storage, logs crudos ni `.env.staging`.
- No imprimir tokens ni secretos.
- Mantener integraciones externas apagadas en el entorno restaurado.
- El worker no se inicia contra la base restaurada.

## Evidencia

- `output/live_integrations/backup_multitenant_live.json`
- `output/live_integrations/restore_multitenant_live.json`
- `output/live_integrations/backup_restore_multitenant_live.json`
