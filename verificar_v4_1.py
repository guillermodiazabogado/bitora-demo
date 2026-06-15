from __future__ import annotations

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


def main() -> None:
    tmp_path = Path(tempfile.mkdtemp(prefix="qr-v4-1-"))
    httpd = None
    try:
        server.DB_PATH = tmp_path / "v4_1.sqlite3"
        server.BACKUP_DIR = tmp_path / "backups"
        server.AppHandler.log_message = lambda self, format, *args: None
        server.init_db()
        server.seed_if_empty()
        httpd = server.OperationalHTTPServer(("127.0.0.1", 0), server.AppHandler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{httpd.server_address[1]}"

        event = req(base, "POST", "/api/prepare-event", {"actor": "Admin", "name": "V4.1", "capacity": 100})
        event_id = event["event_id"]
        spaces = req(base, "GET", f"/api/spaces?event_id={event_id}")
        activity = req(
            base,
            "POST",
            "/api/activities",
            {
                "actor": "Admin",
                "event_id": event_id,
                "space_id": spaces[0]["id"],
                "title": "Portal Experience",
                "starts_at": "2027-10-01T10:00",
                "ends_at": "2027-10-01T11:00",
                "capacity": 1,
                "reservation_mode": "optional",
            },
            201,
        )
        activity_id = activity["id"]
        activity_two = req(
            base,
            "POST",
            "/api/activities",
            {
                "actor": "Admin",
                "event_id": event_id,
                "space_id": spaces[0]["id"],
                "title": "Portal Cooldown",
                "starts_at": "2027-10-01T11:30",
                "ends_at": "2027-10-01T12:00",
                "capacity": 10,
                "reservation_mode": "optional",
            },
            201,
        )
        block_activities = []
        for index in range(6):
            created = req(
                base,
                "POST",
                "/api/activities",
                {
                    "actor": "Admin",
                    "event_id": event_id,
                    "space_id": spaces[0]["id"],
                    "title": f"Bloque reserva {index + 1}",
                    "starts_at": f"2027-10-02T1{index}:00",
                    "ends_at": f"2027-10-02T1{index}:30",
                    "capacity": 10,
                    "reservation_mode": "optional",
                },
                201,
            )
            block_activities.append(created["id"])
        req(base, "POST", "/api/public-display/item", {"actor": "Admin", "event_id": event_id, "activity_id": activity_id})

        landing = req(base, "GET", f"/e.html?event_id={event_id}", parse_json=False)
        assert b"publicActivityChoices" not in landing
        assert b"acepta_whatsapp" not in landing
        assert b"acepta_email" not in landing

        registration = req(
            base,
            "POST",
            "/api/register",
            {
                "actor": "public",
                "event_id": event_id,
                "first_name": "Participante",
                "last_name": "V41",
                "email": "v41@example.test",
                "phone": "5491100000000",
                "company": "Demo",
                "position": "Operacion",
                "type": "General",
                "acepta_email": True,
                "acepta_whatsapp": True,
                "activity_ids": [activity_id],
            },
            201,
        )
        token = registration["token"]
        assert registration["reservations"] == []

        portal_page = req(base, "GET", f"/p/{token}", parse_json=False)
        assert b"Proxima actividad" in portal_page
        assert b"Mi perfil" in portal_page
        assert b"Descargar imagen" in portal_page
        assert b"Descargar PDF" in portal_page
        assert b"Imprimir agenda" in portal_page

        portal = req(base, "GET", f"/api/portal?token={token}")
        assert portal["qr_payload"] == token
        assert portal["next_activity"] is None
        assert portal["reservations"] == []
        assert portal["certificate"]["elegible_certificado"] == 0
        assert portal["activities"][0]["public_availability"]
        assert portal["reservation_config"]["reserva_cooldown_segundos"] == 10

        qr = req(base, "GET", f"/api/qr.svg?token={token}", parse_json=False)
        assert b"<svg" in qr and b"<rect" in qr
        credential = req(base, "GET", f"/api/credential.svg?token={token}", parse_json=False)
        assert b"<svg" in credential and b"Participante V41" in credential and b"Demo" in credential
        credential_png = req(base, "GET", f"/api/credential.png?token={token}", parse_json=False)
        assert credential_png.startswith(b"\x89PNG")
        credential_pdf = req(base, "GET", f"/api/credential.pdf?token={token}", parse_json=False)
        assert credential_pdf.startswith(b"%PDF")

        req(base, "POST", "/api/portal/reserve", {"token": token, "activity_id": activity_id}, 400)
        req(base, "POST", "/api/portal/reserve", {"token": token, "activity_id": activity_id, "confirmed": True, "verification_answer": "8"}, 400)
        reserve = req(base, "POST", "/api/portal/reserve", {"token": token, "activity_id": activity_id, "confirmed": True, "verification_answer": "7"}, 201)
        assert reserve["reservation"]["status"] == "confirmed"
        req(base, "POST", "/api/portal/reserve", {"token": token, "activity_id": activity_id, "confirmed": True, "verification_answer": "7"}, 409)
        req(base, "POST", "/api/portal/reserve", {"token": token, "activity_id": activity_two["id"], "confirmed": True, "verification_answer": "7"}, 429)

        profile = req(
            base,
            "POST",
            "/api/portal/profile",
            {
                "token": token,
                "first_name": "Participante",
                "last_name": "Editado",
                "email": "v41@example.test",
                "phone": "5491111111111",
                "company": "Empresa V41",
                "position": "Coordinacion",
            },
        )
        assert profile["portal"]["last_name"] == "Editado"
        assert profile["portal"]["position"] == "Coordinacion"

        prefs = req(
            base,
            "POST",
            "/api/portal/preferences",
            {"token": token, "email": "v41@example.test", "phone": "5491111111111", "acepta_email": True, "acepta_whatsapp": False, "canal_preferido": "email"},
        )
        assert prefs["portal"]["communication_preference"]["acepta_whatsapp"] == 0

        sent = req(base, "POST", "/api/communications/send", {"actor": "Admin", "event_id": event_id, "channel": "email", "type": "aviso", "subject": "Aviso", "content": "Mensaje V4.1"})
        assert sent["sent"] == 1
        portal_after_comms = req(base, "GET", f"/api/portal?token={token}")
        assert portal_after_comms["communications"]
        assert portal_after_comms["announcements"] is not None

        wait_registration = req(
            base,
            "POST",
            "/api/register",
            {
                "actor": "public",
                "event_id": event_id,
                "first_name": "Espera",
                "last_name": "V41",
                "email": "espera-v41@example.test",
                "type": "General",
            },
            201,
        )
        wait = req(base, "POST", "/api/portal/reserve", {"token": wait_registration["token"], "activity_id": activity_id, "confirmed": True, "verification_answer": "7"}, 201)
        assert wait["reservation"]["status"] == "waitlisted"

        block_registration = req(
            base,
            "POST",
            "/api/register",
            {
                "actor": "public",
                "event_id": event_id,
                "first_name": "Bloque",
                "last_name": "V41",
                "email": "bloque-v41@example.test",
                "type": "General",
            },
            201,
        )
        block_acc = next(row for row in req(base, "GET", f"/api/accreditations?event_id={event_id}") if row["token"] == block_registration["token"])
        for activity_for_block in block_activities[:5]:
            req(base, "POST", "/api/reservations", {"actor": "Admin", "event_id": event_id, "activity_id": activity_for_block, "accreditation_id": block_acc["id"]}, 201)
        blocked = req(base, "POST", "/api/portal/reserve", {"token": block_registration["token"], "activity_id": block_activities[5], "confirmed": True, "verification_answer": "7"}, 429)
        assert blocked["block"] == "five_reservations"
        assert blocked["wait_seconds"] >= 250

        metrics = req(base, "GET", f"/api/participant-metrics?event_id={event_id}")
        assert metrics["registered"] == 3
        assert metrics["with_reservations"] == 3
        assert metrics["with_agenda"] == 2
        assert metrics["consent_email"] == 1

        audit_rows = req(base, "GET", f"/api/audit?event_id={event_id}")
        actions = {row["action"] for row in audit_rows}
        assert "portal.accessed" in actions
        assert "portal.qr_viewed" in actions
        assert "portal.credential_downloaded" in actions
        assert "portal.profile_updated" in actions
        assert "portal.preferences_updated" in actions
        assert "portal.reservation_created" in actions
        assert "portal.reservation_waitlisted" in actions
        assert "portal.reservation_cooldown_blocked" in actions
        assert "portal.reservation_verification_failed" in actions
        assert "accreditation.created" in actions
        assert "portal.generated" in actions

        print("OK: V4.1 flujo simple y reserva controlada")
    finally:
        if httpd:
            httpd.shutdown()
            httpd.server_close()
        shutil.rmtree(tmp_path, ignore_errors=True)


if __name__ == "__main__":
    main()
