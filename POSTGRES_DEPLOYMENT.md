# BITORA - PostgreSQL para produccion inicial

## Alcance

BITORA soporta dos motores:

- `sqlite`: desarrollo, demo local, pruebas y contingencia.
- `postgres`: demo online seria, produccion y eventos reales.

La seleccion se realiza por variables de entorno. La experiencia del operador y los endpoints no cambian.

## Variables

```env
APP_ENV=production
QR_DB_ENGINE=postgres
QR_POSTGRES_DSN=postgresql://usuario:password@host:5432/bitora
QR_POSTGRES_POOL_MIN=1
QR_POSTGRES_POOL_MAX=10
QR_SQLITE_PATH=acreditaciones.sqlite3
```

Para volver a SQLite:

```env
APP_ENV=development
QR_DB_ENGINE=sqlite
QR_SQLITE_PATH=acreditaciones.sqlite3
```

## Crear una base nueva

1. Crear una base PostgreSQL vacia.
2. Configurar `QR_POSTGRES_DSN`.
3. Instalar dependencias:

```bash
pip install -r requirements.txt
```

4. Iniciar BITORA:

```bash
python backend/app.py
```

Al iniciar, BITORA aplica automáticamente las migraciones pendientes de `backend/migrations/`.
La tabla `schema_migrations` registra las versiones aplicadas.

## Migrar datos desde SQLite

Detener escrituras durante la migracion y ejecutar:

```bash
python migrar_sqlite_a_postgres.py
```

Opciones:

```bash
python migrar_sqlite_a_postgres.py --sqlite acreditaciones.sqlite3 --dsn "postgresql://..." --replace
```

El script:

1. genera un backup previo en `backups/`;
2. aplica migraciones;
3. copia datos respetando IDs;
4. reajusta secuencias;
5. compara cantidades;
6. genera un reporte JSON en `output/migration/`.

Usar `--replace` solamente cuando la base PostgreSQL destino puede vaciarse.

## Validacion

Validacion estatica sin una base remota:

```bash
python verificar_postgres.py
```

Validacion real:

```bash
set QR_POSTGRES_DSN=postgresql://usuario:password@host:5432/bitora
python verificar_postgres.py
```

La prueba real aplica migraciones y ejecuta operaciones dentro de una transaccion que finalmente se revierte.

## Concurrencia

PostgreSQL utiliza:

- pool de conexiones configurable;
- bloqueos `FOR UPDATE` para acreditacion, QR, actividad, cupos y promociones;
- `FOR UPDATE SKIP LOCKED` para lista de espera;
- restricciones unicas para tokens, reservas y acceso concedido por actividad;
- transacciones cortas en endpoints criticos.

Para produccion con alta carga se recomienda usar el DSN del pooler de Render, Railway, Supabase o PgBouncer en modo transaccion.

## Backups

Con SQLite, BITORA mantiene copias `.sqlite3`.

Con PostgreSQL, BITORA genera un backup logico JSON desde el panel. Para recuperacion ante desastres se debe habilitar ademas:

- backups administrados del proveedor;
- snapshots diarios;
- retencion minima de 7 a 30 dias;
- `pg_dump` externo antes de cambios importantes.

El backup JSON de la aplicacion no reemplaza los snapshots del proveedor.

## Render

1. Crear PostgreSQL administrado.
2. Copiar el Internal Database URL.
3. Configurar:

```env
APP_ENV=production
QR_DB_ENGINE=postgres
QR_POSTGRES_DSN=<Internal Database URL>
QR_POSTGRES_POOL_MIN=1
QR_POSTGRES_POOL_MAX=10
```

4. Mantener:

```text
Build Command: pip install -r requirements.txt
Start Command: python backend/app.py
Health Check: /health
```

## Railway

Agregar PostgreSQL al proyecto y mapear:

```env
QR_DB_ENGINE=postgres
QR_POSTGRES_DSN=${{Postgres.DATABASE_URL}}
```

Usar un pool maximo conservador en planes pequeños.

## VPS Linux

Se recomienda PostgreSQL 15 o superior, conexión TLS, usuario exclusivo para BITORA y proxy HTTPS. No ejecutar con el usuario administrador de PostgreSQL.

## Reversion operativa

Para volver temporalmente a SQLite:

1. detener BITORA;
2. restaurar la copia SQLite correspondiente;
3. cambiar `QR_DB_ENGINE=sqlite`;
4. definir `QR_SQLITE_PATH`;
5. reiniciar y verificar `/health`.

Los datos nuevos creados en PostgreSQL después de la migración no vuelven automáticamente a SQLite.
