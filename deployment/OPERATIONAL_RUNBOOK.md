# Runbook operacional aislado

## Requisitos

- Docker Engine y Compose funcionales.
- Al menos 4 CPU, 8 GiB de RAM y 10 GiB libres.
- Archivo `.env.operational` creado desde `.env.operational.example` con secretos exclusivos de prueba.

## Preflight

```text
docker info
docker compose --env-file .env.operational -f docker-compose.operational.yml config
python verificar_operational_staging.py
python verificar_operational_postgres_restore.py
python verificar_operational_multiinstance.py
```

## Arranque y observación

```text
docker compose --env-file .env.operational -f docker-compose.operational.yml up -d --build
python scripts/operational_monitor.py --seconds 300 --output artifacts/operational-monitor.jsonl
```

El gateway escucha solamente en `127.0.0.1:18787`. Comunicaciones reales y live mode permanecen desactivados.

## Backup/restore aislado

```text
python scripts/operational_postgres_restore.py --report artifacts/operational-postgres-restore.json
```

El harness usa nombres aleatorios, un dataset controlado y elimina únicamente sus propios recursos.

## Multiinstancia y endurance progresiva

```text
python scripts/operational_multiinstance.py --endurance-seconds 10 --report artifacts/multi-smoke.json
python scripts/operational_multiinstance.py --endurance-seconds 300 --report artifacts/multi-5m.json
```

Solo extender la duración después de aprobar smoke, recursos e integridad.

## Seguridad

```text
python scripts/operational_cve_scan.py --report artifacts/cve-lock.json
python scripts/secret_scan.py
```

Con la imagen construida, agregar `--image <nombre>` para ejecutar Trivy.

## Parada

```text
docker compose --env-file .env.operational -f docker-compose.operational.yml down
```

No usar `down -v` salvo decisión explícita de destruir el staging local. Los harnesses efímeros limpian sus recursos con nombres únicos.

## Incidentes

1. Registrar hora, SHA, contenedor y correlation ID.
2. Consultar `/health` y `/ready`.
3. Preservar logs y el JSONL de monitoreo.
4. Detener carga, no borrar volúmenes.
5. Restaurar únicamente sobre una base nueva y validar checksum/conteos antes de conmutar.
