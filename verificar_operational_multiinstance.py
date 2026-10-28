"""Safety, coverage and isolated fixture gate for the Docker harness."""

from contextlib import redirect_stdout
import io
from pathlib import Path
import tempfile

import server
from scripts import operational_multiinstance_fixture as fixture
from scripts.operational_multiinstance import telemetry_summary


def main() -> None:
    harness = Path("scripts/operational_multiinstance.py").read_text(encoding="utf-8")
    fixture_source = Path("scripts/operational_multiinstance_fixture.py").read_text(encoding="utf-8")
    database_source = Path("backend/database.py").read_text(encoding="utf-8")
    required_harness = {
        "postgres:16-alpine": "PostgreSQL 16",
        "two_distinct_instances_ready": "two application instances",
        "session_cross_instance": "cross-instance sessions",
        "logout_cross_instance_revokes": "cross-instance logout",
        'logged_out_me.get("authenticated") is False': "logout auth contract",
        "role_change_invalidates_session": "role-change revocation",
        'revoked_me.get("authenticated") is False': "role-change auth contract",
        "restart_preserves_shared_session": "restart continuity",
        'base_a = mapped_url(app_a)': "post-restart port discovery",
        "multievent_isolation": "multi-event isolation",
        'if not isinstance(events, list)': "events API list contract",
        "concurrent_entry_anti_passback": "concurrent anti-passback",
        "cross_instance_idempotent_replay": "idempotency",
        "postgres_restart_recovers": "PostgreSQL restart recovery",
        "database_disconnect_observable": "database outage readiness signal",
        'timeout=5': "bounded external outage probe",
        'item["status"] in {0, 503}': "timeout or explicit not-ready evidence",
        "database_reconnect_recovers": "database reconnect recovery",
        '"DB_CONNECTION_TIMEOUT=1"': "bounded database outage detection",
        "connect_timeout=1": "bounded PostgreSQL TCP connection",
        "integrated_http_postgres_endurance": "integrated HTTP/PostgreSQL endurance",
        '"p95"': "latency percentiles",
        "docker(\"stats\", \"--no-stream\"": "container resource telemetry",
        "pg_stat_activity": "PostgreSQL connection telemetry",
        "pg_locks": "PostgreSQL lock telemetry",
        "database_size_bytes": "database growth telemetry",
        "readiness_metrics": "periodic readiness telemetry",
        "deque(maxlen=20)": "bounded failure ring buffer",
        "atomic_json(args.checkpoint": "atomic persistent checkpoint",
        "telemetry_summary": "telemetry trend summary",
        'docker("rm", "-f"': "isolated cleanup",
    }
    missing = [label for token, label in required_harness.items() if token not in harness]
    required_fixture = [
        "set_access_state_enforcement", "auth_sessions", "enterprise_access_events",
        "ORDER BY token_hash",
        'for flag_key in ("command_center_v5", "enterprise_ui_v5_7_1")',
        "sys.path.insert(0, str(Path(__file__).resolve().parents[1]))",
    ]
    missing.extend(token for token in required_fixture if token not in fixture_source)
    if missing:
        raise AssertionError({"missing_multiinstance_coverage": missing})
    required_database = [
        "timeout=config.connection_timeout",
        "reconnect_timeout=config.connection_timeout",
        "_POSTGRES_POOL.close(timeout=config.connection_timeout)",
    ]
    missing_database = [token for token in required_database if token not in database_source]
    if missing_database:
        raise AssertionError({"missing_database_resilience": missing_database})
    forbidden = ["docker system prune", "docker volume prune", "--network host", "deployment/v4-online"]
    present = [token for token in forbidden if token in harness.lower()]
    if present:
        raise AssertionError({"unsafe_multiinstance_harness_tokens": present})

    synthetic = telemetry_summary([
        {"readiness": [{"status": 200, "latency_ms": 10}, {"status": 200, "latency_ms": 12}],
         "postgres": {"connections_total": 3, "locks_waiting": 0, "database_size_bytes": 1000},
         "containers": {"a": {"cpu_percent": 10, "oom_killed": False, "restart_count": 0},
                         "b": {"cpu_percent": 11, "oom_killed": False, "restart_count": 0},
                         "postgres": {"cpu_percent": 5, "oom_killed": False, "restart_count": 0}}},
        {"readiness": [{"status": 200, "latency_ms": 15}, {"status": 503, "latency_ms": 20}],
         "postgres": {"connections_total": 4, "locks_waiting": 1, "database_size_bytes": 1200},
         "containers": {"a": {"cpu_percent": 20, "oom_killed": False, "restart_count": 0},
                         "b": {"cpu_percent": 21, "oom_killed": False, "restart_count": 0},
                         "postgres": {"cpu_percent": 8, "oom_killed": False, "restart_count": 0}}},
    ])
    if synthetic["readiness_200"] != 3 or synthetic["readiness_total"] != 4:
        raise AssertionError({"bad_readiness_summary": synthetic})
    if synthetic["postgres_database_size_bytes"]["change_percent"] != 20.0:
        raise AssertionError({"bad_database_trend": synthetic})

    original_db_path = server.DB_PATH
    original_backup_dir = server.BACKUP_DIR
    try:
        temp_parent = Path.cwd() / "tmp"
        temp_parent.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temp_parent, ignore_cleanup_errors=True) as directory:
            server.DB_PATH = Path(directory) / "fixture.sqlite3"
            server.BACKUP_DIR = Path(directory) / "backups"
            output = io.StringIO()
            with redirect_stdout(output):
                fixture.setup()
                fixture.set_admin_role("Visualizador")
                fixture.set_admin_role("Super Admin")
            if output.getvalue().count("BITORA_OPERATIONAL_RESULT=") != 3:
                raise AssertionError("fixture result framing failed")
            with server.connect() as db:
                events = int(db.execute("SELECT COUNT(*) AS c FROM events").fetchone()["c"])
                users = int(db.execute("SELECT COUNT(*) AS c FROM users WHERE name IN ('Admin', 'multi-access')").fetchone()["c"])
                enforcement = int(db.execute("SELECT COUNT(*) AS c FROM feature_flags WHERE flag_key = 'access_state_engine_enforced' AND enabled = 1").fetchone()["c"])
            if events < 2 or users != 2 or enforcement != 1:
                raise AssertionError({"events": events, "users": users, "enforcement": enforcement})
    finally:
        server.DB_PATH = original_db_path
        server.BACKUP_DIR = original_backup_dir
    print("OK: operational multi-instance harness safety, coverage and isolated fixture")


if __name__ == "__main__":
    main()
