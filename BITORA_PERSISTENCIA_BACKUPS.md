# BITORA - Persistencia Multi-Evento y Backups

Estado: base consolidada inicial
Version relacionada: RC1-live-demo-10 + persistencia/backups
Fecha: 2026-07-20

## Objetivo

Separar con claridad los datos globales de BITORA de los datos propios de cada evento, reforzar el aislamiento multi-evento y evitar que un backup o exportacion de evento incluya informacion de otros eventos.

## Estado Actual

BITORA ya trabaja con una base unica para multiples eventos. La mayor parte de las tablas operativas tienen `event_id` y los endpoints principales filtran por evento activo.

El sistema cuenta con:

- SQLite para demo/local.
- PostgreSQL preparado para produccion.
- Backup completo de base.
- Bundle productivo con base + storage + `manifest.json`.
- Verificacion de integridad por checksum.
- Auditoria de backups.
- Usuarios, roles y asignacion por evento.
- Matriz editable de permisos.

## Datos Globales

Estas entidades son globales de plataforma:

- `users`
- `role_permissions`
- `role_action_permissions`
- configuracion tecnica por variables de entorno
- storage global cuando se usa backup completo
- `technical_logs`

Estas entidades no deben exportarse completas dentro de un backup de evento.

## Datos Por Evento

Estas entidades pertenecen al evento y deben quedar aisladas por `event_id`:

- `events`
- `accreditation_types`
- `spaces`
- `activities`
- `capacity_bags`
- `public_display_config`
- `public_display_items`
- `accreditations`
- `reservations`
- `access_logs`
- `communication_logs`
- `communication_queue`
- `email_delivery_events`
- `communication_assistant_history`
- `communication_tickets`
- `communication_templates` de evento
- `participant_announcements`
- `captation_events`
- `conversation_sources`
- `activity_attendance`
- `certificate_eligibility`
- `jobs`
- `waiting_room_visitors`
- `simulator_state`
- `visualization_layouts`
- auditoria relacionada con ese evento

## Entidades Compartidas Con Alcance De Evento

`people` es global por email, pero en la practica se exporta por evento usando su relacion con `accreditations`.

Para backup de evento, solo se incluyen personas que tienen acreditacion en ese evento.

`participant_communication_preferences` tambien se exporta solo para las personas vinculadas al evento.

## Cambio Implementado

Se agrego `EventBackupService`.

Este servicio genera un ZIP con:

- `event-{event_id}.json`
- `manifest.json`
- conteo de registros por tabla
- checksum SHA-256 del payload
- version de app
- motor de base usado
- actor que genero el backup

El backup de evento:

- incluye solo el evento solicitado;
- incluye solo participantes vinculados a ese evento;
- no incluye otros eventos;
- no incluye usuarios globales salvo asignaciones del evento;
- no reemplaza el backup productivo completo.

## Endpoint Ajustado

`GET /api/backup?event_id={id}`

Ahora genera backup acotado al evento.

Requiere:

- usuario asignado al evento;
- `backups.create_event`;
- `backups.download`.

`GET /api/backup`

Queda reservado para backup completo de sistema.

Requiere:

- `backups.create_full`;
- `backups.download`.

## Permisos Nuevos

Se agregaron permisos finos:

- `backups.view`
- `backups.create_event`
- `backups.create_full`
- `backups.download`
- `backups.verify`
- `backups.restore_event`
- `backups.restore_full`
- `backups.manage_schedule`
- `backups.manage_retention`
- `backups.view_logs`
- `backups.view_manifest`

Valores iniciales:

- Super Admin: todos habilitados.
- Productor: backup del evento, descarga, verificacion y manifiesto.
- Resto de roles: sin permisos de backup por defecto.

## Auditoria

Se audita:

- backup de evento creado;
- backup completo creado;
- resultado de integridad;
- intentos denegados por falta de permisos;
- evento asociado.

## Prueba Agregada

`verificar_persistencia_backups.py`

Valida:

- se crea un backup de un evento;
- el manifiesto es valido;
- el checksum coincide;
- no se filtra otro evento;
- no se filtran personas de otro evento;
- Productor no puede backup completo por defecto;
- Super Admin conserva permisos totales.

## Riesgos Pendientes

1. Restauracion selectiva de evento:
   - preparado conceptualmente, todavia no expuesto como accion operativa.

2. Storage por evento:
   - el backup completo ya respalda storage.
   - el backup por evento hoy prioriza datos de base.
   - conviene ordenar futuras imagenes/adjuntos bajo prefijos por evento.

3. Auditoria:
   - la auditoria historica se filtra por `entity_type/event_id` y por payload.
   - a futuro conviene agregar `event_id` directo a `audit_logs`.

4. People global:
   - hoy `people.email` es unico global.
   - para multi-evento real puede convenir permitir la misma persona en varios eventos sin friccion, manteniendo identidad global.

## Proximo Paso Recomendado

Implementar restauracion controlada de backup de evento en modo seguro:

1. Subir ZIP.
2. Verificar manifest.
3. Validar checksum.
4. Mostrar resumen antes de restaurar.
5. Restaurar como evento nuevo por defecto.
6. Solo permitir sobrescribir evento existente con confirmacion fuerte.
7. Auditar todo.

## Conclusion

BITORA queda mejor preparado para operar multiples eventos sin mezclar informacion. El backup de evento ya no es una descarga completa disfrazada, sino un artefacto aislado, verificable y auditable.
