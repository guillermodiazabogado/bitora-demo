# BITORA R2 Persistent Storage Certification Report

Fecha: 2026-08-11
Staging: https://bitora-staging.onrender.com
Rama: deployment/v4-online
Base tecnica: 961bedebc46238bcf527e00b759d6df08c94eb21

## Resultado

| Control | Estado |
| --- | --- |
| Current Render plan | free |
| Render Persistent Disk | NOT AVAILABLE |
| Selected storage | Cloudflare R2 |
| R2 configured | PASSED |
| Local storage fallback | PASSED |
| Remote PUT | PASSED |
| Remote GET | PASSED |
| Remote DELETE | PASSED |
| Certificate persistence | PASSED |
| Certificate download | PASSED |
| Redeploy persistence | PASSED for app configuration |
| Backup | PASSED |
| Backup ID | bitora-r2-event7-postcert.zip |
| Backup checksum | PASSED |
| Restore isolated | PASSED |
| Restore integrity | PASSED |
| Corrupted restore | PASSED by regression |
| Cross tenant storage | READY, not live-certified |
| Cross event storage | READY, not live-certified |
| Path traversal | BLOCKED by contract test |
| E2E regression | PASSED, existing core regressions |
| Health | PASSED current staging with `storage=r2` and `backup=recent` |
| Ready | PASSED current staging with storage check OK |
| Safe Mode | ON |
| Live Mode | OFF |
| Real communications | 0 |
| Secrets exposed | 0 |
| Verifier | LIVE PASSED for R2 object operations and isolated restore |
| Verifier score | 10/10 |

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

## Accion manual completada

PLATAFORMA: Cloudflare  
SECCION: R2  
ACCION: activar R2 y luego crear bucket/token R2 compatible S3  
BUCKET: bitora-staging-storage  
PERMISOS TOKEN: Object Read, Object Write y Object List sobre el bucket de staging  
ESTADO: COMPLETADO

No pegar secretos en el chat.

## Checkpoint Cloudflare

Cloudflare esta autenticado y muestra la pantalla de activacion de R2.

Estado observado:

```text
Total Due Now: $0.00
Due Monthly: $0.00 + additional usage
Free tier: 10 GB-month, 1M Class A operations, 10M Class B operations
```

Bloqueo previo:

```text
BLOCKED BY BILLING APPROVAL
```

Motivo previo: el boton disponible agregaba una suscripcion de R2 a la cuenta y Cloudflare indicaba que podia facturar uso adicional si se excedian los limites mensuales gratuitos. La activacion fue realizada manualmente por el propietario de la cuenta.

## Evidencia local

`tools/verify_r2_storage_contract.py` ejecutado con credenciales R2 reales cargadas localmente durante la activacion:

- local save: PASSED
- local read: PASSED
- local inventory: PASSED
- traversal por nombre: BLOCKED
- traversal por ruta relativa: BLOCKED
- R2 ready: PASSED
- R2 PUT: PASSED
- R2 GET: PASSED
- R2 LIST: PASSED
- R2 DELETE: PASSED

## Evidencia Render

Render desplego la rama `deployment/v4-online` en el commit `961bedebc46238bcf527e00b759d6df08c94eb21`.

`/ready`:

```text
status=ready
configuration=True
database=True
migrations=True
storage=True
safe_mode=True
live_mode_off=True
```

`/health`:

```text
status=ok
db=online
backup=recent
storage.backend=r2
storage.ready=True
jobs.pending=0
jobs.failed=0
```

## Evidencia Cloudflare R2

Bucket:

```text
bitora-staging-storage
```

Prefijo:

```text
staging/
```

Objeto observado inicialmente:

```text
staging/backups/bitora-event-7-20260811-224929.zip
```

Tamaño observado en Cloudflare:

```text
24.73 KB
```

El artefacto fue generado desde la interfaz de BITORA para el evento certificado `event_id=7`.

## Evidencia de certificado post-R2

Se reemitio controladamente un certificado existente desde la API normal de BITORA para generar un PDF nuevo despues de activar R2.

Evidencia sanitizada:

```text
issuance_id=9
certificate_number=BITORA-004-0007-E2E10_ASISTENCIA-000009
storage_key=events/7/certificates/bitora-004-0007-e2e10_asistencia-000009-9.pdf
file_size=2278
sha256=0CD6FB1465493DDA997A3B2198F92E47D72C1B691C43865FB6695088A66AD8E8
```

No se registra el token de verificacion completo.

## Evidencia de backup descargado

Archivo local descargado inicial:

```text
C:\Users\Noxie-PC\Downloads\bitora-event-7-20260811-224929.zip
```

Contenido inspeccionado:

```text
event-7.json
manifest.json
```

Checksum SHA-256:

```text
BB6934EBA211ECA85D26C79B17043001C0A12411D8BFD4EA037DE64EF279B6C5
```

No se versiona el artefacto.

## Evidencia de backup post-certificado

Luego de emitir el certificado post-R2 se genero un nuevo backup de evento.

```text
backup_file=bitora-r2-event7-postcert.zip
sha256=8CEA435E81D2CF2B416361376EB89E73C80A25DEF2844C7F954D860F7C44B371
size=26838
storage_items=1
storage_item=events/7/certificates/bitora-004-0007-e2e10_asistencia-000009-9.pdf
storage_checksums_ok=True
```

## Evidencia de restore aislado

Se ejecuto `tools/certify_r2_restore_isolated.py` contra el backup post-certificado en una base SQLite temporal y storage temporal, con proveedores externos deshabilitados.

Resultado:

```text
status=PASSED
participants=10
accreditations=10
files=1
files_restored=1
token_regenerated=10
external_effects=0
duration_ms=231
```

Regresiones ejecutadas:

```text
verificar_storage_event_backup_restore.py: PASSED
verificar_event_restore.py: PASSED
```

## Fuentes externas verificadas

- Cloudflare R2 tiene free tier para Standard storage: 10 GB-month, 1M Class A operations y 10M Class B operations mensuales.
- R2 expone API S3-compatible mediante endpoint `https://<ACCOUNT_ID>.r2.cloudflarestorage.com`.

## Estado final

R2 PERSISTENT STORAGE CERTIFICADO

Condiciones cerradas:

1. certificado nuevo persistido y descargable desde R2;
2. backup post-certificado con storage incluido;
3. restore aislado usando el artefacto post-certificado;
4. comparacion de integridad post-restore;
5. regresion de backup/restore.

Queda permitido planificar una nueva corrida de Endurance 24H sobre el commit desplegado con R2 y restore corregido.
