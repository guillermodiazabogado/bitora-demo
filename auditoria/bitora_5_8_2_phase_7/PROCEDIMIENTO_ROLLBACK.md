# Procedimiento de rollback — BITORA 5.8.2

## Alcance validado

El rollback operativo cubre la recreación de las dos instancias y el proxy desde una imagen inmutable, preservando PostgreSQL y los volúmenes. Las migraciones son forward-only: no se ejecuta automáticamente un downgrade destructivo de esquema.

## Antes de cambiar una versión

1. Registrar SHA y digest de la imagen activa.
2. Verificar `/ready` en ambas instancias.
3. Ejecutar un backup PostgreSQL y guardar su SHA-256.
4. Detener nuevas escrituras si la reversión requiere restaurar datos.
5. Confirmar que la imagen anterior sigue disponible localmente o en el registro autorizado.

## Reversión de aplicación

1. Detener las instancias, manteniendo PostgreSQL activo.
2. Seleccionar el tag/digest anterior verificado.
3. Recrear `app-1`, `app-2` y `proxy` sin borrar volúmenes.
4. Esperar healthchecks y validar `/ready`.
5. Ejecutar autenticación, sesión multiinstancia y smoke QR.
6. Si el esquema actual no es compatible con la aplicación anterior, detener el procedimiento y pasar a restauración coordinada.

## Restauración de base

La restauración debe hacerse en una base nueva y aislada, nunca sobre la base activa. Validar checksum, migraciones, estructura y conteos. Cambiar la aplicación a la base restaurada solo después de reconciliar los datos generados desde el punto del backup. El RPO no es cero sin replicación/WAL archivado.

## Criterio de recuperación

- Dos instancias saludables.
- Sesiones y autorización consistentes.
- Integridad PostgreSQL reconciliada.
- Sin errores críticos en logs.
- Responsable operativo registra inicio, fin, evidencia y pérdida de datos observada.

