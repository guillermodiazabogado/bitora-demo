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


def main() -> None:
    tmp_path = Path(tempfile.mkdtemp(prefix="qr-networking-v1-2-"))
    httpd = None
    try:
        server.DB_PATH = tmp_path / "networking_v1_2.sqlite3"
        server.BACKUP_DIR = tmp_path / "backups"
        server.AppHandler.log_message = lambda self, format, *args: None
        server.init_db()
        server.seed_if_empty()

        httpd = server.OperationalHTTPServer(("127.0.0.1", 0), server.AppHandler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{httpd.server_address[1]}"

        org_event = request(base, "POST", "/api/events", {"actor": "Admin", "name": "Evento empresa", "status": "published"}, 201)
        person_event = request(base, "POST", "/api/events", {"actor": "Admin", "name": "Evento persona", "status": "published"}, 201)
        legacy_event = request(base, "POST", "/api/events", {"actor": "Admin", "name": "Evento legacy", "status": "published"}, 201)
        org_event_id = int(org_event["id"])
        person_event_id = int(person_event["id"])
        legacy_event_id = int(legacy_event["id"])

        org_required = ["organization.identity", "organization.activity", "networking.offers_seeks", "contact.permitted_route"]
        org_recommended = ["person.identity", "person.role", "organization.description", "contact.organization_route"]
        cfg_org = request(base, "POST", "/api/networking/config", {"actor": "Admin", "event_id": org_event_id, "networking_profile_mode": "ORGANIZATION_FIRST", "networking_readiness_required": org_required, "networking_readiness_recommended": org_recommended})
        cfg_person = request(base, "POST", "/api/networking/config", {"actor": "Admin", "event_id": person_event_id, "networking_profile_mode": "PERSON_FIRST"})
        cfg_legacy = request(base, "GET", f"/api/networking/config?actor=Admin&event_id={legacy_event_id}")
        assert_true(cfg_org["networking_readiness_required"] == org_required, "config de readiness org no persistio")
        assert_true(cfg_person["networking_profile_mode"] == "PERSON_FIRST", "modo person-first no persistio")
        assert_true("person.bio" in cfg_legacy["networking_readiness_required"], "evento legacy no recibe fallback deterministico")
        request(base, "POST", "/api/networking/config", {"actor": "Admin", "event_id": org_event_id, "networking_profile_mode": "ORGANIZATION_FIRST"})
        cfg_org_after_mode = request(base, "GET", f"/api/networking/config?actor=Admin&event_id={org_event_id}")
        assert_true(cfg_org_after_mode["networking_readiness_required"] == org_required, "guardar solo modo visual borro reglas readiness")

        ana = request(base, "POST", "/api/register", {"actor": "Recepcion", "event_id": org_event_id, "first_name": "Ana", "last_name": "Buyer", "email": "ana.v12@example.test", "type": "General"}, 201)
        bruno = request(base, "POST", "/api/register", {"actor": "Recepcion", "event_id": org_event_id, "first_name": "Bruno", "last_name": "Proveedor", "email": "bruno.v12@example.test", "type": "General"}, 201)
        clara = request(base, "POST", "/api/register", {"actor": "Recepcion", "event_id": person_event_id, "first_name": "Clara", "last_name": "Consultora", "email": "clara.v12@example.test", "type": "General"}, 201)
        diego = request(base, "POST", "/api/register", {"actor": "Recepcion", "event_id": person_event_id, "first_name": "Diego", "last_name": "Tecnico", "email": "diego.v12@example.test", "type": "General"}, 201)

        invalid_preview = request(base, "POST", "/api/networking/import/preview", {"actor": "Admin", "event_id": person_event_id, "rows": [{"first_name": "Sin email"}]})
        assert_true(not invalid_preview["ok"] and invalid_preview["errors"] == 1, "fila estructuralmente invalida no fue marcada")

        incomplete_preview = request(base, "POST", "/api/networking/import/preview", {"actor": "Admin", "event_id": person_event_id, "rows": [{"first_name": "Clara", "last_name": "Consultora", "email": "clara.v12@example.test", "title": "Consultora"}]})
        assert_true(incomplete_preview["valid"] == 1 and incomplete_preview["incomplete"] == 1, "fila valida incompleta no fue diferenciada")
        assert_true(incomplete_preview["rows"][0]["ok"] and "person.bio" in incomplete_preview["rows"][0]["readiness"]["missing_required"], "preview no explica brecha de readiness")
        mixed_import = request(base, "POST", "/api/networking/import", {"actor": "Admin", "event_id": person_event_id, "rows": [{"first_name": "Sin email"}, {"first_name": "Clara", "last_name": "Consultora", "email": "clara.v12@example.test", "title": "Consultora"}]})
        assert_true(not mixed_import["ok"] and mixed_import["errors"] == 1 and mixed_import["created"] == 1, "import mixto debe procesar validas y rechazar invalidas")

        org_rows = [
            {
                "source_external_id": "ana-v12",
                "first_name": "Ana",
                "last_name": "Buyer",
                "email": "ana.v12@example.test",
                "organization": "Compras Patagonia",
                "organization_activity": "Construccion",
                "organization_specialty": "Compras tecnicas",
                "offers": "Compras corporativas y alianzas",
                "title": "Compras",
                "function": "PROCUREMENT",
                "channels": [{"type": "website", "value": "https://compras.example", "visibility": "PUBLIC", "scope": "ORGANIZATION"}],
            },
            {
                "source_external_id": "bruno-v12",
                "first_name": "Bruno",
                "last_name": "Proveedor",
                "email": "bruno.v12@example.test",
                "organization": "Hormigon Sur",
                "organization_activity": "Materiales",
                "organization_specialty": "Hormigon elaborado",
                "organization_description": "Soluciones para obras medianas y grandes.",
                "offers": "Hormigon elaborado",
                "title": "Ejecutivo comercial",
                "function": "COMMERCIAL",
                "channels": [
                    {"type": "website", "value": "https://hormigonsur.example", "visibility": "PUBLIC", "scope": "ORGANIZATION"},
                    {"type": "email", "value": "bruno.privado@example.test", "visibility": "HIDDEN", "scope": "PERSONAL"},
                ],
            },
        ]
        person_rows = [
            {"source_external_id": "clara-v12", "first_name": "Clara", "last_name": "Consultora", "email": "clara.v12@example.test", "title": "Consultora", "function": "PROFESSIONAL_TECHNICAL"},
            {"source_external_id": "diego-v12", "first_name": "Diego", "last_name": "Tecnico", "email": "diego.v12@example.test", "title": "Especialista BIM", "function": "TECHNOLOGY", "bio": "Digitalizacion de obra y coordinacion BIM.", "linkedin": "https://linkedin.example/diego"},
        ]
        org_preview = request(base, "POST", "/api/networking/import/preview", {"actor": "Admin", "event_id": org_event_id, "rows": org_rows})
        assert_true(org_preview["complete"] == 2, "preview no reconoce perfiles completos segun config del evento")
        imported_org = request(base, "POST", "/api/networking/import", {"actor": "Admin", "event_id": org_event_id, "source_system": "BITORA", "rows": org_rows})
        request(base, "POST", "/api/networking/import", {"actor": "Admin", "event_id": org_event_id, "source_system": "BITORA", "rows": org_rows})
        request(base, "POST", "/api/networking/import", {"actor": "Admin", "event_id": person_event_id, "source_system": "BITORA", "rows": person_rows})
        assert_true(all(row["state"] == "PASSIVE" for row in imported_org["rows"]), "import no debe activar")

        ana_session_passive = request(base, "GET", f"/api/networking/session?token={ana['token']}&event_id={org_event_id}")
        assert_true(ana_session_passive["participation"]["state"] == "PASSIVE", "perfil importado completo no debe dejar de ser PASSIVE")
        assert_true(ana_session_passive["participation"]["readiness"]["status"] == "READY", "perfil PASSIVE completo debe poder ser READY como perfil")
        assert_true(not ana_session_passive["participation"]["readiness"]["ready_participation"], "READY de perfil no debe equivaler a participacion lista/activa")

        ana_active = request(base, "POST", "/api/networking/onboarding", {"token": ana["token"], "event_id": org_event_id, "modes": ["COMMERCIAL"], "direction": "SEEKING", "contact_openness": "DIRECT"})
        bruno_active = request(base, "POST", "/api/networking/onboarding", {"token": bruno["token"], "event_id": org_event_id, "modes": ["SERVICES_SOLUTIONS"], "direction": "OFFERING", "contact_openness": "CORPORATE_ROUTE", "representative_visible": False})
        assert_true(bruno_active["participation"]["readiness"]["status"] == "READY", "representante restringido no debe bloquear organizacion lista con ruta corporativa")
        assert_true(bruno_active["participation"]["name"] == "Bruno Proveedor", "el dueno puede ver su identidad")

        scan = request(base, "POST", "/api/networking/scan", {"token": ana["token"], "public_profile_id": bruno_active["participation"]["public_profile_id"]})
        assert_true(scan["created"], "scan inicial debe crear contacto")
        assert_true(scan["profile"]["name"] == "" and scan["profile"]["presentation"]["primary"]["kind"] == "organization", "scan filtro representante restringido y priorizo organizacion")
        assert_true("email" not in {channel["type"] for channel in scan["profile"]["channels"]}, "canal oculto fue expuesto")
        duplicate_scan = request(base, "POST", "/api/networking/scan", {"token": ana["token"], "public_profile_id": bruno_active["participation"]["public_profile_id"]})
        assert_true(not duplicate_scan["created"], "scan repetido duplico contacto")
        request(base, "GET", f"/api/networking/session?token={bruno_active['participation']['public_profile_id']}&event_id={org_event_id}", expect=404)

        clara_active = request(base, "POST", "/api/networking/onboarding", {"token": clara["token"], "event_id": person_event_id, "modes": ["COMMERCIAL"], "direction": "BOTH", "contact_openness": "DIRECT"})
        assert_true(clara_active["participation"]["state"] == "ACTIVE" and clara_active["participation"]["readiness"]["status"] == "INCOMPLETE", "ACTIVE incompleto debe distinguirse de READY")
        clara_completed = request(base, "POST", "/api/networking/complete-profile", {"token": clara["token"], "event_id": person_event_id, "title": "Especialista en obras", "function": "OPERATIONS", "bio": "Coordino operaciones para obras industriales.", "offers": "Gestion operativa", "seeks": "Proveedores regionales", "linkedin": "https://linkedin.example/clara"})
        assert_true(clara_completed["participation"]["readiness"]["status"] == "READY", "completion no dejo perfil READY")
        assert_true(clara_completed["participation"]["offers"] == "Gestion operativa" and clara_completed["participation"]["seeks"] == "Proveedores regionales", "offers y seeks no quedan separados")

        reimport_person = [dict(person_rows[0], title="", function="OTHER")]
        request(base, "POST", "/api/networking/import", {"actor": "Admin", "event_id": person_event_id, "source_system": "BITORA", "rows": reimport_person})
        clara_after_reimport = request(base, "GET", f"/api/networking/session?token={clara['token']}&event_id={person_event_id}")
        assert_true(clara_after_reimport["participation"]["role"] == "Especialista en obras", "reimport borro dato completado por participante")
        assert_true(clara_after_reimport["participation"]["readiness"]["status"] == "READY", "reimport rompio readiness derivado")

        diego_active = request(base, "POST", "/api/networking/onboarding", {"token": diego["token"], "event_id": person_event_id, "modes": ["SERVICES_SOLUTIONS"], "direction": "OFFERING", "contact_openness": "CONNECT_FIRST"})
        request(base, "POST", "/api/networking/scan", {"token": clara["token"], "public_profile_id": diego_active["participation"]["public_profile_id"]})
        contacts_before = request(base, "GET", f"/api/networking/contacts?token={clara['token']}")
        request(base, "POST", "/api/networking/import", {"actor": "Admin", "event_id": person_event_id, "source_system": "BITORA", "rows": person_rows})
        contacts_after = request(base, "GET", f"/api/networking/contacts?token={clara['token']}")
        assert_true(len(contacts_before["contacts"]) == len(contacts_after["contacts"]) == 1, "contactos no sobrevivieron reimport")

        hidden_only = request(base, "POST", "/api/networking/external-register", {"event_id": person_event_id, "first_name": "Hilda", "last_name": "Oculta", "email": "hilda.v12@example.test", "title": "Analista", "bio": "Perfil con canal oculto.", "channel_visibility": {"email": "HIDDEN"}, "channels": [{"type": "email", "value": "hilda@example.test", "visibility": "HIDDEN", "scope": "PERSONAL"}]}, 201)
        hilda_onboard = request(base, "POST", "/api/networking/onboarding", {"token": hidden_only["owner_token"], "event_id": person_event_id, "modes": ["COMMERCIAL"], "direction": "BOTH", "contact_openness": "DIRECT"})
        assert_true("contact.permitted_route" in hilda_onboard["participation"]["readiness"]["missing_required"], "canal oculto no debe satisfacer contactabilidad")

        external = request(base, "POST", "/api/networking/external-register", {"event_id": org_event_id, "first_name": "Eva", "last_name": "Pyme", "email": "eva.v12@example.test", "organization": "Pyme Andes", "organization_activity": "Arquitectura", "offers": "Proyectos sustentables", "website": "https://pymeandes.example"}, 201)
        external_session = request(base, "GET", f"/api/networking/session?token={external['owner_token']}&event_id={org_event_id}")
        assert_true(external_session["participation"]["organization_activity"] == "Arquitectura" and external_session["participation"]["readiness"]["status"] == "READY", "externo no entro al mismo pipeline de readiness")

        readiness = request(base, "GET", f"/api/networking/readiness?actor=Admin&event_id={org_event_id}")
        assert_true(readiness["total"] >= 3 and readiness["ready"] >= 3 and readiness["participants"] == [], "admin readiness default debe resumir sin roster")
        readiness_with_gaps = request(base, "GET", f"/api/networking/readiness?actor=Admin&event_id={person_event_id}&include_participants=1")
        assert_true(all("public_profile_id" not in item and "missing_required" in item["readiness"] for item in readiness_with_gaps["participants"]), "lista admin debe mostrar brechas sin exponer perfil publico")

        networking_html, _ = request(base, "GET", "/networking.html", parse_json=False)
        admin_html, _ = request(base, "GET", "/networking-admin.html", parse_json=False)
        register_html, _ = request(base, "GET", f"/networking-register.html?event_id={org_event_id}", parse_json=False)
        assert_true(b"readinessPanel" in networking_html and b"Preparacion del evento" in admin_html and b"Ofrezco" in register_html, "UI V1.2 incompleta")

        print("OK: BITORA Networking V1.2 readiness/completion/import/admin/privacy")
    finally:
        if httpd:
            httpd.shutdown()
            httpd.server_close()
        shutil.rmtree(tmp_path, ignore_errors=True)


if __name__ == "__main__":
    main()
