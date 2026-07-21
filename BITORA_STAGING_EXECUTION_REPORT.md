# BITORA Staging Execution Report

Fecha: 2026-07-21

## Objetivo

Levantar por primera vez el staging local completo de BITORA usando BDF, sin agregar funcionalidades nuevas ni configurar proveedores externos live.

## Commit base

```text
4f24920298647789d963dafe24fd35fa83635aa6
```

## Infraestructura utilizada

```text
Windows + WSL2 + Ubuntu
Docker Desktop
Docker Engine 29.6.2
Docker Compose v5.3.1
Python 3.12.13
```

## Variables configuradas

El archivo real usado fue:

```text
deployment/staging/.env.staging
```

No se versiona por Git.

Variables relevantes, sin secretos:

```text
APP_ENV=staging
BASE_URL=http://localhost:8788
QR_DB_ENGINE=postgres
DATABASE_ENGINE=postgres
BITORA_DISABLE_EMBEDDED_WORKER=1
BDF_WORKER_LIVE=1
BDF_STAGING_LIVE=1
EMAIL_SAFE_MODE=true
WHATSAPP_SAFE_MODE=true
BITORA_STORAGE_PATH=/bitora/storage
BITORA_BACKUP_PATH=/bitora/backups
```

## Comandos ejecutados

```powershell
python deployment/scripts/bdf.py check
python deployment/scripts/bdf.py build
python deployment/scripts/bdf.py up
python deployment/scripts/bdf.py status
python deployment/scripts/bdf.py health
python deployment/scripts/bdf.py migrate
python deployment/scripts/bdf.py smoke-test
python deployment/scripts/bdf.py backup
python deployment/scripts/bdf.py restore deployment/backup/artifacts/bitora-staging-20260721-040529.sql --yes
python deployment/scripts/bdf.py health
python deployment/scripts/bdf.py smoke-test
```

## Resultados

```text
Docker: PASSED
Docker Compose: PASSED
BDF check: PASSED
Build: PASSED
PostgreSQL: PASSED
App: PASSED
Worker separado: PASSED
Monitor: PASSED
Storage persistente: PASSED
Safe mode: PASSED
Health: PASSED
Migrations: PASSED
Backup: PASSED
Restore: PASSED
Smoke test final: PASSED
```

## Servicios activos

```text
bitora-staging-app: Up / healthy / http://localhost:8788
bitora-staging-postgres: Up / healthy / localhost:55432
bitora-staging-worker: Up
bitora-staging-monitor: Up
```

## Backup y restore

Backup validado:

```text
Archivo: bitora-staging-20260721-040529.sql
Tamanio: 213969 bytes
SHA-256: 95dbc7c065bbb171d6deb95f8c995980f3c83f389af56b21a8175d2f84c81f1a
```

Restore validado:

```text
Esquema public reconstruido.
Dump restaurado.
App, worker y monitor levantados nuevamente.
Health posterior: PASSED.
Smoke-test posterior: PASSED.
```

## Hallazgos corregidos

- Docker Desktop instalado por usuario no estaba en PATH global; BDF ahora lo detecta.
- Build context incluia archivos locales pesados; se agrego `.dockerignore`.
- PostgreSQL requirio ajustes de compatibilidad en migraciones, `statement_timeout`, `PRAGMA table_info`, `GROUP BY` y lectura escalar.
- Restore BDF necesitaba limpiar esquema antes de restaurar.
- Smoke-test `demo_live_10` necesitaba aislar su base temporal SQLite.

## Restricciones pendientes

Continuan fuera de esta etapa:

```text
google_oauth_live
email_organization_live
whatsapp_organization_live
webhook_tenant_resolution_live
```

Estas validaciones requieren credenciales y proveedores sandbox/live reales.

## Estado final

```text
STAGING LOCAL OPERATIVO CON RESTRICCIONES
```
