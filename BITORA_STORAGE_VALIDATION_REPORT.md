# BITORA Storage Persistente Report

- PASSED `event_restore`: OK: restauracion controlada de backup de evento

- PASSED `storage_event_backup_restore`: OK: storage por evento incluido en backup y restauracion

- PASSED `backup_multitenant_live`: {"name": "backup_multitenant_live", "mode": "contract", "status": "omitted", "missing_env": ["APP_ENV", "QR_POSTGRES_DSN", "BITORA_STORAGE_PATH"], "checks": {"organizations_present": 2, "events_with_organization": 2, "plain_secrets": 0}}

- PASSED `restore_multitenant_live`: {"name": "restore_multitenant_live", "mode": "contract", "status": "omitted", "missing_env": ["APP_ENV", "QR_POSTGRES_DSN", "BITORA_STORAGE_PATH"], "checks": {"external_jobs_emitted_after_restore": 0, "cross_organization_after_restore": 0, "secrets_exposed": 0, "safe_mode_after_restore": true}}

- OMITTED `storage_persistent`: Storage persistente de staging requerido. Ruta evaluada: C:\Users\Noxie-PC\Documents\qr white label\storage
- OMITTED `backup_multitenant_live`: Modo contract; estado omitted. Faltan variables: APP_ENV, QR_POSTGRES_DSN, BITORA_STORAGE_PATH
- OMITTED `restore_multitenant_live`: Modo contract; estado omitted. Faltan variables: APP_ENV, QR_POSTGRES_DSN, BITORA_STORAGE_PATH
