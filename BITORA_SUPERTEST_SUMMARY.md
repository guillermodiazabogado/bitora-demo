# BITORA Supertest Summary

Perfil: `release`
Resultado: RECHAZADO
Score: 61.5/100
Pruebas ejecutadas: 24
Pruebas fallidas/timeouts: 9
Hallazgos criticos/altos: 0

## Pruebas

- PASSED `integridad` (1.72s)
- PASSED `convivencia` (1.71s)
- PASSED `email_productivo` (0.49s)
- PASSED `whatsapp_productivo` (0.81s)
- PASSED `event_restore` (0.31s)
- PASSED `storage_event_backup_restore` (0.26s)
- PASSED `demo_live_10` (0.85s)
- PASSED `postgres_static` (0.24s)
- PASSED `production_postgres` (0.07s)
- PASSED `comunicaciones_permisos` (0.75s)
- PASSED `usuarios_eventos` (0.77s)
- PASSED `seguridad_basica` (1.43s)
- PASSED `datos_basura` (1.45s)
- PASSED `errores_humanos` (1.52s)
- PASSED `concurrencia_critica` (5.06s)
- OMITTED `staging_environment` (0s)
- OMITTED `postgres_live` (0s)
- OMITTED `storage_persistent` (0s)
- OMITTED `workers_live` (0s)
- OMITTED `communications_safe_mode` (0s)
- OMITTED `multievent_isolation_20_events` (0s)
- OMITTED `disaster_recovery_live` (0s)
- OMITTED `endurance_24h` (0s)
- OMITTED `upgrade_from_previous_version` (0s)

## Hallazgos

- **MEDIUM** [code] Funcion muy extensa: init_db ocupa mas de 120 lineas (server.py)
- **MEDIUM** [code] Funcion muy extensa: portal_payload ocupa mas de 120 lineas (server.py)
- **MEDIUM** [code] Funcion muy extensa: executive_report_data ocupa mas de 120 lineas (server.py)
- **MEDIUM** [code] Funcion muy extensa: executive_report_pdf_bytes ocupa mas de 120 lineas (server.py)
- **MEDIUM** [code] Funcion muy extensa: handle_api_get ocupa mas de 120 lineas (server.py)
- **MEDIUM** [code] Funcion muy extensa: handle_api_post ocupa mas de 120 lineas (server.py)
- **MEDIUM** [code] Funcion muy extensa: main ocupa mas de 120 lineas (verificar_demo_10_live.py)
- **MEDIUM** [code] Funcion muy extensa: main ocupa mas de 120 lineas (verificar_demo_live_10.py)
- **MEDIUM** [code] Funcion muy extensa: run_checks ocupa mas de 120 lineas (verificar_mvp.py)
- **MEDIUM** [code] Funcion muy extensa: main ocupa mas de 120 lineas (verificar_operacion_8_horas.py)
- **MEDIUM** [code] Funcion muy extensa: main ocupa mas de 120 lineas (verificar_v4.py)
- **MEDIUM** [code] Funcion muy extensa: main ocupa mas de 120 lineas (verificar_v4_1.py)
- **MEDIUM** [code] Funcion muy extensa: main ocupa mas de 120 lineas (verificar_v4_2.py)
- **MEDIUM** [code] Funcion muy extensa: main ocupa mas de 120 lineas (verificar_v4_8_templates.py)
- **MEDIUM** [code] Funcion muy extensa: main ocupa mas de 120 lineas (verificar_v6_1_email_real.py)
- **MEDIUM** [code] Funcion muy extensa: main ocupa mas de 120 lineas (verificar_v6_8_data_visualization.py)
- **MEDIUM** [code] Funcion muy extensa: main ocupa mas de 120 lineas (verificar_v7_whatsapp_productivo.py)
- **MEDIUM** [code] Funcion muy extensa: _simulate_peak_operations ocupa mas de 120 lineas (backend/services/demo_real.py)
- **LOW** [code] Funcion repetida por nombre: assert_true: verificar_convivencia_modulos.py:32, verificar_demo_1000.py:34, verificar_demo_real.py:38, verificar_integridad_bitora.py:32, verificar_landing_config.py:52, verificar_layout_control_room.py:36
- **LOW** [code] Funcion repetida por nombre: connect: server.py:438, verificar_backup_restore.py:25, verificar_event_restore.py:89, verificar_persistencia_backups.py:61, verificar_storage_event_backup_restore.py:87, verificar_v6_1_email_productivo.py:18
- **LOW** [code] Funcion repetida por nombre: do_POST: server.py:5186, verificar_demo_10_live.py:22, verificar_v5_email.py:20, verificar_v6_1_email_real.py:23, verificar_v7_whatsapp_real.py:21
- **LOW** [code] Funcion repetida por nombre: main: migrar_sqlite_a_postgres.py:117, robustness_suite.py:398, server.py:9376, soak_test_8h.py:11, verificar_activity_access_window.py:114, verificar_auth_red.py:43
- **LOW** [code] Funcion repetida por nombre: ready: backend/storage.py:33, backend/services/email.py:27, backend/services/email.py:85, backend/services/email.py:124, backend/services/whatsapp.py:29, backend/services/whatsapp.py:60
- **LOW** [code] Funcion repetida por nombre: req: verificar_activity_access_window.py:27, verificar_busqueda_recepcion.py:16, verificar_convivencia_modulos.py:14, verificar_demo_1000.py:15, verificar_demo_real.py:15, verificar_integridad_bitora.py:14
- **LOW** [code] Funcion repetida por nombre: request: qa2_utils.py:63, robustness_suite.py:64, station_stress_test.py:24, stress_test.py:23, verificar_auth_red.py:18, verificar_limpieza_panel.py:21
- **LOW** [code] Funcion repetida por nombre: validate_configuration: backend/services/email.py:66, backend/services/email.py:127, backend/services/whatsapp.py:48, backend/services/whatsapp.py:78, backend/services/whatsapp.py:169
- **MEDIUM** [security] SQL string formatting: rows = [dict(row) for row in source.execute(f'SELECT * FROM "{table}" ORDER BY 1').fetchall()] if exists else [] (migrar_sqlite_a_postgres.py)
- **MEDIUM** [security] SQL string formatting: db.execute(f"ALTER TABLE communication_queue ADD COLUMN {name} {definition}") (server.py)
- **MEDIUM** [security] SQL string formatting: db.execute(f"ALTER TABLE communication_queue ADD COLUMN {name} {definition}") (server.py)
- **MEDIUM** [security] SQL string formatting: db.execute(f"ALTER TABLE events ADD COLUMN {name} {definition}") (server.py)
- **MEDIUM** [security] SQL string formatting: db.execute(f"ALTER TABLE events ADD COLUMN {name} TEXT NOT NULL DEFAULT ''") (server.py)
- **MEDIUM** [security] SQL string formatting: activities = db.execute(f"SELECT * FROM activities WHERE {where}", params).fetchall() (server.py)
- **MEDIUM** [security] SQL string formatting: visible = db.execute(f"SELECT COUNT(*) AS c FROM events e WHERE {where}", params).fetchone()["c"] (verificar_v9_usuarios_eventos.py)
- **MEDIUM** [security] SQL string formatting: "tables": {table: [dict(row) for row in db.execute(f'SELECT * FROM "{table}" ORDER BY 1').fetchall()] for table in tables}, (backend/services/backup.py)
- **MEDIUM** [security] SQL string formatting: db.execute(f"UPDATE events SET {assignments} WHERE id = ?", [source[name] for name in columns] + [event_id]) (backend/services/backup.py)
- **MEDIUM** [security] SQL string formatting: db.execute(f"DELETE FROM {table} WHERE event_id = ?", (event_id,)) (backend/services/backup.py)
- **MEDIUM** [security] SQL string formatting: restored = db.execute(f"SELECT COUNT(*) AS c FROM {table} WHERE event_id = ?", (event_id,)).fetchone()["c"] (backend/services/backup.py)
- **MEDIUM** [security] SQL string formatting: return [row["name"] for row in db.execute(f"PRAGMA table_info({table})").fetchall()] (backend/services/backup.py)
- **MEDIUM** [security] SQL string formatting: activities = db.execute(f"SELECT * FROM activities WHERE {where}", params).fetchall() (backend/services/capacity_buckets.py)
- **MEDIUM** [security] SQL string formatting: db.execute(f"DELETE FROM {table}") (backend/services/demo_real.py)
- **LOW** [database] Prefijo de migracion duplicado conocido: Prefijo 007 aparece mas de una vez
- **MEDIUM** [architecture] Controlador principal muy grande: server.py tiene 9427 lineas
