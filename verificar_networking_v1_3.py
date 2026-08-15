from __future__ import annotations

import json
import shutil
import tempfile
import threading
import urllib.error
import urllib.request
from pathlib import Path

import server
from backend.services.backup import EventBackupService, EventRestoreService


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


def concept_codes(items: list[dict]) -> set[str]:
    return {item.get("code", "") for item in items}


def token_factory():
    counter = {"value": 0}

    def make_token() -> str:
        counter["value"] += 1
        return f"V13-RESTORE-{counter['value']:04d}"

    return make_token


def main() -> None:
    tmp_path = Path(tempfile.mkdtemp(prefix="qr-networking-v1-3-"))
    httpd = None
    try:
        server.DB_PATH = tmp_path / "networking_v1_3.sqlite3"
        server.BACKUP_DIR = tmp_path / "backups"
        server.AppHandler.log_message = lambda self, format, *args: None
        server.init_db()
        server.seed_if_empty()

        httpd = server.OperationalHTTPServer(("127.0.0.1", 0), server.AppHandler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{httpd.server_address[1]}"

        org_event = request(base, "POST", "/api/events", {"actor": "Admin", "name": "EDIFICA referencia", "status": "published"}, 201)
        person_event = request(base, "POST", "/api/events", {"actor": "Admin", "name": "Comunidad profesional", "status": "published"}, 201)
        org_event_id = int(org_event["id"])
        person_event_id = int(person_event["id"])
        request(base, "POST", "/api/networking/config", {"actor": "Admin", "event_id": org_event_id, "networking_profile_mode": "ORGANIZATION_FIRST"})
        request(base, "POST", "/api/networking/config", {"actor": "Admin", "event_id": person_event_id, "networking_profile_mode": "PERSON_FIRST"})

        org_taxonomy = {
            "actor": "Admin",
            "event_id": org_event_id,
            "concepts": [
                {"code": "INDUSTRY_CONSTRUCTION", "type": "INDUSTRY", "label": "Construccion", "aliases": ["construction"], "enabled": True},
                {"code": "SPECIALTY_READY_MIX_CONCRETE", "type": "SPECIALTY", "label": "Hormigon elaborado", "aliases": ["ready mix", "hormigon elaborado"], "enabled": True},
                {"code": "OFFER_READY_MIX_SUPPLY", "type": "OFFER", "label": "Provision de hormigon elaborado", "enabled": True},
                {"code": "SEEK_CONSTRUCTION_COMPANIES", "type": "SEEK", "label": "Constructoras", "enabled": True},
                {"code": "INTEREST_INFRASTRUCTURE", "type": "INTEREST", "label": "Infraestructura", "enabled": True},
            ],
        }
        person_taxonomy = {
            "actor": "Admin",
            "event_id": person_event_id,
            "concepts": [
                {"code": "OFFER_BIM_CONSULTING", "type": "OFFER", "label": "Consultoria BIM", "enabled": True},
                {"code": "SEEK_INVESTORS", "type": "SEEK", "label": "Inversores", "enabled": True},
                {"code": "INTEREST_DIGITALIZATION", "type": "INTEREST", "label": "Digitalizacion", "enabled": True},
            ],
        }
        request(base, "POST", "/api/networking/taxonomy", org_taxonomy)
        request(base, "POST", "/api/networking/taxonomy", person_taxonomy)
        org_vocab = request(base, "GET", f"/api/networking/taxonomy?actor=Admin&event_id={org_event_id}")
        person_vocab = request(base, "GET", f"/api/networking/taxonomy?actor=Admin&event_id={person_event_id}")
        assert_true("OFFER_READY_MIX_SUPPLY" in concept_codes(org_vocab["concepts"]), "evento org no habilito offer esperado")
        assert_true("OFFER_READY_MIX_SUPPLY" not in concept_codes(person_vocab["concepts"]), "vocabulario semantico se filtro entre eventos")

        stable_label_update = dict(org_taxonomy)
        stable_label_update["concepts"] = [dict(item) for item in org_taxonomy["concepts"]]
        stable_label_update["concepts"][0]["label"] = "Construccion y obras"
        request(base, "POST", "/api/networking/taxonomy", stable_label_update)
        org_vocab_after_label = request(base, "GET", f"/api/networking/taxonomy?actor=Admin&event_id={org_event_id}")
        industry = [item for item in org_vocab_after_label["concepts"] if item["code"] == "INDUSTRY_CONSTRUCTION"][0]
        assert_true(industry["label"] == "Construccion y obras", "identidad estable no sobrevivio cambio de label")
        same_label_other_code = dict(person_taxonomy)
        same_label_other_code["concepts"] = [
            {"code": "OFFER_READY_MIX_ALT", "type": "OFFER", "label": "Provision de hormigon elaborado", "enabled": True},
        ]
        request(base, "POST", "/api/networking/taxonomy", same_label_other_code)
        person_vocab_after_same_label = request(base, "GET", f"/api/networking/taxonomy?actor=Admin&event_id={person_event_id}")
        assert_true("OFFER_READY_MIX_ALT" in concept_codes(person_vocab_after_same_label["concepts"]), "codigo explicito fue colapsado por label global")

        ana = request(base, "POST", "/api/register", {"actor": "Recepcion", "event_id": org_event_id, "first_name": "Ana", "last_name": "Compras", "email": "ana.v13@example.test", "type": "General"}, 201)
        bruno = request(base, "POST", "/api/register", {"actor": "Recepcion", "event_id": org_event_id, "first_name": "Bruno", "last_name": "Hormigon", "email": "bruno.v13@example.test", "type": "General"}, 201)
        clara = request(base, "POST", "/api/register", {"actor": "Recepcion", "event_id": person_event_id, "first_name": "Clara", "last_name": "BIM", "email": "clara.v13@example.test", "type": "General"}, 201)

        org_rows = [
            {
                "source_external_id": "ana-v13",
                "first_name": "Ana",
                "last_name": "Compras",
                "email": "ana.v13@example.test",
                "organization": "Constructora Norte",
                "title": "Jefa de compras",
                "function": "PROCUREMENT",
                "seniority": "MANAGEMENT",
                "channels": [{"type": "website", "value": "https://constructora.example", "visibility": "PUBLIC", "scope": "ORGANIZATION"}],
            },
            {
                "source_external_id": "bruno-v13",
                "first_name": "Bruno",
                "last_name": "Hormigon",
                "email": "bruno.v13@example.test",
                "organization": "Hormigonera Confluencia",
                "organization_activity": "Construccion y obras",
                "organization_description": "Proveedor regional de soluciones para obras.",
                "title": "Gerente comercial",
                "function": "COMMERCIAL",
                "seniority": "MANAGEMENT",
                "specialty_concepts": ["Hormigon elaborado", "Hormigon premium"],
                "offer_concepts": ["Provision de hormigon elaborado"],
                "seek_concepts": ["Constructoras"],
                "interest_concepts": ["Infraestructura"],
                "channels": [
                    {"type": "website", "value": "https://hormigonera.example", "visibility": "PUBLIC", "scope": "ORGANIZATION"},
                    {"type": "email", "value": "bruno.privado@example.test", "visibility": "HIDDEN", "scope": "PERSONAL"},
                ],
            },
        ]
        semantic_preview = request(base, "POST", "/api/networking/import/preview", {"actor": "Admin", "event_id": org_event_id, "rows": org_rows})
        assert_true(semantic_preview["semantic_unknown_concepts"] == 1, "concepto desconocido no fue diagnosticado")
        unknowns = semantic_preview["rows"][1]["semantic"]["unknown"]
        assert_true(unknowns[0]["reason"] == "UNKNOWN_CONCEPT" and unknowns[0]["value"] == "Hormigon premium", "unknown concept no es explicito")

        semantic_import = request(base, "POST", "/api/networking/import", {"actor": "Admin", "event_id": org_event_id, "source_system": "BITORA", "rows": org_rows})
        assert_true(semantic_import["semantic_unknown_concepts"] == 1 and semantic_import["rows"][1]["semantic"]["unknown"][0]["reason"] == "UNKNOWN_CONCEPT", "import no conserva diagnostico de conceptos desconocidos")
        request(base, "POST", "/api/networking/import", {"actor": "Admin", "event_id": org_event_id, "source_system": "BITORA", "rows": org_rows})
        ana_active = request(base, "POST", "/api/networking/onboarding", {"token": ana["token"], "event_id": org_event_id, "modes": ["COMMERCIAL"], "direction": "SEEKING", "contact_openness": "DIRECT"})
        bruno_active = request(base, "POST", "/api/networking/onboarding", {"token": bruno["token"], "event_id": org_event_id, "modes": ["SERVICES_SOLUTIONS"], "direction": "OFFERING", "contact_openness": "CORPORATE_ROUTE", "representative_visible": False})
        bruno_active = request(base, "POST", "/api/networking/complete-profile", {"token": bruno["token"], "event_id": org_event_id, "offer_concepts": ["Provision de hormigon elaborado"], "interest_concepts": ["Infraestructura"]})
        bruno_profile = bruno_active["participation"]
        bruno_semantic = bruno_profile["semantic"]
        assert_true(bruno_profile["credential"]["public_path"] == f"/n/{bruno_profile['public_profile_id']}" and bruno_profile["credential"]["qr_kind"] == "HTTPS_DEEP_LINK", "credencial digital no expone deep link publico")
        assert_true(bruno_profile["discovery"]["status"] == "NOT_CONFIGURED" and bruno_profile["active"], "Discovery incompleto no debe bloquear credencial activa")
        assert_true("OFFER_READY_MIX_SUPPLY" in concept_codes(bruno_semantic["organization_offers"]), "offer organizacional no se persistio")
        assert_true("SEEK_CONSTRUCTION_COMPANIES" in concept_codes(bruno_semantic["seeks"]), "seek event-specific no se persistio")
        assert_true("OFFER_READY_MIX_SUPPLY" not in concept_codes(bruno_semantic["seeks"]), "offers y seeks fueron colapsados")
        assert_true(bruno_profile["role"] == "Gerente comercial" and bruno_profile["function"] == "COMMERCIAL", "title y funcion normalizada no coexisten")
        assert_true(bruno_profile["seniority"] == "MANAGEMENT", "seniority normalizada no persistio")
        qr_body, qr_content_type = request(base, "GET", f"/api/networking/qr.svg?profile_id={bruno_profile['public_profile_id']}", parse_json=False)
        assert_true(b"<svg" in qr_body and "image/svg+xml" in qr_content_type, "QR de credencial invalido")
        public_page, _ = request(base, "GET", f"/n/{bruno_profile['public_profile_id']}", parse_json=False)
        assert_true(b"Perfil BITORA Networking" in public_page and b"Guardar en mis contactos" in public_page, "deep link publico no muestra landing Networking")
        public_profile = request(base, "GET", f"/api/networking/profile?profile_id={bruno_profile['public_profile_id']}")
        assert_true(public_profile["profile"]["public_profile_id"] == bruno_profile["public_profile_id"], "camara normal no resuelve perfil publico")
        assert_true(public_profile["profile"]["participation_id"] is None, "perfil publico logged-out expuso id interno")

        scan = request(base, "POST", "/api/networking/scan", {"token": ana["token"], "qr_payload": f"{base}/n/{bruno_profile['public_profile_id']}"})
        assert_true(scan["created"], "scan inicial debe crear contacto")
        scanned_semantic = scan["profile"]["semantic"]
        assert_true("OFFER_READY_MIX_SUPPLY" in concept_codes(scanned_semantic["organization_offers"]), "organization-first no mostro offer permitido")
        assert_true(scanned_semantic["interests"] == [] and scanned_semantic["seeks"] == [], "representante restringido filtro semantica de persona/participacion")
        assert_true("email" not in {channel["type"] for channel in scan["profile"]["channels"]}, "canal oculto fue expuesto")
        duplicate_scan = request(base, "POST", "/api/networking/scan", {"token": ana["token"], "public_profile_id": bruno_profile["public_profile_id"]})
        assert_true(not duplicate_scan["created"], "scan repetido duplico contacto")
        request(base, "GET", f"/api/networking/session?token={bruno_profile['public_profile_id']}&event_id={org_event_id}", expect=404)
        public_vocab = request(base, "GET", f"/api/networking/live-vocabulary?event_id={org_event_id}")
        public_specialty_labels = {item["label"] for item in public_vocab["vocabulary"]["SPECIALTY"]}
        assert_true("Hormigon premium" not in public_specialty_labels, "vocabulario publico anonimo expuso candidato no curado")
        live_vocab = request(base, "GET", f"/api/networking/live-vocabulary?event_id={org_event_id}&token={ana['token']}")
        specialty_labels = {item["label"] for item in live_vocab["vocabulary"]["SPECIALTY"]}
        assert_true("Hormigon premium" in specialty_labels, "categoria importada desconocida no quedo disponible en vocabulario vivo")

        person_row = {
            "source_external_id": "clara-v13",
            "first_name": "Clara",
            "last_name": "BIM",
            "email": "clara.v13@example.test",
            "title": "Consultora BIM",
            "function": "PROFESSIONAL_TECHNICAL",
            "seek_concepts": ["Inversores"],
        }
        request(base, "POST", "/api/networking/import", {"actor": "Admin", "event_id": person_event_id, "source_system": "BITORA", "rows": [person_row]})
        clara_active = request(base, "POST", "/api/networking/onboarding", {"token": clara["token"], "event_id": person_event_id, "modes": ["BUSINESS_ALLIANCES"], "direction": "BOTH", "contact_openness": "DIRECT"})
        assert_true("SEEK_INVESTORS" in concept_codes(clara_active["participation"]["semantic"]["seeks"]), "seek event-specific de persona no se persistio")
        request(base, "POST", "/api/networking/complete-profile", {"token": clara["token"], "event_id": person_event_id, "offer_concepts": ["Consultoria BIM"], "interest_concepts": ["Digitalizacion"], "bio": "Ayudo a equipos de obra a digitalizar procesos.", "linkedin": "https://linkedin.example/clara"})
        discovery = request(
            base,
            "POST",
            "/api/networking/discovery-onboarding",
            {
                "token": clara["token"],
                "event_id": person_event_id,
                "seeks": ["Inversores"],
                "offers": ["Consultoria BIM"],
                "company_types": ["Geotecnia aplicada"],
                "desired_functions": ["PROCUREMENT", "TECHNOLOGY"],
                "objectives": ["Digitalizacion"],
                "discovery_diversity": False,
            },
        )
        assert_true(discovery["participation"]["discovery"]["status"] == "READY" and not discovery["participation"]["discovery"]["diversity"], "Golden Ticket no dejo Discovery listo por evento")
        discovery_shell = request(base, "GET", f"/api/networking/discovery?token={clara['token']}")
        assert_true(discovery_shell["ready"] and discovery_shell["status"] in {"READY", "EXHAUSTED"} and "score" not in json.dumps(discovery_shell).lower(), "Discovery no es honesto o no esta listo")
        person_live_vocab = request(base, "GET", f"/api/networking/live-vocabulary?event_id={person_event_id}&token={clara['token']}")
        company_type_labels = {item["label"] for item in person_live_vocab["vocabulary"]["COMPANY_TYPE"]}
        assert_true("Geotecnia aplicada" in company_type_labels, "categoria declarada por usuario no alimento vocabulario vivo")
        request(base, "POST", "/api/networking/complete-profile", {"token": clara["token"], "event_id": person_event_id, "offer_concepts": ["Concepto inexistente"]})
        clara_after_typo = request(base, "GET", f"/api/networking/session?token={clara['token']}&event_id={person_event_id}")
        assert_true("OFFER_BIM_CONSULTING" in concept_codes(clara_after_typo["participation"]["semantic"]["offers"]), "typo desconocido borro oferta user-owned existente")
        request(base, "POST", "/api/networking/import", {"actor": "Admin", "event_id": person_event_id, "source_system": "BITORA", "rows": [person_row]})
        clara_after_reimport = request(base, "GET", f"/api/networking/session?token={clara['token']}&event_id={person_event_id}")
        assert_true("OFFER_BIM_CONSULTING" in concept_codes(clara_after_reimport["participation"]["semantic"]["offers"]), "seleccion semantica de usuario no sobrevivio reimport")
        assert_true("INTEREST_DIGITALIZATION" in concept_codes(clara_after_reimport["participation"]["semantic"]["interests"]), "interes user-owned no sobrevivio reimport")
        assert_true("SEEK_INVESTORS" in concept_codes(clara_after_reimport["participation"]["semantic"]["seeks"]), "seek source-owned no sobrevivio reimport")
        assert_true(clara_after_reimport["participation"]["discovery"]["status"] == "READY" and "PROCUREMENT" in clara_after_reimport["participation"]["discovery"]["desired_functions"], "reimport destruyo preferencias Discovery user-owned")

        with server.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                """
                UPDATE networking_organizations
                SET visibility = 'HIDDEN'
                WHERE id = (SELECT organization_id FROM networking_event_participations WHERE public_profile_id = ?)
                """,
                (bruno_profile["public_profile_id"],),
            )
            db.execute("COMMIT")
        hidden_org = request(base, "GET", f"/api/networking/profile?profile_id={bruno_profile['public_profile_id']}&token={ana['token']}")
        assert_true(hidden_org["profile"]["organization"] == "" and hidden_org["profile"]["semantic"]["industries"] == [] and hidden_org["profile"]["semantic"]["organization_offers"] == [], "organizacion oculta filtro semantica organizacional y user-owned")
        with server.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                """
                UPDATE networking_organizations
                SET visibility = 'PUBLIC'
                WHERE id = (SELECT organization_id FROM networking_event_participations WHERE public_profile_id = ?)
                """,
                (bruno_profile["public_profile_id"],),
            )
            db.execute("COMMIT")

        external = request(base, "POST", "/api/networking/external-register", {"event_id": org_event_id, "first_name": "Eva", "last_name": "Pyme", "email": "eva.v13@example.test", "organization": "Pyme Andes", "organization_activity": "Construccion y obras", "offer_concepts": ["Provision de hormigon elaborado"], "website": "https://pyme.example"}, 201)
        external_session = request(base, "GET", f"/api/networking/session?token={external['owner_token']}&event_id={org_event_id}")
        assert_true("OFFER_READY_MIX_SUPPLY" in concept_codes(external_session["participation"]["semantic"]["organization_offers"]), "externo no uso arquitectura semantica canonica")

        contacts_before = request(base, "GET", f"/api/networking/contacts?token={ana['token']}")
        request(base, "POST", "/api/networking/import", {"actor": "Admin", "event_id": org_event_id, "source_system": "BITORA", "rows": [dict(org_rows[1], organization_activity="Construccion y obras")]})
        contacts_after = request(base, "GET", f"/api/networking/contacts?token={ana['token']}")
        assert_true(len(contacts_before["contacts"]) == len(contacts_after["contacts"]) == 1, "contactos no sobrevivieron reimport semantico")

        with server.connect() as db:
            original_semantic = db.execute("SELECT COUNT(*) AS c FROM networking_semantic_classifications WHERE event_id = ?", (org_event_id,)).fetchone()["c"]
            original_vocab = db.execute("SELECT COUNT(*) AS c FROM networking_event_taxonomy_concepts WHERE event_id = ?", (org_event_id,)).fetchone()["c"]
            original_candidates = db.execute("SELECT COUNT(*) AS c FROM networking_event_vocabulary_candidates WHERE event_id = ?", (org_event_id,)).fetchone()["c"]
        backup_service = EventBackupService(server.BACKUP_DIR, server.connect, server.DB_LOCK, app_version="test")
        restore_service = EventRestoreService(server.connect, server.DB_LOCK, token_factory(), server.now_iso, app_version="test", backup_service=backup_service)
        bundle = backup_service.create_event_bundle(org_event_id, "QA")
        restore = restore_service.restore_bytes(bundle.read_bytes(), mode="new_event", actor="Admin", new_event_name="EDIFICA restaurado")
        restored_event_id = int(restore["event_id"])
        with server.connect() as db:
            restored_semantic = db.execute("SELECT COUNT(*) AS c FROM networking_semantic_classifications WHERE event_id = ?", (restored_event_id,)).fetchone()["c"]
            restored_vocab = db.execute("SELECT COUNT(*) AS c FROM networking_event_taxonomy_concepts WHERE event_id = ?", (restored_event_id,)).fetchone()["c"]
            restored_candidates = db.execute("SELECT COUNT(*) AS c FROM networking_event_vocabulary_candidates WHERE event_id = ?", (restored_event_id,)).fetchone()["c"]
        assert_true(restored_semantic == original_semantic and restored_vocab == original_vocab and restored_candidates == original_candidates, "backup/restore no preservo semantica/vocabulario vivo V1.3 con conteos exactos")

        request(base, "GET", "/assets/", expect=404, parse_json=False)
        request(base, "GET", "/api/networking/directory", expect=404)
        request(base, "GET", "/api/networking/recommendations", expect=404)

        networking_html, _ = request(base, "GET", "/networking.html", parse_json=False)
        admin_html, _ = request(base, "GET", "/networking-admin.html", parse_json=False)
        public_html, _ = request(base, "GET", "/networking-public.html", parse_json=False)
        register_html, _ = request(base, "GET", f"/networking-register.html?event_id={org_event_id}", parse_json=False)
        assert_true(b"Golden Ticket" in networking_html and b"event-credential" in networking_html and b"Vocabulario vivo" in admin_html and b"Guardar en mis contactos" in public_html and b"interest_concepts" in register_html, "UI credencial/discovery V1.3 incompleta")

        print("OK: BITORA Networking V1.3 credential/live-vocabulary/discovery foundation")
    finally:
        if httpd:
            httpd.shutdown()
            httpd.server_close()
        shutil.rmtree(tmp_path, ignore_errors=True)


if __name__ == "__main__":
    main()
