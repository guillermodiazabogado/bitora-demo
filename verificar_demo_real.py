from __future__ import annotations

import json
import shutil
import tempfile
import threading
import urllib.error
import urllib.request
from pathlib import Path

import server
from backend.services.demo_real import DemoRealService


def req(base, method, path, payload=None, expect=200, parse_json=True):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
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


def first(rows, **criteria):
    for row in rows:
        if all(row.get(key) == value for key, value in criteria.items()):
            return row
    raise AssertionError(f"No encontrado: {criteria}")


def main() -> None:
    tmp_path = Path(tempfile.mkdtemp(prefix="qr-demo-real-"))
    httpd = None
    try:
        server.DB_PATH = tmp_path / "demo.sqlite3"
        server.BACKUP_DIR = tmp_path / "backups"
        server.AppHandler.log_message = lambda self, format, *args: None
        server.init_db()
        server.seed_if_empty()
        httpd = server.OperationalHTTPServer(("127.0.0.1", 0), server.AppHandler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{httpd.server_address[1]}"

        result = req(base, "POST", "/api/demo-real", {"actor": "Admin", "confirm": "DEMO"}, 201)
        event_id = result["event_id"]
        assert_true(result["event_name"] == DemoRealService.EVENT_NAME, "Evento demo incorrecto")
        assert_true(result["participants"] == 500, "No creo 500 participantes")
        assert_true(result["spaces"] == 5, "No creo 5 espacios")
        assert_true(result["activities"] == 20, "No creo 20 actividades")

        events = req(base, "GET", "/api/events")
        assert_true(events[0]["name"] == DemoRealService.EVENT_NAME, "Evento demo no listado")
        types = req(base, "GET", f"/api/types?event_id={event_id}")
        assert_true({row["name"] for row in types} >= {"General", "VIP", "Prensa", "Staff", "Sponsor", "Disertante"}, "Tipos incompletos")
        spaces = req(base, "GET", f"/api/spaces?event_id={event_id}")
        assert_true(len(spaces) == 5, "Espacios incompletos")
        activities = req(base, "GET", f"/api/activities?event_id={event_id}")
        assert_true(len(activities) == 20, "Actividades incompletas")
        assert_true(any(row["status"] == "cancelled" for row in activities), "No hay actividad cancelada")
        assert_true(any("demorada" in row["title"].lower() for row in activities), "No hay actividad demorada")

        accreditations = req(base, "GET", f"/api/accreditations?event_id={event_id}&limit=600")
        assert_true(len(accreditations) == 500, "Acreditaciones incompletas")
        assert_true(any(row["checked_in_at"] for row in accreditations), "No hay acreditados")
        assert_true(any(row["status"] == "cancelled" for row in accreditations), "No hay cancelados")
        tokens = {row["token"] for row in accreditations}
        assert_true(len(tokens) == 500, "Tokens duplicados")

        reservations = req(base, "GET", f"/api/reservations?event_id={event_id}")
        assert_true(any(row["status"] == "confirmed" for row in reservations), "No hay reservas confirmadas")
        assert_true(any(row["status"] == "waitlisted" for row in reservations), "No hay lista de espera")
        bags = req(base, "GET", f"/api/capacity-bags?event_id={event_id}")
        assert_true(len(bags) >= 20 * 7, "Bolsas incompletas")
        assert_true(any(row["public_visible"] for row in bags), "Sin bolsas publicas")

        demo = req(base, "GET", f"/api/demo-real?event_id={event_id}")
        assert_true(demo["active"] and len(demo["examples"]) == 5, "Ejemplos demo no disponibles")
        token = demo["examples"][0]["token"]
        portal = req(base, "GET", f"/api/portal?token={token}")
        assert_true(portal["event_name"] == DemoRealService.EVENT_NAME, "Portal demo incorrecto")
        qr = req(base, "GET", f"/api/qr.svg?token={token}", parse_json=False)
        assert_true(b"<svg" in qr, "QR demo invalido")

        fresh = next(row for row in accreditations if row["status"] != "cancelled" and not row["checked_in_at"])
        first_scan = req(base, "POST", "/api/validate", {"operator": "Acceso", "checkpoint": "Demo", "token": fresh["token"]})
        second_scan = req(base, "POST", "/api/validate", {"operator": "Acceso", "checkpoint": "Demo", "token": fresh["token"]})
        assert_true(first_scan["result"] == "granted", "QR demo no valido")
        assert_true(second_scan["result"] == "rejected", "QR repetido no rechazado")

        required_activity = next(row for row in activities if row["reservation_mode"] == "required" and row["status"] != "cancelled")
        no_reserve = next(row for row in accreditations if row["status"] != "cancelled" and row["token"] != fresh["token"])
        access_activity = req(
            base,
            "POST",
            "/api/validate",
            {"operator": "Acceso", "checkpoint": "Actividad demo", "token": no_reserve["token"], "activity_id": required_activity["id"]},
        )
        assert_true(access_activity["result"] in {"granted", "rejected"}, "Acceso actividad sin respuesta")

        public_event = req(base, "GET", f"/api/event?event_id={event_id}")
        assert_true("capacity" not in public_event["activities"][0], "Landing expone capacidad fisica")
        display = req(base, "GET", f"/api/public-display?event_id={event_id}")
        display_text = json.dumps(display, ensure_ascii=False).lower()
        assert_true(display["activities"], "Pantalla publica sin actividades")
        for private in ['"dni"', '"email"', '"telefono"', '"phone"', '"operator"', '"audit"', '"checked_in_by"']:
            assert_true(private not in display_text, f"Pantalla publica expone {private}")

        comms = req(base, "GET", f"/api/communications?event_id={event_id}")
        assert_true(comms["stats"]["participants"] >= 480, "Metricas comunicaciones incorrectas")
        assert_true(comms["logs"], "Sin comunicaciones demo")
        backups = list(server.BACKUP_DIR.glob("*.sqlite3"))
        assert_true(len(backups) >= 2, "No genero backups antes/despues")
        assert_true(all(server.verify_backup_file(path)["ok"] for path in backups[:2]), "Backup demo invalido")
        audit_rows = req(base, "GET", f"/api/audit?event_id={event_id}")
        actions = {row["action"] for row in audit_rows}
        assert_true({"demo.created", "demo.backup_after"} <= actions, "Auditoria demo incompleta")

        print("OK: demo real completa")
    finally:
        if httpd:
            httpd.shutdown()
            httpd.server_close()
        shutil.rmtree(tmp_path, ignore_errors=True)


if __name__ == "__main__":
    main()
