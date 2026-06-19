# BITORA - Plan de recuperacion productiva

## Prioridad

1. Proteger inscripciones, acreditaciones y accesos.
2. Evitar escrituras durante una recuperacion.
3. Restaurar desde una copia verificada.
4. Confirmar integridad antes de reabrir.

## Si cae la aplicacion

1. Confirmar `/health` y el estado del proveedor.
2. Revisar logs de inicio, memoria y ultimo error.
3. Reiniciar una sola instancia.
4. Si no recupera, volver al ultimo deploy estable.
5. Mantener recepcion en contingencia con listado exportado y QR ya emitidos.

## Si cae PostgreSQL

1. Pausar inscripciones y accesos que requieran validacion online.
2. Confirmar estado del proveedor y pool.
3. Esperar la reconexion automatica breve.
4. Si no recupera, restaurar snapshot administrado o `pg_dump`.
5. No cambiar a SQLite con escrituras nuevas sin declarar modo contingencia.

## Restaurar backup

1. Detener BITORA.
2. Conservar una copia del estado fallido.
3. Verificar checksum y manifiesto del bundle.
4. Restaurar base y storage en rutas nuevas.
5. Ejecutar integridad, convivencia y una validacion QR.
6. Reabrir primero para Admin, luego operadores y finalmente publico.

## Modo contingencia

- Usar una version local validada y una copia SQLite solamente si fue preparada antes del evento.
- Registrar manualmente toda operacion realizada durante la contingencia.
- No mezclar luego bases divergentes sin una conciliacion controlada.

## Contactos tecnicos

- Responsable plataforma: completar antes del evento.
- Responsable base de datos: completar antes del evento.
- Responsable infraestructura/proveedor: completar antes del evento.
- Responsable operativo del evento: completar antes del evento.

## Checklist posterior

- `/health` en estado `ok`.
- PostgreSQL online y migraciones completas.
- Conteos de eventos, personas, acreditaciones y accesos validados.
- Backup nuevo creado y verificado.
- Login, recepcion, QR, portal, NOC y Sala de Control probados.
- Incidente y decisiones registrados.
