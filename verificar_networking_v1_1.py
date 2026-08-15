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


def assert_true(value, message: str) -> None:
    if not value:
        raise CheckFailed(message)


def channel_types(channels: list[dict]) -> set[str]:
    return {channel.get("type", "") for channel in channels}


def main() -> None:
    tmp_path = Path(tempfile.mkdtemp(prefix="qr-networking-v1-1-"))
    httpd = None
    try:
        server.DB_PATH = tmp_path / "networking_v1_1.sqlite3"
        server.BACKUP_DIR = tmp_path / "backups"
        server.AppHandler.log_message = lambda self, format, *args: None
        server.init_db()
        server.seed_if_empty()

        httpd = server.OperationalHTTPServer(("127.0.0.1", 0), server.AppHandler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{httpd.server_address[1]}"

        org_event = request(base, "POST", "/api/events", {"actor": "Admin", "name": "Evento estilo empresa", "status": "published"}, 201)
        person_event = request(base, "POST", "/api/events", {"actor": "Admin", "name": "Comunidad profesional", "status": "published"}, 201)
        default_event = request(base, "POST", "/api/events", {"actor": "Admin", "name": "Evento predefault", "status": "published"}, 201)
        org_event_id = int(org_event["id"])
        person_event_id = int(person_event["id"])
        default_event_id = int(default_event["id"])

        cfg_org = request(base, "POST", "/api/networking/config", {"actor": "Admin", "event_id": org_event_id, "networking_profile_mode": "ORGANIZATION_FIRST"})
        cfg_person = request(base, "POST", "/api/networking/config", {"actor": "Admin", "event_id": person_event_id, "networking_profile_mode": "PERSON_FIRST"})
        cfg_default = request(base, "GET", f"/api/networking/config?actor=Admin&event_id={default_event_id}")
        assert_true(cfg_org["networking_profile_mode"] == "ORGANIZATION_FIRST", "modo organization-first no persistio")
        assert_true(cfg_person["networking_profile_mode"] == "PERSON_FIRST", "modo person-first no persistio")
        assert_true(cfg_default["networking_profile_mode"] == "AUTO", "default de evento existente/nuevo debe ser AUTO")

        ana = request(base, "POST", "/api/register", {"actor": "Recepcion", "event_id": org_event_id, "first_name": "Ana", "last_name": "Compradora", "email": "ana.v11@example.test", "type": "General"}, 201)
        bruno = request(base, "POST", "/api/register", {"actor": "Recepcion", "event_id": org_event_id, "first_name": "Bruno", "last_name": "Representante", "email": "bruno.v11@example.test", "type": "General"}, 201)
        carla = request(base, "POST", "/api/register", {"actor": "Recepcion", "event_id": person_event_id, "first_name": "Carla", "last_name": "Speaker", "email": "carla.v11@example.test", "type": "General"}, 201)
        diego = request(base, "POST", "/api/register", {"actor": "Recepcion", "event_id": person_event_id, "first_name": "Diego", "last_name": "Consultor", "email": "diego.v11@example.test", "type": "General"}, 201)

        org_rows = [
            {
                "source_external_id": "org-ana",
                "first_name": "Ana",
                "last_name": "Compradora",
                "email": "ana.v11@example.test",
                "organization": "Constructora Norte",
                "title": "Compras",
                "function": "PROCUREMENT",
                "linkedin": "https://linkedin.example/ana",
            },
            {
                "source_external_id": "org-bruno",
                "first_name": "Bruno",
                "last_name": "Representante",
                "email": "bruno.v11@example.test",
                "organization": "Hormigon Patagonia",
                "organization_activity": "Construccion",
                "organization_specialty": "Materiales",
                "organization_description": "Proveedor regional de soluciones para obras.",
                "organization_logo_url": "https://assets.example/logo-hp.png",
                "title": "Representante comercial",
                "function": "COMMERCIAL",
                "bio": "Soy Bruno y coordino cuentas estrategicas",
                "offers": "Hormigon elaborado y asistencia tecnica",
                "channels": [
                    {"type": "website", "value": "https://hormigon.example", "visibility": "PUBLIC", "scope": "ORGANIZATION"},
                    {"type": "email", "value": "bruno.personal@example.test", "visibility": "HIDDEN", "scope": "PERSONAL"},
                    {"type": "linkedin", "value": "https://linkedin.example/bruno", "visibility": "PUBLIC", "scope": "PERSONAL"},
                ],
            },
        ]
        person_rows = [
            {"source_external_id": "person-carla", "first_name": "Carla", "last_name": "Speaker", "email": "carla.v11@example.test", "organization": "Academia Sur", "title": "Directora academica", "function": "INSTITUTIONAL"},
            {"source_external_id": "person-diego", "first_name": "Diego", "last_name": "Consultor", "email": "diego.v11@example.test", "organization": "Consultoria Delta", "title": "Consultor BIM", "function": "PROFESSIONAL_TECHNICAL", "bio": "Especialista en digitalizacion de obras.", "linkedin": "https://linkedin.example/diego"},
        ]
        imported = request(base, "POST", "/api/networking/import", {"actor": "Admin", "event_id": org_event_id, "source_system": "BITORA", "rows": org_rows})
        request(base, "POST", "/api/networking/import", {"actor": "Admin", "event_id": person_event_id, "source_system": "BITORA", "rows": person_rows})
        assert_true(all(row["state"] == "PASSIVE" for row in imported["rows"]), "import sigue sin activar")

        ana_session = request(base, "GET", f"/api/networking/session?token={ana['token']}&event_id={org_event_id}")
        assert_true(ana_session["participation"]["requires_onboarding"], "onboarding sigue obligatorio")

        ana_onboard = request(base, "POST", "/api/networking/onboarding", {"token": ana["token"], "event_id": org_event_id, "modes": ["COMMERCIAL"], "direction": "SEEKING", "contact_openness": "DIRECT"})
        bruno_onboard = request(base, "POST", "/api/networking/onboarding", {"token": bruno["token"], "event_id": org_event_id, "modes": ["SERVICES_SOLUTIONS"], "direction": "OFFERING", "contact_openness": "CORPORATE_ROUTE", "representative_visible": False})
        request(base, "POST", "/api/networking/onboarding", {"token": carla["token"], "event_id": person_event_id, "modes": ["BUSINESS_ALLIANCES"], "direction": "SEEKING", "contact_openness": "CONNECT_FIRST"})
        diego_onboard = request(base, "POST", "/api/networking/onboarding", {"token": diego["token"], "event_id": person_event_id, "modes": ["SERVICES_SOLUTIONS"], "direction": "OFFERING", "contact_openness": "DIRECT"})

        request(base, "GET", f"/api/networking/session?token={bruno_onboard['participation']['public_profile_id']}&event_id={org_event_id}", expect=404)
        scan_org = request(base, "POST", "/api/networking/scan", {"token": ana["token"], "public_profile_id": bruno_onboard["participation"]["public_profile_id"]})
        pres_org = scan_org["profile"]["presentation"]
        assert_true(pres_org["mode"] == "ORGANIZATION_FIRST" and pres_org["primary"]["kind"] == "organization", "organization-first no prioriza organizacion")
        assert_true(pres_org["primary"]["title"] == "Hormigon Patagonia", "organizacion no es identidad principal")
        assert_true("Construccion" in pres_org["primary"]["subtitle"], "actividad/sector no aparece")
        assert_true(not pres_org["person"]["visible"] and pres_org["secondary"]["title"] == "", "representante restringido filtro identidad")
        assert_true(scan_org["profile"]["bio"] == "" and pres_org["secondary"]["description"] == "", "representante restringido filtro bio personal")
        assert_true(channel_types(pres_org["primary"]["actions"]) == {"website"}, "solo canales corporativos permitidos deben ir en accion primaria")
        assert_true("email" not in channel_types(scan_org["profile"]["channels"]), "canal oculto personal fue expuesto")

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
        hidden_org = request(base, "GET", f"/api/networking/profile?profile_id={bruno_onboard['participation']['public_profile_id']}&token={ana['token']}")
        hidden_presentation = hidden_org["profile"]["presentation"]
        assert_true(hidden_org["profile"]["organization"] == "" and hidden_org["profile"]["organization_activity"] == "" and hidden_org["profile"]["organization_description"] == "", "organizacion oculta filtro metadatos")
        assert_true(not hidden_presentation["organization"]["visible"] and hidden_presentation["organization"]["activity"] == "", "presentation filtro metadatos de organizacion oculta")
        with server.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                """
                UPDATE networking_organizations
                SET visibility = 'PUBLIC'
                WHERE id = (SELECT organization_id FROM networking_event_participations WHERE public_profile_id = ?)
                """,
                (bruno_onboard["participation"]["public_profile_id"],),
            )
            db.execute("COMMIT")

        scan_org_again = request(base, "POST", "/api/networking/scan", {"token": ana["token"], "public_profile_id": bruno_onboard["participation"]["public_profile_id"]})
        assert_true(not scan_org_again["created"], "scan repetido no debe duplicar")
        contacts = request(base, "GET", f"/api/networking/contacts?token={ana['token']}")
        assert_true(len(contacts["contacts"]) == 1 and contacts["contacts"][0]["profile"]["presentation"]["primary"]["kind"] == "organization", "Mis contactos no respeta jerarquia")

        scan_person = request(base, "POST", "/api/networking/scan", {"token": carla["token"], "public_profile_id": diego_onboard["participation"]["public_profile_id"]})
        pres_person = scan_person["profile"]["presentation"]
        assert_true(pres_person["mode"] == "PERSON_FIRST" and pres_person["primary"]["kind"] == "person", "person-first no prioriza persona")
        assert_true(pres_person["primary"]["title"] == "Diego Consultor" and "Consultor BIM" in pres_person["primary"]["subtitle"], "persona/cargo no son principales")

        missing_org = request(base, "POST", "/api/networking/external-register", {"event_id": org_event_id, "first_name": "Eva", "last_name": "SinOrg", "email": "eva.v11@example.test"}, 201)
        eva_onboard = request(base, "POST", "/api/networking/onboarding", {"token": missing_org["owner_token"], "event_id": org_event_id, "modes": ["COMMERCIAL"], "direction": "BOTH", "contact_openness": "DIRECT"})
        assert_true(eva_onboard["participation"]["presentation"]["mode"] == "PERSON_FIRST", "organization-first sin organizacion debe degradar a persona")

        external = request(
            base,
            "POST",
            "/api/networking/external-register",
            {
                "event_id": org_event_id,
                "first_name": "Fernanda",
                "last_name": "Pyme",
                "email": "fernanda.v11@example.test",
                "organization": "Pyme Andes",
                "organization_activity": "Arquitectura",
                "organization_specialty": "Sustentabilidad",
                "organization_description": "Estudio enfocado en proyectos eficientes.",
                "website": "https://pymeandes.example",
            },
            201,
        )
        external_session = request(base, "GET", f"/api/networking/session?token={external['owner_token']}&event_id={org_event_id}")
        assert_true(external_session["participation"]["organization_activity"] == "Arquitectura", "externo no normaliza datos de organizacion")

        updated_org_rows = [dict(row) for row in org_rows]
        updated_org_rows[1]["organization_activity"] = "Materiales de obra"
        reimport = request(base, "POST", "/api/networking/import", {"actor": "Admin", "event_id": org_event_id, "source_system": "BITORA", "rows": updated_org_rows})
        contacts_after = request(base, "GET", f"/api/networking/contacts?token={ana['token']}")
        assert_true(reimport["created"] == 0 and len(contacts_after["contacts"]) == 1, "reimport no debe duplicar ni borrar contactos")
        assert_true(contacts_after["contacts"][0]["profile"]["presentation"]["organization"]["activity"] == "Materiales de obra", "reimport no actualizo dato source-owned de organizacion")
        assert_true(contacts_after["contacts"][0]["profile"]["contact_openness"] == "CORPORATE_ROUTE", "reimport piso estado networking")

        networking_html, _ = request(base, "GET", "/networking.html", parse_json=False)
        admin_html, _ = request(base, "GET", "/networking-admin.html", parse_json=False)
        register_html, _ = request(base, "GET", f"/networking-register.html?event_id={org_event_id}", parse_json=False)
        assert_true(b"profile.presentation" in networking_html and b"Jerarquia visual" in admin_html and b"Actividad / sector" in register_html, "UI V1.1 incompleta")

        print("OK: BITORA Networking V1.1 jerarquia visual por evento")
    finally:
        if httpd:
            httpd.shutdown()
            httpd.server_close()
        shutil.rmtree(tmp_path, ignore_errors=True)


if __name__ == "__main__":
    main()
