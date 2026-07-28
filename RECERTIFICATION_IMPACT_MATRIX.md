# RECERTIFICATION_IMPACT_MATRIX

| Tipo de cambio | Gates a repetir |
|---|---|
| RBAC / permisos | `seguridad_basica`, `multievent_isolation_20_events`, regresion funcional |
| Modelos multitenant | `multievent_isolation_20_events`, `backup_multitenant_live`, `restore_multitenant_live`, `disaster_recovery_live`, `upgrade_from_previous_version` |
| Jobs / workers | Worker, idempotencia, integraciones, `disaster_recovery_live`, `upgrade_from_previous_version` |
| Storage | `backup_multitenant_live`, `restore_multitenant_live`, `disaster_recovery_live`, `upgrade_from_previous_version` |
| Email | Email Live, Safe Mode, auditoria, jobs |
| Google OAuth | Google OAuth Live, cifrado, callbacks, tenant isolation |
| WhatsApp | WhatsApp Live, Webhooks Live, Safe Mode, tenant resolution |
| Infraestructura | `disaster_recovery_live`, `upgrade_from_previous_version`, `endurance_24h` |
| Migraciones | Integridad, backup, restore, disaster recovery, upgrade |
| Documentacion menor | Sin recertificacion tecnica |
