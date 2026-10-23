from __future__ import annotations

import json
import shutil
import tempfile
import threading
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
        with urllib.request.urlopen(req, timeout=15) as response:
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
        return json.loads(body.decode("utf-8")) if body else {}
    return body, content_type


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailed(message)


def channel_values(profile: dict) -> dict[str, list[str]]:
    values: dict[str, list[str]] = {}
    for channel in profile.get("channels") or []:
        values.setdefault(channel["type"], []).append(channel["value"])
    return values


def main() -> None:
    tmp_path = Path(tempfile.mkdtemp(prefix="qr-networking-v1-"))
    httpd = None
    try:
        server.DB_PATH = tmp_path / "networking.sqlite3"
        server.BACKUP_DIR = tmp_path / "backups"
        server.AppHandler.log_message = lambda self, format, *args: None
        server.init_db()
        server.seed_if_empty()

        httpd = server.OperationalHTTPServer(("127.0.0.1", 0), server.AppHandler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{httpd.server_address[1]}"

        event = request(base, "POST", "/api/events", {"actor": "Admin", "name": "BITORA Networking V1", "status": "published", "capacity": 300}, 201)
        event_id = int(event["id"])

        ana = request(
            base,
            "POST",
            "/api/register",
            {"actor": "Recepcion", "event_id": event_id, "first_name": "Ana", "last_name": "Comercial", "email": "ana.networking@example.test", "phone": "5491111111111", "type": "General"},
            201,
        )
        bruno = request(
            base,
            "POST",
            "/api/register",
            {"actor": "Recepcion", "event_id": event_id, "first_name": "Bruno", "last_name": "Tecnologia", "email": "bruno.networking@example.test", "phone": "5491122222222", "type": "General"},
            201,
        )

        rows = [
            {
                "source_external_id": "bitora-ana",
                "first_name": "Ana",
                "last_name": "Comercial",
                "email": "ana.networking@example.test",
                "organization": "Expo Connect",
                "title": "Directora Comercial",
                "function": "COMMERCIAL",
                "seniority": "MANAGEMENT",
                "linkedin": "https://linkedin.example/ana",
                "website": "https://ana.example",
            },
            {
                "source_external_id": "bitora-bruno",
                "first_name": "Bruno",
                "last_name": "Tecnologia",
                "email": "bruno.networking@example.test",
                "organization": "Soluciones Live",
                "title": "CTO",
                "function": "TECHNOLOGY",
                "seniority": "EXECUTIVE",
                "linkedin": "https://linkedin.example/bruno",
                "website": "https://bruno.example",
            },
        ]

        preview = request(base, "POST", "/api/networking/import/preview", {"actor": "Admin", "event_id": event_id, "source_system": "BITORA", "rows": rows})
        assert_true(preview["ok"] and preview["valid"] == 2 and preview["existing"] == 0, "preimport no valido las dos filas nuevas")

        imported = request(base, "POST", "/api/networking/import", {"actor": "Admin", "event_id": event_id, "source_system": "BITORA", "rows": rows})
        assert_true(imported["ok"] and imported["created"] == 2 and all(row["state"] == "PASSIVE" for row in imported["rows"]), "import debe crear perfiles pasivos")

        imported_again = request(base, "POST", "/api/networking/import", {"actor": "Admin", "event_id": event_id, "source_system": "BITORA", "rows": rows})
        assert_true(imported_again["ok"] and imported_again["created"] == 0 and imported_again["updated"] == 2, "reimport no debe duplicar perfiles")

        ana_session = request(base, "GET", f"/api/networking/session?token={ana['token']}&event_id={event_id}")
        bruno_session = request(base, "GET", f"/api/networking/session?token={bruno['token']}&event_id={event_id}")
        assert_true(ana_session["participation"]["requires_onboarding"] and bruno_session["participation"]["state"] == "PASSIVE", "import no debe activar networking")

        request(base, "GET", f"/api/networking/qr.svg?profile_id={ana_session['participation']['public_profile_id']}", expect=404, parse_json=False)
        request(base, "GET", f"/api/networking/session?token={ana_session['participation']['public_profile_id']}&event_id={event_id}", expect=404)

        ana_onboard = request(
            base,
            "POST",
            "/api/networking/onboarding",
            {
                "token": ana["token"],
                "event_id": event_id,
                "modes": ["COMMERCIAL", "BUSINESS_ALLIANCES"],
                "direction": "SEEKING",
                "contact_openness": "DIRECT",
                "bio": "Busco partners comerciales para eventos corporativos.",
                "offers": "Operacion comercial",
                "seeks": "Alianzas",
            },
        )
        bruno_onboard = request(
            base,
            "POST",
            "/api/networking/onboarding",
            {
                "token": bruno["token"],
                "event_id": event_id,
                "modes": ["SERVICES_SOLUTIONS"],
                "direction": "OFFERING",
                "contact_openness": "CONNECT_FIRST",
                "bio": "Ofrezco soluciones tecnicas para eventos.",
                "representative_visible": False,
                "channel_visibility": {"email": "HIDDEN"},
            },
        )
        assert_true(ana_onboard["participation"]["state"] == "ACTIVE" and bruno_onboard["participation"]["state"] == "ACTIVE", "onboarding debe activar participantes")
        assert_true(ana_onboard["participation"]["direction"] == "SEEKING", "intencion declarada no persistio")

        qr_body, content_type = request(base, "GET", f"/api/networking/qr.svg?profile_id={ana_onboard['participation']['public_profile_id']}", parse_json=False)
        assert_true(b"<svg" in qr_body and "image/svg+xml" in content_type, "QR publico Networking invalido")
        request(base, "GET", f"/api/networking/session?token={ana_onboard['participation']['public_profile_id']}&event_id={event_id}", expect=404)

        before_contacts = request(base, "GET", f"/api/networking/contacts?token={ana['token']}")
        assert_true(before_contacts["contacts"] == [], "Networking no debe exponer un directorio antes del escaneo")

        scan = request(base, "POST", "/api/networking/scan", {"token": ana["token"], "qr_payload": f"BITORA-NET:{bruno_onboard['participation']['public_profile_id']}"})
        assert_true(scan["ok"] and scan["created"], "scan inicial no creo contacto")
        assert_true(scan["profile"]["name"] == "" and scan["profile"]["role"] == "" and scan["profile"]["photo"] == "", "representante restringido expuso datos personales")
        assert_true(scan["profile"]["organization"] == "Soluciones Live", "oportunidad de organizacion debe sobrevivir representante restringido")
        channels = channel_values(scan["profile"])
        assert_true("email" not in channels, "canal restringido fue expuesto")
        assert_true("website" in channels and "linkedin" not in channels, "jerarquia/privacidad de canales permitidos incorrecta")

        duplicate_scan = request(base, "POST", "/api/networking/scan", {"token": ana["token"], "public_profile_id": bruno_onboard["participation"]["public_profile_id"]})
        assert_true(duplicate_scan["ok"] and not duplicate_scan["created"], "scan repetido no debe duplicar contacto")

        contacts = request(base, "GET", f"/api/networking/contacts?token={ana['token']}")
        assert_true(len(contacts["contacts"]) == 1 and contacts["contacts"][0]["profile"]["public_profile_id"] == bruno_onboard["participation"]["public_profile_id"], "contacto no persiste en Mis contactos")

        with server.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                """
                UPDATE networking_organizations
                SET visibility = 'HIDDEN'
                WHERE id = (SELECT organization_id FROM networking_event_participations WHERE public_profile_id = ?)
                """,
                (bruno_onboard["participation"]["public_profile_id"],),
            )
            db.execute("COMMIT")

        updated_rows = [dict(item) for item in rows]
        updated_rows[0]["title"] = "Head Comercial"
        updated_rows[1]["title"] = "Chief Technology Officer"
        updated_rows[1]["channels"] = [{"type": "email", "value": "bruno.directo@example.test", "visibility": "PUBLIC"}]
        reimport = request(base, "POST", "/api/networking/import", {"actor": "Admin", "event_id": event_id, "source_system": "BITORA", "rows": updated_rows})
        assert_true(reimport["ok"] and reimport["created"] == 0, "reimport de actualizacion no debe crear duplicados")

        ana_after = request(base, "GET", f"/api/networking/session?token={ana['token']}&event_id={event_id}")
        contacts_after = request(base, "GET", f"/api/networking/contacts?token={ana['token']}")
        assert_true(ana_after["participation"]["direction"] == "SEEKING" and ana_after["participation"]["contact_openness"] == "DIRECT", "reimport piso intencion o privacidad")
        assert_true(len(contacts_after["contacts"]) == 1, "reimport elimino contactos networking")
        assert_true("email" not in channel_values(contacts_after["contacts"][0]["profile"]), "reimport expuso canal restringido")
        assert_true(contacts_after["contacts"][0]["profile"]["organization"] == "", "organizacion oculta fue expuesta")

        missing_event = request(base, "POST", "/api/networking/external-register", {"first_name": "Sin", "last_name": "Evento", "email": "sin.evento@example.test"}, 400)
        assert_true("evento" in missing_event["error"].lower(), "registro externo sin evento debe fallar")
        external = request(
            base,
            "POST",
            "/api/networking/external-register",
            {
                "event_id": event_id,
                "first_name": "Carla",
                "last_name": "Visitante",
                "email": "carla.visitante@example.test",
                "organization": "Visitantes SA",
                "title": "Founder",
                "bio": "Visitante espontanea interesada en alianzas.",
                "linkedin": "https://linkedin.example/carla",
            },
            201,
        )
        assert_true(external["ok"] and external["owner_token"] and external["state"] == "PASSIVE", "registro externo debe crear perfil pasivo con token privado")
        external_session = request(base, "GET", f"/api/networking/session?token={external['owner_token']}&event_id={event_id}")
        assert_true(external_session["participation"]["requires_onboarding"], "externo no usa la misma arquitectura pasiva/onboarding")
        assert_true(external_session["participation"]["bio"] == "Visitante espontanea interesada en alianzas.", "bio externo no se conserva en el modelo canonico")

        with server.connect() as db:
            counts = {
                "people": db.execute("SELECT COUNT(*) AS c FROM people WHERE email IN ('ana.networking@example.test', 'bruno.networking@example.test', 'carla.visitante@example.test')").fetchone()["c"],
                "participations": db.execute("SELECT COUNT(*) AS c FROM networking_event_participations WHERE event_id = ?", (event_id,)).fetchone()["c"],
                "contacts": db.execute("SELECT COUNT(*) AS c FROM networking_contacts WHERE event_id = ?", (event_id,)).fetchone()["c"],
                "organizations": db.execute("SELECT COUNT(*) AS c FROM networking_organizations").fetchone()["c"],
                "classifications": db.execute("SELECT COUNT(*) AS c FROM networking_classifications").fetchone()["c"],
            }
        assert_true(counts["people"] == 3 and counts["participations"] == 3 and counts["contacts"] == 1, "separacion Person/EventParticipation/Contact incorrecta")
        assert_true(counts["organizations"] >= 3 and counts["classifications"] >= 4, "fundacion semantica u organizacional incompleta")

        networking_html, _ = request(base, "GET", "/networking.html", parse_json=False)
        register_html, _ = request(base, "GET", f"/networking-register.html?event_id={event_id}", parse_json=False)
        register_without_event, _ = request(base, "GET", "/networking-register.html", parse_json=False)
        assert_true(b"Mis contactos" in networking_html and b"Desarrollado por" in register_html, "UI publica Networking incompleta")
        assert_true(b'eventId = Number(params.get("event_id") || 0)' in register_without_event and b"Falta el identificador del evento" in register_without_event, "formulario externo no debe asumir evento 1")

        print("OK: BITORA Networking V1 import/onboarding/QR/scan/contact/privacy/external")
    finally:
        if httpd:
            httpd.shutdown()
            httpd.server_close()
        shutil.rmtree(tmp_path, ignore_errors=True)


if __name__ == "__main__":
    main()
