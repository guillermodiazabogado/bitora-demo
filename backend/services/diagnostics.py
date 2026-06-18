from __future__ import annotations

import threading
import time
from collections import Counter, deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


@dataclass
class RequestSample:
    timestamp: float
    duration_ms: float
    status: int
    method: str
    path: str


class RuntimeMetrics:
    def __init__(self, max_samples: int = 5000) -> None:
        self._lock = threading.Lock()
        self._samples: deque[RequestSample] = deque(maxlen=max_samples)
        self._active_requests = 0
        self._total_requests = 0
        self._started_at = time.time()

    def begin(self) -> float:
        with self._lock:
            self._active_requests += 1
            self._total_requests += 1
        return time.perf_counter()

    def finish(self, started: float, method: str, path: str, status: int) -> None:
        duration_ms = max(0.0, (time.perf_counter() - started) * 1000)
        with self._lock:
            self._active_requests = max(0, self._active_requests - 1)
            self._samples.append(
                RequestSample(
                    timestamp=time.time(),
                    duration_ms=duration_ms,
                    status=int(status or 200),
                    method=method,
                    path=path,
                )
            )

    def snapshot(self) -> dict[str, Any]:
        now = time.time()
        with self._lock:
            samples = list(self._samples)
            active = self._active_requests
            total = self._total_requests
            started_at = self._started_at
        recent = [sample for sample in samples if sample.timestamp >= now - 60]
        durations = sorted(sample.duration_ms for sample in samples)
        recent_errors = sum(1 for sample in recent if sample.status >= 500)
        return {
            "uptime_seconds": int(now - started_at),
            "active_requests": active,
            "total_requests": total,
            "requests_per_minute": len(recent),
            "average_response_ms": round(sum(durations) / len(durations), 2) if durations else 0,
            "p95_response_ms": _percentile(durations, 0.95),
            "p99_response_ms": _percentile(durations, 0.99),
            "server_errors_per_minute": recent_errors,
        }


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0
    index = min(len(values) - 1, max(0, int(round((len(values) - 1) * percentile))))
    return round(values[index], 2)


class DiagnosticsService:
    def __init__(
        self,
        *,
        engine: str,
        db_path: Path,
        backup_dir: Path,
        app_env: str,
        app_version: str,
        started_at: str,
    ) -> None:
        self.engine = engine
        self.db_path = db_path
        self.backup_dir = backup_dir
        self.app_env = app_env
        self.app_version = app_version
        self.started_at = started_at

    def collect(
        self,
        db,
        *,
        runtime: dict[str, Any],
        sessions: list[dict[str, Any]],
        auto_backup_minutes: int,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        minute_ago = (now - timedelta(minutes=1)).isoformat(timespec="seconds")
        fifteen_minutes_ago = (now - timedelta(minutes=15)).isoformat(timespec="seconds")
        day_ago = (now - timedelta(hours=24)).isoformat(timespec="seconds")

        database = self._database_status(db)
        queues = self._queue_status(db, day_ago)
        webhooks = self._webhook_status(db, day_ago)
        backups = self._backup_status(auto_backup_minutes)
        event_health = self._event_health(db, fifteen_minutes_ago, sessions)
        recent_errors = self._recent_technical_logs(db, levels=("error", "critical"), limit=50)
        recent_logs = self._recent_technical_logs(db, levels=(), limit=100)
        access_per_minute = int(
            db.execute("SELECT COUNT(*) AS c FROM access_logs WHERE created_at >= ?", (minute_ago,)).fetchone()["c"]
            or 0
        )
        qr_per_minute = int(
            db.execute(
                "SELECT COUNT(*) AS c FROM access_logs WHERE created_at >= ? AND token <> ''",
                (minute_ago,),
            ).fetchone()["c"]
            or 0
        )

        services = {
            "api": {"status": "online", "label": "Online"},
            "database": {"status": "online" if database["online"] else "offline", "label": "Online" if database["online"] else "Error"},
            "postgres": {
                "status": "online" if self.engine == "postgres" and database["online"] else ("inactive" if self.engine != "postgres" else "offline"),
                "label": "Conectado" if self.engine == "postgres" and database["online"] else ("No activo" if self.engine != "postgres" else "Error"),
            },
            "cache": {"status": "inactive", "label": "No configurada"},
            "jobs": {"status": queues["status"], "label": queues["label"]},
            "communications": {
                "status": "warning" if queues["failed_24h"] else "online",
                "label": "Errores recientes" if queues["failed_24h"] else "Normal",
            },
            "backups": {"status": backups["status"], "label": backups["label"]},
            "webhooks": {"status": webhooks["status"], "label": webhooks["label"]},
        }

        alerts = self._alerts(runtime, database, queues, backups, webhooks)
        waiting_room = self._waiting_room_status(db)
        simulator = self._simulator_status(db)
        global_status = "critical" if any(item["severity"] == "critical" for item in alerts) else (
            "warning" if alerts else "healthy"
        )
        return {
            "app_status": global_status,
            "database_status": services["database"]["status"],
            "cache_status": services["cache"]["status"],
            "jobs_status": services["jobs"]["status"],
            "backup_status": services["backups"]["status"],
            "webhook_status": services["webhooks"]["status"],
            "uptime": runtime["uptime_seconds"],
            "active_users": len(sessions),
            "active_operators": event_health["active_operators"],
            "recent_errors": recent_errors,
            "meta": {
                "env": self.app_env,
                "version": self.app_version,
                "started_at": self.started_at,
                "generated_at": now.isoformat(timespec="seconds"),
            },
            "services": services,
            "metrics": {
                **runtime,
                "queries_per_minute": runtime["requests_per_minute"],
                "concurrent_users": len(sessions),
                "active_operators": event_health["active_operators"],
                "qr_per_minute": qr_per_minute,
                "accesses_per_minute": access_per_minute,
            },
            "database": database,
            "cache": {
                "enabled": False,
                "backend": "no configurada",
                "hits": 0,
                "misses": 0,
                "size": 0,
            },
            "queues": queues,
            "webhooks": webhooks,
            "backups": backups,
            "event_health": event_health,
            "waiting_room": waiting_room,
            "simulator": simulator,
            "alerts": alerts,
            "logs": recent_logs,
        }

    def _database_status(self, db) -> dict[str, Any]:
        result: dict[str, Any] = {
            "online": True,
            "engine": self.engine,
            "size_bytes": 0,
            "active_connections": 1,
            "slow_queries": 0,
            "last_migration": "sqlite-inline",
        }
        try:
            db.execute("SELECT 1 AS ok").fetchone()
            if self.engine == "postgres":
                size_row = db.execute("SELECT pg_database_size(current_database()) AS size").fetchone()
                connections = db.execute(
                    "SELECT COUNT(*) AS c FROM pg_stat_activity WHERE datname = current_database()"
                ).fetchone()
                migration = db.execute(
                    "SELECT version FROM schema_migrations ORDER BY applied_at DESC LIMIT 1"
                ).fetchone()
                result.update(
                    size_bytes=int(size_row["size"] or 0),
                    active_connections=int(connections["c"] or 0),
                    last_migration=migration["version"] if migration else "sin migraciones",
                )
            elif self.db_path.exists():
                result["size_bytes"] = self.db_path.stat().st_size
        except Exception as exc:
            result["online"] = False
            result["error"] = str(exc)[:180]
        return result

    def _queue_status(self, db, day_ago: str) -> dict[str, Any]:
        job_rows = db.execute(
            """
            SELECT kind, status, COUNT(*) AS total
            FROM jobs
            GROUP BY kind, status
            """
        ).fetchall()
        job_types: dict[str, Counter] = {}
        for row in job_rows:
            family = str(row["kind"] or "other").split(".", 1)[0]
            job_types.setdefault(family, Counter())[str(row["status"])] += int(row["total"] or 0)
        job_totals = Counter()
        for counters in job_types.values():
            job_totals.update(counters)
        rows = db.execute(
            """
            SELECT channel, status, COUNT(*) AS total
            FROM communication_queue
            GROUP BY channel, status
            """
        ).fetchall()
        by_type: dict[str, Counter] = {
            "email": Counter(),
            "whatsapp": Counter(),
            "certificates": Counter(),
            "exports": Counter(),
            "backups": Counter(),
        }
        for row in rows:
            channel = str(row["channel"] or "other").lower()
            bucket = by_type.setdefault(channel, Counter())
            bucket[str(row["status"] or "pending").lower()] += int(row["total"] or 0)
        failed_24h = int(
            db.execute(
                """
                SELECT COUNT(*) AS c
                FROM communication_queue
                WHERE status IN ('error', 'failed', 'bounced') AND processed_at >= ?
                """,
                (day_ago,),
            ).fetchone()["c"]
            or 0
        )
        pending = job_totals["pending"] + job_totals["retrying"]
        processing = job_totals["processing"]
        completed = job_totals["completed"]
        failed_jobs = job_totals["failed"]
        cancelled = job_totals["cancelled"]
        retries = int(
            db.execute("SELECT COALESCE(SUM(CASE WHEN attempts > 1 THEN attempts - 1 ELSE 0 END), 0) AS c FROM communication_queue").fetchone()["c"]
            or 0
        )
        status = "warning" if failed_24h or failed_jobs or pending > 100 else "online"
        return {
            "status": status,
            "label": "Atrasado" if pending > 100 else ("Con errores" if failed_24h or failed_jobs else "Normal"),
            "pending": pending,
            "processing": processing,
            "completed": completed,
            "failed": failed_jobs + failed_24h,
            "failed_24h": failed_24h,
            "cancelled": cancelled,
            "retries": retries,
            "by_type": {key: dict(value) for key, value in by_type.items()},
            "jobs_by_type": {key: dict(value) for key, value in job_types.items()},
        }

    def _webhook_status(self, db, day_ago: str) -> dict[str, Any]:
        email = db.execute(
            """
            SELECT COUNT(*) AS total, MAX(created_at) AS last_received,
                   MAX(CASE WHEN event_type IN ('email.bounced', 'email.failed', 'email.complained') THEN created_at END) AS last_error
            FROM email_delivery_events
            WHERE created_at >= ?
            """,
            (day_ago,),
        ).fetchone()
        whatsapp = db.execute(
            """
            SELECT COUNT(*) AS total, MAX(created_at) AS last_received,
                   MAX(CASE WHEN action LIKE '%error%' OR action LIKE '%failed%' THEN created_at END) AS last_error
            FROM audit_logs
            WHERE actor = 'webhook' AND action LIKE 'communications.whatsapp%' AND created_at >= ?
            """,
            (day_ago,),
        ).fetchone()
        items = {
            "email": dict(email),
            "whatsapp": dict(whatsapp),
            "mercado_pago": {"total": 0, "last_received": None, "last_error": None, "configured": False},
        }
        has_errors = bool(email["last_error"] or whatsapp["last_error"])
        return {
            "status": "warning" if has_errors else "online",
            "label": "Con errores" if has_errors else "Operativos",
            "items": items,
        }

    def _backup_status(self, auto_backup_minutes: int) -> dict[str, Any]:
        patterns = ("*.sqlite3", "bitora-postgres-*.json")
        files = sorted(
            [path for pattern in patterns for path in self.backup_dir.glob(pattern)],
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        ) if self.backup_dir.exists() else []
        latest = files[0] if files else None
        if not latest:
            return {
                "status": "warning",
                "label": "Sin backup",
                "last_success": None,
                "size_bytes": 0,
                "duration_ms": None,
                "available": 0,
                "last_error": None,
            }
        age_minutes = (time.time() - latest.stat().st_mtime) / 60
        max_age = max(auto_backup_minutes * 3, 60) if auto_backup_minutes > 0 else 1440
        return {
            "status": "online" if age_minutes <= max_age else "warning",
            "label": "Reciente" if age_minutes <= max_age else "Antiguo",
            "last_success": datetime.fromtimestamp(latest.stat().st_mtime, timezone.utc).isoformat(timespec="seconds"),
            "name": latest.name,
            "size_bytes": latest.stat().st_size,
            "age_minutes": round(age_minutes, 1),
            "duration_ms": None,
            "available": len(files),
            "last_error": None,
        }

    def _event_health(self, db, fifteen_minutes_ago: str, sessions: list[dict[str, Any]]) -> dict[str, Any]:
        active_events = int(
            db.execute(
                "SELECT COUNT(*) AS c FROM events WHERE status IN ('draft', 'published', 'active')"
            ).fetchone()["c"]
            or 0
        )
        terminals = int(
            db.execute(
                """
                SELECT COUNT(*) AS c FROM (
                    SELECT DISTINCT operator, access_point
                    FROM access_logs
                    WHERE created_at >= ?
                ) active_terminals
                """,
                (fifteen_minutes_ago,),
            ).fetchone()["c"]
            or 0
        )
        operator_roles = {"Super Admin", "Productor", "Coordinador", "Operador de recepcion", "Operador de acceso"}
        active_operators = sum(1 for session in sessions if session.get("role") in operator_roles)
        participants = sum(1 for session in sessions if session.get("role") == "Participante")
        return {
            "active_events": active_events,
            "connected_participants": participants,
            "active_operators": active_operators,
            "active_terminals": terminals,
            "inactive_terminals": 0,
        }

    def _recent_technical_logs(self, db, levels: tuple[str, ...], limit: int) -> list[dict[str, Any]]:
        params: list[Any] = []
        where = ""
        if levels:
            placeholders = ", ".join("?" for _ in levels)
            where = f"WHERE level IN ({placeholders})"
            params.extend(levels)
        params.append(limit)
        rows = db.execute(
            f"""
            SELECT id, level, module, message, detail, created_at
            FROM technical_logs
            {where}
            ORDER BY id DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [dict(row) for row in rows]

    def _alerts(
        self,
        runtime: dict[str, Any],
        database: dict[str, Any],
        queues: dict[str, Any],
        backups: dict[str, Any],
        webhooks: dict[str, Any],
    ) -> list[dict[str, str]]:
        alerts: list[dict[str, str]] = []
        if not database["online"]:
            alerts.append({"severity": "critical", "code": "database_down", "message": "Base de datos desconectada"})
        if backups["status"] != "online":
            alerts.append({"severity": "warning", "code": "backup", "message": backups["label"]})
        if queues["failed_24h"]:
            alerts.append({"severity": "warning", "code": "jobs_failed", "message": f"{queues['failed_24h']} trabajos fallidos en 24 h"})
        if queues["pending"] > 100:
            alerts.append({"severity": "warning", "code": "jobs_delayed", "message": f"Cola atrasada: {queues['pending']} pendientes"})
        if webhooks["status"] == "warning":
            alerts.append({"severity": "warning", "code": "webhooks", "message": "Webhooks con errores recientes"})
        if runtime["p95_response_ms"] > 1000:
            alerts.append({"severity": "critical", "code": "response_slow", "message": f"Respuesta p95 critica: {runtime['p95_response_ms']} ms"})
        elif runtime["p95_response_ms"] > 500:
            alerts.append({"severity": "warning", "code": "response_slow", "message": f"Respuesta p95 elevada: {runtime['p95_response_ms']} ms"})
        if runtime["server_errors_per_minute"] >= 5:
            alerts.append({"severity": "critical", "code": "api_errors", "message": "Errores masivos de API en el ultimo minuto"})
        if not runtime.get("worker_alive", False):
            alerts.append({"severity": "critical", "code": "worker_down", "message": "Worker de jobs detenido"})
        return alerts

    def _waiting_room_status(self, db) -> dict[str, Any]:
        enabled = int(db.execute("SELECT COUNT(*) AS c FROM events WHERE waiting_room_enabled = 1").fetchone()["c"] or 0)
        counts = {
            row["status"]: int(row["total"] or 0)
            for row in db.execute("SELECT status, COUNT(*) AS total FROM waiting_room_visitors GROUP BY status").fetchall()
        }
        admitted = counts.get("admitted", 0)
        completed = counts.get("completed", 0)
        return {
            "enabled_events": enabled,
            "waiting": counts.get("waiting", 0),
            "admitted": admitted,
            "completed": completed,
            "abandoned": counts.get("abandoned", 0),
            "expired": counts.get("expired", 0),
            "throughput": completed,
            "errors": 0,
        }

    def _simulator_status(self, db) -> dict[str, Any]:
        rows = db.execute("SELECT status, COUNT(*) AS total FROM simulator_state GROUP BY status").fetchall()
        counts = {row["status"]: int(row["total"] or 0) for row in rows}
        return {"running": counts.get("running", 0), "paused": counts.get("paused", 0), "stopped": counts.get("stopped", 0)}
