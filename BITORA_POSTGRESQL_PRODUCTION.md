# BITORA - PostgreSQL Productivo

## Objetivo

Ejecutar BITORA sobre PostgreSQL para demo online seria, staging y produccion inicial, manteniendo SQLite para desarrollo y contingencia.

## Variables

Minimas:

```env
APP_ENV=production
QR_DB_ENGINE=postgres
QR_POSTGRES_DSN=postgresql://usuario:password@host:5432/bitora
QR_POSTGRES_POOL_MIN=1
QR_POSTGRES_POOL_MAX=10
DB_CONNECTION_TIMEOUT=10
DB_STATEMENT_TIMEOUT_MS=30000
```

Aliases aceptados:

```env
DATABASE_ENGINE=postgresql
DATABASE_URL=postgresql://usuario:password@host:5432/bitora
DB_POOL_MIN=1
DB_POOL_MAX=10
```

BITORA prioriza `QR_POSTGRES_DSN` sobre `DATABASE_URL`.

## Inicio En PostgreSQL

1. Crear base PostgreSQL vacia.
2. Configurar variables.
3. Instalar dependencias.
4. Iniciar:

```bash
python backend/app.py
```

Al iniciar, BITORA aplica migraciones de:

```text
backend/migrations/
```

## Validacion Rapida

Sin DSN real:

```bash
python verificar_postgres.py
python verificar_production_postgres.py
```

Con DSN real:

```bash
set QR_POSTGRES_DSN=postgresql://...
python verificar_postgres.py
python verificar_production_postgres.py
```

## Migracion Desde SQLite

Dry run:

```bash
python migrar_sqlite_a_postgres.py --sqlite acreditaciones.sqlite3 --dsn "postgresql://..." --dry-run
```

Migracion real sobre base vacia:

```bash
python migrar_sqlite_a_postgres.py --sqlite acreditaciones.sqlite3 --dsn "postgresql://..."
```

Migracion reemplazando destino:

```bash
python migrar_sqlite_a_postgres.py --sqlite acreditaciones.sqlite3 --dsn "postgresql://..." --replace
```

El script genera:

- backup previo SQLite;
- reporte JSON en `output/migration/`;
- comparacion de conteos;
- validacion de relaciones principales.

## Backup

BITORA soporta backup logico PostgreSQL desde la aplicacion.

Para produccion real, activar ademas:

- backups administrados del proveedor;
- snapshots diarios;
- retencion 7 a 30 dias;
- backup manual antes de migraciones;
- prueba de restauracion periodica.

## Restauracion

La restauracion individual por evento es logica y compatible con SQLite/PostgreSQL.

La restauracion completa de PostgreSQL debe probarse siempre en una base aislada:

1. Crear base temporal.
2. Restaurar backup del proveedor o dump.
3. Aplicar validaciones.
4. Conectar BITORA en staging.
5. Ejecutar smoke tests.

## Render

Variables recomendadas:

```env
APP_ENV=production
QR_DB_ENGINE=postgres
QR_POSTGRES_DSN=<Internal Database URL>
QR_POSTGRES_POOL_MIN=1
QR_POSTGRES_POOL_MAX=5
DB_CONNECTION_TIMEOUT=10
DB_STATEMENT_TIMEOUT_MS=30000
QR_REQUIRE_LOGIN=1
```

Comandos:

```text
Build Command: pip install -r requirements.txt
Start Command: python backend/app.py
Health Check: /health
```

## Railway

Usar `DATABASE_URL` o mapearlo:

```env
QR_DB_ENGINE=postgres
QR_POSTGRES_DSN=${{Postgres.DATABASE_URL}}
```

## Seguridad

Recomendaciones:

- usuario exclusivo para BITORA;
- no usar superusuario;
- SSL habilitado;
- credenciales solo en variables;
- restringir red cuando el proveedor lo permita;
- rotar credenciales ante filtraciones;
- no registrar DSN completo en logs.

## Criterio De Go/No-Go

BITORA puede pasar a PostgreSQL operativo cuando:

- migraciones aplican sin errores;
- migracion desde SQLite compara conteos OK;
- integridad no muestra orfandad;
- login, eventos, QR, reservas y comunicaciones funcionan;
- backup y restauracion fueron probados;
- pruebas de concurrencia pasan contra PostgreSQL;
- rollback esta documentado.
