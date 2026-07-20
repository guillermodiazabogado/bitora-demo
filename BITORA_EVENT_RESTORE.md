# BITORA - Restauracion Controlada de Backups de Evento

Estado: implementacion operativa inicial
Fecha: 2026-07-20

## Objetivo

Permitir restaurar un backup individual de evento sin mezclar datos de otros eventos, sin reutilizar tokens sensibles y sin disparar comunicaciones ni jobs automaticos.

## Formato Esperado

El backup debe ser un ZIP generado por BITORA con:

- `manifest.json`
- `event-{event_id}.json`
- `storage/events/{event_id}/...` si el evento tiene archivos asociados

`manifest.json` debe incluir:

- `version`
- `schema_version`
- `scope = event`
- `backup_type = event`
- `event_id`
- `created_at`
- `created_by`
- `app_version`
- `database_engine`
- `payload.name`
- `payload.sha256`
- `payload.size`
- `storage[]` con `key`, `size` y `sha256` de cada archivo fisico del evento
- conteos por tabla

`event-{event_id}.json` debe incluir:

- `format = bitora.event.backup`
- `version`
- `schema_version`
- `event_id`
- `created_at`
- `created_by`
- `database_engine`
- `tables`

## Flujo Implementado

1. El administrador sube un ZIP.
2. BITORA valida extension y tamano.
3. BITORA abre el ZIP en memoria.
4. Se revisan rutas peligrosas y archivos no permitidos.
5. Se lee `manifest.json`.
6. Se verifica el checksum SHA-256 del payload.
7. Se verifican checksums de archivos del evento.
8. Se valida que el backup sea de tipo `event`.
9. Se genera una vista previa.
10. Se crea una referencia temporal `restore_id`.
11. El operador confirma la restauracion.
12. BITORA restaura dentro de una transaccion.
13. Se remapean IDs internos.
14. Se regeneran tokens QR.
15. Se desactivan comunicaciones y jobs restaurados.
16. Se restauran archivos bajo el nuevo `event_id`.
17. Se valida el resultado.
18. Se audita la operacion.

## Endpoints

### Inspeccion

`POST /api/backups/event/inspect`

Recibe:

- `filename`
- `content_base64`

Devuelve:

- `restore_id`
- datos del evento origen
- conteos
- checksum
- advertencias
- conflictos
- modo recomendado

No modifica la base.

### Restauracion

`POST /api/backups/event/restore`

Recibe:

- `restore_id`
- `mode`
- `new_event_name`
- `target_event_id` si corresponde
- `confirm_text` para sobrescritura

Modos:

- `new_event`
- `overwrite`

## Modo Predeterminado

El modo predeterminado es:

`new_event`

BITORA crea un evento nuevo, con estado `draft`, y no afecta el evento original.

## Sobrescritura Controlada

La sobrescritura existe como modo avanzado.

Requiere:

- permiso `backups.restore_event_overwrite`
- evento destino explicito
- texto exacto `RESTAURAR EVENTO`
- backup preventivo del evento destino

Si el backup preventivo falla, la restauracion no continua.

## Remapeo De IDs

Se remapean:

- evento
- espacios
- actividades
- bolsas de cupo
- acreditaciones
- reservas
- comunicaciones en cola
- relaciones dependientes

No se reutilizan claves primarias del backup.

## Archivos Del Evento

Los archivos fisicos se restauran desde:

`storage/events/{source_event_id}/...`

hacia:

`storage/events/{new_event_id}/...`

Reglas:

- no se aceptan rutas fuera del evento origen;
- no se aceptan rutas peligrosas;
- cada archivo se valida con SHA-256;
- si falla una restauracion como evento nuevo, se revierte la base y se eliminan archivos ya copiados;
- no se copian archivos de otros eventos;
- no se ejecutan efectos externos vinculados a archivos restaurados.

## Personas Globales

`people` se conserva como entidad global por email.

Reglas:

- si el email ya existe, se reutiliza la persona;
- si no existe, se crea;
- no se sobrescriben datos personales existentes;
- el conflicto queda informado en la vista previa y en el resultado.

## Usuarios

No se crean usuarios globales automaticamente.

Las asignaciones del evento se restauran solamente si el usuario ya existe.

Si falta un usuario:

- no se crea;
- queda informado como conflicto.

## Tokens Sensibles

Al restaurar como evento nuevo:

- se regeneran tokens QR;
- se limpian check-ins previos;
- se reinicia `access_count`;
- los access logs restaurados apuntan al token regenerado para mantener trazabilidad interna;
- no se reutilizan tokens originales.

## Comunicaciones

Las colas restauradas quedan en:

`restored_inactive`

No se envian automaticamente.

Los historiales se restauran como datos historicos.

## Jobs

Los jobs restaurados quedan en:

`cancelled`

No se ejecutan automaticamente.

## Auditoria

Se registra:

- inspeccion;
- denegacion por permisos;
- restauracion exitosa;
- restauracion fallida;
- modo;
- evento origen;
- evento destino;
- checksum;
- conteos;
- conflictos;
- archivos restaurados;
- duracion;
- backup preventivo si corresponde.

## Permisos

Permisos usados:

- `backups.restore_event`
- `backups.restore_event_overwrite`
- `backups.download`
- `backups.verify`
- `backups.view_manifest`

Super Admin tiene acceso total.

Productor no tiene restauracion habilitada por defecto; se puede activar desde la matriz.

## Interfaz

Se agrego una tarjeta:

`Configurar Evento -> Backups y Recuperacion`

Permite:

- subir ZIP;
- inspeccionar;
- ver resumen;
- restaurar como evento nuevo;
- usar sobrescritura avanzada si tiene permiso.

## SQLite Y PostgreSQL

La restauracion es logica por tabla y no copia archivos de base.

SQLite:

- usa transaccion;
- respeta constraints;
- rollback ante error.

PostgreSQL:

- queda preparada por el adaptador existente;
- no depende de archivos SQLite;
- usa inserciones logicas y remapeo.

## Limitaciones Actuales

- El backup de evento actual no incluye storage por evento.
- La restauracion de archivos queda preparada para una etapa posterior.
- La auditoria historica se restaura como referencia y se agrega auditoria nueva de restauracion.
- La sobrescritura es funcional, pero debe usarse solo como operacion excepcional.

## Pruebas

Prueba principal:

`verificar_event_restore.py`

Valida:

- inspeccion de ZIP valido;
- rechazo por checksum invalido;
- rechazo de backup de sistema;
- restauracion como evento nuevo;
- nuevo `event_id`;
- remapeo de relaciones;
- reutilizacion de persona por email;
- regeneracion de token QR;
- comunicaciones en `restored_inactive`;
- jobs en `cancelled`;
- auditoria registrada;
- no mezcla con evento origen.

## Criterio Operativo

La restauracion individual de evento queda lista para uso administrativo controlado.

Para eventos reales, la recomendacion sigue siendo:

1. hacer backup completo de plataforma;
2. inspeccionar backup de evento;
3. restaurar como evento nuevo;
4. validar manualmente;
5. solo usar sobrescritura con permiso especial y confirmacion reforzada.
