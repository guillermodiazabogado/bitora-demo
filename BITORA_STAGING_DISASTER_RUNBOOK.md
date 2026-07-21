# BITORA Staging Disaster Runbook

## Fallos controlados disponibles

```bash
python deployment/scripts/bdf.py fault stop-worker
python deployment/scripts/bdf.py fault stop-postgres
python deployment/scripts/bdf.py fault stop-app
```

## Recuperacion

```bash
python deployment/scripts/bdf.py recover
```

## Validacion posterior

```bash
python deployment/scripts/bdf.py health
python deployment/scripts/bdf.py smoke-test
python deployment/scripts/bdf.py supertest --profile disaster
```

## Seguridad

Los comandos de fault solo deben usarse en staging. BDF valida `.env.staging` antes de ejecutarlos.
