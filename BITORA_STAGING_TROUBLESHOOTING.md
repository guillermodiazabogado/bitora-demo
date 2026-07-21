# BITORA Staging Troubleshooting

## Docker no disponible

Ejecutar:

```bash
docker compose version
```

Si falla, instalar Docker Desktop y volver a ejecutar:

```bash
python deployment/scripts/bdf.py check
```

## Falta .env.staging

Copiar:

```bash
copy deployment\staging\.env.staging.example deployment\staging\.env.staging
```

## Safe mode bloqueado

Revisar:

```text
EMAIL_SAFE_MODE=true
EMAIL_FORCE_RECIPIENT=...
WHATSAPP_SAFE_MODE=true
WHATSAPP_FORCE_RECIPIENT=...
```

## PostgreSQL no levanta

Ver logs:

```bash
python deployment/scripts/bdf.py logs
```

Recrear entorno:

```bash
python deployment/scripts/bdf.py reset --yes
```

## Health falla

Ejecutar:

```bash
python deployment/scripts/bdf.py status
python deployment/scripts/bdf.py logs
python deployment/scripts/bdf.py health
```
