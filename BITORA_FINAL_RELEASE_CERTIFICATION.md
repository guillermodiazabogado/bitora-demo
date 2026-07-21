# BITORA Final Release Certification

Decision: **NO APROBADA**

Version evaluada: `3b5aca166b3da733e46011970413e1785a21d52f`
Branch: `main`
Perfil: `release`
Score: **58.4/100**
Fecha: 2026-07-20T23:18:37

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
- PASSED `google_oauth_multitenant_live`
- PASSED `email_multitenant_live`
- PASSED `whatsapp_multitenant_live`
- PASSED `webhooks_multitenant_live`
- PASSED `backup_multitenant_live`
- PASSED `restore_multitenant_live`
- PASSED `integrations_disaster_recovery`
- OMITTED `staging_environment`
- OMITTED `postgres_live`
- OMITTED `storage_persistent`
- OMITTED `workers_live`
- OMITTED `communications_safe_mode`
- PASSED `multitenant_organization_isolation`
- PASSED `integration_secret_protection`
- PASSED `integration_assignment`
- OMITTED `google_oauth_live`
- OMITTED `email_organization_live`
- OMITTED `whatsapp_organization_live`
- OMITTED `webhook_tenant_resolution_live`
- PASSED `communications_tenant_isolation`
- OMITTED `backup_multitenant_live`
- OMITTED `restore_multitenant_live`
- OMITTED `disaster_recovery_live`
- OMITTED `endurance_24h`
- OMITTED `upgrade_from_previous_version`

## Pendientes / restricciones

- `staging_environment`: APP_ENV=staging requerido para release final.
- `postgres_live`: Requiere QR_POSTGRES_DSN o DATABASE_URL real de staging.
- `storage_persistent`: Storage persistente de staging requerido. Ruta evaluada: C:\Users\Noxie-PC\Documents\qr white label\storage
- `workers_live`: Requiere levantar worker separado y validar recuperacion tras reinicio.
- `communications_safe_mode`: Safe mode requiere destinatarios forzados de email y WhatsApp.
- `google_oauth_live`: Modo contract; estado omitted. Faltan variables: GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET, GOOGLE_OAUTH_REDIRECT_URI
- `email_organization_live`: Modo contract; estado omitted. Faltan variables: EMAIL_PROVIDER, EMAIL_FORCE_RECIPIENT, EMAIL_SAFE_MODE
- `whatsapp_organization_live`: Modo contract; estado omitted. Faltan variables: WHATSAPP_ACCESS_TOKEN, WHATSAPP_PHONE_NUMBER_ID, WHATSAPP_BUSINESS_ACCOUNT_ID, WHATSAPP_FORCE_RECIPIENT, WHATSAPP_SAFE_MODE
- `webhook_tenant_resolution_live`: Modo contract; estado omitted. Faltan variables: EMAIL_WEBHOOK_SECRET, WHATSAPP_VERIFY_TOKEN, WHATSAPP_APP_SECRET
- `backup_multitenant_live`: Modo contract; estado omitted. Faltan variables: APP_ENV, QR_POSTGRES_DSN, BITORA_STORAGE_PATH
- `restore_multitenant_live`: Modo contract; estado omitted. Faltan variables: APP_ENV, QR_POSTGRES_DSN, BITORA_STORAGE_PATH
- `disaster_recovery_live`: Pendiente perfil --disaster en staging destructible.
- `endurance_24h`: Pendiente ejecucion real de 24 horas.
- `upgrade_from_previous_version`: Pendiente prueba de actualizacion desde version anterior con datos.

## Riesgos residuales

- No declarar aptitud para evento real hasta ejecutar PostgreSQL live, disaster recovery y endurance real en staging.
- Las pruebas omitidas no computan como aprobadas.
- La aprobacion con restricciones solo habilita una demo fisica controlada si el equipo acepta los pendientes documentados.
