from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEPLOYMENT = ROOT / "deployment"
COMPOSE_FILE = DEPLOYMENT / "docker-compose.staging.yml"
ENV_EXAMPLE = DEPLOYMENT / "staging" / ".env.staging.example"
ENV_FILE = DEPLOYMENT / "staging" / ".env.staging"
LOG_DIR = DEPLOYMENT / "logs"
BACKUP_DIR = DEPLOYMENT / "backup" / "artifacts"


class BdfError(RuntimeError):
    pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="BITORA Deployment Framework")
    parser.add_argument("command", choices=[
        "check", "build", "up", "status", "logs", "health", "validate", "migrate",
        "smoke-test", "stop", "down", "reset", "destroy", "backup", "restore",
        "supertest", "fault", "recover", "upgrade-test",
    ])
    parser.add_argument("target", nargs="?", help="Archivo de restore o tipo de fault.")
    parser.add_argument("--profile", default="release", help="Perfil BSTF para supertest.")
    parser.add_argument("--yes", action="store_true", help="Confirma operaciones destructivas.")
    args = parser.parse_args(argv)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    try:
        return dispatch(args)
    except BdfError as exc:
        print(f"BDF ERROR: {exc}", file=sys.stderr)
        return 2


def dispatch(args) -> int:
    if args.command == "check":
        return check()
    if args.command == "build":
        return compose("build")
    if args.command == "up":
        require_safe_env()
        return compose("up", "-d", "--build")
    if args.command == "status":
        return compose("ps")
    if args.command == "logs":
        return compose("logs", "--tail", "200")
    if args.command in {"health", "validate"}:
        return validate()
    if args.command == "migrate":
        require_safe_env()
        return compose("exec", "-T", "bitora-staging-app", "python", "-c", "import server; server.init_db(); print('migrations ok')")
    if args.command == "smoke-test":
        return smoke_test()
    if args.command == "stop":
        return compose("stop")
    if args.command == "down":
        return compose("down")
    if args.command == "reset":
        require_yes(args)
        return compose("down", "-v") or compose("up", "-d", "--build")
    if args.command == "destroy":
        require_yes(args)
        return compose("down", "-v", "--remove-orphans")
    if args.command == "backup":
        return backup()
    if args.command == "restore":
        require_yes(args)
        if not args.target:
            raise BdfError("restore requiere ruta de archivo.")
        return restore(Path(args.target))
    if args.command == "supertest":
        return supertest(args.profile)
    if args.command == "fault":
        return fault(args.target or "")
    if args.command == "recover":
        return compose("up", "-d")
    if args.command == "upgrade-test":
        write_report("upgrade-test", {"status": "blocked", "reason": "No existe tag/version anterior certificada para ejecutar upgrade real."})
        print("Upgrade test preparado, bloqueado por falta de version anterior etiquetada.")
        return 1
    raise BdfError(f"Comando desconocido: {args.command}")


def check() -> int:
    docker_cmd = find_docker()
    checks = {
        "python": sys.version.split()[0],
        "compose_file": COMPOSE_FILE.exists(),
        "env_example": ENV_EXAMPLE.exists(),
        "env_file": ENV_FILE.exists(),
        "docker": bool(docker_cmd),
        "docker_path": docker_cmd or "",
    }
    if checks["docker"]:
        proc = run([docker_cmd, "compose", "version"], check=False)
        checks["docker_compose"] = proc.returncode == 0
        checks["docker_compose_output"] = (proc.stdout or proc.stderr).strip()[:300]
    else:
        checks["docker_compose"] = False
    if ENV_FILE.exists():
        env = read_env(ENV_FILE)
        checks["safe_env"] = safe_env_errors(env)
    else:
        checks["safe_env"] = ["Falta deployment/staging/.env.staging"]
    write_report("check", checks)
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    return 0 if checks["compose_file"] and checks["env_example"] and checks["docker"] and checks["docker_compose"] and not checks["safe_env"] else 1


def validate() -> int:
    health = request_json("http://localhost:8788/health")
    env = read_env(ENV_FILE) if ENV_FILE.exists() else {}
    result = {
        "APP": "HEALTHY" if health.get("status") == "ok" else "UNHEALTHY",
        "POSTGRES": "HEALTHY" if health.get("db") == "online" else "UNKNOWN",
        "STORAGE": "HEALTHY" if health.get("storage", {}).get("ready") else "UNHEALTHY",
        "SAFE_MODE": "ACTIVE" if safe_mode_active(env) else "INACTIVE",
        "BACKUP": "AVAILABLE" if BACKUP_DIR.exists() else "MISSING",
        "health": health,
    }
    write_report("health", result)
    for key, value in result.items():
        if key != "health":
            print(f"{key}: {value}")
    return 0 if all(result[key] in {"HEALTHY", "ACTIVE", "AVAILABLE"} for key in ["APP", "STORAGE", "SAFE_MODE", "BACKUP"]) else 1


def smoke_test() -> int:
    status = validate()
    smoke_status = compose("exec", "-T", "bitora-staging-app", "python", "run_bitora_supertest.py", "--quick") if status == 0 else 1
    result = {"health_ok": status == 0, "bstf_quick_ok": smoke_status == 0}
    write_report("smoke-test", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if status == 0 and smoke_status == 0 else 1


def backup() -> int:
    require_safe_env()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup_file = BACKUP_DIR / f"bitora-staging-{stamp}.sql"
    storage_manifest = BACKUP_DIR / f"bitora-staging-{stamp}.manifest.json"
    proc = run([
        docker(), "compose", "-f", str(COMPOSE_FILE), "exec", "-T", "bitora-staging-postgres",
        "pg_dump", "-U", "bitora_staging", "-d", "bitora_staging",
    ], check=False, echo=False)
    if proc.returncode != 0:
        raise BdfError(proc.stderr or "pg_dump fallo")
    backup_file.write_text(proc.stdout, encoding="utf-8")
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "file": backup_file.name,
        "sha256": sha256(backup_file),
        "size": backup_file.stat().st_size,
        "commit": git(["rev-parse", "HEAD"]),
        "type": "postgres_dump",
    }
    storage_manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


def restore(path: Path) -> int:
    require_safe_env()
    if not path.exists():
        raise BdfError(f"No existe backup: {path}")
    compose("stop", "bitora-staging-app", "bitora-staging-worker", "bitora-staging-monitor")
    reset_sql = (
        "DROP SCHEMA public CASCADE; "
        "CREATE SCHEMA public; "
        "GRANT ALL ON SCHEMA public TO bitora_staging; "
        "GRANT ALL ON SCHEMA public TO public;"
    )
    reset = run([
        docker(), "compose", "-f", str(COMPOSE_FILE), "exec", "-T", "bitora-staging-postgres",
        "psql", "-v", "ON_ERROR_STOP=1", "-U", "bitora_staging", "-d", "bitora_staging", "-c", reset_sql,
    ], check=False)
    if reset.returncode != 0:
        compose("up", "-d")
        raise BdfError(reset.stderr or "reset previo al restore fallo")
    proc = run([
        docker(), "compose", "-f", str(COMPOSE_FILE), "exec", "-T", "bitora-staging-postgres",
        "psql", "-v", "ON_ERROR_STOP=1", "-U", "bitora_staging", "-d", "bitora_staging",
    ], input_text=path.read_text(encoding="utf-8", errors="replace"), check=False, echo=False)
    if proc.returncode != 0:
        compose("up", "-d")
        raise BdfError(proc.stderr or "restore fallo")
    compose("up", "-d")
    write_report("restore", {"file": str(path), "sha256": sha256(path), "status": "completed"})
    print("Restore completado")
    return 0


def supertest(profile: str) -> int:
    require_safe_env()
    return compose("exec", "-T", "bitora-staging-app", "python", "run_bitora_supertest.py", f"--{profile}")


def fault(target: str) -> int:
    require_safe_env()
    allowed = {
        "stop-worker": ["stop", "bitora-staging-worker"],
        "stop-postgres": ["stop", "bitora-staging-postgres"],
        "stop-app": ["stop", "bitora-staging-app"],
    }
    if target not in allowed:
        raise BdfError("Fault permitido: stop-worker, stop-postgres, stop-app")
    return compose(*allowed[target])


def compose(*args: str) -> int:
    return run([docker(), "compose", "-f", str(COMPOSE_FILE), *args]).returncode


def docker() -> str:
    docker_cmd = find_docker()
    if not docker_cmd:
        raise BdfError("Docker no esta instalado o no esta disponible en PATH.")
    return docker_cmd


def find_docker() -> str:
    detected = shutil.which("docker")
    if detected:
        return detected
    candidates = []
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        candidates.append(Path(local_app_data) / "Programs" / "DockerDesktop" / "resources" / "bin" / "docker.exe")
    candidates.extend([
        Path("C:/Program Files/Docker/Docker/resources/bin/docker.exe"),
        Path("C:/Program Files/Docker/Docker/resources/bin/com.docker.cli.exe"),
    ])
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return ""


def run(cmd: list[str], *, input_text: str | None = None, check: bool = True, echo: bool = True):
    env = os.environ.copy()
    if cmd and Path(cmd[0]).name.lower() in {"docker.exe", "docker"}:
        docker_dir = str(Path(cmd[0]).parent)
        env["PATH"] = docker_dir + os.pathsep + env.get("PATH", "")
    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        input=input_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    if echo and proc.stdout:
        print(proc.stdout.rstrip())
    if echo and proc.stderr:
        print(proc.stderr.rstrip(), file=sys.stderr)
    if check and proc.returncode != 0:
        raise BdfError(f"Fallo comando: {' '.join(cmd)}")
    return proc


def request_json(url: str) -> dict:
    try:
        with urllib.request.urlopen(url, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def require_yes(args) -> None:
    if not args.yes:
        raise BdfError("Operacion destructiva. Repetir con --yes.")


def require_safe_env() -> None:
    if not ENV_FILE.exists():
        raise BdfError("Falta deployment/staging/.env.staging. Copiar desde .env.staging.example.")
    errors = safe_env_errors(read_env(ENV_FILE))
    if errors:
        raise BdfError("; ".join(errors))


def read_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text or text.startswith("#") or "=" not in text:
            continue
        key, value = text.split("=", 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def safe_env_errors(env: dict[str, str]) -> list[str]:
    errors = []
    if env.get("APP_ENV") != "staging":
        errors.append("APP_ENV debe ser staging")
    dsn = (env.get("QR_POSTGRES_DSN") or env.get("DATABASE_URL") or "").lower()
    if not dsn or "bitora_staging" not in dsn:
        errors.append("DSN debe apuntar a base bitora_staging")
    forbidden = ("production", "prod", "render.com/production")
    joined = "\n".join(f"{k}={v}" for k, v in env.items()).lower()
    if any(token in joined for token in forbidden):
        errors.append("Configuracion parece contener referencias productivas")
    if not safe_mode_active(env):
        errors.append("Safe mode de email/whatsapp requiere force/test recipients")
    if not env.get("BITORA_INTEGRATION_ENCRYPTION_KEY"):
        errors.append("BITORA_INTEGRATION_ENCRYPTION_KEY es obligatoria en staging")
    if env.get("BITORA_DISABLE_EMBEDDED_WORKER") != "1":
        errors.append("BITORA_DISABLE_EMBEDDED_WORKER=1 es obligatorio para validar worker separado")
    if env.get("BDF_WORKER_LIVE") != "1":
        errors.append("BDF_WORKER_LIVE=1 es obligatorio para validar worker separado")
    storage_path = env.get("BITORA_STORAGE_PATH", "")
    if not storage_path:
        errors.append("BITORA_STORAGE_PATH es obligatorio")
    callback_keys = ["GOOGLE_OAUTH_REDIRECT_URI", "META_OAUTH_REDIRECT_URI"]
    for key in callback_keys:
        value = env.get(key, "")
        if not value:
            errors.append(f"{key} es obligatorio para staging de integraciones")
        elif any(token in value.lower() for token in ("production", "prod", "bitora-demo.onrender.com")):
            errors.append(f"{key} no debe apuntar a produccion")
    return errors


def safe_mode_active(env: dict[str, str]) -> bool:
    email_safe = env.get("EMAIL_SAFE_MODE", "").lower() in {"1", "true", "yes", "si"}
    whatsapp_safe = env.get("WHATSAPP_SAFE_MODE", "").lower() in {"1", "true", "yes", "si"}
    email_target = bool(env.get("EMAIL_FORCE_RECIPIENT") or env.get("EMAIL_TEST_RECIPIENT"))
    whatsapp_target = bool(env.get("WHATSAPP_FORCE_RECIPIENT") or env.get("WHATSAPP_TEST_RECIPIENT"))
    return email_safe and whatsapp_safe and email_target and whatsapp_target


def write_report(name: str, payload: dict) -> None:
    path = LOG_DIR / f"bdf-{name}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""


if __name__ == "__main__":
    raise SystemExit(main())
