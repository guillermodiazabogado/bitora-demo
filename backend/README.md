# Backend

API central de la plataforma.

Entrada actual:

```powershell
python backend\app.py
```

Por compatibilidad, `server.py` conserva el servidor HTTP y la logica existente. La nueva ruta de crecimiento es mover reglas criticas desde `server.py` hacia `backend/services` y exponerlas por endpoints API.

## Responsabilidades

- Eventos, actividades, espacios y agenda.
- Acreditaciones, QR, reservas, cupos y accesos.
- Usuarios, roles, auditoria, reportes y backups.
- Integraciones externas: WhatsApp, email, pagos y servicios futuros.
- Jobs/colas para tareas externas o lentas.

## Base de datos

Modo actual:

- SQLite para demo/local.

Objetivo de produccion:

- PostgreSQL.

Variables preparadas:

```powershell
$env:QR_DB_ENGINE='postgres'
$env:QR_POSTGRES_DSN='postgresql://usuario:clave@host:5432/base'
```

Mientras `QR_DB_ENGINE` sea `sqlite`, la app usa `acreditaciones.sqlite3`.

## Migracion interna

Estado documentado en:

```text
backend/MIGRATION_STATUS.md
```

Reportes V4:

```text
V4_MIGRATION_REPORT.md
V4_TEST_REPORT.md
```
