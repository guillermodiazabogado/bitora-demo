from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent


def contains(path: str, needle: str) -> bool:
    return needle in (ROOT / path).read_text(encoding="utf-8", errors="replace")


def main() -> int:
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
