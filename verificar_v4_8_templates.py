from __future__ import annotations

import csv
import io
import json
import shutil
import tempfile
import threading
import urllib.error
import urllib.request
from pathlib import Path

import server


def req(base, method, path, payload=None, expect=200, parse_json=True):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            body = response.read()
            status = response.status
            content_type = response.headers.get("Content-Type", "")
    except urllib.error.HTTPError as exc:
        body = exc.read()
        status = exc.code
        content_type = exc.headers.get("Content-Type", "")
    if status != expect:
        raise AssertionError(f"{method} {path}: esperado {expect}, recibido {status}: {body!r}")
    if parse_json and "application/json" in content_type:
        return json.loads(body.decode("utf-8")) if body else {}
    return body


def assert_true(value, message):
    if not value:
        raise AssertionError(message)


def main() -> None:
    tmp_path = Path(tempfile.mkdtemp(prefix="qr-v4-8-"))
    httpd = None
    try:
        server.DB_PATH = tmp_path / "v4_8.sqlite3"
        server.BACKUP_DIR = tmp_path / "backups"
        server.AppHandler.log_message = lambda self, format, *args: None
        server.init_db()
        server.seed_if_empty()
        httpd = server.OperationalHTTPServer(("127.0.0.1", 0), server.AppHandler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{httpd.server_address[1]}"

        simple = req(
            base,
            "POST",
            "/api/events",
            {
                "actor": "Admin",
                "name": "Evento simple",
                "status": "published",
                "capacity": 200,
                "activities_enabled": False,
                "capacity_control_enabled": False,
                "waitlist_enabled": False,
            },
            201,
        )
        simple_id = simple["id"]
        simple_event = req(base, "GET", f"/api/event?event_id={simple_id}")
        assert_true(simple_event["activities_enabled"] == 0, "No persiste actividades OFF")
        assert_true(simple_event["capacity_control_enabled"] == 0, "No persiste cupos OFF")
        assert_true(simple_event["waitlist_enabled"] == 0, "No persiste espera OFF")
        assert_true(simple_event["activities"] == [], "Landing no debe exponer actividades con modulo OFF")

        registration = req(
            base,
            "POST",
            "/api/register",
            {
                "actor": "public",
                "event_id": simple_id,
                "first_name": "Evento",
                "last_name": "Simple",
                "email": "simple@example.test",
                "type": "General",
            },
            201,
        )
        portal = req(base, "GET", f"/api/portal?token={registration['token']}")
        assert_true(portal["activities"] == [] and portal["reservations"] == [], "Portal no se adapta a actividades OFF")

        full = req(
            base,
            "POST",
            "/api/events",
            {
                "actor": "Admin",
                "name": "Evento plantilla",
                "status": "published",
                "capacity": 500,
                "activities_enabled": True,
                "capacity_control_enabled": False,
                "waitlist_enabled": False,
            },
            201,
        )
        event_id = full["id"]
        space_id = req(base, "GET", f"/api/spaces?event_id={event_id}")[0]["id"]
        activity = req(
            base,
            "POST",
            "/api/activities",
            {
                "actor": "Admin",
                "event_id": event_id,
                "space_id": space_id,
                "title": "Charla sin cupo",
                "starts_at": "2026-09-01T10:00",
                "ends_at": "2026-09-01T11:00",
                "capacity": 1,
                "reservation_mode": "required",
            },
            201,
        )
        public_event = req(base, "GET", f"/api/event?event_id={event_id}")
        assert_true(public_event["activities"][0]["public_availability"] == "Inscripcion abierta", "Cupos OFF sigue mostrando disponibilidad")

        people = []
        for index in range(2):
            reg = req(
                base,
                "POST",
                "/api/register",
                {
                    "actor": "Recepcion",
                    "event_id": event_id,
                    "first_name": f"Persona {index}",
                    "last_name": "Reserva",
                    "email": f"reserva{index}@example.test",
                    "type": "General",
                },
                201,
            )
            with server.connect() as db:
                acc = db.execute("SELECT id FROM accreditations WHERE token = ?", (reg["token"],)).fetchone()
                people.append(int(acc["id"]))
        for accreditation_id in people:
            reservation = req(
                base,
                "POST",
                "/api/reservations",
                {"actor": "Recepcion", "event_id": event_id, "activity_id": activity["id"], "accreditation_id": accreditation_id},
                201,
            )
            assert_true(reservation["status"] == "confirmed", "Cupos OFF no debe bloquear inscripciones")

        structure = req(base, "GET", f"/api/event-structure.json?event_id={event_id}")
        assert_true(structure["event"]["name"] == "Evento plantilla", "Exportacion de estructura incompleta")
        clone = req(base, "POST", "/api/events/clone", {"actor": "Admin", "source_event_id": event_id, "name": "Evento clonado"}, 201)
        clone_event = req(base, "GET", f"/api/event?event_id={clone['event_id']}")
        assert_true(clone_event["name"] == "Evento clonado", "Clonacion no crea evento nuevo")
        assert_true(len(clone_event["activities"]) == 1, "Clonacion no copio agenda")

        imported = req(base, "POST", "/api/event-structure/import", {"actor": "Admin", "name": "Evento importado", "structure": structure}, 201)
        imported_event = req(base, "GET", f"/api/event?event_id={imported['event_id']}")
        assert_true(imported_event["name"] == "Evento importado", "Importacion de estructura fallo")

        agenda_csv = "Sala,Actividad,Fecha,Hora inicio,Hora fin,Disertante,Descripcion,Capacidad,Tipo actividad\nSala Nueva,Charla importada,2026-09-02,10:00,11:00,Ana,Demo,80,Charla\nSala Nueva,Charla pisada,2026-09-02,10:30,11:30,Ana,Debe fallar,80,Charla\n"
        agenda = req(base, "POST", "/api/agenda/import", {"actor": "Productor", "event_id": imported["event_id"], "csv": agenda_csv})
        assert_true(agenda["created"] == 1 and len(agenda["errors"]) == 1, "Importacion de agenda no valida transicion/superposicion")
        agenda_export = req(base, "GET", f"/api/agenda.csv?event_id={imported['event_id']}", parse_json=False)
        decoded = agenda_export.decode("utf-8-sig")
        assert_true("Charla importada" in decoded, "Exportacion de agenda no incluye actividad importada")
        rows = list(csv.reader(io.StringIO(decoded)))
        assert_true(rows[0][:5] == ["Sala", "Actividad", "Fecha", "Hora inicio", "Hora fin"], "CSV de agenda tiene columnas incorrectas")

        dashboard_html = req(base, "GET", "/index.html", parse_json=False)
        assert_true(b"Archivos del evento y agenda" in dashboard_html, "Panel no incluye seccion de archivos")

        audit = req(base, "GET", f"/api/audit?event_id={imported['event_id']}")
        actions = {row["action"] for row in audit}
        assert_true("event.structure_imported" in actions and "agenda.imported" in actions, "Falta auditoria de importaciones")

        print("OK: V4.8 configuracion flexible, plantillas e importacion de agenda")
    finally:
        if httpd:
            httpd.shutdown()
            httpd.server_close()
        shutil.rmtree(tmp_path, ignore_errors=True)


if __name__ == "__main__":
    main()
