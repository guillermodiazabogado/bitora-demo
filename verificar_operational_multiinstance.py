"""Safety, coverage and isolated fixture gate for the Docker harness."""

from contextlib import redirect_stdout
import io
from pathlib import Path
import tempfile

import server
from scripts import operational_multiinstance_fixture as fixture


def main() -> None:
    harness = Path("scripts/operational_multiinstance.py").read_text(encoding="utf-8")
    fixture_source = Path("scripts/operational_multiinstance_fixture.py").read_text(encoding="utf-8")
    required_harness = {
        "postgres:16-alpine": "PostgreSQL 16",
        "two_distinct_instances_ready": "two application instances",
        "session_cross_instance": "cross-instance sessions",
        "logout_cross_instance_revokes": "cross-instance logout",
        'logged_out_me.get("authenticated") is False': "logout auth contract",
        "role_change_invalidates_session": "role-change revocation",
        'revoked_me.get("authenticated") is False': "role-change auth contract",
        "restart_preserves_shared_session": "restart continuity",
        "multievent_isolation": "multi-event isolation",
        "concurrent_entry_anti_passback": "concurrent anti-passback",
        "cross_instance_idempotent_replay": "idempotency",
        "integrated_http_postgres_endurance": "integrated HTTP/PostgreSQL endurance",
        '"p95"': "latency percentiles",
        'docker("rm", "-f"': "isolated cleanup",
    }
    missing = [label for token, label in required_harness.items() if token not in harness]
    required_fixture = [
        "set_access_state_enforcement", "auth_sessions", "enterprise_access_events",
        "sys.path.insert(0, str(Path(__file__).resolve().parents[1]))",
    ]
    missing.extend(token for token in required_fixture if token not in fixture_source)
    if missing:
        raise AssertionError({"missing_multiinstance_coverage": missing})
    forbidden = ["docker system prune", "docker volume prune", "--network host", "deployment/v4-online"]
    present = [token for token in forbidden if token in harness.lower()]
    if present:
        raise AssertionError({"unsafe_multiinstance_harness_tokens": present})

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
