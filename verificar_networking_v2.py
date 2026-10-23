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


def first_profile(stream: dict) -> dict:
    assert_true(stream.get("items"), "Discovery no devolvio candidatos")
    return stream["items"][0]["profile"]


def token_factory():
    counter = {"value": 0}

    def make_token() -> str:
        counter["value"] += 1
        return f"V2-RESTORE-{counter['value']:04d}"

    return make_token


def onboard(base: str, token: str, event_id: int, *, function: str = "COMMERCIAL", representative_visible: bool = True) -> dict:
    return request(
        base,
        "POST",
        "/api/networking/onboarding",
        {
            "token": token,
            "event_id": event_id,
            "modes": ["COMMERCIAL"],
            "direction": "BOTH",
            "contact_openness": "DIRECT",
            "function": function,
            "representative_visible": representative_visible,
            "website": "https://contact.example",
            "channel_visibility_default": "PUBLIC",
        },
    )


def main() -> None:
    tmp_path = Path(tempfile.mkdtemp(prefix="qr-networking-v2-"))
    httpd = None
    try:
        server.DB_PATH = tmp_path / "networking_v2.sqlite3"
        server.BACKUP_DIR = tmp_path / "backups"
        server.AppHandler.log_message = lambda self, format, *args: None
        server.init_db()
        server.seed_if_empty()

        httpd = server.OperationalHTTPServer(("127.0.0.1", 0), server.AppHandler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{httpd.server_address[1]}"

        event = request(base, "POST", "/api/events", {"actor": "Admin", "name": "Discovery Expo", "status": "published"}, 201)
        second_event = request(base, "POST", "/api/events", {"actor": "Admin", "name": "Discovery aislado", "status": "published"}, 201)
        disabled_event = request(base, "POST", "/api/events", {"actor": "Admin", "name": "Discovery apagado", "status": "published"}, 201)
        event_id = int(event["id"])
        second_event_id = int(second_event["id"])
        disabled_event_id = int(disabled_event["id"])
        request(
            base,
            "POST",
            "/api/networking/config",
            {"actor": "Admin", "event_id": event_id, "networking_profile_mode": "ORGANIZATION_FIRST", "networking_discovery_enabled": 1, "networking_discovery_batch_size": 3, "networking_discovery_exploration_frequency": 3},
        )
        request(base, "POST", "/api/networking/config", {"actor": "Admin", "event_id": second_event_id, "networking_profile_mode": "PERSON_FIRST"})
        request(base, "POST", "/api/networking/config", {"actor": "Admin", "event_id": disabled_event_id, "networking_discovery_enabled": 0})

        taxonomy = {
            "actor": "Admin",
            "event_id": event_id,
            "concepts": [
                {"code": "INDUSTRY_CONSTRUCTION", "type": "INDUSTRY", "label": "Construccion", "enabled": True},
                {"code": "INDUSTRY_ENERGY", "type": "INDUSTRY", "label": "Energia", "enabled": True},
                {"code": "SPECIALTY_STRUCTURES", "type": "SPECIALTY", "label": "Estructuras", "enabled": True},
                {"code": "OFFER_CONCRETE", "type": "OFFER", "label": "Hormigon elaborado", "enabled": True},
                {"code": "OFFER_SOFTWARE", "type": "OFFER", "label": "Software para obras", "enabled": True},
                {"code": "SEEK_CONCRETE", "type": "SEEK", "label": "Hormigon elaborado", "enabled": True},
                {"code": "SEEK_CLIENTS", "type": "SEEK", "label": "Clientes", "enabled": True},
                {"code": "INTEREST_INFRA", "type": "INTEREST", "label": "Infraestructura", "enabled": True},
            ],
        }
        request(base, "POST", "/api/networking/taxonomy", taxonomy)
        request(base, "POST", "/api/networking/taxonomy", {"actor": "Admin", "event_id": second_event_id, "concepts": taxonomy["concepts"]})

        people = {}
        for key, first, last, email in [
            ("owner", "Ana", "Compras", "ana.v2@example.test"),
            ("concrete", "Bruno", "Hormigon", "bruno.v2@example.test"),
            ("procurement", "Carla", "Compras", "carla.v2@example.test"),
            ("explore", "Diego", "Energia", "diego.v2@example.test"),
            ("hidden", "Eva", "Oculta", "eva.v2@example.test"),
            ("external", "Fede", "Externo", "fede.v2@example.test"),
        ]:
            people[key] = request(base, "POST", "/api/register", {"actor": "Recepcion", "event_id": event_id, "first_name": first, "last_name": last, "email": email, "type": "General"}, 201)

        rows = [
            {
                "source_external_id": "owner-v2",
                "first_name": "Ana",
                "last_name": "Compras",
                "email": "ana.v2@example.test",
                "organization": "Constructora Norte",
                "organization_activity": "Construccion",
                "title": "Jefa de abastecimiento",
                "function": "PROCUREMENT",
                "seek_concepts": ["Hormigon elaborado"],
                "offer_concepts": ["Software para obras"],
                "channels": [{"type": "website", "value": "https://norte.example", "visibility": "PUBLIC", "scope": "ORGANIZATION"}],
            },
            {
                "source_external_id": "concrete-v2",
                "first_name": "Bruno",
                "last_name": "Hormigon",
                "email": "bruno.v2@example.test",
                "organization": "Hormigonera Confluencia",
                "organization_activity": "Construccion",
                "organization_specialty": "Estructuras",
                "title": "Gerente comercial",
                "function": "COMMERCIAL",
                "offer_concepts": ["Hormigon elaborado"],
                "channels": [
                    {"type": "website", "value": "https://hormigon.example", "visibility": "PUBLIC", "scope": "ORGANIZATION"},
                    {"type": "email", "value": "privado@example.test", "visibility": "HIDDEN", "scope": "PERSONAL"},
                ],
            },
            {
                "source_external_id": "proc-v2",
                "first_name": "Carla",
                "last_name": "Compras",
                "email": "carla.v2@example.test",
                "organization": "Metalurgica Sur",
                "organization_activity": "Construccion",
                "title": "Compras tecnicas",
                "function": "PROCUREMENT",
                "interest_concepts": ["Infraestructura"],
                "channels": [{"type": "website", "value": "https://metal.example", "visibility": "PUBLIC", "scope": "ORGANIZATION"}],
            },
            {
                "source_external_id": "explore-v2",
                "first_name": "Diego",
                "last_name": "Energia",
                "email": "diego.v2@example.test",
                "organization": "Energia Austral",
                "organization_activity": "Energia",
                "title": "Director",
                "function": "EXECUTIVE",
                "offer_concepts": ["Software para obras"],
                "channels": [{"type": "website", "value": "https://energia.example", "visibility": "PUBLIC", "scope": "ORGANIZATION"}],
            },
            {
                "source_external_id": "hidden-v2",
                "first_name": "Eva",
                "last_name": "Oculta",
                "email": "eva.v2@example.test",
                "organization": "Org Oculta",
                "organization_activity": "Construccion",
                "offer_concepts": ["Hormigon elaborado"],
                "channels": [{"type": "website", "value": "https://hidden.example", "visibility": "PUBLIC", "scope": "ORGANIZATION"}],
            },
        ]
        request(base, "POST", "/api/networking/import", {"actor": "Admin", "event_id": event_id, "source_system": "BITORA", "rows": rows})
        for key, function in [("owner", "PROCUREMENT"), ("concrete", "COMMERCIAL"), ("procurement", "PROCUREMENT"), ("explore", "EXECUTIVE"), ("hidden", "COMMERCIAL")]:
            onboard(base, people[key]["token"], event_id, function=function, representative_visible=(key != "concrete"))

        with server.connect() as db:
            db.execute(
                "UPDATE networking_intents SET profile_visible = 0 WHERE participation_id = (SELECT id FROM networking_event_participations WHERE event_id = ? AND source_external_id = 'hidden-v2')",
                (event_id,),
            )

        not_ready = request(base, "GET", f"/api/networking/discovery?token={people['owner']['token']}")
        assert_true(not_ready["status"] == "NOT_CONFIGURED" and not_ready["items"] == [], "Discovery no configurado no debe abrir stream")
        owner_ready = request(
            base,
            "POST",
            "/api/networking/discovery-onboarding",
            {
                "token": people["owner"]["token"],
                "event_id": event_id,
                "seeks": ["Hormigon elaborado"],
                "offers": ["Software para obras"],
                "company_types": ["INDUSTRY_CONSTRUCTION"],
                "desired_functions": ["PROCUREMENT"],
                "objectives": ["Infraestructura"],
                "discovery_diversity": False,
            },
        )
        assert_true(owner_ready["participation"]["active"] and owner_ready["participation"]["discovery"]["ready"], "Discovery ready no debe cambiar ACTIVE/basic credential")

        stream = request(base, "GET", f"/api/networking/discovery?token={people['owner']['token']}&limit=10000")
        assert_true(len(stream["items"]) <= 5, "endpoint Discovery permite lote tipo directorio")
        first = first_profile(stream)
        reason_codes = {reason["code"] for reason in stream["items"][0]["reasons"]}
        assert_true(first["public_profile_id"] != owner_ready["participation"]["public_profile_id"], "Discovery mostro self")
        assert_true(first["organization"] == "Hormigonera Confluencia", "seek/offer directo no fue priorizado")
        assert_true("SEEK_OFFER_MATCH" in reason_codes, "resultado directo no explica seek/offer")
        assert_true("relevance" not in json.dumps(stream).lower() and "score" not in json.dumps(stream).lower(), "Discovery expuso precision interna")
        assert_true("email" not in {channel["type"] for channel in first["channels"]}, "Discovery expuso canal oculto")
        assert_true("profile_visible" not in json.dumps(stream), "Discovery expuso banderas internas de privacidad")

        skip = request(base, "POST", "/api/networking/discovery-action", {"token": people["owner"]["token"], "action": "skip", "public_profile_id": first["public_profile_id"]})
        assert_true(skip["ok"] and not skip.get("contact_id"), "Skip creo contacto o fallo")
        after_skip_first = first_profile(skip["next"])
        assert_true(after_skip_first["public_profile_id"] != first["public_profile_id"], "Skip repitio inmediatamente el mismo perfil")

        save = request(base, "POST", "/api/networking/discovery-action", {"token": people["owner"]["token"], "action": "save", "public_profile_id": after_skip_first["public_profile_id"]})
        assert_true(save["contact_id"] and save["created"], "Save Discovery no creo contacto canonico")
        duplicate_save = request(base, "POST", "/api/networking/discovery-action", {"token": people["owner"]["token"], "action": "save", "public_profile_id": after_skip_first["public_profile_id"]})
        assert_true(not duplicate_save["created"] and duplicate_save["contact_id"] == save["contact_id"], "Save Discovery duplico contacto")
        contacts = request(base, "GET", f"/api/networking/contacts?token={people['owner']['token']}")
        assert_true(any(item["contact_id"] == save["contact_id"] for item in contacts["contacts"]), "Contacto Discovery no aparece en Mis contactos")

        request(
            base,
            "POST",
            "/api/networking/discovery-onboarding",
            {
                "token": people["owner"]["token"],
                "event_id": event_id,
                "seeks": ["Hormigon elaborado"],
                "offers": ["Software para obras"],
                "company_types": ["INDUSTRY_CONSTRUCTION"],
                "desired_functions": ["PROCUREMENT"],
                "objectives": ["Infraestructura"],
                "discovery_diversity": True,
            },
        )
        diversity_stream = request(base, "GET", f"/api/networking/discovery?token={people['owner']['token']}")
        assert_true(diversity_stream["ready"], "Discovery con diversidad no queda listo")

        exhausted_count = 0
        seen = set()
        current = diversity_stream
        while current.get("items") and exhausted_count < 10:
            target = current["items"][0]["profile"]["public_profile_id"]
            assert_true(target not in seen, "Discovery repitio un perfil antes de agotar")
            seen.add(target)
            current = request(base, "POST", "/api/networking/discovery-action", {"token": people["owner"]["token"], "action": "skip", "public_profile_id": target})["next"]
            exhausted_count += 1
        assert_true(current.get("exhausted"), "Discovery no devuelve estado de agotamiento")

        ext = request(
            base,
            "POST",
            "/api/networking/external-register",
            {
                "event_id": event_id,
                "first_name": "Fede",
                "last_name": "Externo",
                "email": "fede.v2@example.test",
                "organization": "Logistica Andina",
                "organization_activity": "Logistica aplicada",
                "offers": "Transporte de materiales",
            },
            201,
        )
        onboard(base, ext["owner_token"], event_id, function="OPERATIONS")
        with server.connect() as db:
            external_row = db.execute(
                "SELECT id FROM networking_event_participations WHERE event_id = ? AND source_system = 'EXTERNAL_FORM'",
                (event_id,),
            ).fetchone()
            assert_true(bool(external_row), "Participante externo no usa arquitectura canonica")

        second_reg = request(base, "POST", "/api/register", {"actor": "Recepcion", "event_id": second_event_id, "first_name": "Ana", "last_name": "Compras", "email": "ana.v2b@example.test", "type": "General"}, 201)
        request(base, "POST", "/api/networking/import", {"actor": "Admin", "event_id": second_event_id, "rows": [{"source_external_id": "ana-second", "first_name": "Ana", "last_name": "Compras", "email": "ana.v2b@example.test", "organization": "Otra Org", "seek_concepts": ["Clientes"], "offer_concepts": ["Software para obras"]}]})
        onboard(base, second_reg["token"], second_event_id, function="MARKETING")
        request(base, "POST", "/api/networking/discovery-onboarding", {"token": second_reg["token"], "event_id": second_event_id, "seeks": ["Clientes"], "offers": ["Software para obras"], "company_types": ["INDUSTRY_ENERGY"], "desired_functions": ["MARKETING"], "objectives": ["Infraestructura"], "discovery_diversity": True})
        second_session = request(base, "GET", f"/api/networking/session?token={second_reg['token']}&event_id={second_event_id}")
        assert_true(second_session["participation"]["discovery"]["desired_functions"] == ["MARKETING"], "Preferencias Discovery se filtraron entre eventos")

        disabled_reg = request(base, "POST", "/api/register", {"actor": "Recepcion", "event_id": disabled_event_id, "first_name": "Dina", "last_name": "Off", "email": "dina.v2@example.test", "type": "General"}, 201)
        request(base, "POST", "/api/networking/import", {"actor": "Admin", "event_id": disabled_event_id, "rows": [{"source_external_id": "disabled", "first_name": "Dina", "last_name": "Off", "email": "dina.v2@example.test", "organization": "Off Org", "offer_concepts": ["Software para obras"], "seek_concepts": ["Clientes"]}]})
        onboard(base, disabled_reg["token"], disabled_event_id)
        request(base, "POST", "/api/networking/discovery-onboarding", {"token": disabled_reg["token"], "event_id": disabled_event_id, "seeks": ["Clientes"], "offers": ["Software para obras"], "company_types": ["INDUSTRY_CONSTRUCTION"], "desired_functions": ["COMMERCIAL"], "objectives": ["Infraestructura"], "discovery_diversity": True})
        disabled_stream = request(base, "GET", f"/api/networking/discovery?token={disabled_reg['token']}")
        assert_true(disabled_stream["status"] == "DISABLED" and disabled_stream["items"] == [], "Discovery deshabilitado promete stream")

        reimport_rows = [dict(row) for row in rows]
        reimport_rows[1]["organization_description"] = "Descripcion actualizada por fuente."
        request(base, "POST", "/api/networking/import", {"actor": "Admin", "event_id": event_id, "source_system": "BITORA", "rows": reimport_rows})
        session_after_reimport = request(base, "GET", f"/api/networking/session?token={people['owner']['token']}&event_id={event_id}")
        assert_true(session_after_reimport["participation"]["discovery"]["ready"], "Reimport destruyo preferencias Discovery")
        contacts_after_reimport = request(base, "GET", f"/api/networking/contacts?token={people['owner']['token']}")
        assert_true(any(item["contact_id"] == save["contact_id"] for item in contacts_after_reimport["contacts"]), "Reimport destruyo contacto Discovery")

        with server.connect() as db:
            shown = db.execute("SELECT COUNT(*) AS c FROM networking_interaction_events WHERE event_id = ? AND event_type = 'discovery_shown'", (event_id,)).fetchone()["c"]
            skipped = db.execute("SELECT COUNT(*) AS c FROM networking_interaction_events WHERE event_id = ? AND event_type = 'discovery_skipped'", (event_id,)).fetchone()["c"]
            saved = db.execute("SELECT COUNT(*) AS c FROM networking_interaction_events WHERE event_id = ? AND event_type = 'discovery_saved'", (event_id,)).fetchone()["c"]
            hidden_seen = db.execute(
                """
                SELECT COUNT(*) AS c
                FROM networking_interaction_events ie
                JOIN networking_event_participations nep ON nep.id = ie.target_participation_id
                WHERE ie.event_id = ? AND nep.source_external_id = 'hidden-v2'
                """,
                (event_id,),
            ).fetchone()["c"]
            assert_true(shown > 0 and skipped > 0 and saved > 0, "Historial Discovery no registro shown/skip/save")
            assert_true(hidden_seen == 0, "Participante oculto aparecio en Discovery")
            original_interactions = db.execute("SELECT COUNT(*) AS c FROM networking_interaction_events WHERE event_id = ?", (event_id,)).fetchone()["c"]
            original_contacts = db.execute("SELECT COUNT(*) AS c FROM networking_contacts WHERE event_id = ?", (event_id,)).fetchone()["c"]

        backup_dir = tmp_path / "event-backups"
        backup_service = EventBackupService(backup_dir, server.connect, server.DB_LOCK, "networking-v2-test")
        restore_service = EventRestoreService(server.connect, server.DB_LOCK, token_factory(), server.now_iso, app_version="test", backup_service=backup_service)
        bundle = backup_service.create_event_bundle(event_id, "Admin")
        restored = restore_service.restore_bytes(bundle.read_bytes(), actor="Admin", mode="new_event")
        restored_event_id = int(restored["event_id"])
        with server.connect() as db:
            restored_interactions = db.execute("SELECT COUNT(*) AS c FROM networking_interaction_events WHERE event_id = ?", (restored_event_id,)).fetchone()["c"]
            restored_contacts = db.execute("SELECT COUNT(*) AS c FROM networking_contacts WHERE event_id = ?", (restored_event_id,)).fetchone()["c"]
            restored_config = db.execute("SELECT networking_discovery_enabled, networking_discovery_batch_size FROM events WHERE id = ?", (restored_event_id,)).fetchone()
        assert_true(restored_interactions == original_interactions and restored_contacts == original_contacts, "Backup/restore no preservo estado Discovery")
        assert_true(int(restored_config["networking_discovery_enabled"]) == 1 and int(restored_config["networking_discovery_batch_size"]) == 3, "Backup/restore no preservo config Discovery")

        request(base, "GET", "/api/networking/directory", expect=404)
        request(base, "GET", "/api/networking/recommendations", expect=404)
        request(base, "GET", "/api/networking/discovery?token=", expect=404)
        ui_body, _ = request(base, "GET", "/networking.html", parse_json=False)
        ui_text = ui_body.decode("utf-8", "ignore").lower()
        assert_true("guardar contacto" in ui_text and "siguiente" in ui_text and "compatibilidad" not in ui_text and "score" not in ui_text, "UI Discovery expone score o no tiene acciones simples")
        source_blob = Path("backend/services/networking.py").read_text(encoding="utf-8").lower()
        assert_true("embedding" not in source_blob and "openai" not in source_blob and "compatibility" not in source_blob, "V2 introdujo AI/ML o fake precision")

        print("OK: BITORA Networking V2 discovery engine/smart contact guide")
    finally:
        if httpd:
            httpd.shutdown()
            httpd.server_close()
        shutil.rmtree(tmp_path, ignore_errors=True)


if __name__ == "__main__":
    main()
