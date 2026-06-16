# BITORA QA2 - Prueba de destruccion controlada y robustez extrema

Fecha: 2026-06-16

## Recomendacion final

Resultado: APTO PARA DEMO.

Observacion: para evento real de alta concurrencia sostenida, migrar a PostgreSQL antes de produccion. SQLite respondio correctamente en las pruebas de demo y estres controlado, pero no es el objetivo final para operacion cloud con multiples instancias.

## Pruebas ejecutadas

- `verificar_integridad_bitora.py`
- `verificar_convivencia_modulos.py`
- `verificar_stress_extremo.py`
- `verificar_errores_humanos.py`
- `verificar_recuperacion.py`
- `verificar_seguridad_basica.py`
- `verificar_datos_basura.py`
- `verificar_tiempos_operativos.py`
- `verificar_concurrencia_critica.py`
- `robustness_suite.py`
- `station_stress_test.py`

## Stress extremo

`verificar_stress_extremo.py`

- 20.000 participantes simulados.
- 50 actividades.
- 10 salas.
- 50 operadores QR.
- 10.000 escaneos concurrentes.
- 1.000 inscripciones simultaneas.
- 1.000 reservas simultaneas sobre una actividad con cupo 200.
- QR duplicado simultaneo.

Resultado:

- Escaneos correctos: 10.000.
- Errores de escaneo: 0.
- Tiempo promedio escaneo: 0.325 s.
- p95 escaneo: 0.349 s.
- Maximo escaneo: 0.412 s.
- Inscripciones simultaneas correctas: 1.000.
- Reservas simultaneas correctas: 1.000.
- Confirmadas: 200.
- Lista de espera: 800.
- Sobrecupo: no.
- QR duplicado simultaneo: 1 concedido, 99 rechazados.
- Duracion total: 90.4 s.

## Robustez previa

`robustness_suite.py`

- 30 estaciones QR en paralelo.
- 3.000 lecturas.
- 3.000 OK.
- 0 errores.
- Promedio: 0.207 s.
- p95: 0.231 s.
- Maximo: 0.303 s.
- Rendimiento: 143.8 QR/s.
- Doble lectura simultanea del mismo QR: 1 concedido, 999 rechazados.
- Backup bajo carga: 912 operaciones OK, 0 errores.
- Recuperacion post reinicio OK.

`station_stress_test.py`

- 30 estaciones.
- Escalas de 30 a 3.000 lecturas.
- 100% de exito.
- Punto de quiebre: sin quiebre hasta el maximo probado.

## Errores humanos

`verificar_errores_humanos.py`

Validado:

- QR equivocado no concede acceso.
- QR anticipado no concede acceso.
- QR repetido no concede acceso.
- Acreditacion cancelada no permite ingreso.
- Acreditacion reactivada vuelve a estado operativo.
- Inscripcion duplicada se reconoce como existente.
- Persona sin QR puede buscarse por recepcion.
- Cambio de sala y cancelacion de actividad quedan auditados.
- CSV/agenda con errores responden de forma controlada.

Resultado: OK.

## Corte y recuperacion

`verificar_recuperacion.py`

Validado:

- Reinicio del servidor.
- QR usado sigue usado despues del reinicio.
- Inscripcion incompleta no deja estado incoherente.
- Validacion incompleta no concede acceso.
- Importacion incompleta informa errores.
- Backup genera archivo recuperable.
- `PRAGMA integrity_check` OK.
- Dashboard responde despues del reinicio.

Resultado: OK.

## Seguridad basica

`verificar_seguridad_basica.py`

Validado:

- Rol Acceso no puede crear evento.
- Rol Acceso no puede modificar cupos.
- Rol Acceso no puede enviar comunicaciones masivas.
- Rol Recepcion no puede preparar evento.
- Visualizador no puede editar acreditados.
- Pantalla publica no expone email, telefono ni DNI.
- Sala de control no expone datos sensibles.
- QR no contiene datos personales.
- Portal participante no permite ver datos de otro participante.

Resultado: OK.

## Datos basura

`verificar_datos_basura.py`

Validado:

- Caracteres raros y nombres largos.
- DNI duplicado controlado.
- Email invalido controlado.
- CSV con columnas faltantes.
- CSV con columnas extra.
- Agenda con horarios solapados.
- Agenda sin sala.
- Agenda sin horario.
- Actividad sin nombre.
- ICS corrupto.

Resultado: OK.

## Tiempos operativos

`verificar_tiempos_operativos.py`

Reporte generado: `BITORA_PERFORMANCE_REPORT.md`

Ultima medicion:

- Inscripcion: 0.009 s.
- Busqueda recepcion: 0.002 s.
- Generacion QR/credencial: 0.034 s.
- Validacion QR: 0.009 s.
- Dashboard: 0.008 s.
- Portal: 0.003 s.
- Exportacion CSV: 0.008 s.
- Backup: 0.018 s.

Resultado: OK.

## Concurrencia critica

`verificar_concurrencia_critica.py`

Validado:

- 100 escaneos simultaneos del mismo QR: 1 concedido, 99 rechazados.
- 100 reservas simultaneas al ultimo cupo: 1 confirmado, 99 en espera.
- 100 operadores consultando dashboard: 100 OK.
- Importaciones concurrentes responden controladamente.
- Doble click masivo de formulario: solo una inscripcion real.

Resultado: OK.

## Errores encontrados y corregidos durante QA2

- Ajuste de seed masivo para generar tokens con el mismo mecanismo real de BITORA.
- Ajuste de prueba de QR para usar la ruta real de credencial/QR.
- Ajuste de recuperacion para aceptar errores HTTP controlados como rechazo valido cuando no hay token.
- Ajuste de agenda basura para provocar solape sobre la sala real del evento.

No se detectaron corrupciones de base, sobrecupos, duplicacion de QR concedidos ni exposicion de datos sensibles en los flujos probados.

## Pendientes recomendados antes de evento real

- Repetir QA2 contra PostgreSQL cuando se active modo produccion.
- Repetir prueba desde la URL cloud final con varios celulares reales.
- Probar impresora termica de pulseras con papel real antes del evento.
- Definir limite operativo esperado por sede: cantidad de estaciones, red WiFi y cantidad de participantes por minuto.
