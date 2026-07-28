# RECERTIFICATION_IMPACT_MATRIX

Esta matriz define que gates deben repetirse cuando un cambio futuro modifica una zona funcional de BITORA. Las certificaciones anteriores son baseline historica; no son un permiso para cambiar sin revalidar.

| Tipo de cambio | Gates a repetir |
|---|---|
| Documentacion menor | Sin recertificacion tecnica; revisar secretos |
| Textos o estilos no funcionales | Smoke UI afectada |
| RBAC / permisos | `seguridad_basica`, `multievent_isolation_20_events`, regresion funcional |
| Modelos multitenant | `multievent_isolation_20_events`, `backup_multitenant_live`, `restore_multitenant_live`, `disaster_recovery_live`, `upgrade_from_previous_version` |
| Migraciones | Integridad, backup, restore, disaster recovery, upgrade |
| Jobs / workers | Worker, idempotencia, integraciones afectadas, `disaster_recovery_live`, `upgrade_from_previous_version` |
| Storage | `backup_multitenant_live`, `restore_multitenant_live`, `disaster_recovery_live`, `upgrade_from_previous_version` |
| Email | Email Live, Safe Mode, auditoria, jobs |
| Google OAuth | Google OAuth Live, cifrado, callbacks, tenant isolation |
| WhatsApp | WhatsApp Live, Webhooks Live, Safe Mode, tenant resolution |
| Infraestructura | BDF, health, `disaster_recovery_live`, `upgrade_from_previous_version`, `endurance_24h` |
| Asistencia V4 | `seguridad_basica`, `multievent_isolation_20_events`, auditoria, QR/acceso, backup, restore, upgrade; V4.1 requiere repetir pruebas dirigidas de idempotencia y feature flag; V4.2 requiere snapshots, reglas versionadas y cierre/elegibilidad |
| Cierre de asistencia | Seguridad, auditoria, backup, restore, upgrade, determinismo, concurrencia; jobs solo si hay cierres programados |
| Certificados V4 | Storage, comunicaciones, auditoria, backup, restore, disaster recovery, upgrade |
| Encuestas V4 | Privacidad, multitenant, exportaciones, backup, restore, upgrade |
| Disertantes V4 | Autenticacion, RBAC, storage, multitenant, backup, restore |
| Permisos por zonas | Seguridad, QR/acceso, aislamiento, operacion offline si aplica, carga |
| Historial participante | Privacidad, multitenant, exportaciones, backup, restore |
| Autocompletado | Privacidad, deduplicacion, multitenant, auditoria |
| Centro operativo | UI, permisos, jobs, reportes, performance |
| Incidencias | RBAC, auditoria, multitenant, notificaciones si aplica |
| Comunicaciones V4 | Email, WhatsApp, Safe Mode, jobs, idempotencia, webhooks |
| Automatizaciones | Jobs, Safe Mode, disaster recovery, upgrade, integraciones afectadas |
| Analytics/reportes | Consistencia, exportaciones, permisos, performance |

## Regla de Impacto

Cambios BAJOS pueden requerir solo smoke test. Cambios MEDIOS requieren pruebas del modulo y regresion afectada. Cambios ALTOS requieren BSTF parcial y gates live o destructivos si el dominio toca integraciones, storage, backup, restore, disaster recovery o upgrade.
