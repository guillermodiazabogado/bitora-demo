from __future__ import annotations

import json
import shutil
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import server


class CheckFailed(Exception):
    pass


def request(base: str, method: str, path: str, payload: dict | None = None, expect: int = 200, parse_json: bool = True):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            body = response.read()
            status = response.status
            content_type = response.headers.get("Content-Type", "")
    except urllib.error.HTTPError as exc:
        body = exc.read()
        status = exc.code
        content_type = exc.headers.get("Content-Type", "")
    if status != expect:
        raise CheckFailed(f"{method} {path}: esperado {expect}, recibido {status}: {body.decode('utf-8', 'ignore')}")
    if parse_json and "application/json" in content_type:
        return json.loads(body.decode("utf-8")) if body else None
    return body, content_type


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailed(message)


def first(rows: list[dict], **criteria) -> dict:
    for row in rows:
        if all(row.get(key) == value for key, value in criteria.items()):
            return row
    raise CheckFailed(f"No se encontro fila con {criteria}")


def run_checks() -> None:
    tmp_path = Path(tempfile.mkdtemp(prefix="qr-mvp-check-"))
    try:
        server.DB_PATH = tmp_path / "check.sqlite3"
        server.BACKUP_DIR = tmp_path / "backups"
        server.AppHandler.log_message = lambda self, format, *args: None
        server.init_db()
        server.seed_if_empty()

        httpd = server.OperationalHTTPServer(("localhost", 0), server.AppHandler)
        port = httpd.server_address[1]
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        base = f"http://localhost:{port}"

        try:
            prepared = request(
                base,
                "POST",
                "/api/prepare-event",
                {
                    "actor": "Admin",
                    "name": "Evento Verificacion",
                    "venue": "Centro de pruebas",
                    "starts_at": "2026-08-01T09:00",
                    "ends_at": "2026-08-01T18:00",
                    "capacity": 100,
                    "description": "Chequeo automatico del MVP",
                },
                200,
            )
            event_id = prepared["event_id"]
            assert_true((tmp_path / "backups" / prepared["backup"]).exists(), "El prepare-event no genero backup")

            events = request(base, "GET", "/api/events")
            assert_true(len(events) == 1 and events[0]["name"] == "Evento Verificacion", "La preparacion no dejo un unico evento limpio")
            assert_true(events[0]["accreditation_count"] == 0, "El evento limpio no debe tener acreditados")

            types = request(base, "GET", f"/api/types?event_id={event_id}")
            spaces = request(base, "GET", f"/api/spaces?event_id={event_id}")
            assert_true(len(types) >= 6, "Faltan tipos base de acreditacion")
            assert_true(len(spaces) == 1, "Debe existir un espacio base")
            space_id = spaces[0]["id"]

            public_event = request(base, "GET", f"/api/event?event_id={event_id}")
            assert_true(public_event["name"] == "Evento Verificacion", "Endpoint publico de evento incorrecto")
            public_page, public_type = request(base, "GET", f"/e.html?event_id={event_id}", parse_json=False)
            assert_true(b"publicRegisterForm" in public_page, "Landing publica no contiene formulario")
            print_page, _ = request(base, "GET", f"/print.html?event_id={event_id}", parse_json=False)
            assert_true(b"printSheet" in print_page, "Pagina de impresion no contiene hoja de credenciales")

            request(base, "POST", "/api/types", {"actor": "Admin", "event_id": event_id, "name": "VIP", "capacity": 1, "access_enabled": True})
            vip_one = request(
                base,
                "POST",
                "/api/register",
                {"actor": "Recepcion", "event_id": event_id, "first_name": "Ana", "last_name": "VIP", "email": "ana.vip@example.com", "type": "VIP"},
                201,
            )
            vip_two = request(
                base,
                "POST",
                "/api/register",
                {"actor": "Recepcion", "event_id": event_id, "first_name": "Luis", "last_name": "VIP", "email": "luis.vip@example.com", "type": "VIP"},
                409,
            )
            assert_true("Cupo completo" in vip_two["error"], "El cupo por tipo no bloqueo el segundo VIP")

            general_one = request(
                base,
                "POST",
                "/api/register",
                {"actor": "Recepcion", "event_id": event_id, "first_name": "QR", "last_name": "Uno", "email": "qr1@example.com", "type": "General"},
                201,
            )
            granted = request(base, "POST", "/api/validate", {"operator": "Acceso", "checkpoint": "Acceso principal", "token": general_one["token"]})
            repeated = request(base, "POST", "/api/validate", {"operator": "Acceso", "checkpoint": "Acceso principal", "token": general_one["token"]})
            assert_true(granted["result"] == "granted", "El primer QR no concedio acceso")
            assert_true(repeated["reason"] == "QR ya utilizado", "El segundo uso del QR no fue rechazado")

            cancel_reg = request(
                base,
                "POST",
                "/api/register",
                {"actor": "Recepcion", "event_id": event_id, "first_name": "Cancel", "last_name": "Test", "email": "cancel@example.com", "type": "General"},
                201,
            )
            cancel_acc = first(request(base, "GET", f"/api/accreditations?event_id={event_id}"), token=cancel_reg["token"])
            denied = request(base, "POST", "/api/accreditations/status", {"actor": "Visualizador", "id": cancel_acc["id"], "status": "cancelled"}, 403)
            assert_true("no tiene permiso" in denied["error"], "Visualizador pudo modificar una acreditacion")
            request(base, "POST", "/api/accreditations/status", {"actor": "Recepcion", "id": cancel_acc["id"], "status": "cancelled"})
            cancelled = request(base, "POST", "/api/validate", {"operator": "Acceso", "checkpoint": "Acceso principal", "token": cancel_reg["token"]})
            assert_true(cancelled["reason"] == "Acreditacion cancelada", "Una acreditacion cancelada no fue rechazada")

            activity = request(
                base,
                "POST",
                "/api/activities",
                {
                    "actor": "Admin",
                    "event_id": event_id,
                    "space_id": space_id,
                    "title": "Workshop Cupo 1",
                    "starts_at": "2026-08-01T10:00",
                    "ends_at": "2026-08-01T11:00",
                    "capacity": 1,
                    "reservation_mode": "required",
                    "activity_type": "Workshop",
                },
                201,
            )
            conflict = request(
                base,
                "POST",
                "/api/activities",
                {
                    "actor": "Admin",
                    "event_id": event_id,
                    "space_id": space_id,
                    "title": "Sin transicion",
                    "starts_at": "2026-08-01T11:05",
                    "ends_at": "2026-08-01T12:00",
                    "capacity": 10,
                    "reservation_mode": "free",
                },
                409,
            )
            assert_true("Transicion minima" in conflict["error"], "No se bloqueo conflicto de transicion")

            accs = request(base, "GET", f"/api/accreditations?event_id={event_id}")
            confirmed_acc = first(accs, token=vip_one["token"])
            wait_acc = first(accs, token=cancel_reg["token"])
            request(base, "POST", "/api/accreditations/status", {"actor": "Recepcion", "id": wait_acc["id"], "status": "active"})
            reservation_one = request(base, "POST", "/api/reservations", {"actor": "Recepcion", "event_id": event_id, "activity_id": activity["id"], "accreditation_id": confirmed_acc["id"]}, 201)
            reservation_two = request(base, "POST", "/api/reservations", {"actor": "Recepcion", "event_id": event_id, "activity_id": activity["id"], "accreditation_id": wait_acc["id"]}, 201)
            assert_true(reservation_one["status"] == "confirmed", "La primera reserva no quedo confirmada")
            assert_true(reservation_two["status"] == "waitlisted", "La segunda reserva no entro en espera")

            public_registration = request(
                base,
                "POST",
                "/api/register",
                {
                    "actor": "public",
                    "event_id": event_id,
                    "first_name": "Publica",
                    "last_name": "Landing",
                    "email": "publica@example.com",
                    "phone": "5491112345678",
                    "type": "General",
                    "activity_ids": [activity["id"]],
                },
                201,
            )
            public_portal, _ = request(base, "GET", public_registration["portal_url"], parse_json=False)
            assert_true(b"Credencial digital" in public_portal, "La inscripcion publica no genero portal")
            assert_true(public_registration["reservations"] == [], "La landing publica no debe reservar actividades")
            public_reserve = request(
                base,
                "POST",
                "/api/portal/reserve",
                {"token": public_registration["token"], "activity_id": activity["id"], "confirmed": True, "verification_answer": "7"},
                201,
            )
            assert_true(public_reserve["reservation"]["status"] == "waitlisted", "El portal no genero reserva/lista de espera")

            import_result = request(
                base,
                "POST",
                "/api/import-accreditations",
                {
                    "actor": "Recepcion",
                    "event_id": event_id,
                    "rows": [
                        {"nombre": "Import", "apellido": "Uno", "email": "import1@example.com", "tipo": "General"},
                        {"nombre": "Import", "apellido": "Dos", "email": "import2@example.com", "tipo": "General"},
                        {"nombre": "Import", "apellido": "Uno", "email": "import1@example.com", "tipo": "General"},
                    ],
                },
            )
            assert_true(import_result["created"] == 2 and import_result["existing"] == 1, "Importacion masiva no respeto creados/existentes")

            activity_ok = request(base, "POST", "/api/validate", {"operator": "Acceso", "checkpoint": "Workshop", "activity_id": activity["id"], "token": vip_one["token"]})
            activity_no = request(base, "POST", "/api/validate", {"operator": "Acceso", "checkpoint": "Workshop", "activity_id": activity["id"], "token": cancel_reg["token"]})
            assert_true(activity_ok["result"] == "granted", "La reserva confirmada no paso control de actividad")
            assert_true(activity_no["reason"] == "Sin reserva confirmada", "La lista de espera paso control de actividad")

            reservations = request(base, "GET", f"/api/reservations?event_id={event_id}")
            confirmed_reservation = first(reservations, activity_id=activity["id"], token=vip_one["token"])
            waitlisted_reservation = first(reservations, activity_id=activity["id"], token=cancel_reg["token"])
            changed = request(
                base,
                "POST",
                "/api/reservations/status",
                {"actor": "Recepcion", "id": confirmed_reservation["id"], "status": "cancelled"},
            )
            assert_true(changed["promoted"]["id"] == waitlisted_reservation["id"], "No se promovio automaticamente la primera reserva en espera")
            promoted_rows = request(base, "GET", f"/api/reservations?event_id={event_id}")
            promoted = first(promoted_rows, id=waitlisted_reservation["id"])
            assert_true(promoted["status"] == "confirmed", "La reserva en espera no quedo confirmada")

            backup_body, backup_type = request(base, "GET", "/api/backup", parse_json=False)
            assert_true(backup_type == "application/octet-stream", "Backup no devolvio binario")
            assert_true(len(backup_body) > 0, "Backup vacio")

            export = request(base, "GET", f"/api/export.json?event_id={event_id}", parse_json=False)
            assert_true(export[1].startswith("application/json"), "Export JSON no devolvio JSON")
            exported = json.loads(export[0].decode("utf-8"))
            assert_true(exported["event"]["id"] == event_id, "Export JSON no corresponde al evento")
            reservations_csv, reservations_type = request(base, "GET", f"/api/reservations.csv?event_id={event_id}&activity_id={activity['id']}", parse_json=False)
            assert_true(reservations_type.startswith("text/csv"), "Export CSV de reservas no devolvio CSV")
            assert_true(b"Actividad" in reservations_csv, "Export CSV de reservas incompleto")

            status = request(base, "GET", f"/api/system-status?event_id={event_id}")
            assert_true("recent_access" in status and "active_operators" in status, "Estado operativo incompleto")
            summary = request(base, "GET", f"/api/summary?event_id={event_id}")
            assert_true("by_type" in summary and "by_activity" in summary, "Resumen operativo incompleto")
            readiness = request(base, "GET", f"/api/readiness?event_id={event_id}")
            assert_true("checks" in readiness and readiness["auto_backup_minutes"] >= 0, "Preparacion operativa incompleta")

            qr_body, qr_type = request(base, "GET", f"/api/qr.svg?token={vip_one['token']}", parse_json=False)
            assert_true(qr_type.startswith("image/svg+xml"), "QR no es SVG")
            assert_true(b"<svg" in qr_body, "QR SVG invalido")

        finally:
            httpd.shutdown()
            thread.join(timeout=5)
            httpd.server_close()
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


if __name__ == "__main__":
    start = time.time()
    try:
        run_checks()
    except Exception as exc:
        print(f"FALLO: {exc}")
        raise SystemExit(1)
    print(f"OK: verificacion MVP completa en {time.time() - start:.1f}s")
