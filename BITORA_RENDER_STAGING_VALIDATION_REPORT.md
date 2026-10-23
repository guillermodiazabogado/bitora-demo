# BITORA Render Staging Validation Report

Fecha: 2026-08-04

Rama: `deployment/v4-online`

HEAD validado: `4c70d4224acba79f3fc140ae1413248d165f4f59`

Deployment PR: `#12`

Resultado: `READY FOR HOSTING APPROVAL`

## Resumen ejecutivo

BITORA V4 quedo desplegado en Render como staging online con Docker y PostgreSQL real. El servicio publico responde por HTTPS y `/ready` confirma configuracion, base, migraciones, storage local, Safe Mode y Live Mode apagado.

La certificacion remota completa no queda aprobada todavia porque Render Free no soporta discos persistentes. El propio `/ready` advierte que el storage local requiere disco persistente y backup externo, y `/health` informa `backup: missing`.

Por esta razon no se fusiona la PR `#12` y no se declara staging online certificado.

## Recursos Render

| Recurso | Estado | Evidencia |
| --- | --- | --- |
| Render authentication | PASSED | Dashboard autenticado |
| Blueprint | PASSED | `bitora-v4-staging` |
| Blueprint ID | RECORDED | `exs-d9p5l3bm8hqs73acbmo0` |
| Web service | PASSED | `bitora-staging` |
| Web service ID | RECORDED | `srv-d9p5pn6gekts73f8u24g` |
| Web service plan | BLOCKING | `Free` |
| PostgreSQL | PASSED | `bitora-staging-postgres` creado por Blueprint |
| URL publica | PASSED | `https://bitora-staging.onrender.com` |
| Branch desplegada | PASSED | `deployment/v4-online` |
| Commit desplegado | PASSED | `4c70d42` |

## Bootstrap

| Control | Resultado |
| --- | --- |
| Usuario bootstrap generado | PASSED |
| Password bootstrap fuerte generado | PASSED |
| Secretos cargados en Render | PASSED |
| Secretos versionados | 0 |
| Secretos mostrados en reportes | 0 |

Los valores de bootstrap fueron cargados directamente en Render y no se registran en Git ni en reportes.

## Validacion remota ejecutada

| Prueba | Resultado | Evidencia |
| --- | --- | --- |
| HTTPS publico | PASSED | `https://bitora-staging.onrender.com` responde 200 |
| `/health` | PARTIAL | `status=ok`, `env=staging`, `db=online`, `backup=missing` |
| `/ready` | PARTIAL | `status=ready`, checks obligatorios true, warning de storage persistente |
| Login UI | PASSED | Login bootstrap exitoso en navegador |
| UI principal | PASSED | Panel operativo y navegacion principal cargan |
| Safe Mode | PASSED | `/ready`: `safe_mode=true` |
| Live Mode OFF | PASSED | `/ready`: `live_mode_off=true` |
| Headers seguridad basicos | PARTIAL | HSTS, Referrer-Policy y X-Content-Type-Options presentes; CSP no observado |
| CI PR #12 | PASSED | GitHub muestra `2 / 2 checks OK` |
| Conflictos PR #12 | PASSED | GitHub muestra `No conflicts with base branch` |

## Bloqueos

| Gate remoto | Estado | Motivo |
| --- | --- | --- |
| Storage persistent online | BLOCKED | Render informa que los discos no estan soportados en plan Free |
| Backup online | BLOCKED | `/health` reporta `backup=missing`; falta storage persistente o backup externo |
| Restore online aislado | NOT EXECUTED | No debe ejecutarse sin artefacto backup persistente validado |
| Restart persistence | NOT EXECUTED | No puede certificarse storage persistente sin disco Render |
| Release online final | NOT CERTIFIED | Falta evidencia de persistencia, backup y restore remoto |

## Paid plan gate

Render mostro el mensaje:

`Disks are not supported for free instance types. Upgrading to the Starter instance type also includes Persistent Disks.`

Decision requerida:

`READY FOR HOSTING APPROVAL`

No se acepto ningun plan pago y no se avanzo con la configuracion de disco.

## Estado de PR

| Item | Estado |
| --- | --- |
| PR | `#12` |
| Estado GitHub | Ready to merge |
| Checks GitHub | PASSED |
| Conflictos | 0 |
| Merge | NOT EXECUTED |

La PR no se mergea porque los criterios operativos de staging online completo aun no estan cumplidos.

## Siguiente accion requerida

1. Aprobar o rechazar el upgrade de Render a un plan con disco persistente.
2. Si se aprueba, agregar disco persistente para `/bitora/storage` y `/bitora/backups`, o definir storage externo equivalente.
3. Redeploy de `bitora-staging`.
4. Revalidar `/health` hasta que `backup` no sea `missing`.
5. Ejecutar backup remoto real.
6. Ejecutar restore remoto en entorno aislado.
7. Ejecutar restart persistence.
8. Solo entonces revaluar merge de PR `#12`.
