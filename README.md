# Plataforma de acreditaciones QR

MVP local para operar eventos, inscripciones, acreditaciones, tokens QR, recepcion y control de acceso.

## Ejecutar

Opcion simple: doble clic en:

```text
iniciar_plataforma.bat
```

Para operar desde otras PCs de la misma red local, doble clic en:

```text
iniciar_red_local.bat
```

O usar el Python incluido por Codex:

```powershell
& 'C:\Users\Noxie-PC\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' backend\app.py
```

Luego abrir:

```text
http://localhost:8787
```

Para operar desde otras maquinas de la red local:

```powershell
$env:QR_HOST='0.0.0.0'; & 'C:\Users\Noxie-PC\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' backend\app.py
```

Cuando se expone en red local, la consola pide PIN:

- Admin: `1234`
- Recepcion: `2222`
- Acceso: `3333`

La landing publica y las credenciales siguen abiertas para participantes.

Para ajustar backups automaticos:

```powershell
$env:QR_AUTO_BACKUP_MINUTES='5'
$env:QR_BACKUP_KEEP_LAST='48'
```

## Arquitectura preparada

El proyecto ya esta separado en:

- `frontend/`: dashboard, recepcion, escaner QR, pantalla publica, portal participante y landing publica.
- `backend/`: entrada de API, configuracion de base de datos, servicios de negocio, integraciones futuras y jobs/colas.

El sistema sigue funcionando igual para operar hoy, pero el camino de crecimiento queda orientado a frontend consumiendo API y reglas criticas en backend.

Documentos:

- `ARCHITECTURE.md`
- `backend/API_CONTRACT.md`
- `backend/README.md`
- `frontend/README.md`

## Que incluye esta primera version

- Crear eventos.
- Landing publica simple por evento.
- Registrar participantes.
- Inscripcion publica sin login.
- Seleccion de actividades en inscripcion publica.
- Importacion masiva de acreditados desde CSV pegado en recepcion.
- Generar acreditacion con token unico y QR local.
- Portal publico de participante.
- Impresion individual de credencial con QR.
- Recepcion con busqueda y filtros por estado/tipo.
- Impresion por lote de credenciales respetando filtros de recepcion.
- Acreditacion manual desde recepcion.
- Validacion de acceso con bloqueo transaccional.
- Tipos de acreditacion con cupos y acceso habilitado/deshabilitado.
- Espacios y actividades con transicion minima de 15 minutos.
- Exportacion CSV de reservas por actividad o agenda completa.
- Reservas de actividades con lista de espera automatica.
- Cancelacion de reservas con promocion automatica del primer participante en espera.
- Reservas creadas desde formulario publico.
- Control de acceso por actividad con reserva confirmada.
- Bolsas de cupos por actividad: online, mostrador, empresas, invitaciones, sponsors, prensa, protocolo, staff y backup operativo.
- Disponibilidad publica efectiva sin mostrar capacidad fisica.
- Liberacion/movimiento dinamico de cupos entre bolsas.
- Pantalla publica separada para TV/proyector.
- Modos de pantalla publica: aeropuerto, ahora/proximas y por sala.
- Mensajes generales para pantalla publica.
- Portal personal del participante con credencial, QR unico, agenda, reservas, novedades, preferencias y certificados futuros.
- Reserva posterior de actividades desde el portal personal.
- Consentimientos operativos por email y WhatsApp.
- Centro de comunicaciones interno en modo demo.
- Historial de comunicaciones y plantillas base.
- Detalle operativo de actividad con bolsas y ocupacion.
- Alertas operativas de cupos llenos y listas de espera.
- Usuarios operativos con roles basicos.
- Permisos minimos por rol para configuracion, recepcion y acceso.
- Edicion, cancelacion y reactivacion de acreditaciones desde recepcion.
- Auditoria de inscripciones y accesos.
- Auditoria visible de acciones operativas.
- Exportacion CSV de acreditados.
- Exportacion CSV de reservas.
- Exportacion JSON completa del evento.
- Backup descargable de la base SQLite.
- Backup automatico cada 10 minutos con retencion de copias.
- Estado operativo del sistema en el dashboard.
- Semaforo de preparacion antes de abrir puertas.
- Resumen operativo por estado, tipo, reservas, actividades y accesos.
- Operadores activos en los ultimos 15 minutos.
- Ultimos rechazos visibles para detectar problemas de acceso.

## Resguardo

Desde el panel operativo:

- `Exportar JSON`: descarga todos los datos del evento activo.
- `Backup`: descarga una copia completa de la base y deja otra copia en `backups/`.
- Backup automatico: por defecto corre cada 10 minutos y conserva las ultimas 24 copias.

## Preparar evento real

En el panel operativo, abrir `Preparar evento real`.

Esa accion:

- Crea un backup previo.
- Limpia datos operativos actuales: eventos, personas, acreditaciones, accesos, actividades y reservas.
- Crea un evento nuevo publicado.
- Crea tipos de acreditacion base.
- Crea el espacio `Auditorio principal`.

Para confirmar hay que escribir `PREPARAR`.

## Modo dia de evento

El panel muestra:

- Servidor online.
- Semaforo de preparacion.
- Resumen de acreditaciones activas, pendientes, acreditadas y canceladas.
- Reservas confirmadas y lista de espera.
- Actividades con cantidad de reservas.
- Bolsas de cupos y disponibilidad publica.
- Pantalla publica para hall, TV o proyector.
- Escaneos de los ultimos 15 minutos.
- Rechazos de los ultimos 15 minutos.
- Operadores activos.
- Tamano de base local.
- Ultimo backup.
- Ultimos rechazos con motivo.

## Verificacion de salud

Antes de operar un evento, se puede correr:

```powershell
& 'C:\Users\Noxie-PC\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' verificar_mvp.py
```

La prueba usa una base temporal y no modifica `acreditaciones.sqlite3`.

Valida:

- Preparacion de evento real.
- Landing publica e inscripcion externa.
- Reservas desde inscripcion publica.
- Importacion masiva de acreditados.
- Cupos por tipo.
- QR de un solo uso.
- Cancelacion y permisos por rol.
- Agenda con transicion minima.
- Reservas, lista de espera y promocion automatica.
- Control de acceso por actividad.
- Pagina de impresion de credenciales.
- Resumen operativo.
- Semaforo de preparacion.
- Exportacion CSV de reservas por actividad.
- Bolsas de cupos y pantalla publica V2.
- Backup, exportacion JSON, estado operativo y QR local.

## Pruebas de robustez

Prueba integral:

```powershell
& 'C:\Users\Noxie-PC\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' robustness_suite.py
```

Prueba de 30 estaciones QR:

```powershell
& 'C:\Users\Noxie-PC\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' station_stress_test.py
```

Prueba V2:

```powershell
& 'C:\Users\Noxie-PC\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' verificar_v2.py
```

Prueba V3:

```powershell
& 'C:\Users\Noxie-PC\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' verificar_v3.py
```

Prueba V4:

```powershell
& 'C:\Users\Noxie-PC\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' verificar_v4.py
```

Prueba demo real V4.0.5:

```powershell
& 'C:\Users\Noxie-PC\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' verificar_demo_real.py
```

## Demo real V4.0.5

Desde el panel operativo se puede abrir `Crear Demo Real`, escribir `DEMO` y generar un evento completo ficticio:

- Congreso de Innovacion Neuquen 2027.
- 500 participantes simulados.
- 5 espacios.
- 20 actividades.
- Reservas, listas de espera y bolsas de cupos.
- Pantalla publica configurada.
- Participantes demo para probar portal, QR, agenda y reservas.
- Comunicaciones demo.
- Backup previo y backup posterior.

Ver `DEMO_REAL_REPORT.md`.

## Regla central

El token representa una acreditacion, no una persona. La validacion real vive en la base de datos.
