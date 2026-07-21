# LOCAL MACHINE DIAGNOSTIC

Fecha: 2026-07-21

## Objetivo

Validar que esta PC pueda ejecutar BITORA en staging local mediante BDF.

## Resultado general

```text
PC LISTA PARA STAGING LOCAL
```

## Validaciones reales

```text
WSL2: OK
Ubuntu: OK
Docker: OK
Docker Engine: OK
Docker Compose v5.3.1: OK
```

Docker fue detectado en:

```text
C:\Users\Noxie-PC\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe
```

## Repositorio

Ruta:

```text
C:\Users\Noxie-PC\Documents\qr white label
```

Commit base solicitado:

```text
4f24920298647789d963dafe24fd35fa83635aa6
```

Estado inicial:

```text
Repositorio limpio antes de las correcciones de staging.
```

## BDF check

Comando ejecutado:

```powershell
python deployment/scripts/bdf.py check
```

Resultado:

```text
BDF check: PASSED
Docker: PASSED
Docker Compose: PASSED
Safe env: PASSED
```

## Staging local

Servicios levantados:

```text
bitora-staging-app: healthy
bitora-staging-postgres: healthy
bitora-staging-worker: running
bitora-staging-monitor: running
```

Puertos:

```text
Aplicacion: http://localhost:8788
PostgreSQL: localhost:55432
```

## Health

Resultado:

```text
APP: HEALTHY
POSTGRES: HEALTHY
STORAGE: HEALTHY
SAFE_MODE: ACTIVE
BACKUP: AVAILABLE
```

## Diagnostico final

La maquina local ya permite ejecutar BITORA en staging con Docker, PostgreSQL real, worker separado, monitor, storage persistente, safe mode, backup y restore local.

Quedan fuera de esta etapa las integraciones externas live: Google OAuth, email real por organizacion, WhatsApp real por organizacion y webhooks tenant-aware live.
