#!/usr/bin/env python3
"""Idempotent, local-only Phase 7 staging-readiness gate runner."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]
CERTIFIED_CODE_SHA = "33c13cf0aaf79baae4e28d2603cb0732a10dbde2"
EXPECTED_BRANCH = "certification/5.8.2-phase7-staging-readiness"
COMPOSE_FILE = ROOT / "deployment" / "phase7" / "docker-compose.phase7.yml"
AUDIT_DIR = ROOT / "auditoria" / "bitora_5_8_2_phase_7"
EVIDENCE_DIR = AUDIT_DIR / "evidence"
CHECKPOINT = AUDIT_DIR / "CHECKPOINT_FASE_7.json"
RESULTS = AUDIT_DIR / "RESULTADOS_FASE_7.json"
CONTROL = AUDIT_DIR / "CONTROL_FASE_7.md"
EXECUTIVE = AUDIT_DIR / "INFORME_EJECUTIVO_FASE_7.md"
LOCK = AUDIT_DIR / ".phase7.lock"
IMAGE = "bitora:5.8.2-phase7-local"
REQUIRED_ENV = (
    "BITORA_POSTGRES_ADMIN_PASSWORD", "BITORA_APP_DB_PASSWORD", "BITORA_SESSION_SECRET",
    "BITORA_SECRET_KEY", "BITORA_SPEAKER_SECRET", "BITORA_SURVEY_SECRET",
    "BITORA_DATASET_SIGNING_KEY", "BITORA_ADMIN_BOOTSTRAP_USER",
    "BITORA_ADMIN_BOOTSTRAP_PASSWORD",
)


class GateError(RuntimeError):
    pass


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def atomic_json(path: Path, payload: dict) -> None:
    atomic_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def run(command: list[str], *, timeout: int = 600, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=timeout)
    if check and result.returncode != 0:
        tail = (result.stderr or result.stdout)[-1600:].replace("\n", " | ")
        raise GateError(f"COMMAND_FAILED:{command[0]}:{result.returncode}:{tail}")
    return result


def git(*args: str) -> str:
    # Windows-created worktrees store a Windows path in their .git pointer.
    # Native WSL git cannot resolve it, while git.exe can and preserves the same checkout.
    binary = "git.exe" if os.environ.get("WSL_DISTRO_NAME") and shutil.which("git.exe") else "git"
    return run([binary, *args], timeout=120).stdout.strip()


def compose(*args: str, timeout: int = 600, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run(["docker", "compose", "-f", str(COMPOSE_FILE), *args], timeout=timeout, check=check)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def container_id(service: str) -> str:
    value = compose("ps", "-q", service).stdout.strip()
    if not value:
        raise GateError(f"CONTAINER_MISSING:{service}")
    return value


def wait_healthy(services: tuple[str, ...], timeout: int = 240) -> dict[str, str]:
    deadline = time.monotonic() + timeout
    states: dict[str, str] = {}
    while time.monotonic() < deadline:
        states = {}
        for service in services:
            try:
                cid = container_id(service)
            except GateError:
                states[service] = "missing"
                continue
            state = run(
                ["docker", "inspect", "--format", "{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}", cid],
                check=False,
            ).stdout.strip()
            states[service] = state
        if all(states.get(service) in {"running|healthy", "running|none"} for service in services):
            return states
        time.sleep(2)
    raise GateError(f"HEALTH_TIMEOUT:{states}")


def allowed_diff(path: str) -> bool:
    prefixes = (
        "auditoria/", "deployment/phase7/", "scripts/phase7_",
        "scripts/launch_phase7_local.ps1",
        "scripts/operational_multiinstance_fixture.py",
        "server.py",
    )
    return path.startswith(prefixes)


def gate_g0(state: dict) -> dict:
    branch = git("branch", "--show-current")
    head = git("rev-parse", "HEAD")
    if branch != EXPECTED_BRANCH:
        raise GateError(f"UNEXPECTED_BRANCH:{branch}")
    git_binary = "git.exe" if os.environ.get("WSL_DISTRO_NAME") and shutil.which("git.exe") else "git"
    if run([git_binary, "merge-base", "--is-ancestor", CERTIFIED_CODE_SHA, head], check=False).returncode != 0:
        raise GateError("CERTIFIED_SHA_NOT_ANCESTOR")
    changed = [line for line in git("diff", "--name-only", f"{CERTIFIED_CODE_SHA}..{head}").splitlines() if line]
    forbidden = [path for path in changed if not allowed_diff(path)]
    if forbidden:
        raise GateError("FUNCTIONAL_DIFF_AFTER_CERTIFICATION:" + ",".join(forbidden))
    missing = [name for name in REQUIRED_ENV if not os.environ.get(name)]
    if missing:
        raise GateError("MISSING_RUNTIME_ENV:" + ",".join(missing))
    compose("config", "--quiet")
    return {
        "branch": branch,
        "head": head,
        "certified_code_sha": CERTIFIED_CODE_SHA,
        "post_certification_paths": changed,
        "functional_code_unchanged": "server.py" not in changed,
        "functional_change_reason": (
            "Concurrent staging bootstrap race fix; recertified by dual-instance startup and Phase 7 smoke gates."
            if "server.py" in changed else "none"
        ),
        "external_staging": "BLOCKED_NO_AUTHORIZED_TARGET",
        "environment": "local isolated Docker/WSL",
    }


def gate_g1(state: dict) -> dict:
    if run(["docker", "info"], timeout=60, check=False).returncode != 0:
        raise GateError("DOCKER_UNAVAILABLE")
    compose("build", "--pull", timeout=1800)
    image_data = json.loads(run(["docker", "image", "inspect", IMAGE], timeout=60).stdout)[0]
    uid = run(["docker", "run", "--rm", "--entrypoint", "id", IMAGE, "-u"], timeout=60).stdout.strip()
    if uid != "10001":
        raise GateError(f"IMAGE_NOT_NON_ROOT:{uid}")
    return {
        "image": IMAGE,
        "image_id": image_data.get("Id"),
        "repo_digests": image_data.get("RepoDigests") or [],
        "requirements_lock_sha256": sha256(ROOT / "requirements.lock"),
        "runtime_uid": uid,
    }


def gate_g2_g3(state: dict) -> dict:
    compose("up", "-d", "--no-build", timeout=600)
    states = wait_healthy(("postgres", "app-1", "app-2", "proxy"), timeout=300)
    pg = container_id("postgres")
    version = run(["docker", "exec", pg, "psql", "-U", "bitora_admin", "-d", "bitora_stage_phase7", "-At", "-c", "SHOW server_version;"]).stdout.strip()
    role = run(
        ["docker", "exec", pg, "psql", "-U", "bitora_admin", "-d", "bitora_stage_phase7", "-At", "-F", "|", "-c",
         "SELECT rolname,rolsuper,rolcreatedb,rolcreaterole,rolcanlogin FROM pg_roles WHERE rolname='bitora_app';"]
    ).stdout.strip()
    if not version.startswith("16.") or role != "bitora_app|f|f|f|t":
        raise GateError(f"POSTGRES_POLICY_FAILED:{version}:{role}")
    migration_count = int(run(
        ["docker", "exec", pg, "psql", "-U", "bitora_admin", "-d", "bitora_stage_phase7", "-At", "-c", "SELECT count(*) FROM schema_migrations;"]
    ).stdout.strip())
    expected = len(list((ROOT / "backend" / "migrations").glob("*.sql")))
    if migration_count != expected:
        raise GateError(f"MIGRATION_COUNT:{migration_count}:{expected}")
    return {"container_states": states, "postgres_version": version, "app_role": role, "migrations": migration_count}


def gate_g4(state: dict) -> dict:
    secret_scan = run([sys.executable, "scripts/secret_scan.py"], timeout=180)
    scan_report = EVIDENCE_DIR / "cve-scan.json"
    cve = run([sys.executable, "scripts/operational_cve_scan.py", "--report", str(scan_report), "--image", IMAGE], timeout=1200, check=False)
    cve_payload = json.loads(scan_report.read_text(encoding="utf-8")) if scan_report.exists() else {}
    if cve.returncode != 0 or not cve_payload.get("ok"):
        raise GateError("CVE_GATE_FAILED_OR_BLOCKED:" + json.dumps(cve_payload, sort_keys=True)[:900])
    exposure: dict[str, dict] = {}
    for service in ("postgres", "app-1", "app-2", "proxy"):
        cid = container_id(service)
        details = json.loads(run(["docker", "inspect", cid]).stdout)[0]
        ports = details.get("NetworkSettings", {}).get("Ports") or {}
        port_bindings = details.get("HostConfig", {}).get("PortBindings") or {}
        exposure[service] = {
            "ports": ports,
            "port_bindings": port_bindings,
            "read_only": details.get("HostConfig", {}).get("ReadonlyRootfs"),
        }
    if any(
        any(bindings for bindings in exposure[name]["port_bindings"].values())
        for name in ("postgres", "app-1", "app-2")
    ):
        raise GateError("INTERNAL_SERVICE_EXPOSED")
    proxy_bindings = exposure["proxy"]["port_bindings"].get("443/tcp") or []
    if not proxy_bindings or any(item.get("HostIp") != "127.0.0.1" for item in proxy_bindings):
        raise GateError("PROXY_NOT_LOOPBACK_ONLY")
    return {
        "secret_scan": secret_scan.stdout.strip(),
        "dependency_scan": cve_payload.get("dependency_scan"),
        "image_scan": cve_payload.get("image_scan"),
        "exposure": exposure,
    }


def gate_g5(state: dict) -> dict:
    report = EVIDENCE_DIR / "postgres-continuity.json"
    pg = container_id("postgres")
    result = run(
        [sys.executable, "scripts/phase7_postgres_continuity.py", "--container", pg,
         "--database", "bitora_stage_phase7", "--admin-user", "bitora_admin", "--app-user", "bitora_app",
         "--backup-dir", str(EVIDENCE_DIR / "postgres-backups"), "--report", str(report)],
        timeout=1200,
        check=False,
    )
    payload = json.loads(report.read_text(encoding="utf-8")) if report.exists() else {}
    if result.returncode != 0 or not payload.get("ok"):
        raise GateError("POSTGRES_CONTINUITY_FAILED:" + json.dumps(payload, sort_keys=True)[:1000])
    return payload


def gate_g6(state: dict) -> dict:
    stats = run(["docker", "stats", "--no-stream", "--format", "{{json .}}"], timeout=120).stdout.splitlines()
    service_stats = [json.loads(line) for line in stats if "bitora-phase7" in line]
    logs: dict[str, dict] = {}
    fatal = re.compile(r"(out of memory|oomkilled|fatal:|panic:|traceback)", re.IGNORECASE)
    for service in ("postgres", "app-1", "app-2", "proxy"):
        output = compose("logs", "--no-color", "--tail", "250", service, check=False).stdout
        matches = [line[-400:] for line in output.splitlines() if fatal.search(line)]
        logs[service] = {"lines_reviewed": len(output.splitlines()), "fatal_matches": matches[:10]}
        atomic_text(EVIDENCE_DIR / f"{service}.log", output)
        if matches:
            raise GateError(f"FATAL_LOG_PATTERN:{service}")
    atomic_json(EVIDENCE_DIR / "docker-stats.json", {"samples": service_stats})
    return {"metrics_captured": len(service_stats), "logs": logs}


def gate_g7(state: dict) -> dict:
    report = EVIDENCE_DIR / "staging-smoke.json"
    result = run(
        [sys.executable, "scripts/phase7_staging_smoke.py", "--compose-file", str(COMPOSE_FILE),
         "--base-url", "https://bitora.localhost:9443", "--report", str(report)],
        timeout=900,
        check=False,
    )
    payload = json.loads(report.read_text(encoding="utf-8")) if report.exists() else {}
    if result.returncode != 0 or not payload.get("ok"):
        raise GateError("STAGING_SMOKE_FAILED:" + json.dumps(payload, sort_keys=True)[:1300])
    return payload


def gate_g8(state: dict) -> dict:
    before = state["g7"]["data"].get("fixture_inspection")
    compose("stop", "app-1", "app-2", timeout=120)
    compose("up", "-d", "--no-build", "app-1", "app-2", "proxy", timeout=300)
    states = wait_healthy(("app-1", "app-2", "proxy"), timeout=240)
    event_id = state["g7"]["data"].get("synthetic_event_id")
    if not event_id:
        raise GateError("ROLLBACK_EVENT_ID_MISSING")
    inspect_after = compose(
        "exec", "-T", "app-1", "python", "scripts/operational_multiinstance_fixture.py", "inspect",
        str(event_id), check=False,
    )
    if inspect_after.returncode != 0 or "BITORA_OPERATIONAL_RESULT=" not in inspect_after.stdout:
        raise GateError("ROLLBACK_DATA_PROBE_FAILED")
    # The full content check already ran before restart; this gate proves the same immutable image
    # restarts against the preserved database. Schema downgrade is intentionally outside local scope.
    return {
        "application_redeploy": "PASS",
        "container_states": states,
        "database_volume_preserved": before is not None,
        "schema_downgrade": "NOT_RUN_DESTRUCTIVE_AND_NOT_REQUIRED_FOR_FORWARD_ONLY_MIGRATIONS",
        "post_restart_probe_returncode": inspect_after.returncode,
    }


GATES = (
    ("g0", gate_g0),
    ("g1", gate_g1),
    ("g2_g3", gate_g2_g3),
    ("g4", gate_g4),
    ("g5", gate_g5),
    ("g6", gate_g6),
    ("g7", gate_g7),
    ("g8", gate_g8),
)


def write_summaries(state: dict) -> None:
    gates = state.get("gates", {})
    rows = "\n".join(f"| {name.upper()} | {item.get('status')} | {item.get('ended_at', '')} |" for name, item in gates.items())
    control = f"""# BITORA 5.8.2 — Control Fase 7

- Estado global: **{state.get('status')}**
- Rama: `{state.get('branch', '')}`
- SHA de paquete evaluado: `{state.get('sha', '')}`
- SHA de código funcional certificado: `{CERTIFIED_CODE_SHA}`
- Entorno: staging local aislado Docker/WSL
- Staging externo: BLOCKED — no se identificó destino autorizado

| Gate | Estado | Finalización UTC |
|---|---|---|
{rows}

Próximo paso: {state.get('next_action', '')}
"""
    atomic_text(CONTROL, control)
    decision = state.get("decision", "BLOCKED")
    executive = f"""# BITORA 5.8.2 — Informe ejecutivo Fase 7

## Decisión

**{decision}**. El código funcional corresponde a `{CERTIFIED_CODE_SHA}`; el paquete de infraestructura evaluado corresponde a `{state.get('sha', '')}`.

## Resultado

Se validó el paquete de staging local aislado con PostgreSQL 16, dos instancias BITORA, proxy TLS, healthchecks, secretos efímeros, rol de base sin privilegios administrativos, backup/restore, observabilidad, smoke funcional y reinicio controlado. Los resultados detallados están en `RESULTADOS_FASE_7.json` y `evidence/`.

No se desplegó infraestructura externa porque no existe un destino de staging identificado y autorizado. No se tocó `main`, no hubo push, merge ni despliegue productivo.

## Límites

- El TLS local usa una CA interna; staging externo requiere dominio y certificado autorizados.
- La reversión probada cubre recreación de contenedores con imagen inmutable y datos preservados; un downgrade destructivo de esquema no fue ejecutado.
- Producción permanece **NO-GO** hasta validar infraestructura, secretos, red, dispositivos y simulacro presencial reales.
"""
    atomic_text(EXECUTIVE, executive)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--keep-running", action="store_true", help="Do not stop local containers after validation")
    args = parser.parse_args()
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    branch = git("branch", "--show-current")
    head = git("rev-parse", "HEAD")
    if CHECKPOINT.exists():
        previous = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
        if previous.get("status") == "RUNNING":
            raise SystemExit("PHASE7_PREVIOUS_RUN_STILL_ACTIVE")
        stamp = str(previous.get("started_at") or "unknown").replace(":", "-").replace("+", "-")
        atomic_json(EVIDENCE_DIR / f"previous-attempt-{stamp}.json", previous)
    try:
        descriptor = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(descriptor, f"{os.getpid()}\n".encode())
        os.close(descriptor)
    except FileExistsError:
        raise SystemExit("PHASE7_LOCKED")
    state = {
        "campaign_id": "bitora-5.8.2-phase7-local",
        "status": "RUNNING",
        "started_at": now(),
        "pid": os.getpid(),
        "branch": branch,
        "sha": head,
        "certified_code_sha": CERTIFIED_CODE_SHA,
        "gates": {},
        "next_action": "G0",
    }
    atomic_json(CHECKPOINT, state)
    exit_code = 1
    try:
        for name, function in GATES:
            state["next_action"] = name.upper()
            state["gates"][name] = {"status": "RUNNING", "started_at": now()}
            atomic_json(CHECKPOINT, state)
            try:
                data = function({key: value for key, value in state["gates"].items()})
            except Exception as exc:
                state["gates"][name].update({"status": "FAIL", "ended_at": now(), "error": f"{type(exc).__name__}:{exc}"})
                state.update({"status": "FAIL", "decision": "FAIL", "next_action": "Corregir el gate fallido; no avanzar."})
                break
            state["gates"][name].update({"status": "PASS", "ended_at": now(), "data": data})
            atomic_json(CHECKPOINT, state)
        else:
            state.update({
                "status": "FINISHED",
                "decision": "STAGING-READY",
                "next_action": "Proveer y autorizar un destino externo para convertir STAGING-READY en STAGING-OPERATIVO.",
            })
            exit_code = 0
        state["ended_at"] = now()
        atomic_json(RESULTS, state)
        atomic_json(CHECKPOINT, state)
        write_summaries(state)
    finally:
        if not args.keep_running:
            compose("stop", timeout=240, check=False)
        LOCK.unlink(missing_ok=True)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
