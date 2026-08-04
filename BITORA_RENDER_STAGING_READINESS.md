# BITORA Render Staging Readiness

Fecha: 2026-08-04

Rama: `deployment/v4-online`

HEAD validado: `4c70d4224acba79f3fc140ae1413248d165f4f59`

Estado: `READY FOR HOSTING APPROVAL`

## Resumen

BITORA esta online en Render como staging V4:

- Web service: `bitora-staging`
- PostgreSQL: `bitora-staging-postgres`
- URL publica: `https://bitora-staging.onrender.com`
- App env: `staging`
- Safe Mode: ON
- Live Mode: OFF

El despliegue funciona, pero no puede cerrarse como staging online certificado porque el servicio esta en plan Free y Render no permite Persistent Disks en ese plan. El storage local actual no cumple el requisito de persistencia online ni permite certificar backup/restore remoto.

## Readiness remoto

`/ready` devuelve:

| Check | Estado |
| --- | --- |
| configuration | PASSED |
| database | PASSED |
| migrations | PASSED |
| storage | PASSED local |
| safe_mode | PASSED |
| live_mode_off | PASSED |

Advertencia remota:

`Storage local requiere disco persistente y backup externo`

## Health remoto

`/health` devuelve:

| Campo | Estado |
| --- | --- |
| status | `ok` |
| env | `staging` |
| db | `online` |
| jobs | `ok` |
| storage | `local`, ready |
| backup | `missing` |

## Gate de hosting

Render informa que los discos persistentes no estan disponibles para instancias Free. Para continuar hace falta una decision explicita sobre hosting:

- subir el servicio a un plan que permita disco persistente; o
- configurar storage persistente externo compatible; o
- aceptar que staging online queda no certificado para backup/restore remoto.

## Estado de validacion

| Requisito | Estado |
| --- | --- |
| Render authentication | PASSED |
| Blueprint creado | PASSED |
| PostgreSQL Render creado | PASSED |
| Web service Render creado | PASSED |
| URL staging HTTPS | PASSED |
| Login online | PASSED |
| Smoke UI online | PASSED |
| Storage persistente | BLOCKED |
| Backup online | BLOCKED |
| Restore online | NOT EXECUTED |
| Restart persistence | NOT EXECUTED |
| Merge PR #12 | NOT EXECUTED |

## Accion siguiente

Autorizar o descartar el upgrade de Render necesario para Persistent Disk. No se debe mergear `deployment/v4-online` a `develop/v4` hasta completar y documentar storage persistente, backup remoto, restore remoto y restart persistence.
