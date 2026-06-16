# BITORA QA - Auditoria funcional integral

Fecha: 2026-06-16

## Estado general

Resultado: APTO PARA DEMO, con observacion operativa.

La plataforma queda validada de punta a punta en modo demo/local para los flujos criticos actuales:

- inscripcion simple sin actividades;
- inscripcion con actividades y reservas;
- cupos, lista de espera y promocion automatica;
- recepcion y acreditacion;
- validacion QR general y por actividad;
- bloqueo de QR repetidos;
- bloqueo de acceso anticipado a actividad;
- pantalla publica;
- sala de control;
- asistencia y elegibilidad de certificados;
- captacion/origen de participantes;
- comunicaciones operativas V5;
- backups, exportaciones y auditoria;
- convivencia de modulos.

Observacion: la publicacion online depende de que Render despliegue el ultimo commit del repositorio. La aplicacion esta preparada para cloud, pero la prueba de camara QR siempre depende tambien del navegador/dispositivo y permisos HTTPS.

## Pruebas nuevas creadas

- `verificar_integridad_bitora.py`
- `verificar_convivencia_modulos.py`

## Resultados de suite final

Pasaron correctamente:

- `verificar_mvp.py`
- `verificar_v2.py`
- `verificar_v3.py`
- `verificar_v4.py`
- `verificar_demo_real.py`
- `verificar_v4_1.py`
- `verificar_v4_2.py`
- `verificar_v4_4.py`
- `verificar_v4_5_cloud.py`
- `verificar_v4_6_deploy.py`
- `verificar_v4_8_templates.py`
- `verificar_v4_8_1_calendar_import.py`
- `verificar_v4_9_visual_reports.py`
- `verificar_v4_9_1_control_room.py`
- `verificar_v5_communications.py`
- `verificar_v5_email.py`
- `verificar_v5_whatsapp.py`
- `verificar_v5_whatsapp_assistant.py`
- `verificar_activity_access_window.py`
- `verificar_limpieza_panel.py`
- `verificar_integridad_bitora.py`
- `verificar_convivencia_modulos.py`
- `robustness_suite.py`
- `station_stress_test.py`

## Robustez medida

`robustness_suite.py`

- 30 estaciones QR en paralelo.
- 3.000 lecturas.
- 3.000 correctas.
- 0 errores.
- Promedio: 0.207 s.
- p95: 0.231 s.
- Maximo: 0.303 s.
- Rendimiento: 143.8 QR/s.
- Doble lectura simultanea del mismo QR: 1 concedido, 999 rechazados por usado.
- Base grande de 10.000 registros: busqueda, validacion, resumen e impresion OK.
- Backup bajo carga: 912 operaciones OK, 0 errores.
- Recuperacion post reinicio OK.

`station_stress_test.py`

- 30 estaciones.
- Escalas de 30 a 3.000 lecturas.
- 100% de exito.
- Corte detectado: sin quiebre hasta el maximo probado.

## Correcciones realizadas durante QA

- La prueba integral fue ajustada para validar el contrato real de reservas, buscando el identificador interno cuando la API no lo devuelve en la respuesta de creacion.
- La prueba de convivencia fue ajustada para aceptar las formas validas actuales de pantalla publica, sin depender de un unico nombre interno de lista.
- La auditoria integral fue reforzada para revisar la bitacora completa de la base temporal cuando una accion auditada corresponde a otro evento derivado, como clonado.

## Riesgos pendientes

- La prueba visual automatizada de navegador no se ejecuto desde el entorno de herramientas por limitacion de automatizacion local, pero las rutas HTTP y flujos principales fueron validados por scripts.
- SQLite es valido para demo y pruebas controladas. Para produccion con mucha concurrencia real, PostgreSQL sigue siendo la recomendacion.
- Email y WhatsApp reales estan preparados por proveedores/env vars, pero en demo se validan en modo cola/log sin envio real salvo configuracion externa.

## Recomendacion

BITORA queda apto para demo publica y para avanzar a una segunda etapa de destruccion controlada extrema antes de usarlo en un evento real.
