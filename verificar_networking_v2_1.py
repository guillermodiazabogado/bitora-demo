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


def token_factory():
    counter = {"value": 0}

    def make_token() -> str:
        counter["value"] += 1
        return f"V21-RESTORE-{counter['value']:04d}"

    return make_token


def register(base: str, event_id: int, key: str) -> dict:
    return request(
        base,
        "POST",
        "/api/register",
        {"actor": "Recepcion", "event_id": event_id, "first_name": key.title(), "last_name": "Discovery", "email": f"{key}.v21@example.test", "type": "General"},
        201,
    )


def onboard(base: str, token: str, event_id: int, *, function: str = "COMMERCIAL") -> dict:
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
            "website": "https://contact.example",
            "channel_visibility_default": "PUBLIC",
        },
    )


def complete_discovery(base: str, token: str, event_id: int, *, diversity: bool = True, seek: str = "Hormigon elaborado") -> dict:
    return request(
        base,
        "POST",
        "/api/networking/discovery-onboarding",
        {
            "token": token,
            "event_id": event_id,
            "seeks": [seek],
            "offers": ["Software para obras"],
            "company_types": ["INDUSTRY_CONSTRUCTION"],
            "desired_functions": ["PROCUREMENT"],
            "objectives": ["Infraestructura"],
            "discovery_diversity": diversity,
        },
    )


def first_item(stream: dict) -> dict:
    assert_true(stream.get("items"), f"Discovery sin items: {stream}")
    return stream["items"][0]


def skip_first(base: str, token: str, stream: dict) -> dict:
    profile_id = first_item(stream)["profile"]["public_profile_id"]
    return request(base, "POST", "/api/networking/discovery-action", {"token": token, "action": "skip", "public_profile_id": profile_id})


def concept_setup(base: str, event_id: int) -> None:
    request(
        base,
        "POST",
        "/api/networking/taxonomy",
        {
            "actor": "Admin",
            "event_id": event_id,
            "concepts": [
                {"code": "INDUSTRY_CONSTRUCTION", "type": "INDUSTRY", "label": "Construccion", "enabled": True},
                {"code": "INDUSTRY_ENERGY", "type": "INDUSTRY", "label": "Energia", "enabled": True},
                {"code": "OFFER_CONCRETE", "type": "OFFER", "label": "Hormigon elaborado", "enabled": True},
                {"code": "OFFER_SOFTWARE", "type": "OFFER", "label": "Software para obras", "enabled": True},
                {"code": "SEEK_CONCRETE", "type": "SEEK", "label": "Hormigon elaborado", "enabled": True},
                {"code": "SEEK_CLIENTS", "type": "SEEK", "label": "Clientes", "enabled": True},
                {"code": "INTEREST_INFRA", "type": "INTEREST", "label": "Infraestructura", "enabled": True},
            ],
        },
    )


def import_profiles(base: str, event_id: int, keys: list[str]) -> None:
    org_by_key = {
        "owner": "Constructora Norte",
        "a1": "Hormigonera Central",
        "a2": "Hormigonera Central",
        "b": "Metalurgica Sur",
        "c": "Energia Austral",
        "d": "Constructora Patagonia",
        "e": "Servicios Andinos",
        "fresh": "Nueva Logistica",
        "external": "Externo Canonico",
        "powner": "Persona Norte",
        "pa1": "Persona Central",
        "pb": "Persona Sur",
    }
    rows = []
    for key in keys:
        is_owner = key == "owner"
        rows.append({
            "source_external_id": f"{key}-v21",
            "first_name": key.title(),
            "last_name": "Discovery",
            "email": f"{key}.v21@example.test",
            "organization": org_by_key[key],
            "organization_activity": "Energia" if key == "c" else "Construccion",
            "title": "Compras" if key == "b" else "Comercial",
            "function": "PROCUREMENT" if key == "b" else "COMMERCIAL",
            "seek_concepts": ["Clientes"] if not is_owner else ["Hormigon elaborado"],
            "offer_concepts": ["Software para obras"] if key == "c" else ["Hormigon elaborado"],
            "interest_concepts": ["Infraestructura"],
            "channels": [{"type": "website", "value": f"https://{key}.example", "visibility": "PUBLIC", "scope": "ORGANIZATION"}],
        })
    request(base, "POST", "/api/networking/import", {"actor": "Admin", "event_id": event_id, "source_system": "BITORA", "rows": rows})


def main() -> None:
    tmp_path = Path(tempfile.mkdtemp(prefix="qr-networking-v2-1-"))
    httpd = None
    try:
        server.DB_PATH = tmp_path / "networking_v2_1.sqlite3"
        server.BACKUP_DIR = tmp_path / "backups"
        server.AppHandler.log_message = lambda self, format, *args: None
        server.init_db()
        server.seed_if_empty()

        httpd = server.OperationalHTTPServer(("127.0.0.1", 0), server.AppHandler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{httpd.server_address[1]}"

        event = request(base, "POST", "/api/events", {"actor": "Admin", "name": "Discovery V21", "status": "published"}, 201)
        person_event = request(base, "POST", "/api/events", {"actor": "Admin", "name": "Person V21", "status": "published"}, 201)
        event_id = int(event["id"])
        person_event_id = int(person_event["id"])
        request(base, "POST", "/api/networking/config", {"actor": "Admin", "event_id": event_id, "networking_profile_mode": "ORGANIZATION_FIRST", "networking_discovery_enabled": 1, "networking_discovery_batch_size": 3, "networking_discovery_exploration_frequency": 3})
        request(base, "POST", "/api/networking/config", {"actor": "Admin", "event_id": person_event_id, "networking_profile_mode": "PERSON_FIRST", "networking_discovery_enabled": 1})
        concept_setup(base, event_id)
        concept_setup(base, person_event_id)

        registrations = {key: register(base, event_id, key) for key in ["owner", "a1", "a2", "b", "c", "d", "e"]}
        import_profiles(base, event_id, ["owner", "a1", "a2", "b", "c", "d", "e"])
        for key in registrations:
            onboard(base, registrations[key]["token"], event_id, function="PROCUREMENT" if key == "b" else "COMMERCIAL")
        owner_token = registrations["owner"]["token"]
        owner_ready = complete_discovery(base, owner_token, event_id, diversity=True)
        assert_true(owner_ready["participation"]["discovery"]["ready"], "Golden Ticket no dejo Discovery listo")

        stream = request(base, "GET", f"/api/networking/discovery?token={owner_token}&limit=10000")
        assert_true(len(stream["items"]) <= 5 and stream["phase"] == "fresh", "Discovery no mantiene API bounded/fresh")
        first = first_item(stream)
        first_id = first["profile"]["public_profile_id"]
        first_org = first["profile"]["organization"]
        assert_true(first["reasons"][0]["code"] in {"SEEK_OFFER_MATCH", "PREFERRED_SECTOR", "DESIRED_FUNCTION", "SHARED_OBJECTIVE", "EXPLORATION"}, "Reason invalida")
        assert_true("score" not in json.dumps(stream).lower() and "relevance" not in json.dumps(stream).lower(), "Discovery expone precision interna")

        double_skip = request(base, "POST", "/api/networking/discovery-action", {"token": owner_token, "action": "skip", "public_profile_id": first_id})
        repeated_skip = request(base, "POST", "/api/networking/discovery-action", {"token": owner_token, "action": "skip", "public_profile_id": first_id})
        second = first_item(double_skip["next"])
        assert_true(second["profile"]["public_profile_id"] != first_id, "Skip repitio inmediatamente el perfil")
        if any(item["profile"]["organization"] != first_org for item in stream["items"][1:]):
            assert_true(second["profile"]["organization"] != first_org, "Organizacion se repitio aunque habia alternativas")
        with server.connect() as db:
            skipped_count = db.execute(
                """
                SELECT COUNT(*) AS c FROM networking_interaction_events
                WHERE event_id = ? AND actor_participation_id = ? AND target_participation_id = (
                    SELECT id FROM networking_event_participations WHERE public_profile_id = ?
                ) AND event_type = 'discovery_skipped'
                """,
                (event_id, owner_ready["participation"]["participation_id"], first_id),
            ).fetchone()["c"]
        assert_true(skipped_count == 1 and repeated_skip["ok"], "Doble siguiente duplico skip")

        save_target = second["profile"]["public_profile_id"]
        saved = request(base, "POST", "/api/networking/discovery-action", {"token": owner_token, "action": "save", "public_profile_id": save_target})
        duplicate_saved = request(base, "POST", "/api/networking/discovery-action", {"token": owner_token, "action": "save", "public_profile_id": save_target})
        assert_true(saved["created"] and not duplicate_saved["created"] and saved["contact_id"] == duplicate_saved["contact_id"], "Guardar no es idempotente")

        qr_contact_target = first_item(saved["next"])["profile"]["public_profile_id"]
        request(base, "POST", "/api/networking/discovery-action", {"token": owner_token, "action": "skip", "public_profile_id": qr_contact_target})
        scan_contact = request(base, "POST", "/api/networking/scan", {"token": owner_token, "public_profile_id": qr_contact_target})
        assert_true(scan_contact["created"], "Contacto por QR no se creo")

        current = request(base, "GET", f"/api/networking/discovery?token={owner_token}")
        skipped_ids = {first_id, qr_contact_target}
        safety = 0
        while current.get("items") and current.get("phase") == "fresh" and safety < 12:
            target = first_item(current)["profile"]["public_profile_id"]
            skipped_ids.add(target)
            current = request(base, "POST", "/api/networking/discovery-action", {"token": owner_token, "action": "skip", "public_profile_id": target})["next"]
            safety += 1
        assert_true(current["status"] in {"RECYCLE", "EXHAUSTED"}, "Discovery no salio de fresh tras agotar frescos")
        if current["status"] == "RECYCLE":
            recycled = first_item(current)
            assert_true(recycled["phase"] == "recycle", "Recycle no se marca como fase")
            assert_true(recycled["profile"]["public_profile_id"] not in {save_target, qr_contact_target}, "Recycle devolvio contacto guardado/QR")
            assert_true(recycled["profile"]["public_profile_id"] in skipped_ids, "Recycle no devolvio un skipped viejo")

        recycle_seen = set()
        while current.get("items") and safety < 25:
            target = first_item(current)["profile"]["public_profile_id"]
            assert_true(target not in recycle_seen, "Recycle repitio candidato dentro del mismo ciclo")
            recycle_seen.add(target)
            current = request(base, "POST", "/api/networking/discovery-action", {"token": owner_token, "action": "skip", "public_profile_id": target})["next"]
            safety += 1
        assert_true(current["status"] == "EXHAUSTED" and current["items"] == [], "True exhaustion no es explicita")

        fresh_reg = register(base, event_id, "fresh")
        import_profiles(base, event_id, ["fresh"])
        onboard(base, fresh_reg["token"], event_id)
        after_import = request(base, "GET", f"/api/networking/discovery?token={owner_token}")
        assert_true(after_import["phase"] == "fresh" and first_item(after_import)["profile"]["organization"] == "Nueva Logistica", "Nuevo import no volvio como fresh")

        external = request(base, "POST", "/api/networking/external-register", {"event_id": event_id, "first_name": "External", "last_name": "Discovery", "email": "external.v21@example.test", "organization": "Externo Canonico", "organization_activity": "Construccion", "offers": "Hormigon elaborado"}, 201)
        onboard(base, external["owner_token"], event_id)
        external_stream = request(base, "GET", f"/api/networking/discovery?token={owner_token}")
        assert_true(any(item["profile"]["organization"] in {"Nueva Logistica", "Externo Canonico"} for item in external_stream["items"]), "Externo canonico no entra al pool")

        hidden_target = first_item(external_stream)["profile"]["public_profile_id"]
        request(base, "POST", "/api/networking/discovery-action", {"token": owner_token, "action": "skip", "public_profile_id": hidden_target})
        with server.connect() as db:
            db.execute(
                "UPDATE networking_intents SET profile_visible = 0 WHERE participation_id = (SELECT id FROM networking_event_participations WHERE public_profile_id = ?)",
                (hidden_target,),
            )
            db.execute(
                "UPDATE networking_event_participations SET participation_state = 'REVOKED' WHERE event_id = ? AND source_external_id = 'e-v21'",
                (event_id,),
            )
        privacy_stream = request(base, "GET", f"/api/networking/discovery?token={owner_token}")
        assert_true(hidden_target not in {item["profile"]["public_profile_id"] for item in privacy_stream["items"]}, "Privacy update no gano sobre recycle")
        assert_true("Servicios Andinos" not in {item["profile"]["organization"] for item in privacy_stream["items"]}, "Revoked participant sigue apareciendo")

        request(base, "POST", "/api/networking/discovery-onboarding", {"token": owner_token, "event_id": event_id, "seeks": ["Clientes"], "offers": ["Software para obras"], "company_types": ["INDUSTRY_ENERGY"], "desired_functions": ["COMMERCIAL"], "objectives": ["Infraestructura"], "discovery_diversity": True})
        updated_pref_stream = request(base, "GET", f"/api/networking/discovery?token={owner_token}")
        assert_true(updated_pref_stream["ready"], "Editar preferencias rompio Discovery")

        person_regs = {key: register(base, person_event_id, key) for key in ["powner", "pa1", "pb"]}
        import_profiles(base, person_event_id, ["powner", "pa1", "pb"])
        for reg in person_regs.values():
            onboard(base, reg["token"], person_event_id)
        complete_discovery(base, person_regs["powner"]["token"], person_event_id, diversity=True)
        person_stream = request(base, "GET", f"/api/networking/discovery?token={person_regs['powner']['token']}")
        assert_true(person_stream["items"], "Person First no devuelve individuos")

        with server.connect() as db:
            original_interactions = db.execute("SELECT COUNT(*) AS c FROM networking_interaction_events WHERE event_id = ?", (event_id,)).fetchone()["c"]
            original_contacts = db.execute("SELECT COUNT(*) AS c FROM networking_contacts WHERE event_id = ?", (event_id,)).fetchone()["c"]
        backup_dir = tmp_path / "event-backups"
        backup_service = EventBackupService(backup_dir, server.connect, server.DB_LOCK, "networking-v21-test")
        restore_service = EventRestoreService(server.connect, server.DB_LOCK, token_factory(), server.now_iso, app_version="test", backup_service=backup_service)
        bundle = backup_service.create_event_bundle(event_id, "Admin")
        restored = restore_service.restore_bytes(bundle.read_bytes(), actor="Admin", mode="new_event")
        restored_event_id = int(restored["event_id"])
        with server.connect() as db:
            restored_interactions = db.execute("SELECT COUNT(*) AS c FROM networking_interaction_events WHERE event_id = ?", (restored_event_id,)).fetchone()["c"]
            restored_contacts = db.execute("SELECT COUNT(*) AS c FROM networking_contacts WHERE event_id = ?", (restored_event_id,)).fetchone()["c"]
        assert_true(restored_interactions == original_interactions and restored_contacts == original_contacts, "Backup/restore no preservo rotacion/contactos")

        request(base, "GET", "/api/networking/directory", expect=404)
        request(base, "GET", "/api/networking/recommendations", expect=404)
        capped = request(base, "GET", f"/api/networking/discovery?token={owner_token}&limit=10000")
        assert_true(len(capped["items"]) <= 5, "V2.1 debilito el limite anti-directorio")

        ui_body, _ = request(base, "GET", "/networking.html", parse_json=False)
        ui_text = ui_body.decode("utf-8", "ignore")
        for needle in ["discovery-loading", "Volver a intentar", "Guardado en Mis Contactos", "Ver perfil", "touch-action", "@media (max-width: 560px)"]:
            assert_true(needle in ui_text, f"UX movil falta: {needle}")
        assert_true("compatibilidad" not in ui_text.lower() and "score" not in ui_text.lower(), "UI movil expone fake intelligence")

        source_blob = Path("backend/services/networking.py").read_text(encoding="utf-8").lower()
        assert_true("embedding" not in source_blob and "openai" not in source_blob and "vector" not in source_blob, "V2.1 introdujo AI/ML")

        print("OK: BITORA Networking V2.1 discovery rotation/session/mobile UX")
    finally:
        if httpd:
            httpd.shutdown()
            httpd.server_close()
        shutil.rmtree(tmp_path, ignore_errors=True)


if __name__ == "__main__":
    main()
