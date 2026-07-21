# BITORA Demo Live 10 - Informe final inicial

## Resumen ejecutivo

Se preparo y automatizo la prueba `BITORA Demo Live 10` para validar el circuito operativo completo con 10 participantes controlados. La ejecucion automatica cubre evento, usuarios, participantes, QR, reservas, lista de espera, accesos, asistencia, comunicaciones en cola, certificados, backup, restauracion y aislamiento.

## Entorno

- Fecha: 2026-07-20.
- Entorno automatico: SQLite temporal.
- Entorno recomendado para prueba humana: Render/Staging con HTTPS.
- Comunicaciones reales: pendientes de credenciales productivas y destinatarios autorizados.

## Version

Base actual: BITORA 7.x con preparacion PostgreSQL, email productivo y WhatsApp Cloud API productivo.

## Participantes

- 10 perfiles ficticios controlados.
- 6 origen publico.
- 2 origen administrativo.
- 2 origen importacion controlada.
- Todos aislados dentro del evento Demo Live 10.

## Escenarios ejecutados automaticamente

- Creacion de evento independiente.
- Asignacion de usuarios operativos por evento.
- Creacion de espacios, actividades y tipos.
- Creacion de 10 acreditaciones con QR unico.
- Reserva de actividad con cupo 5.
- Cancelacion y promocion desde lista de espera.
- Acceso general con QR.
- Rechazo de QR duplicado.
- Rechazo de QR invalido.
- Asistencia a actividades.
- Elegibilidad/certificados.
- Cola e historial de comunicaciones.
- Backup individual del evento.
- Inspeccion del backup.
- Restauracion como nuevo evento.
- Comparacion basica original/restaurado.

## Resultados

La prueba automatica se considera aprobada cuando `verificar_demo_live_10.py` finaliza con `OK` y genera `output/demo_live_10/demo_live_10_result.json`.

## Incidentes

Ver `BITORA_DEMO_LIVE_10_INCIDENTS.md`.

Incidentes abiertos principales:

- Envio real email/WhatsApp pendiente de credenciales productivas.
- Prueba con dispositivos reales pendiente.

## Riesgos pendientes

- Validar latencia real en Render.
- Validar camaras de celulares reales.
- Validar entrega real de email/WhatsApp.
- Registrar tiempos de recepcion/acceso con operadores humanos.
- Confirmar entrenamiento minimo de operadores.

## Recomendacion

Estado: **aprobado con condiciones para demo controlada**.

No pasar todavia a piloto real hasta ejecutar:

1. prueba humana con 10 personas/dispositivos;
2. email real con dominio verificado;
3. WhatsApp real con plantilla aprobada;
4. backup/restauracion en entorno online;
5. registro de incidentes y segunda ejecucion.
