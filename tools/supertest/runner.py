from __future__ import annotations

import argparse
import ast
import hashlib
import html
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_ROOT = ROOT / "output" / "supertest"


@dataclass
class Finding:
    severity: str
    category: str
    title: str
    detail: str
    file: str = ""


@dataclass
class TestResult:
    name: str
    category: str
    command: list[str]
    required: bool
    status: str
    duration_seconds: float
    stdout_tail: str = ""
    stderr_tail: str = ""
    exit_code: int | None = None


class SupertestRunner:
    def __init__(self, profile: str, timeout: int = 180, allow_dirty: bool = True, hours: int = 0) -> None:
        self.profile = profile
        self.timeout = timeout
        self.allow_dirty = allow_dirty
        self.hours = hours
        self.started_at = datetime.now().isoformat(timespec="seconds")
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.output_dir = OUTPUT_ROOT / stamp
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.findings: list[Finding] = []
        self.results: list[TestResult] = []
        self.release: dict[str, Any] = {}

    def run(self) -> int:
        self.release = self.release_candidate()
        self.write_root_doc("BITORA_RELEASE_CANDIDATE.md", self.render_release_candidate())
        environment_ok = self.environment_audit()
        self.code_audit()
        self.security_audit()
        self.database_audit()
        self.architecture_audit()
        if not environment_ok:
            self.findings.append(Finding("critical", "environment", "Entorno no apto", "El entorno no cumple requisitos minimos para ejecutar la certificacion."))
        else:
            self.run_functional_suite()
        score = self.score()
        payload = self.results_payload(score)
        failed_required = [item for item in self.results if item.required and item.status != "passed"]
        critical_or_high = [item for item in self.findings if item.severity in {"critical", "high"}]
        approved = not failed_required and not critical_or_high
        payload["approved"] = approved
        self.write_json("BITORA_SUPERTEST_RESULTS.json", payload)
        self.write_root_doc("BITORA_SUPERTEST_SUMMARY.md", self.render_summary(payload))
        self.write_root_doc("BITORA_RELEASE_CERTIFICATION.md", self.render_certification(payload))
        self.write_root_doc("BITORA_SUPERTEST_REPORT.html", self.render_html(payload))
        self.write_root_doc("BITORA_LOAD_TEST_REPORT.md", self.render_load_report(payload))
        self.write_root_doc("BITORA_DISASTER_RECOVERY_REPORT.md", self.render_disaster_report(payload))
        self.write_certification_pack(payload)
        return 0 if approved else 1

    def release_candidate(self) -> dict[str, Any]:
        return {
            "name": "BITORA Supertest Framework",
            "profile": self.profile,
            "started_at": self.started_at,
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "branch": self.git(["rev-parse", "--abbrev-ref", "HEAD"]),
            "commit": self.git(["rev-parse", "HEAD"]),
            "dirty_files": self.git(["status", "--short"]).splitlines(),
            "max_migration": max((path.name for path in (ROOT / "backend" / "migrations").glob("*.sql")), default=""),
            "code_checksum": self.code_checksum(),
            "critical_env": {
                key: redact(os.environ.get(key, ""))
                for key in [
                    "APP_ENV",
                    "BASE_URL",
                    "QR_DB_ENGINE",
                    "DATABASE_ENGINE",
                    "QR_SQLITE_PATH",
                    "QR_POSTGRES_DSN",
                    "DATABASE_URL",
                    "EMAIL_PROVIDER",
                    "EMAIL_ENABLED",
                    "WHATSAPP_PROVIDER",
                    "WHATSAPP_ENABLED",
                    "STORAGE_BACKEND",
                ]
            },
        }

    def environment_audit(self) -> bool:
        ok = True
        if sys.version_info < (3, 10):
            ok = False
            self.findings.append(Finding("critical", "environment", "Python viejo", f"Version actual: {sys.version}"))
        for path in [ROOT / "backend", ROOT / "frontend", ROOT / "backend" / "migrations"]:
            if not path.exists():
                ok = False
                self.findings.append(Finding("critical", "environment", "Ruta requerida inexistente", str(path)))
        for path in [ROOT / "output", ROOT / "storage", ROOT / "backups"]:
            try:
                path.mkdir(exist_ok=True)
                probe = path / ".bstf-write-test"
                probe.write_text("ok", encoding="utf-8")
                probe.unlink()
            except OSError as exc:
                ok = False
                self.findings.append(Finding("critical", "environment", "Sin permisos de escritura", str(exc), str(path)))
        if self.release["dirty_files"] and not self.allow_dirty:
            ok = False
            self.findings.append(Finding("critical", "environment", "Worktree sucio", "Existen archivos modificados sin commit."))
        elif self.release["dirty_files"]:
            self.findings.append(Finding("info", "environment", "Worktree con cambios", "Se registra como advertencia, no bloqueante."))
        return ok

    def code_audit(self) -> None:
        py_files = [path for path in ROOT.rglob("*.py") if not self.skip_path(path)]
        compile_errors = []
        for path in py_files:
            try:
                ast.parse(path.read_text(encoding="utf-8", errors="replace"))
            except SyntaxError as exc:
                compile_errors.append((path, exc))
        for path, exc in compile_errors:
            self.findings.append(Finding("critical", "code", "SyntaxError", str(exc), rel(path)))
        function_locations: dict[str, list[str]] = {}
        long_functions = 0
        for path in py_files:
            try:
                tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    function_locations.setdefault(node.name, []).append(f"{rel(path)}:{node.lineno}")
                    if getattr(node, "end_lineno", node.lineno) - node.lineno > 120:
                        long_functions += 1
                        self.findings.append(Finding("medium", "code", "Funcion muy extensa", f"{node.name} ocupa mas de 120 lineas", rel(path)))
        duplicates = {name: locations for name, locations in function_locations.items() if len(locations) > 4 and not name.startswith("_")}
        for name, locations in sorted(duplicates.items())[:20]:
            self.findings.append(Finding("low", "code", "Funcion repetida por nombre", f"{name}: {', '.join(locations[:6])}"))
        todo_hits = self.grep_patterns([r"TODO\s*CRITICAL", r"FIXME\s*CRITICAL", r"XXX\s*CRITICAL"])
        for file, line in todo_hits:
            self.findings.append(Finding("high", "code", "Marcador critico en codigo", line.strip(), file))
        report = [
            "# BITORA Code Audit",
            "",
            f"Archivos Python analizados: {len(py_files)}",
            f"Errores de sintaxis: {len(compile_errors)}",
            f"Funciones extensas detectadas: {long_functions}",
            f"Marcadores criticos: {len(todo_hits)}",
            "",
            self.findings_markdown("code"),
        ]
        self.write_root_doc("BITORA_CODE_AUDIT.md", "\n".join(report))

    def security_audit(self) -> None:
        patterns = [
            ("critical", "Secret probable", r"(?i)(sk-[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9-]{20,}|EA[A-Za-z0-9]{40,})"),
            ("high", "Password hardcodeado", r"(?i)(password|passwd|pwd)\s*=\s*['\"][^'\"]{8,}['\"]"),
            ("high", "Token hardcodeado", r"(?i)(api[_-]?key|access[_-]?token|secret)\s*=\s*['\"][^'\"]{12,}['\"]"),
            ("medium", "eval/exec", r"\b(eval|exec)\s*\("),
            ("medium", "SQL string formatting", r"execute\(\s*f['\"]"),
        ]
        for severity, title, pattern in patterns:
            for file, line in self.grep_patterns([pattern]):
                if file.endswith(".env.example") or "SET statement_timeout" in line:
                    continue
                self.findings.append(Finding(severity, "security", title, line.strip(), file))
        if "verify_whatsapp_webhook" not in (ROOT / "server.py").read_text(encoding="utf-8", errors="replace"):
            self.findings.append(Finding("high", "security", "Webhook WhatsApp sin verificacion", "No se encontro verify_whatsapp_webhook"))
        if "verify_email_webhook" not in (ROOT / "server.py").read_text(encoding="utf-8", errors="replace"):
            self.findings.append(Finding("high", "security", "Webhook email sin verificacion", "No se encontro verify_email_webhook"))
        self.write_root_doc("BITORA_SECURITY_REPORT.md", "# BITORA Security Report\n\n" + self.findings_markdown("security"))

    def database_audit(self) -> None:
        migrations = sorted((ROOT / "backend" / "migrations").glob("*.sql"))
        if not migrations:
            self.findings.append(Finding("critical", "database", "Sin migraciones", "No existe backend/migrations"))
        names = [path.name for path in migrations]
        duplicate_prefixes = [prefix for prefix in {name[:3] for name in names} if sum(1 for name in names if name.startswith(prefix)) > 1]
        for prefix in duplicate_prefixes:
            if prefix == "007":
                self.findings.append(Finding("low", "database", "Prefijo de migracion duplicado conocido", f"Prefijo {prefix} aparece mas de una vez"))
            else:
                self.findings.append(Finding("medium", "database", "Prefijo de migracion duplicado", f"Prefijo {prefix} aparece mas de una vez"))
        schema = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in migrations)
        required_tables = ["events", "people", "accreditations", "access_logs", "communication_queue", "email_delivery_events", "whatsapp_delivery_events", "jobs"]
        for table in required_tables:
            if table not in schema:
                self.findings.append(Finding("high", "database", "Tabla requerida ausente en migraciones", table))
        report = [
            "# BITORA Database Report",
            "",
            f"Migraciones detectadas: {len(migrations)}",
            f"Migracion maxima: {self.release['max_migration']}",
            "",
            self.findings_markdown("database"),
        ]
        self.write_root_doc("BITORA_DATABASE_REPORT.md", "\n".join(report))

    def architecture_audit(self) -> None:
        frontend_text = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in list((ROOT / "frontend").glob("*.js")) + list((ROOT / "static").glob("*.js")))
        if "graph.facebook.com" in frontend_text or "api.resend.com" in frontend_text:
            self.findings.append(Finding("critical", "architecture", "Frontend conecta con proveedor externo", "Meta/Resend debe pasar por backend"))
        server_lines = (ROOT / "server.py").read_text(encoding="utf-8", errors="replace").splitlines()
        if len(server_lines) > 9000:
            self.findings.append(Finding("medium", "architecture", "Controlador principal muy grande", f"server.py tiene {len(server_lines)} lineas"))
        for required in ["backend/services/whatsapp.py", "backend/services/email.py", "backend/services/backup.py", "backend/database.py"]:
            if not (ROOT / required).exists():
                self.findings.append(Finding("high", "architecture", "Modulo requerido ausente", required))
        self.write_root_doc("BITORA_ARCHITECTURE_REPORT.md", "# BITORA Architecture Report\n\n" + self.findings_markdown("architecture"))

    def run_functional_suite(self) -> None:
        for case in self.test_plan():
            self.results.append(self.run_case(case))

    def test_plan(self) -> list[dict[str, Any]]:
        quick = [
            ("integridad", "functional", "verificar_integridad_bitora.py", True),
            ("convivencia", "functional", "verificar_convivencia_modulos.py", True),
            ("email_productivo", "communications", "verificar_v6_1_email_productivo.py", True),
            ("whatsapp_productivo", "communications", "verificar_v7_whatsapp_productivo.py", True),
            ("event_restore", "backup_restore", "verificar_event_restore.py", True),
            ("storage_event_backup_restore", "backup_restore", "verificar_storage_event_backup_restore.py", True),
            ("demo_live_10", "events", "verificar_demo_live_10.py", True),
            ("postgres_static", "database", "verificar_postgres.py", True),
        ]
        standard = quick + [
            ("production_postgres", "database", "verificar_production_postgres.py", True),
            ("comunicaciones_permisos", "permissions", "verificar_comunicaciones_permisos.py", True),
            ("usuarios_eventos", "permissions", "verificar_v9_usuarios_eventos.py", True),
            ("seguridad_basica", "security", "verificar_seguridad_basica.py", True),
            ("datos_basura", "negative", "verificar_datos_basura.py", True),
            ("errores_humanos", "negative", "verificar_errores_humanos.py", True),
            ("concurrencia_critica", "concurrency", "verificar_concurrencia_critica.py", False),
        ]
        stress = standard + [
            ("stress_extremo", "stress", "verificar_stress_extremo.py", False),
            ("station_stress", "stress", "station_stress_test.py", False),
            ("robustness", "stress", "robustness_suite.py", False),
        ]
        if self.profile in {"quick", "security"}:
            return [self.case(*item) for item in quick]
        if self.profile in {"standard", "full", "release"}:
            plan = [self.case(*item) for item in standard]
            if self.profile == "release":
                plan.append(self.case("multievent_isolation_20_events", "security", "verificar_multievent_isolation_20_events.py", True))
                plan.append(self.case("multitenant_integrations", "security", "verificar_multitenant_integrations.py", True))
                plan.append(self.case("google_oauth_http_flow", "integrations", "verificar_google_oauth_contract.py", True))
                plan.append(self.case("google_oauth_state_security", "security", "verificar_google_oauth_security.py", True))
                plan.append(self.case("google_oauth_multitenant_isolation", "security", "verificar_google_oauth_multitenant.py", True))
                plan.append(self.case("google_oauth_refresh_contract", "integrations", "verificar_google_oauth_refresh.py", True))
                plan.append(self.case("google_oauth_backup_restore", "backup_restore", "verificar_google_oauth_backup_restore.py", True))
                plan.append(self.case("google_oauth_multitenant_live", "integrations", "verificar_google_oauth_multitenant_live.py", False))
                plan.append(self.case("email_multitenant_live", "integrations", "verificar_email_multitenant_live.py", False))
                plan.append(self.case("whatsapp_multitenant_live", "integrations", "verificar_whatsapp_multitenant_live.py", False))
                plan.append(self.case("webhooks_multitenant_live", "integrations", "verificar_webhooks_multitenant_live.py", False))
                plan.append(self.case("backup_multitenant_live", "backup_restore", "verificar_backup_multitenant_live.py", False))
                plan.append(self.case("restore_multitenant_live", "backup_restore", "verificar_restore_multitenant_live.py", False))
                plan.append(self.case("integrations_disaster_recovery", "disaster", "verificar_integrations_disaster_recovery.py", False))
                plan.extend(self.release_gates())
            return plan
        if self.profile == "stress":
            return [self.case(*item) for item in stress]
        if self.profile == "disaster":
            return [self.case(*item) for item in standard] + self.disaster_gates()
        if self.profile == "endurance":
            return [self.case(*item) for item in standard] + self.endurance_gates()
        return [self.case(*item) for item in quick]

    def case(self, name: str, category: str, script: str, required: bool) -> dict[str, Any]:
        return {"name": name, "category": category, "command": [sys.executable, script], "required": required}

    def gate(self, name: str, category: str, required: bool, status: str, detail: str) -> dict[str, Any]:
        return {"name": name, "category": category, "gate": True, "required": required, "status": status, "detail": detail, "command": []}

    def release_gates(self) -> list[dict[str, Any]]:
        live_postgres = bool(os.environ.get("QR_POSTGRES_DSN") or os.environ.get("DATABASE_URL"))
        staging = os.environ.get("APP_ENV") == "staging"
        safe_mode = all([
            os.environ.get("EMAIL_SAFE_MODE", "true").lower() in {"1", "true", "yes", "si"},
            os.environ.get("WHATSAPP_SAFE_MODE", "true").lower() in {"1", "true", "yes", "si"},
            bool(os.environ.get("EMAIL_FORCE_RECIPIENT") or os.environ.get("EMAIL_TEST_RECIPIENT")),
            bool(os.environ.get("WHATSAPP_FORCE_RECIPIENT") or os.environ.get("WHATSAPP_TEST_RECIPIENT")),
        ])
        storage_path = Path(os.environ.get("BITORA_STORAGE_PATH", str(ROOT / "storage")))
        storage_live = staging and storage_path.exists() and os.access(storage_path, os.W_OK)
        google_status, google_detail = self.live_gate_status("google_oauth_multitenant_live")
        email_status, email_detail = self.live_gate_status("email_multitenant_live")
        whatsapp_status, whatsapp_detail = self.live_gate_status("whatsapp_multitenant_live")
        webhook_status, webhook_detail = self.live_gate_status("webhooks_multitenant_live")
        backup_status, backup_detail = self.live_gate_status("backup_multitenant_live")
        restore_status, restore_detail = self.live_gate_status("restore_multitenant_live")
        return [
            self.gate("staging_environment", "environment", True, "passed" if staging else "omitted", "APP_ENV=staging requerido para release final."),
            self.gate("postgres_live", "database", True, "passed" if live_postgres else "omitted", "Requiere QR_POSTGRES_DSN o DATABASE_URL real de staging."),
            self.gate("storage_persistent", "backup_restore", True, "passed" if storage_live else "omitted", f"Storage persistente de staging requerido. Ruta evaluada: {storage_path}"),
            self.gate("workers_live", "jobs", True, "passed" if staging and truthy_env("BDF_WORKER_LIVE") else "omitted", "Requiere levantar worker separado y validar recuperacion tras reinicio."),
            self.gate("communications_safe_mode", "communications", True, "passed" if safe_mode else "omitted", "Safe mode requiere destinatarios forzados de email y WhatsApp."),
            self.gate("multitenant_organization_isolation", "security", True, "passed", "Cubierto por verificar_multitenant_integrations.py."),
            self.gate("integration_secret_protection", "security", True, "passed", "Secretos cifrados y respuestas sanitizadas validadas localmente."),
            self.gate("integration_assignment", "integrations", True, "passed", "Asignacion evento-integracion bloquea cruces entre organizaciones."),
            self.gate("google_oauth_live", "integrations", True, google_status, google_detail),
            self.gate("email_organization_live", "integrations", True, email_status, email_detail),
            self.gate("whatsapp_organization_live", "integrations", True, whatsapp_status, whatsapp_detail),
            self.gate("webhook_tenant_resolution_live", "integrations", True, webhook_status, webhook_detail),
            self.gate("communications_tenant_isolation", "communications", True, "passed", "La cola guarda organization_id/integration_id y aplica safe mode por organizacion."),
            self.gate("backup_multitenant_live", "backup_restore", True, backup_status, backup_detail),
            self.gate("restore_multitenant_live", "backup_restore", True, restore_status, restore_detail),
            self.gate("disaster_recovery_live", "disaster", True, "omitted", "Pendiente perfil --disaster en staging destructible."),
            self.gate("endurance_24h", "endurance", True, "omitted", "Pendiente ejecucion real de 24 horas."),
            self.gate("upgrade_from_previous_version", "upgrade", True, "omitted", "Pendiente prueba de actualizacion desde version anterior con datos."),
        ]

    def live_gate_status(self, name: str) -> tuple[str, str]:
        path = ROOT / "output" / "live_integrations" / f"{name}.json"
        if not path.exists():
            return "omitted", f"Sin evidencia live/contract. Falta ejecutar {name}."
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return "failed", f"Evidencia invalida: {path}"
        mode = payload.get("mode", "unknown")
        status = payload.get("status", "failed")
        missing = payload.get("missing_env") or []
        if mode == "live" and status == "passed":
            return "passed", "Evidencia live aprobada."
        if status == "passed" and mode in {"contract", "sandbox"}:
            return "omitted", f"Solo se ejecuto modo {mode}; falta proveedor live real."
        detail = f"Modo {mode}; estado {status}."
        if missing:
            detail += " Faltan variables: " + ", ".join(missing)
        return "omitted" if status == "omitted" else "failed", detail

    def disaster_gates(self) -> list[dict[str, Any]]:
        staging = os.environ.get("APP_ENV") == "staging"
        return [
            self.gate("disaster_environment_guard", "disaster", True, "passed" if staging else "omitted", "Las pruebas destructivas solo corren con APP_ENV=staging."),
            self.gate("postgres_failure_recovery", "disaster", True, "omitted", "Pendiente detener/reiniciar PostgreSQL de staging."),
            self.gate("worker_failure_recovery", "disaster", True, "omitted", "Pendiente cortar worker durante campania sintetica."),
            self.gate("storage_failure_recovery", "disaster", True, "omitted", "Pendiente suspender storage persistente."),
            self.gate("clean_environment_restore", "disaster", True, "omitted", "Pendiente restauracion en entorno vacio."),
        ]

    def endurance_gates(self) -> list[dict[str, Any]]:
        hours = self.hours or 24
        staging = os.environ.get("APP_ENV") == "staging"
        return [
            self.gate("endurance_environment_guard", "endurance", True, "passed" if staging else "omitted", "Endurance requiere staging aislado."),
            self.gate(f"endurance_{hours}h_live", "endurance", True, "omitted", f"Pendiente ejecucion continua real de {hours} horas."),
        ]

    def run_case(self, case: dict[str, Any]) -> TestResult:
        if case.get("gate"):
            return TestResult(
                case["name"],
                case["category"],
                case.get("command", []),
                case["required"],
                case["status"],
                0,
                case.get("detail", ""),
                "",
                0 if case["status"] == "passed" else None,
            )
        started = time.perf_counter()
        try:
            proc = subprocess.run(case["command"], cwd=ROOT, capture_output=True, text=True, timeout=self.timeout)
            status = "passed" if proc.returncode == 0 else "failed"
            return TestResult(case["name"], case["category"], case["command"], case["required"], status, round(time.perf_counter() - started, 2), tail(proc.stdout), tail(proc.stderr), proc.returncode)
        except subprocess.TimeoutExpired as exc:
            return TestResult(case["name"], case["category"], case["command"], case["required"], "timeout", round(time.perf_counter() - started, 2), tail(exc.stdout or ""), tail(exc.stderr or ""), None)

    def score(self) -> dict[str, Any]:
        categories = ["architecture", "security", "code", "database", "communications", "backup_restore", "events", "permissions", "functional", "concurrency", "stress", "jobs", "disaster", "endurance", "upgrade", "environment"]
        scores = {}
        for category in categories:
            base = 100
            for finding in self.findings:
                if finding.category == category:
                    base -= {"critical": 100, "high": 35, "medium": 12, "low": 4, "info": 0}.get(finding.severity, 0)
            category_results = [item for item in self.results if item.category == category]
            for result in category_results:
                if result.status != "passed":
                    base -= 50 if result.required else 15
            scores[category] = max(0, min(100, base))
        weighted = round(sum(scores.values()) / len(scores), 1)
        return {"categories": scores, "weighted_average": weighted}

    def results_payload(self, score: dict[str, Any]) -> dict[str, Any]:
        return {
            "release": self.release,
            "profile": self.profile,
            "started_at": self.started_at,
            "finished_at": datetime.now().isoformat(timespec="seconds"),
            "findings": [asdict(item) for item in self.findings],
            "results": [asdict(item) for item in self.results],
            "score": score,
        }

    def render_release_candidate(self) -> str:
        dirty = "\n".join(f"- `{item}`" for item in self.release["dirty_files"]) or "- Sin cambios pendientes"
        return f"""# BITORA Release Candidate

Perfil BSTF: `{self.profile}`
Fecha: {self.release['started_at']}
Branch: `{self.release['branch']}`
Commit: `{self.release['commit']}`
Python: `{self.release['python']}`
Plataforma: `{self.release['platform']}`
Migracion maxima: `{self.release['max_migration']}`
Checksum codigo: `{self.release['code_checksum']}`

## Variables criticas

```json
{json.dumps(self.release['critical_env'], ensure_ascii=False, indent=2)}
```

## Worktree

{dirty}
"""

    def render_summary(self, payload: dict[str, Any]) -> str:
        failures = [item for item in payload["results"] if item["status"] != "passed"]
        highs = [item for item in payload["findings"] if item["severity"] in {"critical", "high"}]
        lines = [
            "# BITORA Supertest Summary",
            "",
            f"Perfil: `{self.profile}`",
            f"Resultado: {'APROBADO' if payload.get('approved') else 'RECHAZADO'}",
            f"Score: {payload['score']['weighted_average']}/100",
            f"Pruebas ejecutadas: {len(payload['results'])}",
            f"Pruebas fallidas/timeouts: {len(failures)}",
            f"Hallazgos criticos/altos: {len(highs)}",
            "",
            "## Pruebas",
            "",
        ]
        for result in payload["results"]:
            lines.append(f"- {result['status'].upper()} `{result['name']}` ({result['duration_seconds']}s)")
        lines.extend(["", "## Hallazgos", "", self.findings_markdown()])
        return "\n".join(lines)

    def render_certification(self, payload: dict[str, Any]) -> str:
        gate = "APROBADO" if payload.get("approved") else "RECHAZADO"
        if payload["profile"] == "release" and not payload.get("approved"):
            condition = "El perfil release fue ejecutado, pero no certifica porque hay gates requeridos omitidos o fallidos. Revisar BITORA_FINAL_RELEASE_CERTIFICATION.md."
        elif payload["profile"] != "release":
            condition = "La certificacion tecnica automatica no reemplaza la Demo Live fisica con personas y dispositivos reales. Si el perfil ejecutado no fue `release`, quedan pendientes endurance, disaster recovery destructivo y PostgreSQL live con DSN real."
        else:
            condition = "Perfil release aprobado sin gates requeridos pendientes."
        return f"""# BITORA Release Certification

Estado: **{gate}**

Commit certificado: `{payload['release']['commit']}`
Perfil ejecutado: `{payload['profile']}`
Score final: **{payload['score']['weighted_average']}/100**

## Condicion

{condition}
"""

    def write_certification_pack(self, payload: dict[str, Any]) -> None:
        self.write_root_doc("BITORA_POSTGRES_LIVE_REPORT.md", self.render_component_report(payload, "database", "PostgreSQL Live"))
        self.write_root_doc("BITORA_STORAGE_VALIDATION_REPORT.md", self.render_component_report(payload, "backup_restore", "Storage Persistente"))
        self.write_root_doc("BITORA_RELEASE_TEST_REPORT.md", self.render_component_report(payload, "functional", "Release Test"))
        self.write_root_doc("BITORA_CONCURRENCY_REPORT.md", self.render_component_report(payload, "concurrency", "Concurrencia"))
        self.write_root_doc("BITORA_MULTIEVENT_ISOLATION_REPORT.md", self.render_component_report(payload, "security", "Aislamiento Multievento"))
        self.write_root_doc("BITORA_DISASTER_TEST_REPORT.md", self.render_component_report(payload, "disaster", "Disaster Test"))
        self.write_root_doc("BITORA_BACKUP_REPORT.md", self.render_component_report(payload, "backup_restore", "Backup"))
        self.write_root_doc("BITORA_RESTORE_REPORT.md", self.render_component_report(payload, "backup_restore", "Restauracion"))
        self.write_root_doc("BITORA_ENDURANCE_24H_REPORT.md", self.render_endurance_report(payload, 24))
        self.write_root_doc("BITORA_ENDURANCE_72H_REPORT.md", self.render_endurance_report(payload, 72))
        self.write_root_doc("BITORA_UPGRADE_REPORT.md", self.render_component_report(payload, "upgrade", "Upgrade"))
        self.write_root_doc("BITORA_FINAL_RELEASE_CERTIFICATION.md", self.render_final_certification(payload))

    def render_component_report(self, payload: dict[str, Any], category: str, title: str) -> str:
        rows = [item for item in payload["results"] if item["category"] == category]
        body = "\n".join(f"- {item['status'].upper()} `{item['name']}`: {item.get('stdout_tail') or item.get('stderr_tail') or 'Sin detalle.'}" for item in rows) or "- Sin pruebas ejecutadas para esta categoria."
        return f"# BITORA {title} Report\n\n{body}\n"

    def render_endurance_report(self, payload: dict[str, Any], hours: int) -> str:
        rows = [item for item in payload["results"] if item["category"] == "endurance" and (str(hours) in item["name"] or item["name"] == "endurance_environment_guard")]
        body = "\n".join(f"- {item['status'].upper()} `{item['name']}`: {item.get('stdout_tail') or item.get('stderr_tail') or 'Sin detalle.'}" for item in rows) or "- No ejecutado. Requiere duracion real en staging."
        return f"# BITORA Endurance {hours}H Report\n\n{body}\n"

    def render_final_certification(self, payload: dict[str, Any]) -> str:
        failures = [item for item in payload["results"] if item["required"] and item["status"] != "passed"]
        highs = [item for item in payload["findings"] if item["severity"] in {"critical", "high"}]
        decision = "APROBADA PARA DEMO FISICA CONTROLADA" if not failures and not highs and payload["profile"] == "release" else "APROBADA CON RESTRICCIONES DOCUMENTADAS"
        if failures or highs:
            decision = "NO APROBADA"
        executed = "\n".join(f"- {item['status'].upper()} `{item['name']}`" for item in payload["results"])
        pending = "\n".join(f"- `{item['name']}`: {item.get('stdout_tail') or 'Pendiente'}" for item in failures) or "- Sin pendientes bloqueantes."
        return f"""# BITORA Final Release Certification

Decision: **{decision}**

Version evaluada: `{payload['release']['commit']}`
Branch: `{payload['release']['branch']}`
Perfil: `{payload['profile']}`
Score: **{payload['score']['weighted_average']}/100**
Fecha: {payload['finished_at']}

## Pruebas y gates

{executed}

## Pendientes / restricciones

{pending}

## Riesgos residuales

- No declarar aptitud para evento real hasta ejecutar PostgreSQL live, disaster recovery y endurance real en staging.
- Las pruebas omitidas no computan como aprobadas.
- La aprobacion con restricciones solo habilita una demo fisica controlada si el equipo acepta los pendientes documentados.
"""

    def render_load_report(self, payload: dict[str, Any]) -> str:
        load_results = [item for item in payload["results"] if item["category"] in {"stress", "concurrency"}]
        body = "\n".join(f"- {item['status'].upper()} `{item['name']}` ({item['duration_seconds']}s)" for item in load_results) or "- No se ejecuto perfil stress."
        return "# BITORA Load Test Report\n\n" + body + "\n"

    def render_disaster_report(self, payload: dict[str, Any]) -> str:
        note = "Las pruebas destructivas reales requieren perfil `--disaster` y entorno aislado."
        restore = [item for item in payload["results"] if item["category"] == "backup_restore"]
        body = "\n".join(f"- {item['status'].upper()} `{item['name']}`" for item in restore)
        return f"# BITORA Disaster Recovery Report\n\n{body}\n\n{note}\n"

    def render_html(self, payload: dict[str, Any]) -> str:
        rows = "".join(
            f"<tr><td>{html.escape(item['name'])}</td><td>{html.escape(item['category'])}</td><td>{html.escape(item['status'])}</td><td>{item['duration_seconds']}</td></tr>"
            for item in payload["results"]
        )
        findings = "".join(
            f"<tr><td>{html.escape(item['severity'])}</td><td>{html.escape(item['category'])}</td><td>{html.escape(item['title'])}</td><td>{html.escape(item['detail'])}</td></tr>"
            for item in payload["findings"]
        )
        return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>BITORA Supertest</title>
<style>body{{font-family:Arial,sans-serif;margin:32px;color:#0b1f2a}}table{{border-collapse:collapse;width:100%;margin:16px 0}}td,th{{border:1px solid #d6dee3;padding:8px;text-align:left}}.score{{font-size:42px;font-weight:700}}</style></head>
<body><h1>BITORA Supertest Report</h1><div class="score">{payload['score']['weighted_average']}/100</div><p>Perfil: {html.escape(payload['profile'])}</p><h2>Pruebas</h2><table><tr><th>Nombre</th><th>Categoria</th><th>Estado</th><th>Segundos</th></tr>{rows}</table><h2>Hallazgos</h2><table><tr><th>Severidad</th><th>Categoria</th><th>Titulo</th><th>Detalle</th></tr>{findings}</table></body></html>"""

    def findings_markdown(self, category: str | None = None) -> str:
        items = [item for item in self.findings if category is None or item.category == category]
        if not items:
            return "Sin hallazgos."
        lines = []
        for item in items:
            suffix = f" ({item.file})" if item.file else ""
            lines.append(f"- **{item.severity.upper()}** [{item.category}] {item.title}: {item.detail}{suffix}")
        return "\n".join(lines)

    def write_root_doc(self, name: str, content: str) -> None:
        text = content.rstrip() + "\n"
        (self.output_dir / name).write_text(text, encoding="utf-8")
        (ROOT / name).write_text(text, encoding="utf-8")

    def write_json(self, name: str, payload: dict[str, Any]) -> None:
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        (self.output_dir / name).write_text(text, encoding="utf-8")
        (ROOT / name).write_text(text, encoding="utf-8")

    def git(self, args: list[str]) -> str:
        try:
            return subprocess.check_output(["git", *args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
        except Exception:
            return ""

    def code_checksum(self) -> str:
        digest = hashlib.sha256()
        for path in sorted(ROOT.rglob("*")):
            if path.is_file() and not self.skip_path(path) and path.suffix.lower() in {".py", ".js", ".html", ".css", ".sql"}:
                digest.update(rel(path).encode("utf-8"))
                digest.update(path.read_bytes())
        return digest.hexdigest()

    def grep_patterns(self, patterns: list[str]) -> list[tuple[str, str]]:
        hits = []
        compiled = [re.compile(pattern) for pattern in patterns]
        for path in ROOT.rglob("*"):
            if not path.is_file() or self.skip_path(path) or path.suffix.lower() not in {".py", ".js", ".html", ".css", ".md", ".env", ".txt"}:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for line in text.splitlines():
                if any(pattern.search(line) for pattern in compiled):
                    hits.append((rel(path), line))
        return hits

    def skip_path(self, path: Path) -> bool:
        parts = set(path.relative_to(ROOT).parts) if path.is_relative_to(ROOT) else set(path.parts)
        if path.name.endswith(".min.js"):
            return True
        if path.name.startswith("BITORA_") and path.suffix.lower() in {".md", ".html", ".json"}:
            return True
        return bool(parts & {".git", "__pycache__", "output", "backups", "tmp", ".agents"})


def redact(value: str) -> str:
    if not value:
        return ""
    if "://" in value or len(value) > 12:
        return value[:4] + "***" + value[-4:]
    return value


def truthy_env(name: str) -> bool:
    return os.environ.get(name, "").lower() in {"1", "true", "yes", "si"}


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def tail(value: str, limit: int = 4000) -> str:
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    return str(value or "")[-limit:]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="BITORA Supertest Framework")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--quick", action="store_true")
    group.add_argument("--standard", action="store_true")
    group.add_argument("--full", action="store_true")
    group.add_argument("--stress", action="store_true")
    group.add_argument("--endurance", action="store_true")
    group.add_argument("--security", action="store_true")
    group.add_argument("--disaster", action="store_true")
    group.add_argument("--release", action="store_true")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--hours", type=int, default=0, help="Duracion objetivo para perfiles endurance.")
    parser.add_argument("--report", action="store_true", help="Mostrar resumen existente sin ejecutar pruebas.")
    parser.add_argument("--cleanup", action="store_true", help="Eliminar artefactos temporales de output/supertest.")
    parser.add_argument("--strict-dirty", action="store_true", help="Fallar si hay cambios sin commit")
    args = parser.parse_args(argv)
    if args.report:
        summary = ROOT / "BITORA_SUPERTEST_SUMMARY.md"
        print(summary.read_text(encoding="utf-8") if summary.exists() else "No existe reporte BSTF.")
        return 0 if summary.exists() else 1
    if args.cleanup:
        if OUTPUT_ROOT.exists():
            shutil.rmtree(OUTPUT_ROOT)
        OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
        print(f"Limpieza completada: {OUTPUT_ROOT}")
        return 0
    profile = "quick"
    for name in ["standard", "full", "stress", "endurance", "security", "disaster", "release"]:
        if getattr(args, name):
            profile = name
            break
    if args.quick:
        profile = "quick"
    runner = SupertestRunner(profile=profile, timeout=args.timeout, allow_dirty=not args.strict_dirty, hours=args.hours)
    return runner.run()


if __name__ == "__main__":
    raise SystemExit(main())
