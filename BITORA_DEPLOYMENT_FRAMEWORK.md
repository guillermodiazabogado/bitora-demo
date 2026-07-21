# BITORA Deployment Framework

## Objetivo

BDF despliega, valida, detiene, destruye y reconstruye entornos BITORA de staging.

BDF no certifica funcionalmente. La certificacion la ejecuta BSTF.

Flujo:

```text
BDF despliega
BSTF certifica
```

## Comando maestro

```bash
python deployment/scripts/bdf.py <comando>
```

## Comandos

```bash
python deployment/scripts/bdf.py check
python deployment/scripts/bdf.py build
python deployment/scripts/bdf.py up
python deployment/scripts/bdf.py status
python deployment/scripts/bdf.py logs
python deployment/scripts/bdf.py health
python deployment/scripts/bdf.py validate
python deployment/scripts/bdf.py migrate
python deployment/scripts/bdf.py smoke-test
python deployment/scripts/bdf.py backup
python deployment/scripts/bdf.py restore <archivo> --yes
python deployment/scripts/bdf.py stop
python deployment/scripts/bdf.py down
python deployment/scripts/bdf.py reset --yes
python deployment/scripts/bdf.py destroy --yes
python deployment/scripts/bdf.py supertest --profile release
python deployment/scripts/bdf.py fault stop-worker
python deployment/scripts/bdf.py fault stop-postgres
python deployment/scripts/bdf.py fault stop-app
python deployment/scripts/bdf.py recover
python deployment/scripts/bdf.py upgrade-test
```

## Servicios

- `bitora-staging-app`
- `bitora-staging-postgres`
- `bitora-staging-worker`
- `bitora-staging-monitor`

## Protecciones

BDF bloquea operaciones si:

- `APP_ENV` no es `staging`;
- el DSN no apunta a `bitora_staging`;
- safe mode no esta activo;
- faltan destinatarios forzados;
- se intenta una accion destructiva sin `--yes`.

## Integracion con BSTF

```bash
python deployment/scripts/bdf.py supertest --profile release
```

ejecuta dentro del contenedor:

```bash
python run_bitora_supertest.py --release
```
