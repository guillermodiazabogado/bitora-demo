# BITORA Multitenant Backup Live Report

Estado: preparado, pendiente de ejecucion con BDF en staging Docker/PostgreSQL.

Prueba disponible:

```bash
python verificar_backup_multitenant_live.py
```

Sin `APP_ENV=staging`, `QR_POSTGRES_DSN` y `BITORA_STORAGE_PATH`, el resultado queda en modo contract/omitted.

Resultado ejecutado local:

```text
mode=contract
status=omitted
organizations_present=2
events_with_organization=2
plain_secrets=0
```
