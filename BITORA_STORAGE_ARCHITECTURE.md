# BITORA - Arquitectura de Storage por Evento

## Estado

BITORA ya separa el almacenamiento fisico por evento y mantiene compatibilidad con el storage historico local.

El objetivo es que cada evento pueda:

- guardar sus propios archivos;
- generar backup individual con datos y archivos;
- restaurarse como evento nuevo;
- evitar mezcla de archivos entre eventos;
- quedar preparado para almacenamiento externo futuro.

## Estructura fisica

Raiz configurable:

```text
BITORA_STORAGE_PATH=storage
```

Estructura consolidada:

```text
storage/
  system/
    branding/
    icons/
    logos/
    providers/
  events/
    {event_id}/
      qr/
      credentials/
      certificates/
      uploads/
      exports/
      attachments/
      communications/
      images/
      public/
  temporary/
  backups/
    event/
    full/
```

Tambien se conservan las carpetas historicas:

```text
storage/landing
storage/qr
storage/certificates
storage/exports
storage/attachments
```

Esto evita romper codigo o datos existentes mientras se migra progresivamente al modelo por evento.

## Servicio central

El servicio `StorageService` es el punto unico de acceso al storage.

Funciones nuevas:

- `save_event(event_id, category, name, content)`
- `read_event(event_id, category, name)`
- `delete_event(event_id, category, name)`
- `event_inventory(event_id)`
- `event_size(event_id)`
- `restore_event_file(event_id, relative_path, content)`
- `delete_event_files(event_id)`

Todas las rutas se validan para impedir:

- path traversal;
- archivos fuera de la raiz;
- categorias no permitidas;
- nombres inseguros.

## Backup individual de evento

`EventBackupService` ahora incluye:

- payload de base de datos del evento;
- `manifest.json`;
- checksums SHA-256;
- conteo de tablas;
- archivos bajo `storage/events/{event_id}`.

El ZIP contiene:

```text
manifest.json
event-{event_id}.json
storage/events/{event_id}/...
```

No incluye archivos de otros eventos.

## Restauracion individual de evento

`EventRestoreService` ahora restaura tambien archivos del evento.

En modo predeterminado:

```text
Restaurar como nuevo evento
```

La restauracion:

- crea un nuevo `event_id`;
- remapea IDs internos;
- regenera tokens QR;
- deja comunicaciones y jobs inactivos;
- copia archivos del backup al nuevo `storage/events/{new_event_id}`;
- registra auditoria;
- hace rollback de base y limpia archivos del nuevo evento si falla.

## Auditoria por evento

`audit_logs` incorpora columna fisica:

```sql
event_id
```

Esto permite consultar auditoria por evento sin depender del contenido JSON en `payload`.

Se mantiene compatibilidad con auditoria anterior buscando tambien:

- `entity_type = 'event' AND entity_id = ?`;
- `payload LIKE '%"event_id": ?%'`.

## Migraciones

Nueva migracion:

```text
backend/migrations/011_event_storage_audit.sql
```

Incluye:

- `audit_logs.event_id`;
- indice `idx_audit_logs_event_created`.

## Preparacion para storage externo

La interfaz del servicio ya contempla `STORAGE_BACKEND`.

Valores:

```text
STORAGE_BACKEND=local
STORAGE_BACKEND=s3
```

El backend S3 queda preparado pero no activo. Para produccion futura se recomienda:

- S3 compatible;
- bucket privado;
- URLs firmadas;
- cifrado del proveedor;
- politicas por prefijo `events/{event_id}`;
- backups externos versionados.

## Pruebas

Prueba nueva:

```text
verificar_storage_event_backup_restore.py
```

Valida:

1. Archivos de evento se guardan bajo `storage/events/{event_id}`.
2. Backup de evento incluye solo archivos del evento.
3. No se filtran archivos de otro evento.
4. Vista previa informa cantidad y tamano de archivos.
5. Restauracion como nuevo evento reconstruye archivos.
6. Tokens QR se regeneran.
7. Personas globales no se duplican.
8. Auditoria queda vinculada al nuevo `event_id`.
9. El resultado queda aislado del evento original.

## Pendientes recomendados

- Migrar landing images desde base64 en DB hacia `storage/events/{event_id}/images`.
- Migrar credenciales/certificados generados bajo demanda hacia cache fisico opcional por evento.
- Agregar pantalla de metricas de storage por evento.
- Implementar S3 real cuando se active produccion con archivos pesados.
- Definir politica de retencion por evento.
