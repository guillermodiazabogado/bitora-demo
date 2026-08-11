# BITORA R2 Persistent Storage Certification Report

Fecha: 2026-08-11  
Staging: https://bitora-staging.onrender.com  
Rama: feature/r2-persistent-storage  
Base tecnica: a5aabfd986c652d853bc1ae4e1ee120953c90a09

## Resultado

| Control | Estado |
| --- | --- |
| Current Render plan | free |
| Render Persistent Disk | NOT AVAILABLE |
| Selected storage | Cloudflare R2 |
| R2 configured | BLOCKED BY BILLING APPROVAL |
| Local storage fallback | PASSED |
| Remote PUT | BLOCKED |
| Remote GET | BLOCKED |
| Remote DELETE | BLOCKED |
| Certificate persistence | READY, not live-certified |
| Certificate download | READY, not live-certified |
| Redeploy persistence | BLOCKED |
| Backup | READY, not live-certified |
| Backup ID | N/A |
| Backup checksum | N/A |
| Restore isolated | BLOCKED |
| Restore integrity | N/A |
| Corrupted restore | READY, not live-certified |
| Cross tenant storage | READY, not live-certified |
| Cross event storage | READY, not live-certified |
| Path traversal | BLOCKED by contract test |
| E2E regression | PASSED, existing core regressions |
| Health | PASSED current staging |
| Ready | PASSED current staging with local-storage warning |
| Safe Mode | ON |
| Live Mode | OFF |
| Real communications | 0 |
| Secrets exposed | 0 |
| Verifier | CONTRACT PASSED / LIVE OMITTED |
| Verifier score | 5/10 until R2 live credentials exist |

## Implementacion

Se completo la abstraccion existente `StorageService` con:

- backend local;
- backend R2/S3-compatible;
- escritura, lectura, borrado e inventario remoto;
- validacion de rutas y bloqueo de traversal;
- checksum SHA-256;
- metadata de content type para PDFs;
- health check liviano del bucket para `/ready`;
- upload de bundles de backup a R2 cuando el backend remoto esta activo.

No se modifico logica funcional de certificados, speakers ni backup de evento. Esos modulos siguen usando la misma frontera de storage.

## Variables requeridas en Render

No guardar estos valores en Git. Cargarlos como Environment Variables/Secrets del servicio `bitora-staging`.

```text
BITORA_STORAGE_PROVIDER=r2
R2_ACCOUNT_ID=<account id>
R2_ACCESS_KEY_ID=<access key id>
R2_SECRET_ACCESS_KEY=<secret access key>
R2_BUCKET=bitora-staging-storage
R2_PREFIX=staging
R2_REGION=auto
```

`R2_ENDPOINT` es opcional si `R2_ACCOUNT_ID` esta presente. Si se usa, debe tener esta forma:

```text
https://<ACCOUNT_ID>.r2.cloudflarestorage.com
```

## Accion manual requerida

PLATAFORMA: Cloudflare  
SECCION: R2  
ACCION: activar R2 y luego crear bucket/token R2 compatible S3  
BUCKET: bitora-staging-storage  
PERMISOS TOKEN: Object Read, Object Write y Object List sobre el bucket de staging  
REANUDAR CON: `R2 listo`

No pegar secretos en el chat.

## Checkpoint Cloudflare

Cloudflare esta autenticado y muestra la pantalla de activacion de R2.

Estado observado:

```text
Total Due Now: $0.00
Due Monthly: $0.00 + additional usage
Free tier: 10 GB-month, 1M Class A operations, 10M Class B operations
```

Bloqueo:

```text
BLOCKED BY BILLING APPROVAL
```

Motivo: el boton disponible agrega una suscripcion de R2 a la cuenta y Cloudflare indica que puede facturar uso adicional si se exceden los limites mensuales gratuitos. Codex no esta autorizado a aceptar esa accion.

## Evidencia local

`tools/verify_r2_storage_contract.py` ejecutado en modo contract:

- local save: PASSED
- local read: PASSED
- local inventory: PASSED
- traversal por nombre: BLOCKED
- traversal por ruta relativa: BLOCKED
- R2 live: OMITTED por falta de variables reales

## Fuentes externas verificadas

- Cloudflare R2 tiene free tier para Standard storage: 10 GB-month, 1M Class A operations y 10M Class B operations mensuales.
- R2 expone API S3-compatible mediante endpoint `https://<ACCOUNT_ID>.r2.cloudflarestorage.com`.

## Estado final

BLOCKED BY BILLING APPROVAL

No corresponde ejecutar nuevo Endurance 24H hasta completar:

1. credenciales R2 en Render;
2. deploy con `BITORA_STORAGE_PROVIDER=r2`;
3. remote PUT/GET/DELETE PASSED;
4. certificado persistido y descargable desde R2;
5. backup real en R2;
6. restore aislado;
7. redeploy persistence;
8. regresion E2E.
