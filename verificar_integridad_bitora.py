from __future__ import annotations

import json
import shutil
import tempfile
import threading
import urllib.error
import urllib.request
from pathlib import Path

import server


def req(base, method, path, payload=None, expect=200):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    request = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read()
            status = response.status
            content_type = response.headers.get("Content-Type", "")
    except urllib.error.HTTPError as exc:
        body = exc.read()
        status = exc.code
        content_type = exc.headers.get("Content-Type", "")
    if status != expect:
        raise AssertionError(f"{method} {path}: esperado {expect}, recibido {status}: {body!r}")
    return json.loads(body.decode("utf-8")) if "application/json" in content_type and body else body


def assert_true(value, message):
    if not value:
        raise AssertionError(message)


def acc_id_for(token):
    with server.connect() as db:
        return int(db.execute("SELECT id FROM accreditations WHERE token = ?", (token,)).fetchone()["id"])


def reservation_id_for(activity_id, accreditation_id):
    with server.connect() as db:
        row = db.execute(
            "SELECT id FROM reservations WHERE activity_id = ? AND accreditation_id = ?",
            (activity_id, accreditation_id),
        ).fetchone()
        return int(row["id"])


def audit_actions():
    with server.connect() as db:
        return {
            row["action"]
            for row in db.execute("SELECT action FROM audit_logs").fetchall()
        }


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="qr-integridad-"))
    httpd = None
    try:
        server.DB_PATH = tmp / "integridad.sqlite3"
        server.BACKUP_DIR = tmp / "backups"
        server.AppHandler.log_message = lambda self, format, *args: None
        server.init_db()
        server.seed_if_empty()
        httpd = server.OperationalHTTPServer(("127.0.0.1", 0), server.AppHandler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{httpd.server_address[1]}"

        simple_id = req(base, "POST", "/api/events", {"actor": "Admin", "name": "Simple", "status": "published", "activities_enabled": False, "waitlist_enabled": False}, 201)["id"]
        simple_reg = req(base, "POST", "/api/register", {"actor": "public", "event_id": simple_id, "first_name": "Simple", "last_name": "Uno", "email": "simple.qa@example.test", "type": "General"}, 201)
        assert_true(req(base, "GET", f"/api/event?event_id={simple_id}")["activities"] == [], "Evento simple expone actividades")
        assert_true(req(base, "POST", "/api/validate", {"operator": "Acceso", "checkpoint": "General", "token": simple_reg["token"]})["result"] == "granted", "Acceso general simple fallo")

        event_id = req(base, "POST", "/api/events", {"actor": "Admin", "name": "Integral", "status": "published", "capacity": 200, "waitlist_enabled": True, "activity_access_open_minutes_before": 10}, 201)["id"]
        space_id = req(base, "GET", f"/api/spaces?event_id={event_id}")[0]["id"]
        activity_id = req(base, "POST", "/api/activities", {"actor": "Admin", "event_id": event_id, "space_id": space_id, "title": "Actividad Integral", "starts_at": "2026-12-10T10:00", "ends_at": "2026-12-10T11:00", "capacity": 1, "reservation_mode": "required"}, 201)["id"]
        bags = req(base, "GET", f"/api/capacity-bags?event_id={event_id}&activity_id={activity_id}")
        online = next(row for row in bags if row["code"] == "online")
        req(base, "POST", "/api/capacity-bags", {"actor": "Admin", "id": online["id"], "assigned_capacity": 1, "public_visible": True, "public_registration": True, "reception_enabled": True, "status": "active"})

        reg1 = req(base, "POST", "/api/register", {"actor": "public", "event_id": event_id, "first_name": "Uno", "last_name": "QA", "email": "uno.qa@example.test", "phone": "5492991111111", "type": "General", "acepta_email": True, "acepta_whatsapp": True}, 201)
        reg2 = req(base, "POST", "/api/register", {"actor": "public", "event_id": event_id, "first_name": "Dos", "last_name": "QA", "email": "dos.qa@example.test", "phone": "5492992222222", "type": "General", "acepta_email": True, "acepta_whatsapp": True}, 201)
        acc1_id = acc_id_for(reg1["token"])
        acc2_id = acc_id_for(reg2["token"])
        r1 = req(base, "POST", "/api/reservations", {"actor": "Recepcion", "event_id": event_id, "activity_id": activity_id, "accreditation_id": acc1_id}, 201)
        r2 = req(base, "POST", "/api/reservations", {"actor": "Recepcion", "event_id": event_id, "activity_id": activity_id, "accreditation_id": acc2_id}, 201)
        r1_id = reservation_id_for(activity_id, acc1_id)
        r2_id = reservation_id_for(activity_id, acc2_id)
        assert_true(r1["status"] == "confirmed" and r2["status"] == "waitlisted", "Lista de espera integral fallo")
        early = req(base, "POST", "/api/validate", {"operator": "Acceso", "checkpoint": "Actividad", "token": reg1["token"], "activity_id": activity_id})
        assert_true(early["result"] == "rejected" and "habilitado" in early["reason"], "QR anticipado no fue rechazado correctamente")
        general = req(base, "POST", "/api/validate", {"operator": "Acceso", "checkpoint": "General", "token": reg1["token"]})
        assert_true(general["result"] == "granted", "QR anticipado consumio acceso general")
        repeat = req(base, "POST", "/api/validate", {"operator": "Acceso", "checkpoint": "General", "token": reg1["token"]})
        assert_true(repeat["result"] == "rejected", "QR duplicado no rechazo")

        changed = req(base, "POST", "/api/reservations/status", {"actor": "Recepcion", "id": r1_id, "status": "cancelled"})
        assert_true(changed["promoted"]["id"] == r2_id, "Promocion automatica no ocurrio")
        public_event = req(base, "GET", f"/api/event?event_id={event_id}")
        assert_true("capacity" not in public_event["activities"][0], "Landing expone capacidad fisica")
        display = req(base, "GET", f"/api/public-display?event_id={event_id}")
        control = req(base, "GET", f"/api/reports/visual-summary?event_id={event_id}")
        display_ok = isinstance(display, dict) and any(key in display for key in ("items", "activities", "agenda", "event"))
        assert_true(display_ok and "event_health" in control and "operational_alerts" in control, "Pantalla/sala de control incompletas")

        comms = req(base, "POST", "/api/communications/send", {"actor": "Admin", "event_id": event_id, "audience": "all", "channel": "both", "subject": "QR", "content": "Portal {{portal_participante}}", "confirm": True})
        assert_true(comms["queued"] >= 2, "Comunicaciones no encolan")
        backup = req(base, "GET", f"/api/backup?event_id={event_id}")
        assert_true(str(backup).startswith("b'") or backup, "Backup no respondio")
        structure = req(base, "GET", f"/api/event-structure.json?event_id={event_id}")
        clone = req(base, "POST", "/api/events/clone", {"actor": "Admin", "source_event_id": event_id, "name": "Integral clon"}, 201)
        assert_true(clone["event_id"] != event_id and "accreditations" not in structure, "Clonacion/export estructura insegura")
        agenda = req(base, "POST", "/api/agenda/import", {"actor": "Productor", "event_id": event_id, "csv": "Sala,Actividad,Fecha,Hora inicio,Hora fin\nSala QA,Nueva QA,2026-12-10,12:00,13:00"})
        assert_true(agenda["created"] == 1, "Importacion agenda fallo")
        denied = req(base, "POST", "/api/capacity-bags", {"actor": "Acceso", "id": online["id"], "assigned_capacity": 2}, 403)
        assert_true("error" in denied, "Rol Acceso pudo modificar cupos")
        audit = req(base, "GET", f"/api/audit?event_id={event_id}")
        assert_true(audit, "Endpoint de auditoria no respondio registros del evento")
        actions = audit_actions()
        assert_true({"communications.queued", "event.cloned", "agenda.imported"}.issubset(actions), "Auditoria integral incompleta")
        print("OK: integridad BITORA punta a punta")
    finally:
        if httpd:
            httpd.shutdown()
            httpd.server_close()
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
