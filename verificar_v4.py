from __future__ import annotations

import importlib
import json
import shutil
import tempfile
import threading
import urllib.error
import urllib.request
from pathlib import Path

import server


ROOT = Path(__file__).resolve().parent


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


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def first(rows, **criteria):
    for row in rows:
        if all(row.get(key) == value for key, value in criteria.items()):
            return row
    raise AssertionError(f"No encontrado: {criteria}")


def check_architecture() -> None:
    assert_true((ROOT / "frontend").is_dir(), "Falta frontend/")
    assert_true((ROOT / "backend").is_dir(), "Falta backend/")
    assert_true((ROOT / "backend" / "app.py").is_file(), "Falta backend/app.py")
    assert_true((ROOT / "server.py").is_file(), "Falta server.py compatible")
    for module in [
        "backend.services.qr",
        "backend.services.access_validation",
        "backend.services.reservations",
        "backend.services.capacity_buckets",
        "backend.services.audit",
        "backend.services.backup",
        "backend.services.notifications",
        "backend.services.payments",
        "backend.repositories.sqlite",
        "backend.repositories.events",
        "backend.repositories.participants",
        "backend.repositories.accreditations",
        "backend.repositories.activities",
        "backend.repositories.reservations",
        "backend.repositories.access",
        "backend.repositories.audit",
        "backend.repositories.capacity_buckets",
        "backend.repositories.communications",
        "backend.repositories.backups",
    ]:
        importlib.import_module(module)


def main() -> None:
    check_architecture()
    tmp_path = Path(tempfile.mkdtemp(prefix="qr-v4-"))
    httpd = None
    try:
        server.DB_PATH = tmp_path / "v4.sqlite3"
        server.BACKUP_DIR = tmp_path / "backups"
        server.AppHandler.log_message = lambda self, format, *args: None
        server.init_db()
        server.seed_if_empty()
        httpd = server.OperationalHTTPServer(("127.0.0.1", 0), server.AppHandler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{httpd.server_address[1]}"

        event = req(base, "POST", "/api/prepare-event", {"actor": "Admin", "name": "V4", "capacity": 100})
        event_id = event["event_id"]
        req(base, "POST", "/api/types", {"actor": "Admin", "event_id": event_id, "name": "General", "capacity": 0, "access_enabled": True})
        req(
            base,
            "POST",
            "/api/spaces",
            {"actor": "Admin", "event_id": event_id, "name": "Sala V4", "capacity": 40, "transition_minutes": 15},
        )
        space_id = first(req(base, "GET", f"/api/spaces?event_id={event_id}"), name="Sala V4")["id"]
        activity_one = req(
            base,
            "POST",
            "/api/activities",
            {
                "actor": "Admin",
                "event_id": event_id,
                "space_id": space_id,
                "title": "Acceso requerido V4",
                "starts_at": "2026-10-01T10:00",
                "ends_at": "2026-10-01T11:00",
                "capacity": 2,
                "reservation_mode": "required",
            },
            201,
        )
        activity_id = activity_one["id"]
        req(
            base,
            "POST",
            "/api/activities",
            {
                "actor": "Admin",
                "event_id": event_id,
                "space_id": space_id,
                "title": "Solapada",
                "starts_at": "2026-10-01T10:30",
                "ends_at": "2026-10-01T11:30",
                "capacity": 1,
                "reservation_mode": "optional",
            },
            409,
        )
        activity_two = req(
            base,
            "POST",
            "/api/activities",
            {
                "actor": "Admin",
                "event_id": event_id,
                "space_id": space_id,
                "title": "Posterior V4",
                "starts_at": "2026-10-01T11:15",
                "ends_at": "2026-10-01T12:00",
                "capacity": 10,
                "reservation_mode": "required",
            },
            201,
        )
        activity_two_id = activity_two["id"]

        bags = req(base, "GET", f"/api/capacity-bags?event_id={event_id}&activity_id={activity_id}")
        online = first(bags, code="online")
        mostrador = first(bags, code="mostrador")
        req(base, "POST", "/api/capacity-bags", {"actor": "Admin", "id": online["id"], "assigned_capacity": 1, "public_visible": True, "public_registration": True, "reception_enabled": True, "status": "active"})
        req(base, "POST", "/api/capacity-bags", {"actor": "Admin", "id": mostrador["id"], "assigned_capacity": 1, "public_visible": False, "public_registration": False, "reception_enabled": True, "status": "active"})
        req(base, "POST", "/api/capacity-bags", {"actor": "Acceso", "id": online["id"], "assigned_capacity": 2, "public_visible": True, "public_registration": True, "reception_enabled": True, "status": "active"}, 403)

        reg_one = req(
            base,
            "POST",
            "/api/register",
            {
                "actor": "public",
                "event_id": event_id,
                "first_name": "Uno",
                "last_name": "V4",
                "email": "uno.v4@example.test",
                "phone": "5491100000001",
                "type": "General",
                "acepta_email": True,
                "acepta_whatsapp": True,
            },
            201,
        )
        token_one = reg_one["token"]
        qr = req(base, "GET", f"/api/qr.svg?token={token_one}", parse_json=False)
        assert_true(b"<svg" in qr, "No genero QR")
        portal_page = req(base, "GET", f"/p/{token_one}", parse_json=False)
        assert_true(b"Credencial digital" in portal_page, "No abre portal participante")
        reserve_one = req(base, "POST", "/api/portal/reserve", {"token": token_one, "activity_id": activity_id, "confirmed": True, "verification_answer": "7"}, 201)
        assert_true(reserve_one["reservation"]["status"] == "confirmed", "Reserva portal no confirmada")

        reg_two = req(base, "POST", "/api/register", {"actor": "public", "event_id": event_id, "first_name": "Dos", "last_name": "V4", "email": "dos.v4@example.test", "type": "General"}, 201)
        reserve_two = req(base, "POST", "/api/portal/reserve", {"token": reg_two["token"], "activity_id": activity_id, "confirmed": True, "verification_answer": "7"}, 201)
        assert_true(reserve_two["reservation"]["status"] == "waitlisted", "No genero lista de espera")
        req(base, "POST", "/api/portal/reservations/status", {"token": token_one, "id": reserve_one["portal"]["reservations"][0]["id"], "status": "cancelled"})
        reservations = req(base, "GET", f"/api/reservations?event_id={event_id}")
        assert_true(first(reservations, token=reg_two["token"])["status"] == "confirmed", "No promovio lista de espera")

        granted = req(base, "POST", "/api/validate", {"operator": "Acceso", "checkpoint": "General", "token": reg_two["token"]})
        repeated = req(base, "POST", "/api/validate", {"operator": "Acceso", "checkpoint": "General", "token": reg_two["token"]}, 200)
        assert_true(granted["result"] == "granted" and repeated["result"] == "rejected", "QR unico no se comporto correctamente")
        reg_three = req(base, "POST", "/api/register", {"actor": "public", "event_id": event_id, "first_name": "Tres", "last_name": "V4", "email": "tres.v4@example.test", "type": "General"}, 201)
        no_reserve = req(base, "POST", "/api/validate", {"operator": "Acceso", "checkpoint": "Actividad", "token": reg_three["token"], "activity_id": activity_two_id})
        assert_true(no_reserve["result"] == "rejected" and "reserva" in no_reserve["reason"].lower(), "No rechazo actividad requerida sin reserva")
        acc_three = first(req(base, "GET", f"/api/accreditations?event_id={event_id}"), token=reg_three["token"])
        req(base, "POST", "/api/accreditations/status", {"actor": "Recepcion", "id": acc_three["id"], "status": "cancelled"})
        cancelled = req(base, "POST", "/api/validate", {"operator": "Acceso", "checkpoint": "General", "token": reg_three["token"]})
        assert_true(cancelled["result"] == "rejected", "No rechazo QR cancelado")

        req(base, "POST", "/api/capacity-bags/move", {"actor": "Admin", "origin_id": mostrador["id"], "target_id": online["id"], "amount": 1, "reason": "V4"})
        public_event = req(base, "GET", f"/api/event?event_id={event_id}")
        assert_true("capacity" not in public_event["activities"][0], "Landing expone capacidad fisica")
        display_modes = ["airport", "now", "room"]
        for mode in display_modes:
            req(base, "POST", "/api/public-display/config", {"actor": "Admin", "event_id": event_id, "mode": mode, "refresh_seconds": 5, "message": "V4"})
            display = req(base, "GET", f"/api/public-display?event_id={event_id}")
            text = json.dumps(display, ensure_ascii=False).lower()
            assert_true(display["config"]["mode"] == mode, f"Pantalla no cambio a {mode}")
            for private in ["dni", "email", "telefono", "phone", "operator", "audit", "checked_in_by"]:
                assert_true(private not in text, f"Pantalla publica expone {private}")

        req(base, "POST", "/api/portal/preferences", {"token": token_one, "acepta_email": True, "acepta_whatsapp": True, "canal_preferido": "whatsapp"})
        sent = req(base, "POST", "/api/communications/send", {"actor": "Admin", "event_id": event_id, "channel": "both", "type": "recordatorio", "subject": "V4", "content": "Demo V4"})
        assert_true(sent["sent"] >= 2, "No registro comunicaciones demo")
        comms = req(base, "GET", f"/api/communications?event_id={event_id}")
        assert_true(comms["logs"], "No hay historial de comunicaciones")

        backup = req(base, "GET", f"/api/backup?event_id={event_id}", parse_json=False)
        assert_true(len(backup) > 0, "Backup vacio")
        backups = list(server.BACKUP_DIR.glob("*.sqlite3"))
        assert_true(backups and server.verify_backup_file(backups[0])["ok"], "Backup no valido")
        export = req(base, "GET", f"/api/export.json?event_id={event_id}")
        assert_true(export["event"]["id"] == event_id, "Export JSON invalido")
        audit_rows = req(base, "GET", f"/api/audit?event_id={event_id}")
        actions = {row["action"] for row in audit_rows}
        assert_true("access.validated" in actions, "Falta auditoria de acceso")
        assert_true("capacity_bag.moved" in actions, "Falta auditoria de movimiento de cupos")
        assert_true("backup.created" in actions, "Falta auditoria de backup")
        status = req(base, "GET", f"/api/system-status?event_id={event_id}")
        assert_true(status["latest_backup"]["integrity_ok"], "Estado no informa backup valido")

        print("OK: V4 arquitectura, seguridad operativa y contrato final")
    finally:
        if httpd:
            httpd.shutdown()
            httpd.server_close()
        shutil.rmtree(tmp_path, ignore_errors=True)


if __name__ == "__main__":
    main()
