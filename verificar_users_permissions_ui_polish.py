from __future__ import annotations

import json
import shutil
import threading
import urllib.error
import urllib.request
from pathlib import Path

import server


ROOT = Path(__file__).resolve().parent


def contains(path: str, needle: str) -> bool:
    return needle in (ROOT / path).read_text(encoding="utf-8", errors="replace")


def request(base: str, method: str, path: str, payload: dict | None = None, cookie: str = "") -> tuple[int, dict, str]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    if cookie:
        headers["Cookie"] = cookie
    req = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            body = response.read()
            parsed = json.loads(body.decode("utf-8")) if body else {}
            return response.status, parsed, response.headers.get("Set-Cookie", "")
    except urllib.error.HTTPError as exc:
        body = exc.read()
        parsed = json.loads(body.decode("utf-8")) if body else {}
        return exc.code, parsed, ""


def dynamic_delete_checks() -> tuple[bool, str]:
    tmp = ROOT / ".tmp-users-permissions-verifier.sqlite3"
    if tmp.exists():
        tmp.unlink()
    httpd = None
    original_db_path = server.DB_PATH
    original_backup_dir = server.BACKUP_DIR
    backup_tmp = ROOT / ".tmp-users-permissions-backups"
    try:
        server.DB_PATH = tmp
        server.BACKUP_DIR = backup_tmp
        server.AppHandler.log_message = lambda self, format, *args: None
        server.AUTH_SESSIONS.clear()
        server.init_db()
        server.seed_if_empty()
        admin_pin = server.generate_temporary_password()
        delete_pin = server.generate_temporary_password()
        unauthorized_pin = server.generate_temporary_password()
        with server.connect() as db:
            db.execute(
                "UPDATE users SET pin_hash = ?, active = 1, must_change_password = 0 WHERE name = 'Admin'",
                (server.hash_pin(admin_pin),),
            )
        httpd = server.OperationalHTTPServer(("127.0.0.1", 0), server.AppHandler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{httpd.server_address[1]}"

        create_status, created, _ = request(base, "POST", "/api/users", {
            "actor": "Admin",
            "name": "DeleteVerifier",
            "role": "Visualizador",
            "pin": delete_pin,
            "active": True,
            "must_change_password": False,
        })
        if create_status != 200:
            return False, f"crear usuario temporal devolvio {create_status}: {created}"
        user_id = int(created["user"]["id"])

        login_status, _login_body, cookie = request(base, "POST", "/api/auth/login", {"name": "DeleteVerifier", "pin": delete_pin})
        if login_status != 200 or "qr_session=" not in cookie:
            return False, "login previo del usuario temporal no funciono"
        session_token = cookie.split("qr_session=", 1)[1].split(";", 1)[0]

        delete_status, delete_body, _ = request(base, "POST", "/api/users/delete", {"actor": "Admin", "user_id": user_id})
        if delete_status != 200 or not delete_body.get("ok"):
            return False, f"eliminar usuario temporal devolvio {delete_status}: {delete_body}"

        if session_token in server.AUTH_SESSIONS:
            return False, "sesion del usuario eliminado siguio activa"

        relogin_status, _body, _ = request(base, "POST", "/api/auth/login", {"name": "DeleteVerifier", "pin": delete_pin})
        if relogin_status != 403:
            return False, "login posterior a eliminacion no fue bloqueado"

        admin_id = 0
        with server.connect() as db:
            admin_id = int(db.execute("SELECT id FROM users WHERE name = 'Admin'").fetchone()["id"])
            audit_row = db.execute("SELECT 1 FROM audit_logs WHERE action = 'user.deleted' AND entity_id = ?", (user_id,)).fetchone()
            if not audit_row:
                return False, "auditoria user.deleted no fue registrada"

        last_admin_status, _last_admin_body, _ = request(base, "POST", "/api/users/delete", {"actor": "Admin", "user_id": admin_id})
        if last_admin_status != 409:
            return False, "ultimo Super Admin no fue bloqueado"

        admin_login_status, _admin_body, admin_cookie = request(base, "POST", "/api/auth/login", {"name": "Admin", "pin": admin_pin})
        if admin_login_status != 200:
            return False, "login Admin para self-delete no funciono"
        self_status, _self_body, _ = request(base, "POST", "/api/users/delete", {"user_id": admin_id}, cookie=admin_cookie)
        if self_status != 409:
            return False, "autoeliminacion no fue bloqueada"

        other_status, other_body, _ = request(base, "POST", "/api/users", {
            "actor": "Admin",
            "name": "DeleteVerifierUnauthorized",
            "role": "Visualizador",
            "pin": unauthorized_pin,
            "active": True,
            "must_change_password": False,
        })
        if other_status != 200:
            return False, f"crear usuario para prueba no autorizada devolvio {other_status}: {other_body}"
        unauthorized_status, _unauthorized_body, _ = request(base, "POST", "/api/users/delete", {"actor": "Recepcion", "user_id": int(other_body["user"]["id"])})
        if unauthorized_status != 403:
            return False, "actor no autorizado pudo intentar eliminar usuario"

        double_status, _double_body, _ = request(base, "POST", "/api/users/delete", {"actor": "Admin", "user_id": user_id})
        if double_status != 404:
            return False, "doble eliminacion no fue controlada"

        return True, "Eliminacion real, auditoria, sesiones y bloqueos criticos validados."
    finally:
        if httpd:
            httpd.shutdown()
            httpd.server_close()
        server.DB_PATH = original_db_path
        server.BACKUP_DIR = original_backup_dir
        if tmp.exists():
            try:
                tmp.unlink()
            except PermissionError:
                pass
        if backup_tmp.exists():
            shutil.rmtree(backup_tmp, ignore_errors=True)


def main() -> int:
    delete_dynamic_ok, delete_dynamic_detail = dynamic_delete_checks()
    checks: list[tuple[str, bool, str]] = [
        (
            "users_layout",
            contains("frontend/index.html", "users-polish-layout")
            and contains("frontend/index.html", "users-clean-list")
            and contains("frontend/index.html", "selectedUserDetail"),
            "La pantalla separa lista de usuarios y panel de permisos.",
        ),
        (
            "user_search_selection",
            contains("frontend/app.js", "userSearchInput")
            and contains("frontend/app.js", "renderUsersList")
            and contains("frontend/app.js", "selectUser"),
            "Busqueda, seleccion y detalle de usuario disponibles.",
        ),
        (
            "permissions_checkboxes",
            contains("frontend/app.js", 'type="checkbox"')
            and contains("frontend/app.js", "permission-check-cell")
            and not contains("frontend/app.js", 'button\n      type="button"\n      class="permission-cell'),
            "La matriz usa checkboxes y deja atras las celdas Si/No.",
        ),
        (
            "unsaved_permissions",
            contains("frontend/app.js", "permissionChanges")
            and contains("frontend/index.html", "Cambios sin guardar")
            and contains("frontend/app.js", "savePermissionChanges"),
            "Los cambios quedan pendientes hasta Guardar cambios.",
        ),
        (
            "user_delete_ui",
            contains("frontend/app.js", "deleteUser(")
            and contains("frontend/app.js", "Esta accion no se puede deshacer")
            and contains("frontend/index.html", "Buscar usuario"),
            "Eliminar usuario existe en UI con confirmacion.",
        ),
        (
            "user_delete_backend",
            contains("server.py", 'if path == "/api/users/delete"')
            and contains("server.py", "DELETE FROM users WHERE id = ?")
            and contains("server.py", "user.deleted"),
            "Backend ejecuta eliminacion real auditada.",
        ),
        (
            "last_super_admin_protection",
            contains("server.py", "No se puede eliminar el unico Super Admin")
            and contains("server.py", "active_super_admins"),
            "Ultimo Super Admin protegido.",
        ),
        (
            "self_delete_protection",
            contains("server.py", "No podes eliminar tu propio usuario"),
            "Cuenta actual protegida contra eliminacion accidental.",
        ),
        (
            "session_invalidation",
            contains("server.py", "AUTH_SESSIONS.pop(token, None)")
            and contains("server.py", "deleted_user"),
            "Sesiones en memoria del usuario eliminado se invalidan.",
        ),
        (
            "static_sync",
            (ROOT / "frontend/index.html").read_text(encoding="utf-8", errors="replace")
            == (ROOT / "static/index.html").read_text(encoding="utf-8", errors="replace")
            and (ROOT / "frontend/app.js").read_text(encoding="utf-8", errors="replace")
            == (ROOT / "static/app.js").read_text(encoding="utf-8", errors="replace")
            and (ROOT / "frontend/styles.css").read_text(encoding="utf-8", errors="replace")
            == (ROOT / "static/styles.css").read_text(encoding="utf-8", errors="replace"),
            "Frontend y static sincronizados.",
        ),
        (
            "dynamic_delete_security",
            delete_dynamic_ok,
            delete_dynamic_detail,
        ),
    ]
    passed = sum(1 for _name, ok, _detail in checks if ok)
    total = len(checks)
    print("BITORA USERS & PERMISSIONS UI POLISH")
    for name, ok, detail in checks:
        print(f"{name}: {'PASSED' if ok else 'FAILED'} - {detail}")
    print(f"Verifier score: {passed}/{total}")
    print(f"Final state: {'USERS & PERMISSIONS UI READY' if passed >= 9 else 'READY FOR UI FIXES'}")
    return 0 if passed >= 9 else 1


if __name__ == "__main__":
    raise SystemExit(main())
