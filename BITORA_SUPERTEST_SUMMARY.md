# BITORA Supertest Summary

Perfil: `release`
Resultado: RECHAZADO
Score: 82.6/100
Pruebas ejecutadas: 47
Pruebas fallidas/timeouts: 5
Hallazgos criticos/altos: 0

## Pruebas

- PASSED `integridad` (9.09s)
- PASSED `convivencia` (7.21s)
- PASSED `email_productivo` (0.84s)
- PASSED `whatsapp_productivo` (0.85s)
- PASSED `event_restore` (0.52s)
- PASSED `storage_event_backup_restore` (0.54s)
- PASSED `demo_live_10` (0.93s)
- PASSED `postgres_static` (0.47s)
- PASSED `production_postgres` (0.47s)
- PASSED `comunicaciones_permisos` (4.61s)
- PASSED `usuarios_eventos` (4.23s)
- PASSED `seguridad_basica` (7.33s)
- PASSED `datos_basura` (4.87s)
- PASSED `errores_humanos` (5.15s)
- PASSED `concurrencia_critica` (8.71s)
- PASSED `multievent_isolation_20_events` (9.37s)
- PASSED `multitenant_integrations` (0.89s)
- PASSED `google_oauth_http_flow` (0.67s)
- PASSED `google_oauth_state_security` (0.92s)
- PASSED `google_oauth_multitenant_isolation` (0.87s)
- PASSED `google_oauth_refresh_contract` (0.69s)
- PASSED `google_oauth_backup_restore` (0.85s)
- PASSED `google_oauth_multitenant_live` (5.94s)
- PASSED `email_multitenant_live` (5.43s)
- FAILED `whatsapp_multitenant_live` (67.39s)
- FAILED `webhooks_multitenant_live` (0.62s)
- PASSED `backup_multitenant_live` (0.64s)
- PASSED `restore_multitenant_live` (0.62s)
- PASSED `integrations_disaster_recovery` (0.91s)
- PASSED `staging_environment` (0s)
- PASSED `postgres_live` (0s)
- PASSED `storage_persistent` (0s)
- PASSED `workers_live` (0s)
- PASSED `communications_safe_mode` (0s)
- PASSED `multitenant_organization_isolation` (0s)
- PASSED `integration_secret_protection` (0s)
- PASSED `integration_assignment` (0s)
- PASSED `google_oauth_live` (0s)
- PASSED `email_organization_live` (0s)
- FAILED `whatsapp_organization_live` (0s)
- OMITTED `webhook_tenant_resolution_live` (0s)
- PASSED `communications_tenant_isolation` (0s)
- PASSED `backup_multitenant_live` (0s)
- PASSED `restore_multitenant_live` (0s)
- PASSED `disaster_recovery_live` (0s)
- OMITTED `endurance_24h` (0s)
- PASSED `upgrade_from_previous_version` (0s)

## Hallazgos

- **MEDIUM** [code] Funcion muy extensa: main ocupa mas de 120 lineas (verificar_v4_2.py)
- **MEDIUM** [code] Funcion muy extensa: main ocupa mas de 120 lineas (verificar_demo_live_10.py)
- **MEDIUM** [code] Funcion muy extensa: _live_result ocupa mas de 120 lineas (verificar_whatsapp_multitenant_live.py)
- **MEDIUM** [code] Funcion muy extensa: main ocupa mas de 120 lineas (verificar_v7_whatsapp_productivo.py)
- **MEDIUM** [code] Funcion muy extensa: main ocupa mas de 120 lineas (verificar_operacion_8_horas.py)
- **MEDIUM** [code] Funcion muy extensa: main ocupa mas de 120 lineas (verificar_demo_10_live.py)
- **MEDIUM** [code] Funcion muy extensa: main ocupa mas de 120 lineas (verificar_v6_1_email_real.py)
- **MEDIUM** [code] Funcion muy extensa: main ocupa mas de 120 lineas (verificar_v4_1.py)
- **MEDIUM** [code] Funcion muy extensa: main ocupa mas de 120 lineas (verificar_multitenant_integrations.py)
- **MEDIUM** [code] Funcion muy extensa: _live_result ocupa mas de 120 lineas (verificar_webhooks_multitenant_live.py)
- **MEDIUM** [code] Funcion muy extensa: main ocupa mas de 120 lineas (verificar_v4_8_templates.py)
- **MEDIUM** [code] Funcion muy extensa: main ocupa mas de 120 lineas (verificar_v4.py)
- **MEDIUM** [code] Funcion muy extensa: main ocupa mas de 120 lineas (verificar_multievent_isolation_20_events.py)
- **MEDIUM** [code] Funcion muy extensa: init_db ocupa mas de 120 lineas (server.py)
- **MEDIUM** [code] Funcion muy extensa: queue_communication ocupa mas de 120 lineas (server.py)
- **MEDIUM** [code] Funcion muy extensa: portal_payload ocupa mas de 120 lineas (server.py)
- **MEDIUM** [code] Funcion muy extensa: executive_report_data ocupa mas de 120 lineas (server.py)
- **MEDIUM** [code] Funcion muy extensa: executive_report_pdf_bytes ocupa mas de 120 lineas (server.py)
- **MEDIUM** [code] Funcion muy extensa: handle_api_get ocupa mas de 120 lineas (server.py)
- **MEDIUM** [code] Funcion muy extensa: handle_api_post ocupa mas de 120 lineas (server.py)
- **MEDIUM** [code] Funcion muy extensa: run_checks ocupa mas de 120 lineas (verificar_mvp.py)
- **MEDIUM** [code] Funcion muy extensa: _live_result ocupa mas de 120 lineas (verificar_email_multitenant_live.py)
- **MEDIUM** [code] Funcion muy extensa: main ocupa mas de 120 lineas (verificar_v6_8_data_visualization.py)
- **MEDIUM** [code] Funcion muy extensa: seed_dataset ocupa mas de 120 lineas (tools/backup_restore_live_dataset.py)
- **MEDIUM** [code] Funcion muy extensa: write_outputs ocupa mas de 120 lineas (deployment/scripts/certify_disaster_recovery_live.py)
- **MEDIUM** [code] Funcion muy extensa: main ocupa mas de 120 lineas (deployment/scripts/certify_backup_restore_live.py)
- **MEDIUM** [code] Funcion muy extensa: write_markdown_reports ocupa mas de 120 lineas (deployment/scripts/certify_backup_restore_live.py)
- **MEDIUM** [code] Funcion muy extensa: _simulate_peak_operations ocupa mas de 120 lineas (backend/services/demo_real.py)
- **LOW** [code] Funcion repetida por nombre: assert_true: verificar_v4_2.py:38, verificar_v4_9_1_control_room.py:37, verificar_limpieza_panel.py:44, verificar_landing_config.py:52, verificar_v4_9_visual_reports.py:37, verificar_reorganizacion_inscribir_recepcion.py:12
- **LOW** [code] Funcion repetida por nombre: connect: verificar_persistencia_backups.py:61, verificar_backup_restore.py:25, verificar_event_restore.py:89, verificar_v6_1_email_productivo.py:18, verificar_storage_event_backup_restore.py:87, server.py:466
- **LOW** [code] Funcion repetida por nombre: do_POST: verificar_v7_whatsapp_real.py:21, verificar_v5_email.py:20, verificar_demo_10_live.py:22, verificar_v6_1_email_real.py:23, server.py:5702
- **LOW** [code] Funcion repetida por nombre: log_message: verificar_v7_whatsapp_real.py:18, verificar_v5_email.py:17, verificar_demo_10_live.py:19, verificar_v6_1_email_real.py:20, server.py:5573
- **LOW** [code] Funcion repetida por nombre: main: verificar_recuperacion.py:20, verificar_v4_2.py:43, verificar_demo_live_10.py:66, verificar_v4_9_1_control_room.py:42, verificar_stress_extremo.py:31, verificar_persistencia_backups.py:55
- **LOW** [code] Funcion repetida por nombre: ready: backend/storage.py:33, backend/services/whatsapp.py:46, backend/services/whatsapp.py:77, backend/services/whatsapp.py:122, backend/services/email.py:27, backend/services/email.py:85
- **LOW** [code] Funcion repetida por nombre: req: verificar_v4_2.py:15, verificar_v4_9_1_control_room.py:14, verificar_landing_config.py:21, verificar_activity_access_window.py:27, verificar_v5_email.py:31, verificar_v4_9_visual_reports.py:14
- **LOW** [code] Funcion repetida por nombre: request: verificar_limpieza_panel.py:21, stress_test.py:23, qa2_utils.py:63, robustness_suite.py:64, verificar_mvp.py:19, verificar_auth_red.py:18
- **LOW** [code] Funcion repetida por nombre: run: tools/supertest/runner.py:61, deployment/scripts/certify_disaster_recovery_live.py:457, deployment/scripts/certify_backup_restore_live.py:377, deployment/scripts/bdf.py:253, backend/services/jobs.py:163
- **LOW** [code] Funcion repetida por nombre: validate_configuration: backend/services/whatsapp.py:65, backend/services/whatsapp.py:95, backend/services/whatsapp.py:186, backend/services/email.py:66, backend/services/email.py:127, backend/services/google_oauth.py:76
- **MEDIUM** [security] SQL string formatting: db.execute(f"ALTER TABLE jobs ADD COLUMN {name} {definition}") (server.py)
- **MEDIUM** [security] SQL string formatting: db.execute(f"ALTER TABLE communication_queue ADD COLUMN {name} {definition}") (server.py)
- **MEDIUM** [security] SQL string formatting: db.execute(f"ALTER TABLE communication_queue ADD COLUMN {name} {definition}") (server.py)
- **MEDIUM** [security] SQL string formatting: db.execute(f"ALTER TABLE communication_queue ADD COLUMN {name} {definition}") (server.py)
- **MEDIUM** [security] SQL string formatting: db.execute(f"ALTER TABLE events ADD COLUMN {name} {definition}") (server.py)
- **MEDIUM** [security] SQL string formatting: db.execute(f"ALTER TABLE events ADD COLUMN {name} TEXT NOT NULL DEFAULT ''") (server.py)
- **MEDIUM** [security] SQL string formatting: activities = db.execute(f"SELECT * FROM activities WHERE {where}", params).fetchall() (server.py)
- **MEDIUM** [security] SQL string formatting: rows = [dict(row) for row in source.execute(f'SELECT * FROM "{table}" ORDER BY 1').fetchall()] if exists else [] (migrar_sqlite_a_postgres.py)
- **MEDIUM** [security] SQL string formatting: visible = db.execute(f"SELECT COUNT(*) AS c FROM events e WHERE {where}", params).fetchone()["c"] (verificar_v9_usuarios_eventos.py)
- **MEDIUM** [security] SQL string formatting: return int(db.execute(f"SELECT COUNT(*) AS c FROM {table} WHERE {where}", params).fetchone()["c"] or 0) (tools/backup_restore_live_dataset.py)
- **MEDIUM** [security] SQL string formatting: return int(db.execute(f"SELECT COUNT(*) AS c FROM {table} WHERE {column} IN ({placeholders})", tuple(ids)).fetchone()["c"] or 0) (tools/backup_restore_live_dataset.py)
- **MEDIUM** [security] SQL string formatting: rows = db.execute(f"SELECT * FROM {table} WHERE {where} ORDER BY id", params).fetchall() (tools/backup_restore_live_dataset.py)
- **MEDIUM** [security] SQL string formatting: rows = db.execute(f"SELECT * FROM {table} WHERE {column} IN ({placeholders}) ORDER BY id", tuple(ids)).fetchall() (tools/backup_restore_live_dataset.py)
- **MEDIUM** [security] SQL string formatting: "tables": {table: [dict(row) for row in db.execute(f'SELECT * FROM "{table}" ORDER BY 1').fetchall()] for table in tables}, (backend/services/backup.py)
- **MEDIUM** [security] SQL string formatting: db.execute(f"UPDATE events SET {assignments} WHERE id = ?", [source[name] for name in columns] + [event_id]) (backend/services/backup.py)
- **MEDIUM** [security] SQL string formatting: db.execute(f"DELETE FROM {table} WHERE event_id = ?", (event_id,)) (backend/services/backup.py)
- **MEDIUM** [security] SQL string formatting: restored = db.execute(f"SELECT COUNT(*) AS c FROM {table} WHERE event_id = ?", (event_id,)).fetchone()["c"] (backend/services/backup.py)
- **MEDIUM** [security] SQL string formatting: return [row["name"] for row in db.execute(f"PRAGMA table_info({table})").fetchall()] (backend/services/backup.py)
- **MEDIUM** [security] SQL string formatting: db.execute(f"DELETE FROM {table}") (backend/services/demo_real.py)
- **MEDIUM** [security] SQL string formatting: activities = db.execute(f"SELECT * FROM activities WHERE {where}", params).fetchall() (backend/services/capacity_buckets.py)
- **LOW** [database] Prefijo de migracion duplicado conocido: Prefijo 007 aparece mas de una vez
- **MEDIUM** [database] Prefijo de migracion duplicado: Prefijo 015 aparece mas de una vez
- **MEDIUM** [architecture] Controlador principal muy grande: server.py tiene 10453 lineas
