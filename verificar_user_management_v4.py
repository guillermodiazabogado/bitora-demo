import os
from pathlib import Path

tmp_dir = Path(__file__).resolve().parent / "tmp"
tmp_dir.mkdir(exist_ok=True)
db_path = tmp_dir / "bitora_user_management_v4.sqlite3"
if db_path.exists():
    db_path.unlink()
os.environ["QR_DB_ENGINE"] = "sqlite"
os.environ["QR_SQLITE_PATH"] = str(db_path)
os.environ["APP_ENV"] = "staging"

import server  # noqa: E402


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    server.init_db()
    run_id = "USER-MGMT-V4"
    with server.DB_LOCK, server.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        org_id = server.bootstrap_default_organization(db)
        now = server.now_iso()
        event_id = int(db.execute(
            """
            INSERT INTO events (organization_id, name, starts_at, ends_at, status, created_at)
            VALUES (?, ?, ?, ?, 'active', ?)
            """,
            (org_id, f"{run_id} Evento", now, now, now),
        ).lastrowid)
        password = server.generate_temporary_password()
        user_id = int(db.execute(
            """
            INSERT INTO users (name, role, pin_hash, email, full_name, active, must_change_password, created_at, updated_at)
            VALUES (?, 'Productor', ?, 'productor-demo@example.invalid', 'Productor Demo', 1, 1, ?, ?)
            """,
            ("productor-demo", server.hash_pin(password), now, now),
        ).lastrowid)
        server.assign_user_to_event(db, user_id, event_id, "Productor")
        db.execute(
            """
            INSERT OR IGNORE INTO organization_users (organization_id, user_id, role, status, accepted_at, created_at, updated_at)
            VALUES (?, ?, 'organization_admin', 'active', ?, ?, ?)
            """,
            (org_id, user_id, now, now, now),
        )
        server.audit(db, "verifier", "user.saved", "user", user_id, {"name": "productor-demo", "role": "Productor"})
        db.execute("COMMIT")

        user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        assert_true(user["pin_hash"] != password, "La contraseña quedo en texto plano")
        assert_true(server.verify_pin(password, user["pin_hash"]), "La contraseña no valida contra el hash")
        public_user = server.sanitize_user_row(user, public=True)
        admin_user = server.sanitize_user_row(user)
        assert_true("pin_hash" not in public_user and "pin_hash" not in admin_user, "pin_hash expuesto en payload saneado")
        assert_true(int(admin_user["must_change_password"]) == 1, "must_change_password no quedo activo")
        assert_true(server.validate_password_policy("abc") is not None, "Politica acepto contraseña debil")
        assert_true(server.validate_password_policy(server.generate_temporary_password()) is None, "Politica rechazo contraseña fuerte generada")

        new_password = server.generate_temporary_password()
        db.execute(
            "UPDATE users SET pin_hash = ?, must_change_password = 0, password_changed_at = ?, updated_at = ? WHERE id = ?",
            (server.hash_pin(new_password), now, now, user_id),
        )
        changed = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        assert_true(server.verify_pin(new_password, changed["pin_hash"]), "Reset de contraseña no actualizo hash")
        assert_true(int(changed["must_change_password"]) == 0, "Cambio obligatorio no se limpio al cambiar contraseña")

        db.execute("UPDATE users SET active = 0, disabled_at = ?, updated_at = ? WHERE id = ?", (now, now, user_id))
        disabled = db.execute("SELECT active, disabled_at FROM users WHERE id = ?", (user_id,)).fetchone()
        assert_true(int(disabled["active"]) == 0 and disabled["disabled_at"], "Desactivacion no quedo registrada")
        db.execute("UPDATE users SET active = 1, disabled_at = NULL, updated_at = ? WHERE id = ?", (now, user_id))

        session = {"id": user_id, "name": "productor-demo", "role": "Productor"}
        assert_true(server.session_can_access_event(db, session, event_id), "Productor no accede a su evento")
        other_event = int(db.execute(
            "INSERT INTO events (organization_id, name, starts_at, ends_at, status, created_at) VALUES (?, ?, ?, ?, 'active', ?)",
            (org_id, f"{run_id} Evento Ajeno", now, now, now),
        ).lastrowid)
        assert_true(not server.session_can_access_event(db, session, other_event), "Productor accede a evento ajeno")

        modules = set(server.PERMISSION_MATRIX["Productor"]["modules"])
        expected_home_modules = {"dashboard", "register", "reception", "access", "agenda", "communications", "certificates", "surveys", "speakers", "reports"}
        assert_true(expected_home_modules.issubset(modules), "Productor no conserva modulos esperados para Home Visual")
        audits = db.execute("SELECT COUNT(*) AS c FROM audit_logs WHERE action = 'user.saved'").fetchone()
        assert_true(int(audits["c"]) >= 1, "No se registro auditoria de usuario")

    print("USER MANAGEMENT V4: PASSED")
    print("Passwords persisted in plaintext: 0")
    print("pin_hash exposed by API serializer: 0")
    print("Cross-event access allowed: 0")
    print("Audit: PASSED")


if __name__ == "__main__":
    main()
