import json
import os
import tempfile

os.environ.setdefault("QR_REQUIRE_LOGIN", "0")

import server


def main():
    fd, path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    original_path = server.DB_PATH
    server.DB_PATH = server.Path(path)
    try:
        server.init_db()
        with server.connect() as db:
            admin = server.user_by_name(db, "Admin")
            productor = server.user_by_name(db, "Productor")
            assert admin, "Debe existir usuario Admin"
            assert productor, "Debe existir usuario Productor"

            cur = db.execute(
                """
                INSERT INTO events (name, description, venue, starts_at, ends_at, status, project_type, capacity, created_at)
                VALUES (?, '', 'Domuyo', '', '', 'published', 'conference', 100, ?)
                """,
                ("IA Week", server.now_iso()),
            )
            event_id = int(cur.lastrowid)
            server.ensure_default_types(db, event_id)
            server.ensure_default_spaces(db, event_id)
            server.ensure_super_admin_event_access(db, event_id)

            admin_rows = db.execute(
                """
                SELECT COUNT(*) AS c
                FROM user_event_roles
                WHERE event_id = ? AND user_id = ? AND role = 'Super Admin' AND active = 1
                """,
                (event_id, admin["id"]),
            ).fetchone()["c"]
            assert int(admin_rows) == 1, "Super Admin debe quedar asignado al evento"

            server.assign_user_to_event(db, int(productor["id"]), event_id, "Productor")
            visualizador = server.user_by_name(db, "Visualizador")
            assert visualizador, "Debe existir usuario Visualizador"
            server.assign_user_to_event(db, int(visualizador["id"]), event_id, "Coordinador")

            assert "Comunicaciones" in server.PERMISSION_MATRIX, "Debe existir rol Comunicaciones"
            assert "Soporte tecnico" in server.PERMISSION_MATRIX, "Debe existir rol Soporte tecnico"
            assert "users" in server.PERMISSION_MATRIX["Productor"]["modules"], "Productor debe poder administrar equipo del evento"
            assert "diagnostics" in server.PERMISSION_MATRIX["Soporte tecnico"]["modules"], "Soporte tecnico debe ver diagnostico"
            assert "configure" not in server.PERMISSION_MATRIX["Operador de acceso"]["modules"], "Acceso no debe configurar eventos"
            assert "access" in server.PERMISSION_MATRIX["Operador de acceso"]["modules"], "Acceso debe ver modulo QR"
            assert server.session_effective_role(db, {"id": int(visualizador["id"]), "role": "Visualizador"}, event_id) == "Coordinador", "El rol efectivo del evento debe pisar el rol base"
            assert server.can_actor(db, "Visualizador", {"Coordinador"}), "Un rol asignado al evento debe habilitar permisos operativos"

            team = db.execute(
                """
                SELECT u.name, uer.role
                FROM user_event_roles uer
                JOIN users u ON u.id = uer.user_id
                WHERE uer.event_id = ? AND uer.active = 1
                ORDER BY u.name
                """,
                (event_id,),
            ).fetchall()
            payload = [dict(row) for row in team]
            assert any(row["name"] == "Productor" and row["role"] == "Productor" for row in payload), "Productor asignado"
            assert any(row["name"] == "Visualizador" and row["role"] == "Coordinador" for row in payload), "Visualizador asignado como Coordinador"

            where, params = server.event_access_clause({"id": int(productor["id"]), "name": "Productor", "role": "Productor"}, "e")
            visible = db.execute(f"SELECT COUNT(*) AS c FROM events e WHERE {where}", params).fetchone()["c"]
            assert int(visible) >= 1, "Productor debe ver eventos asignados"
            assert server.session_can_access_event(db, {"id": int(productor["id"]), "role": "Productor"}, event_id), "Productor debe poder operar evento asignado"

            cur_other = db.execute(
                """
                INSERT INTO events (name, description, venue, starts_at, ends_at, status, project_type, capacity, created_at)
                VALUES (?, '', 'Otra sede', '', '', 'published', 'conference', 100, ?)
                """,
                ("Evento no asignado", server.now_iso()),
            )
            other_event_id = int(cur_other.lastrowid)
            assert not server.session_can_access_event(db, {"id": int(productor["id"]), "role": "Productor"}, other_event_id), "Productor no debe operar evento no asignado"

        print(json.dumps({"ok": True, "event_id": event_id, "team_members": len(payload)}, ensure_ascii=False))
    finally:
        server.DB_PATH = original_path
        try:
            os.remove(path)
        except OSError:
            pass


if __name__ == "__main__":
    main()
