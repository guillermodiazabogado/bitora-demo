# BITORA Deployment Current State

## Arquitectura actual

BITORA es una aplicacion Python servida por `server.py` y expuesta mediante `backend/app.py`.

El servidor HTTP usa `ThreadingHTTPServer` y publica:

- frontend estatico;
- API operativa;
- `/health`;
- diagnostico tecnico;
- backups;
- comunicaciones;
- QR;
- portal participante.

## Inicio de aplicacion

Comando actual:

```bash
python backend/app.py
```

En Render se usa el mismo comando.

## Worker y colas

La cola durable vive en la tabla `jobs`.

Antes de BDF, el worker arrancaba embebido dentro del proceso web mediante `start_job_worker()`.

Para staging se agrego:

```bash
python backend/worker.py
```

El proceso web puede desactivar el worker embebido con:

```text
BITORA_DISABLE_EMBEDDED_WORKER=1
```

## Base de datos

BITORA soporta:

- SQLite local/demo.
- PostgreSQL mediante `QR_DB_ENGINE=postgres`.

Variables reales:

- `QR_DB_ENGINE`
- `QR_SQLITE_PATH`
- `QR_POSTGRES_DSN`
- `DATABASE_URL`
- `QR_POSTGRES_POOL_MIN`
- `QR_POSTGRES_POOL_MAX`

Las migraciones PostgreSQL se aplican desde:

```text
backend/migrations/
```

mediante `server.init_db()`.

## Storage

Storage local:

```text
BITORA_STORAGE_PATH
```

El servicio `StorageService` aisla archivos por evento bajo:

```text
storage/events/{event_id}/...
```

## Backups

Backups operativos:

- SQLite / PostgreSQL segun motor activo;
- bundles por evento;
- storage asociado;
- manifiestos y checksums.

## Health checks

Endpoint:

```text
GET /health
```

Devuelve estado de:

- app;
- env;
- db;
- jobs;
- cache;
- backup;
- storage;
- uptime.

## Riesgos actuales

- El worker embebido es correcto para demo simple, pero staging necesita worker separado.
- PostgreSQL live todavia debe ejecutarse en entorno real.
- Disaster y endurance no deben correr en la demo publica.
- El score release seguira bloqueado hasta levantar staging real.

## Decision BDF

Se adopta Docker Compose como mecanismo reproducible de staging porque permite:

- PostgreSQL real;
- storage persistente;
- worker separado;
- monitor basico;
- destruccion/recreacion controlada.
