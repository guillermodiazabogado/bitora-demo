# BITORA Final Release Certification

Decision: **NO APROBADA**

Version evaluada: `9bbba102b37ae19c160c54af038da5eb41d14937`
Branch: `main`
Perfil: `release`
Score: **59.6/100**
Fecha: 2026-07-20T23:05:49

## Pruebas y gates

- PASSED `integridad`
- PASSED `convivencia`
- PASSED `email_productivo`
- PASSED `whatsapp_productivo`
- PASSED `event_restore`
- PASSED `storage_event_backup_restore`
- PASSED `demo_live_10`
- PASSED `postgres_static`
- PASSED `production_postgres`
- PASSED `comunicaciones_permisos`
- PASSED `usuarios_eventos`
- PASSED `seguridad_basica`
- PASSED `datos_basura`
- PASSED `errores_humanos`
- PASSED `concurrencia_critica`
- PASSED `multievent_isolation_20_events`
- PASSED `multitenant_integrations`
- OMITTED `staging_environment`
- OMITTED `postgres_live`
- OMITTED `storage_persistent`
- OMITTED `workers_live`
- OMITTED `communications_safe_mode`
- PASSED `multitenant_organization_isolation`
- PASSED `integration_secret_protection`
- PASSED `integration_assignment`
- OMITTED `google_integration_flow`
- OMITTED `meta_integration_flow`
- OMITTED `email_integration_flow`
- OMITTED `webhook_tenant_resolution`
- PASSED `communications_tenant_isolation`
- OMITTED `backup_multitenant`
- OMITTED `restore_multitenant`
- OMITTED `disaster_recovery_live`
- OMITTED `endurance_24h`
- OMITTED `upgrade_from_previous_version`

## Pendientes / restricciones

- `staging_environment`: APP_ENV=staging requerido para release final.
- `postgres_live`: Requiere QR_POSTGRES_DSN o DATABASE_URL real de staging.
- `storage_persistent`: Storage persistente de staging requerido. Ruta evaluada: C:\Users\Noxie-PC\Documents\qr white label\storage
- `workers_live`: Requiere levantar worker separado y validar recuperacion tras reinicio.
- `communications_safe_mode`: Safe mode requiere destinatarios forzados de email y WhatsApp.
- `disaster_recovery_live`: Pendiente perfil --disaster en staging destructible.
- `endurance_24h`: Pendiente ejecucion real de 24 horas.
- `upgrade_from_previous_version`: Pendiente prueba de actualizacion desde version anterior con datos.

## Riesgos residuales

- No declarar aptitud para evento real hasta ejecutar PostgreSQL live, disaster recovery y endurance real en staging.
- Las pruebas omitidas no computan como aprobadas.
- La aprobacion con restricciones solo habilita una demo fisica controlada si el equipo acepta los pendientes documentados.
