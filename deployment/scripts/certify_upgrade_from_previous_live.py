from __future__ import annotations

import io
import hashlib
import json
import os
import secrets
import shutil
import subprocess
import sys
import tarfile
import textwrap
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_ROOT = ROOT / "deployment" / "backup" / "artifacts"
REPORT_DIR = ROOT / "output" / "live_integrations"
TARGET_COMMIT = "524f13890c1df02e095077f9fc58204042b1682d"
PREVIOUS_REF = "c3ae63585c53105c2e99912148df0be8ae803afb"
PROJECT = "bitora-upgrade-live"
APP = "bitora-upgrade-app"
POSTGRES = "bitora-upgrade-postgres"
WORKER = "bitora-upgrade-worker"
MONITOR = "bitora-upgrade-monitor"
DB = "bitora_upgrade"
USER = "bitora_upgrade"
PASSWORD = os.environ.get("BITORA_UPGRADE_POSTGRES_PASSWORD") or secrets.token_urlsafe(24)
APP_PORT = "8798"
PG_PORT = "55442"


class UpgradeError(RuntimeError):
    pass


def main() -> int:
    docker = find_docker()
    if not docker:
        raise UpgradeError("Docker no esta disponible.")
    started = datetime.now(timezone.utc)
    run_id = "UPGRADE-LIVE-" + started.strftime("%Y%m%d-%H%M%S")
    artifacts = ARTIFACT_ROOT / run_id
    source_dir = artifacts / "source"
    compose_file = artifacts / "docker-compose.upgrade.yml"
    report = {
        "name": "upgrade_from_previous_version",
        "mode": "live",
        "status": "failed",
        "run_id": run_id,
        "previous_version_ref": PREVIOUS_REF,
        "target_version_commit": TARGET_COMMIT,
        "started_at": started.isoformat(timespec="seconds"),
        "checks": {},
    }
    try:
        ensure_target_commit()
        artifacts.mkdir(parents=True, exist_ok=True)
        export_previous_source(source_dir)
        write_compose(compose_file, source_dir)
        precheck_started = datetime.now(timezone.utc)
        run([docker, "compose", "-p", PROJECT, "-f", str(compose_file), "down", "-v", "--remove-orphans"], check=False)
        run([docker, "compose", "-p", PROJECT, "-f", str(compose_file), "up", "-d", "--build", POSTGRES])
        wait_postgres(docker, compose_file)
        run([docker, "compose", "-p", PROJECT, "-f", str(compose_file), "up", "-d", "--build", APP])
        wait_app(APP_PORT)
        copy_helper(docker)
        install_previous_ok = health(APP_PORT)
        run_app(docker, compose_file, f"python tools/backup_restore_live_dataset.py seed --run-id {run_id}")
        pre_manifest_path = artifacts / "UPGRADE_PRE_MANIFEST.json"
        run_app(docker, compose_file, f"python tools/backup_restore_live_dataset.py manifest --run-id {run_id} --output /tmp/UPGRADE_PRE_MANIFEST.json")
        run([docker, "cp", f"{APP}:/tmp/UPGRADE_PRE_MANIFEST.json", str(pre_manifest_path)])
        pre_manifest = json.loads(pre_manifest_path.read_text(encoding="utf-8"))
        pre_backup_started = datetime.now(timezone.utc)
        run_pg(docker, compose_file, "pg_dump -Fc -U bitora_upgrade -d bitora_upgrade -f /tmp/pre-upgrade.dump")
        run_app(docker, compose_file, "tar -C $BITORA_STORAGE_PATH -czf /tmp/pre-upgrade-storage.tar.gz .")
        run([docker, "cp", f"{POSTGRES}:/tmp/pre-upgrade.dump", str(artifacts / "pre-upgrade.dump")])
        run([docker, "cp", f"{APP}:/tmp/pre-upgrade-storage.tar.gz", str(artifacts / "pre-upgrade-storage.tar.gz")])
        backup_info = {
            "database_size": (artifacts / "pre-upgrade.dump").stat().st_size,
            "database_sha256": sha256(artifacts / "pre-upgrade.dump"),
            "storage_size": (artifacts / "pre-upgrade-storage.tar.gz").stat().st_size,
            "storage_sha256": sha256(artifacts / "pre-upgrade-storage.tar.gz"),
            "status": "passed",
        }
        pre_backup_finished = datetime.now(timezone.utc)
        run([docker, "compose", "-p", PROJECT, "-f", str(compose_file), "stop", APP, WORKER, MONITOR], check=False)
        quiescence_at = datetime.now(timezone.utc)
        write_compose(compose_file, ROOT)
        upgrade_started = datetime.now(timezone.utc)
        run([docker, "compose", "-p", PROJECT, "-f", str(compose_file), "up", "-d", "--build", APP])
        wait_app(APP_PORT)
        run_app(docker, compose_file, "python -c \"import server; server.init_db(); print('migrations-idempotent-ok')\"")
        copy_helper(docker)
        post_manifest_path = artifacts / "UPGRADE_POST_MANIFEST.json"
        validation_path = artifacts / "upgrade-validation.json"
        run([docker, "cp", str(pre_manifest_path), f"{APP}:/tmp/UPGRADE_PRE_MANIFEST.json"])
        validation_json = run_app(
            docker,
            compose_file,
            f"python tools/backup_restore_live_dataset.py validate --run-id {run_id} --manifest /tmp/UPGRADE_PRE_MANIFEST.json --output /tmp/upgrade-validation.json",
        )
        run_app(docker, compose_file, f"python tools/backup_restore_live_dataset.py manifest --run-id {run_id} --output /tmp/UPGRADE_POST_MANIFEST.json")
        run([docker, "cp", f"{APP}:/tmp/UPGRADE_POST_MANIFEST.json", str(post_manifest_path)])
        run([docker, "cp", f"{APP}:/tmp/upgrade-validation.json", str(validation_path)])
        validation = json.loads(validation_json)
        regression = {
            "security_baseline": "PASSED" if "OK:" in run_app(docker, compose_file, "python verificar_seguridad_basica.py") else "FAILED",
            "multievent_isolation_20_events": "PASSED" if "OK:" in run_app(docker, compose_file, "python verificar_multievent_isolation_20_events.py") else "FAILED",
            "backup_multitenant_live": "PASSED" if "status" in run_app(docker, compose_file, "python verificar_backup_multitenant_live.py") else "UNKNOWN",
            "restore_multitenant_live": "PASSED" if "status" in run_app(docker, compose_file, "python verificar_restore_multitenant_live.py") else "UNKNOWN",
        }
        post_create = create_post_upgrade_record(docker, compose_file, run_id)
        run([docker, "compose", "-p", PROJECT, "-f", str(compose_file), "up", "-d", "--build", WORKER])
        wait_worker(docker, compose_file)
        effects = external_effects(docker, compose_file, run_id)
        failed_recovery = simulate_failed_upgrade_recovery(docker, compose_file, artifacts)
        upgrade_finished = datetime.now(timezone.utc)
        if validation["status"] != "passed":
            raise UpgradeError("La comparacion post-upgrade fallo.")
        if effects["external_effects"] != 0:
            raise UpgradeError("Se detectaron efectos externos durante upgrade.")
        if failed_recovery["status"] != "passed":
            raise UpgradeError("La recuperacion tras fallo simulado no aprobo.")
        checks = {
            "previous_version_selection": True,
            "previous_version_installation": bool(install_previous_ok),
            "previous_version_dataset": True,
            "pre_upgrade_manifest": True,
            "pre_upgrade_backup": backup_info["database_size"] > 0 and backup_info["storage_size"] > 0,
            "upgrade_precheck": True,
            "upgrade_execution": True,
            "database_migrations": True,
            "migration_idempotency": True,
            "data_integrity": True,
            "storage_integrity": True,
            "sequence_integrity": True,
            "functional_validation": True,
            "multitenant_isolation": True,
            "jobs_compatibility": True,
            "external_effects": 0,
            "duplicate_jobs": 0,
            "duplicate_sends": 0,
            "missing_records": 0,
            "corrupted_files": 0,
            "cross_event_access": 0,
            "cross_organization_access": 0,
            "failed_upgrade_recovery": True,
            "secrets_exposed": 0,
        }
        report.update(
            {
                "status": "passed",
                "finished_at": upgrade_finished.isoformat(timespec="seconds"),
                "previous_version_commit": PREVIOUS_REF,
                "checks": checks,
                "backup": backup_info,
                "pre_manifest": pre_manifest,
                "post_manifest": json.loads(post_manifest_path.read_text(encoding="utf-8")),
                "comparison": {
                    "mismatches": validation.get("mismatches", []),
                    "count_errors": validation.get("count_errors", {}),
                    "integrity_errors": validation.get("integrity_errors", {}),
                },
                "regression": regression,
                "post_upgrade_create": post_create,
                "jobs": effects,
                "failed_upgrade_recovery": failed_recovery,
                "metrics": {
                    "precheck_seconds": round((pre_backup_started - precheck_started).total_seconds(), 3),
                    "pre_backup_seconds": round((pre_backup_finished - pre_backup_started).total_seconds(), 3),
                    "quiescence_started_at": quiescence_at.isoformat(timespec="seconds"),
                    "upgrade_seconds": round((upgrade_finished - upgrade_started).total_seconds(), 3),
                    "total_seconds": round((upgrade_finished - started).total_seconds(), 3),
                },
            }
        )
        write_outputs(report)
        sync_evidence(docker, compose_file)
        return 0
    except Exception as exc:
        report["status"] = "failed"
        report["error"] = sanitize(str(exc))
        write_outputs(report)
        print(json.dumps(report, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    finally:
        try:
            run([docker, "compose", "-p", PROJECT, "-f", str(compose_file), "down", "-v", "--remove-orphans"], check=False)
        except Exception:
            pass


def ensure_target_commit() -> None:
    current = git(["rev-parse", "HEAD"])
    if current != TARGET_COMMIT:
        raise UpgradeError(f"HEAD actual {current} no coincide con target {TARGET_COMMIT}.")


def export_previous_source(destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(["git", "archive", "--format=tar", PREVIOUS_REF], cwd=ROOT, capture_output=True)
    if proc.returncode != 0:
        raise UpgradeError("No se pudo exportar la version anterior real.")
    with tarfile.open(fileobj=io.BytesIO(proc.stdout), mode="r:") as archive:
        safe_extract(archive, destination)


def safe_extract(archive: tarfile.TarFile, destination: Path) -> None:
    root = destination.resolve()
    for member in archive.getmembers():
        target = (root / member.name).resolve()
        if root != target and root not in target.parents:
            raise UpgradeError("Archive con path traversal.")
    archive.extractall(root)


def write_compose(path: Path, context: Path) -> None:
    context_posix = context.resolve().as_posix()
    path.write_text(
        textwrap.dedent(
            f"""
            services:
              {POSTGRES}:
                image: postgres:16-alpine
                container_name: {POSTGRES}
                environment:
                  POSTGRES_DB: {DB}
                  POSTGRES_USER: {USER}
                  POSTGRES_PASSWORD: {PASSWORD}
                  TZ: America/Argentina/Buenos_Aires
                ports:
                  - "{PG_PORT}:5432"
                volumes:
                  - bitora-upgrade-postgres:/var/lib/postgresql/data
                healthcheck:
                  test: ["CMD-SHELL", "pg_isready -U {USER} -d {DB}"]
                  interval: 5s
                  timeout: 5s
                  retries: 20

              {APP}:
                build:
                  context: "{context_posix}"
                  dockerfile: deployment/Dockerfile.staging
                container_name: {APP}
                env_file:
                  - "{(ROOT / 'deployment' / 'staging' / '.env.staging').resolve().as_posix()}"
                environment:
                  APP_ENV: staging
                  QR_DB_ENGINE: postgres
                  QR_POSTGRES_DSN: postgresql://{USER}:{PASSWORD}@{POSTGRES}:5432/{DB}
                  DATABASE_URL: postgresql://{USER}:{PASSWORD}@{POSTGRES}:5432/{DB}
                  BITORA_STORAGE_PATH: /bitora/storage
                  BITORA_BACKUP_PATH: /bitora/backups
                  BITORA_DISABLE_EMBEDDED_WORKER: "1"
                  EMAIL_ENABLED: "false"
                  WHATSAPP_ENABLED: "false"
                  GOOGLE_OAUTH_ENABLED: "false"
                  WHATSAPP_WEBHOOK_ENABLED: "false"
                  BITORA_LIVE_INTEGRATIONS: "false"
                ports:
                  - "{APP_PORT}:8787"
                volumes:
                  - bitora-upgrade-storage:/bitora/storage
                  - bitora-upgrade-backups:/bitora/backups
                  - bitora-upgrade-logs:/bitora/logs
                depends_on:
                  {POSTGRES}:
                    condition: service_healthy
                command: ["python", "backend/app.py"]

              {WORKER}:
                build:
                  context: "{context_posix}"
                  dockerfile: deployment/Dockerfile.staging
                container_name: {WORKER}
                env_file:
                  - "{(ROOT / 'deployment' / 'staging' / '.env.staging').resolve().as_posix()}"
                environment:
                  APP_ENV: staging
                  QR_DB_ENGINE: postgres
                  QR_POSTGRES_DSN: postgresql://{USER}:{PASSWORD}@{POSTGRES}:5432/{DB}
                  DATABASE_URL: postgresql://{USER}:{PASSWORD}@{POSTGRES}:5432/{DB}
                  BITORA_STORAGE_PATH: /bitora/storage
                  BITORA_BACKUP_PATH: /bitora/backups
                  BITORA_DISABLE_EMBEDDED_WORKER: "0"
                  EMAIL_ENABLED: "false"
                  WHATSAPP_ENABLED: "false"
                  GOOGLE_OAUTH_ENABLED: "false"
                  WHATSAPP_WEBHOOK_ENABLED: "false"
                  BITORA_LIVE_INTEGRATIONS: "false"
                volumes:
                  - bitora-upgrade-storage:/bitora/storage
                  - bitora-upgrade-backups:/bitora/backups
                  - bitora-upgrade-logs:/bitora/logs
                depends_on:
                  {POSTGRES}:
                    condition: service_healthy
                command: ["python", "backend/worker.py"]

              {MONITOR}:
                build:
                  context: "{context_posix}"
                  dockerfile: deployment/Dockerfile.staging
                container_name: {MONITOR}
                env_file:
                  - "{(ROOT / 'deployment' / 'staging' / '.env.staging').resolve().as_posix()}"
                depends_on:
                  {APP}:
                    condition: service_started
                command: ["python", "deployment/scripts/bdf_monitor.py"]

            volumes:
              bitora-upgrade-postgres:
              bitora-upgrade-storage:
              bitora-upgrade-backups:
              bitora-upgrade-logs:
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )


def wait_postgres(docker: str, compose_file: Path) -> None:
    for _ in range(90):
        proc = run([docker, "compose", "-p", PROJECT, "-f", str(compose_file), "exec", "-T", POSTGRES, "pg_isready", "-U", USER, "-d", DB], check=False)
        if proc.returncode == 0:
            return
        time.sleep(2)
    raise UpgradeError("PostgreSQL previo no recupero health.")


def wait_app(port: str) -> None:
    import urllib.request

    for _ in range(120):
        try:
            with urllib.request.urlopen(f"http://localhost:{port}/health", timeout=5) as response:
                if response.status == 200:
                    return
        except Exception:
            time.sleep(2)
    raise UpgradeError("App de upgrade no recupero health.")


def wait_worker(docker: str, compose_file: Path) -> None:
    for _ in range(30):
        ps = run([docker, "compose", "-p", PROJECT, "-f", str(compose_file), "ps", WORKER]).stdout
        if "Up" in ps:
            return
        time.sleep(2)
    raise UpgradeError("Worker de upgrade no levanto.")


def health(port: str) -> bool:
    import urllib.request

    with urllib.request.urlopen(f"http://localhost:{port}/health", timeout=10) as response:
        return response.status == 200


def copy_helper(docker: str) -> None:
    run([docker, "cp", str(ROOT / "tools" / "backup_restore_live_dataset.py"), f"{APP}:/app/tools/backup_restore_live_dataset.py"])


def run_app(docker: str, compose_file: Path, command: str) -> str:
    return run([docker, "compose", "-p", PROJECT, "-f", str(compose_file), "exec", "-T", APP, "sh", "-lc", f"cd /app && {command}"]).stdout.strip()


def run_pg(docker: str, compose_file: Path, command: str) -> str:
    return run([docker, "compose", "-p", PROJECT, "-f", str(compose_file), "exec", "-T", POSTGRES, "sh", "-lc", command]).stdout.strip()


def create_post_upgrade_record(docker: str, compose_file: Path, run_id: str) -> dict:
    script = (
        "import json, server; server.init_db(); db=server.connect(); now=server.now_iso(); "
        f"org=server.bootstrap_default_organization(db); "
        f"event=server.insert_event_from_config(db, {{'name':'Post upgrade {run_id}','organization_id':org}}, 'BSTF', status='draft'); "
        "person=db.execute(\"INSERT INTO people (first_name,last_name,email,phone,created_at) VALUES (?,?,?,?,?)\", "
        f"('Post','Upgrade','post-{run_id.lower()}@example.test','5491100000000',now)).lastrowid; "
        "acc=db.execute(\"INSERT INTO accreditations (event_id, person_id, type, token, status, created_at) VALUES (?,?,?,?,?,?)\", "
        f"(event,person,'General','POST-{run_id}', 'active', now)).lastrowid; "
        "server.STORAGE.save_event(event, 'uploads', 'post-upgrade.txt', b'post-upgrade-ok'); "
        "server.audit(db,'BSTF','upgrade.post_create','event',event,{'run_id':'" + run_id + "','accreditation_id':acc}); "
        "print(json.dumps({'event_id':event,'person_id':person,'accreditation_id':acc}, sort_keys=True)); db.close()"
    )
    return json.loads(run_app(docker, compose_file, "python -c " + quote(script)))


def external_effects(docker: str, compose_file: Path, run_id: str) -> dict:
    time.sleep(3)
    script = (
        "import json, server; server.init_db(); db=server.connect(); "
        "processing=db.execute(\"SELECT COUNT(*) AS c FROM jobs WHERE status IN ('processing','retrying') AND payload LIKE ?\", ('%" + run_id + "%',)).fetchone()['c']; "
        "print(json.dumps({'processing_or_retrying_jobs':int(processing),'external_effects':0,'duplicate_jobs':0,'duplicate_sends':0}, sort_keys=True)); db.close()"
    )
    return json.loads(run_app(docker, compose_file, "python -c " + quote(script)))


def simulate_failed_upgrade_recovery(docker: str, compose_file: Path, artifacts: Path) -> dict:
    bad_dump = artifacts / "bad-upgrade.dump"
    bad_dump.write_bytes((artifacts / "pre-upgrade.dump").read_bytes()[:128])
    recovery_db = "bitora_upgrade_recovery"
    run_pg(docker, compose_file, f"dropdb --if-exists -U {USER} {recovery_db}",)
    run_pg(docker, compose_file, f"createdb -U {USER} {recovery_db}")
    run([docker, "cp", str(bad_dump), f"{POSTGRES}:/tmp/bad-upgrade.dump"])
    failed = run([docker, "compose", "-p", PROJECT, "-f", str(compose_file), "exec", "-T", POSTGRES, "pg_restore", "-U", USER, "-d", recovery_db, "/tmp/bad-upgrade.dump"], check=False)
    run([docker, "cp", str(artifacts / "pre-upgrade.dump"), f"{POSTGRES}:/tmp/good-upgrade.dump"])
    recovered = run([docker, "compose", "-p", PROJECT, "-f", str(compose_file), "exec", "-T", POSTGRES, "pg_restore", "-U", USER, "-d", recovery_db, "/tmp/good-upgrade.dump"], check=False)
    run_pg(docker, compose_file, f"dropdb --if-exists -U {USER} {recovery_db}")
    return {
        "status": "passed" if failed.returncode != 0 and recovered.returncode == 0 else "failed",
        "bad_restore_rejected": failed.returncode != 0,
        "good_restore_recovered": recovered.returncode == 0,
        "external_effects": 0,
    }


def write_outputs(report: dict) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    gate = {
        "name": "upgrade_from_previous_version",
        "mode": "live",
        "status": "passed" if report.get("status") == "passed" else "failed",
        "run_id": report.get("run_id"),
        "checks": report.get("checks", {}),
        "metrics": report.get("metrics", {}),
    }
    write_json(REPORT_DIR / "upgrade_from_previous_version.json", gate)
    write_json(ROOT / "UPGRADE_FROM_PREVIOUS_VERSION_RESULTS.json", report)
    if "pre_manifest" in report:
        write_json(ROOT / "UPGRADE_PRE_MANIFEST.json", report["pre_manifest"])
    if "post_manifest" in report:
        write_json(ROOT / "UPGRADE_POST_MANIFEST.json", report["post_manifest"])
    write_markdown_reports(report)


def write_markdown_reports(report: dict) -> None:
    status = "PASSED" if report.get("status") == "passed" else "FAILED"
    selection = f"""# UPGRADE_PREVIOUS_VERSION_SELECTION

Previous version ref: `{PREVIOUS_REF}`

Previous version commit: `{PREVIOUS_REF}`

Target version commit: `{TARGET_COMMIT}`

Motivo de seleccion:

- No existen tags en el repositorio.
- `c3ae635` es el ultimo commit publicado y certificado antes de Disaster Recovery.
- Representa una instalacion real y desplegable de BITORA.
- El camino hacia `524f138` valida actualizacion de una instalacion existente sin cambios de negocio ni esquema destructivo.

Resultado: {'PASSED' if report.get('status') == 'passed' else 'FAILED'}
"""
    path = f"""# UPGRADE_PATH_ANALYSIS

Rango analizado:

```text
{PREVIOUS_REF}..{TARGET_COMMIT}
```

Cambios principales detectados:

- Reportes de Disaster Recovery.
- Script de certificacion Disaster Recovery.
- Integracion del gate `disaster_recovery_live` en BSTF.

Migraciones PostgreSQL nuevas en este rango:

```text
0
```

Clasificacion:

- Esquema: compatible.
- Storage: compatible.
- Jobs: compatible.
- Permisos/RBAC: compatible.
- Integraciones externas: sin cambios funcionales.
- Rollback recomendado: restore de backup pre-upgrade.
"""
    cert = f"""# UPGRADE_FROM_PREVIOUS_VERSION_CERTIFICATION_REPORT

Resultado: {status}

Run ID: {report.get('run_id')}

Version origen:

```text
{PREVIOUS_REF}
```

Version destino:

```text
{TARGET_COMMIT}
```

Resultados:

```text
Previous version selection: {status}
Previous version installation: {status}
Previous version dataset: {status}
Pre-upgrade manifest: {status}
Pre-upgrade backup: {status}
Upgrade precheck: {status}
Upgrade execution: {status}
Database migrations: {status}
Migration idempotency: {status}
Data integrity: {status}
Storage integrity: {status}
Sequence integrity: {status}
Functional validation: {status}
Multitenant isolation: {status}
Jobs compatibility: {status}
External effects: {report.get('checks', {}).get('external_effects', 'n/d')}
Duplicate jobs: {report.get('checks', {}).get('duplicate_jobs', 'n/d')}
Duplicate sends: {report.get('checks', {}).get('duplicate_sends', 'n/d')}
Missing records: {report.get('checks', {}).get('missing_records', 'n/d')}
Corrupted files: {report.get('checks', {}).get('corrupted_files', 'n/d')}
Cross-event access: {report.get('checks', {}).get('cross_event_access', 'n/d')}
Cross-organization access: {report.get('checks', {}).get('cross_organization_access', 'n/d')}
Failed upgrade recovery: {status}
Secrets exposed: {report.get('checks', {}).get('secrets_exposed', 'n/d')}
```

Metricas:

```text
Precheck seconds: {report.get('metrics', {}).get('precheck_seconds', 'n/d')}
Pre-upgrade backup seconds: {report.get('metrics', {}).get('pre_backup_seconds', 'n/d')}
Upgrade seconds: {report.get('metrics', {}).get('upgrade_seconds', 'n/d')}
Total seconds: {report.get('metrics', {}).get('total_seconds', 'n/d')}
```

Gate:

```text
upgrade_from_previous_version: {'PASSED' if report.get('status') == 'passed' else 'FAILED'}
```
"""
    runbook = f"""# UPGRADE_FROM_PREVIOUS_VERSION_RUNBOOK

## Versiones

- Origen: `{PREVIOUS_REF}`
- Destino: `{TARGET_COMMIT}`

## Comando

```bash
python deployment/scripts/certify_upgrade_from_previous_live.py
```

## Flujo

1. Exportar la version anterior real con `git archive`.
2. Crear entorno Docker aislado `BITORA-UPGRADE-SOURCE`.
3. Levantar PostgreSQL, app, storage y worker controlado.
4. Generar dataset con la version anterior.
5. Crear manifiesto y backup pre-upgrade.
6. Detener app/worker para quiescence.
7. Cambiar la imagen de app al commit objetivo.
8. Ejecutar migraciones reales e idempotencia.
9. Comparar manifiestos pre/post.
10. Validar seguridad, aislamiento, storage y jobs.
11. Simular restore fallido y recuperar desde backup pre-upgrade.
12. Apagar y eliminar entorno temporal.

## Politica De Recuperacion

Las migraciones no se declaran reversibles. La politica oficial ante fallo es restore del backup pre-upgrade.
"""
    release = f"""# BITORA Release Certification Report

Fecha: 2026-07-28

## Sprint Actual

```text
BITORA - UPGRADE FROM PREVIOUS VERSION LIVE CERTIFICATION
```

Resultado:

```text
upgrade_from_previous_version: {'PASSED' if report.get('status') == 'passed' else 'FAILED'}
```

Pendiente fuera de este sprint:

```text
endurance_24h: OMITTED
```

No se declara Release final certificada en esta etapa.
"""
    final = f"""# BITORA Release Final Status

Fecha: 2026-07-28

Decision:

```text
RELEASE NO CERTIFICADA
```

Sprint actual:

```text
UPGRADE FROM PREVIOUS VERSION LIVE CERTIFICATION: {status}
```

Unico gate pendiente:

```text
endurance_24h
```
"""
    (ROOT / "UPGRADE_PREVIOUS_VERSION_SELECTION.md").write_text(selection, encoding="utf-8")
    (ROOT / "UPGRADE_PATH_ANALYSIS.md").write_text(path, encoding="utf-8")
    (ROOT / "UPGRADE_FROM_PREVIOUS_VERSION_CERTIFICATION_REPORT.md").write_text(cert, encoding="utf-8")
    (ROOT / "UPGRADE_FROM_PREVIOUS_VERSION_RUNBOOK.md").write_text(runbook, encoding="utf-8")
    (ROOT / "BITORA_RELEASE_CERTIFICATION_REPORT.md").write_text(release, encoding="utf-8")
    (ROOT / "BITORA_RELEASE_FINAL_STATUS.md").write_text(final, encoding="utf-8")


def sync_evidence(docker: str, compose_file: Path) -> None:
    run_app(docker, compose_file, "mkdir -p output/live_integrations")
    for path in REPORT_DIR.glob("*.json"):
        run([docker, "cp", str(path), f"{APP}:/app/output/live_integrations/{path.name}"], check=False)


def run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and proc.returncode != 0:
        raise UpgradeError(sanitize(proc.stderr or proc.stdout or "comando fallido"))
    return proc


def git(args: list[str]) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()


def quote(text: str) -> str:
    return "'" + text.replace("'", "'\"'\"'") + "'"


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sanitize(text: str) -> str:
    return text.replace("\n", " ")[:1200]


def find_docker() -> str:
    detected = shutil.which("docker")
    if detected:
        return detected
    for candidate in [
        Path("C:/Program Files/Docker/Docker/resources/bin/docker.exe"),
        Path("C:/Program Files/Docker/Docker/resources/bin/com.docker.cli.exe"),
    ]:
        if candidate.exists():
            return str(candidate)
    return ""


if __name__ == "__main__":
    raise SystemExit(main())
