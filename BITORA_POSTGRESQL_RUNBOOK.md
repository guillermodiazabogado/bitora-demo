# BITORA - Runbook PostgreSQL

## Base No Disponible

1. Verificar estado del proveedor PostgreSQL.
2. Revisar `/health`.
3. Revisar Diagnostico Tecnico.
4. Confirmar `QR_POSTGRES_DSN` o `DATABASE_URL`.
5. Reiniciar servicio si el proveedor ya recupero.
6. Si no recupera, activar plan de rollback.

No publicar credenciales en tickets ni chats.

## Pool Agotado

Sintomas:

- respuestas lentas;
- errores de conexion;
- p95/p99 elevados.

Acciones:

1. Reducir workers o instancias si exceden conexiones.
2. Revisar `QR_POSTGRES_POOL_MAX`.
3. Usar pooler del proveedor si existe.
4. Buscar consultas o transacciones largas.
5. Reiniciar solo si hay conexiones colgadas.

## Migracion Fallida

1. No abrir operacion.
2. Revisar reporte en `output/migration/`.
3. Corregir causa.
4. Descartar base destino fallida o ejecutar `--replace` solo en staging/base vacia.
5. Repetir migracion desde SQLite original protegido.

## Consulta Bloqueada

1. Revisar panel del proveedor.
2. Identificar query bloqueante.
3. Confirmar si esta relacionada con reservas, QR o jobs.
4. No matar procesos sin entender si hay transaccion critica.
5. Si es necesario, pausar workers no criticos.

## Backup Fallido

1. Verificar espacio disponible.
2. Verificar permisos de storage.
3. Ejecutar backup del proveedor.
4. Revisar logs de BITORA.
5. No continuar con migraciones sin backup valido.

## Restauracion

Nunca restaurar sobre produccion directamente.

Flujo:

1. Crear base aislada.
2. Restaurar backup.
3. Configurar BITORA staging contra esa base.
4. Ejecutar validaciones.
5. Comparar conteos.
6. Aprobar recuperacion.

## Rollback

Activar rollback si:

- migracion no compara conteos;
- integridad falla;
- QR o reservas fallan;
- rendimiento no permite operar.

Pasos:

1. Detener servicio.
2. Restaurar variables anteriores.
3. Volver a `QR_DB_ENGINE=sqlite`.
4. Usar SQLite protegido previo al corte.
5. Iniciar servicio.
6. Ejecutar smoke test.

Importante: las escrituras realizadas en PostgreSQL despues del corte no vuelven automaticamente a SQLite.

## Smoke Test Post-Cambio

Validar:

- `/health`;
- login;
- listado de eventos;
- landing;
- inscripcion;
- portal participante;
- QR;
- acceso general;
- reserva;
- comunicacion demo;
- backup.
