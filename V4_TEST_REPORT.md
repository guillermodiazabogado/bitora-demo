# V4 Test Report

## Suite obligatoria

Resultados de la ultima ejecucion V4:

- `verificar_mvp.py`: OK.
- `verificar_v2.py`: OK.
- `verificar_v3.py`: OK.
- `verificar_v4.py`: OK.
- `verificar_demo_real.py`: OK.
- `robustness_suite.py`: OK.
- `station_stress_test.py`: OK.

## Cobertura de verificar_v4.py

- Arquitectura: carpetas, `backend/app.py`, `server.py`, servicios y repositorios.
- Evento: preparacion, tipos, espacio y actividades.
- Agenda: transicion minima y rechazo de solapamiento.
- Inscripcion: token unico, QR y portal.
- Reservas: reserva desde portal, lista de espera, cancelacion y promocion.
- Accesos: QR correcto, QR reutilizado, QR cancelado, actividad requerida sin reserva.
- Bolsas: creacion, disponibilidad, movimiento y permisos.
- Pantalla publica: modos aeropuerto, ahora/proximas y sala sin datos sensibles.
- Comunicaciones demo: preferencias, envio demo e historial.
- Backups: archivo creado, integridad SQLite, export JSON y auditoria.
- Roles: Admin configura, Recepcion cancela/acredita, Acceso valida y no modifica cupos.

## Observaciones

Durante V4 se corrigio:

- Auditoria de acceso ahora incluye `event_id`.
- Auditoria de backup ahora incluye `event_id` cuando se solicita con `event_id`.
- Estado del sistema incluye integridad y edad del ultimo backup.

Este archivo debe actualizarse con los resultados finales despues de correr la suite completa.
## Robustez final

`robustness_suite.py`:

- 30 estaciones x 100 lecturas: 3000/3000 OK.
- Operacion mixta: 1912/1912 OK.
- Doble lectura simultanea: 1 concedido, 999 rechazados por QR usado.
- Base grande 10000: 4/4 OK.
- Backup bajo carga: 912/912 OK.
- Caida y recuperacion: OK.
- Datos malos y permisos: OK.

`station_stress_test.py`:

- 30 estaciones hasta 100 lecturas por estacion.
- Maximo probado: 3000/3000 OK.
- Corte: sin quiebre hasta el maximo probado.

## Demo real V4.0.5

`verificar_demo_real.py`:

- Evento demo creado: OK.
- 500 participantes: OK.
- 5 espacios: OK.
- 20 actividades: OK.
- Tipos, bolsas, reservas y lista de espera: OK.
- Portal participante y QR: OK.
- Pantalla publica sin datos sensibles: OK.
- Comunicaciones demo: OK.
- Backups antes/despues e integridad: OK.
- Auditoria demo: OK.
