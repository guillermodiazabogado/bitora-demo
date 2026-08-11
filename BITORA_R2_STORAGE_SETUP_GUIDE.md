# BITORA R2 Storage Setup Guide

## Objetivo

Usar Render Free para la app y Cloudflare R2 para archivos persistentes, backups y assets generados.

## Pasos en Cloudflare

1. Entrar a Cloudflare Dashboard.
2. Abrir R2.
3. Crear el bucket:

```text
bitora-staging-storage
```

4. Crear un API token R2 compatible S3 limitado al bucket.
5. Permisos minimos:

```text
Object Read
Object Write
Object List
```

6. Guardar localmente los datos solo para cargarlos en Render. No pegarlos en chats ni documentos.

## Variables en Render

En el servicio `bitora-staging`, cargar:

```text
BITORA_STORAGE_PROVIDER=r2
R2_ACCOUNT_ID=<valor real>
R2_ACCESS_KEY_ID=<valor real>
R2_SECRET_ACCESS_KEY=<valor real>
R2_BUCKET=bitora-staging-storage
R2_PREFIX=staging
R2_REGION=auto
```

No modificar produccion.

## Deploy

Despues de cargar variables:

1. Ejecutar deploy manual de staging.
2. Verificar `/health`.
3. Verificar `/ready`.
4. Ejecutar:

```bash
python tools/verify_r2_storage_contract.py
```

En staging, el verificador live debe mostrar:

```text
r2_ready: PASSED
r2_put: PASSED
r2_get: PASSED
r2_list_prefix: PASSED
r2_delete: PASSED
```

## Criterio de avance

Solo cuando R2 live pase, ejecutar backup/restore y redeploy persistence. Endurance 24H sigue bloqueado hasta entonces.
