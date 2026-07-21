# BITORA Staging Backup Restore

## Backup

```bash
python deployment/scripts/bdf.py backup
```

Genera:

- dump PostgreSQL;
- manifiesto JSON;
- checksum SHA-256;
- commit;
- fecha.

Destino local:

```text
deployment/backup/artifacts/
```

Esta carpeta esta ignorada por Git.

## Restore

```bash
python deployment/scripts/bdf.py restore deployment/backup/artifacts/<archivo>.sql --yes
```

## Restricciones

Solo funciona si `deployment/staging/.env.staging` pasa las validaciones de seguridad.

No debe usarse contra produccion.
