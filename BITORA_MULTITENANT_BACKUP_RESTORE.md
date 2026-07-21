# Backup Y Restore Multi-Tenant Live

## Backup

```bash
python deployment/scripts/bdf.py backup
```

Debe incluir PostgreSQL, storage, manifiesto, checksum y commit.

## Restore

```bash
python deployment/scripts/bdf.py restore <archivo> --yes
```

Despues de restaurar:

- safe mode activo;
- jobs externos pausados o pendientes de revision;
- integraciones externas requieren validacion;
- cero comunicaciones automaticas.

## Pruebas

```bash
python verificar_backup_multitenant_live.py
python verificar_restore_multitenant_live.py
```
