# BITORA - Informe de Compatibilidad SQLite/PostgreSQL

Fecha: 2026-07-20

## Estado Actual

BITORA mantiene SQLite como motor local/demo y PostgreSQL como motor productivo preparado.

Componentes existentes:

- `backend/database.py`: seleccion de motor, pool PostgreSQL, traduccion SQL basica y migraciones.
- `backend/migrations/`: esquema PostgreSQL versionado.
- `backend/repositories/postgres.py`: bloqueos de fila en decisiones criticas.
- `migrar_sqlite_a_postgres.py`: migracion controlada desde SQLite.
- `verificar_postgres.py`: validacion estatica y prueba real cuando existe DSN.
- `verificar_production_postgres.py`: validacion de preparacion productiva.

## Dependencias Detectadas

| Archivo | Dependencia | Impacto | Tratamiento |
| --- | --- | --- | --- |
| `server.py` | `AUTOINCREMENT` en esquema SQLite | Solo aplica al init SQLite | PostgreSQL usa migraciones separadas |
| `server.py` | `PRAGMA table_info` | Introspeccion SQLite | Adaptador PostgreSQL traduce PRAGMA a no-op y servicios tienen fallback a `information_schema` donde corresponde |
| `server.py` | `INSERT OR IGNORE` | Sintaxis SQLite | Traductor lo convierte a `ON CONFLICT DO NOTHING` |
| `server.py` | `datetime('now', '-15 minutes')` | Funcion SQLite | Traductor lo convierte a `CURRENT_TIMESTAMP - INTERVAL` |
| `backend/services/backup.py` | `PRAGMA wal_checkpoint` | Solo backup SQLite | `PostgresBackupService` usa backup logico JSON |
| `backend/services/backup.py` | `PRAGMA quick_check` | Verificacion SQLite | Adaptador responde para compatibilidad; recuperacion real PG requiere prueba sobre base aislada/proveedor |
| `backend/services/jobs.py` | `BEGIN IMMEDIATE` | Bloqueo SQLite | Traductor lo convierte a `BEGIN`; jobs usan `FOR UPDATE SKIP LOCKED` en PostgreSQL |
| `backend/services/capacity_buckets.py` | Conteo + decision de cupo | Riesgo de concurrencia | Se usa `FOR UPDATE` en PostgreSQL para bolsas/capacidad |
| `backend/repositories/postgres.py` | QR/acceso/reserva | Critico | Usa `FOR UPDATE` y `SKIP LOCKED` |

## Configuracion Consolidada

Variables primarias:

- `QR_DB_ENGINE=sqlite|postgres`
- `QR_SQLITE_PATH`
- `QR_POSTGRES_DSN`
- `QR_POSTGRES_POOL_MIN`
- `QR_POSTGRES_POOL_MAX`

Aliases cloud aceptados:

- `DATABASE_ENGINE`
- `DATABASE_URL`
- `DB_POOL_MIN`
- `DB_POOL_MAX`
- `DB_CONNECTION_TIMEOUT`
- `DB_STATEMENT_TIMEOUT_MS`

Prioridad:

1. Variables `QR_*`.
2. Aliases cloud.
3. Valores por defecto seguros.

## Migraciones

Las migraciones PostgreSQL viven en:

```text
backend/migrations/
```

La tabla:

```text
schema_migrations
```

registra cada archivo aplicado.

## Concurrencia

Protecciones actuales:

- QR/acreditacion con `FOR UPDATE`.
- Reserva/capacidad con `FOR UPDATE`.
- Lista de espera con `FOR UPDATE SKIP LOCKED`.
- Jobs con `FOR UPDATE SKIP LOCKED`.
- Tokens y relaciones criticas con constraints/indices.

Riesgo pendiente:

- Validar con una base PostgreSQL real bajo carga antes de evento real.

## Migracion SQLite -> PostgreSQL

El script:

```text
migrar_sqlite_a_postgres.py
```

ahora:

- aplica migraciones;
- genera backup previo SQLite;
- copia tablas en orden de dependencias;
- conserva IDs;
- reajusta secuencias;
- compara conteos;
- valida relaciones principales;
- genera reporte JSON;
- permite `--dry-run`.

## Backups

PostgreSQL cuenta con backup logico JSON desde `PostgresBackupService`.

Recomendacion productiva:

- usar backup administrado del proveedor;
- snapshots diarios;
- `pg_dump` antes de migraciones mayores;
- probar restauracion en base aislada.

## Estado De Aceptacion

Estado: **Preparado para staging PostgreSQL**.

No debe declararse apto para evento real hasta ejecutar:

- `verificar_postgres.py` con `QR_POSTGRES_DSN`;
- `verificar_production_postgres.py` con `QR_POSTGRES_DSN`;
- prueba de migracion SQLite -> PostgreSQL sobre copia real;
- prueba de concurrencia critica contra PostgreSQL;
- prueba de backup/restauracion en base aislada.
