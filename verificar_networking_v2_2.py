from __future__ import annotations

import csv
import io
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
        return f"V22-RESTORE-{counter['value']:04d}"

    return make_token


def register(base: str, event_id: int, key: str) -> dict:
    return request(
        base,
        "POST",
        "/api/register",
        {"actor": "Recepcion", "event_id": event_id, "first_name": key.title(), "last_name": "Ops", "email": f"{key}.v22@example.test", "type": "General"},
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


def discovery_ready(base: str, token: str, event_id: int, *, diversity: bool = True) -> dict:
    return request(
        base,
        "POST",
        "/api/networking/discovery-onboarding",
        {
            "token": token,
            "event_id": event_id,
            "seeks": ["Hormigon elaborado", "Geotecnia aplicada"],
            "offers": ["Software para obras"],
            "company_types": ["INDUSTRY_CONSTRUCTION"],
            "desired_functions": ["PROCUREMENT"],
            "objectives": ["Infraestructura"],
            "discovery_diversity": diversity,
        },
    )


def setup_taxonomy(base: str, event_id: int) -> None:
    request(
        base,
        "POST",
        "/api/networking/taxonomy",
        {
            "actor": "Admin",
            "event_id": event_id,
            "concepts": [
                {"code": "INDUSTRY_CONSTRUCTION", "type": "INDUSTRY", "label": "Construccion", "enabled": True},
                {"code": "OFFER_CONCRETE", "type": "OFFER", "label": "Hormigon elaborado", "enabled": True},
                {"code": "OFFER_SOFTWARE", "type": "OFFER", "label": "Software para obras", "enabled": True},
                {"code": "SEEK_CONCRETE", "type": "SEEK", "label": "Hormigon elaborado", "enabled": True},
                {"code": "SEEK_CLIENTS", "type": "SEEK", "label": "Clientes", "enabled": True},
                {"code": "INTEREST_INFRA", "type": "INTEREST", "label": "Infraestructura", "enabled": True},
            ],
        },
    )


def import_profiles(base: str, event_id: int, keys: list[str]) -> None:
    rows = []
    for key in keys:
        rows.append(
            {
                "source_external_id": f"{key}-v22",
                "first_name": key.title(),
                "last_name": "Ops",
                "email": f"{key}.v22@example.test",
                "organization": {
                    "owner": "Constructora Operativa",
                    "supplier": "Hormigonera Operativa",
                    "buyer": "Compras Patagonia",
                    "external": "Geotecnia Externa",
                    "hidden": "Privada Oculta",
                }.get(key, f"Org {key}"),
                "organization_activity": "Construccion",
                "title": "Compras" if key == "buyer" else "Comercial",
                "function": "PROCUREMENT" if key == "buyer" else "COMMERCIAL",
                "seek_concepts": ["Clientes"] if key != "owner" else ["Hormigon elaborado"],
                "offer_concepts": ["Hormigon elaborado"] if key == "supplier" else ["Software para obras"],
                "interest_concepts": ["Infraestructura"],
                "channels": [{"type": "website", "value": f"https://{key}.example", "visibility": "PUBLIC", "scope": "ORGANIZATION"}],
            }
        )
    request(base, "POST", "/api/networking/import", {"actor": "Admin", "event_id": event_id, "source_system": "BITORA", "rows": rows})


def first_profile_id(stream: dict) -> str:
    assert_true(stream.get("items"), f"Discovery sin items: {stream}")
    return stream["items"][0]["profile"]["public_profile_id"]


def main() -> None:
    tmp_path = Path(tempfile.mkdtemp(prefix="qr-networking-v2-2-"))
    httpd = None
    try:
        server.DB_PATH = tmp_path / "networking_v2_2.sqlite3"
        server.BACKUP_DIR = tmp_path / "backups"
        server.AppHandler.log_message = lambda self, format, *args: None
        server.init_db()
        server.seed_if_empty()

        httpd = server.OperationalHTTPServer(("127.0.0.1", 0), server.AppHandler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{httpd.server_address[1]}"

        event = request(base, "POST", "/api/events", {"actor": "Admin", "name": "Operaciones Networking", "status": "published"}, 201)
        isolated = request(base, "POST", "/api/events", {"actor": "Admin", "name": "Operaciones Aisladas", "status": "published"}, 201)
        disabled = request(base, "POST", "/api/events", {"actor": "Admin", "name": "Networking sin Discovery", "status": "published"}, 201)
        empty = request(base, "POST", "/api/events", {"actor": "Admin", "name": "Evento nuevo", "status": "draft"}, 201)
        event_id = int(event["id"])
        isolated_id = int(isolated["id"])
        disabled_id = int(disabled["id"])
        empty_id = int(empty["id"])

        empty_ops = request(base, "GET", f"/api/networking/operations?actor=Admin&event_id={empty_id}")
        assert_true(empty_ops["participants"]["total"] == 0 and empty_ops["status"] == "NEEDS_ATTENTION", "Evento nuevo no muestra preparacion honesta")
        assert_true(any(w["code"] == "NO_PARTICIPANTS" for w in empty_ops["warnings"]), "Evento sin participantes no advierte preparacion")

        request(base, "POST", "/api/networking/config", {"actor": "Admin", "event_id": event_id, "networking_profile_mode": "ORGANIZATION_FIRST", "networking_discovery_enabled": 1, "networking_discovery_batch_size": 2, "networking_discovery_exploration_frequency": 3})
        request(base, "POST", "/api/networking/config", {"actor": "Admin", "event_id": isolated_id, "networking_profile_mode": "PERSON_FIRST", "networking_discovery_enabled": 1})
        request(base, "POST", "/api/networking/config", {"actor": "Admin", "event_id": disabled_id, "networking_discovery_enabled": 0})
        setup_taxonomy(base, event_id)
        setup_taxonomy(base, isolated_id)

        registrations = {key: register(base, event_id, key) for key in ["owner", "supplier", "buyer", "hidden"]}
        import_profiles(base, event_id, ["owner", "supplier", "buyer", "hidden"])
        passive_ops = request(base, "GET", f"/api/networking/operations?actor=Admin&event_id={event_id}")
        assert_true(passive_ops["participants"]["total"] == 4 and passive_ops["participants"]["passive"] == 4, "PASSIVE/importados no se cuentan distinto")
        assert_true(passive_ops["participants"]["active"] == 0, "Import no debe activar participantes")

        owner = onboard(base, registrations["owner"]["token"], event_id)
        supplier = onboard(base, registrations["supplier"]["token"], event_id, function="COMMERCIAL")
        buyer = onboard(base, registrations["buyer"]["token"], event_id, function="PROCUREMENT")
        hidden = onboard(base, registrations["hidden"]["token"], event_id)
        owner_token = registrations["owner"]["token"]
        supplier_profile = supplier["participation"]["public_profile_id"]
        buyer_profile = buyer["participation"]["public_profile_id"]
        hidden_profile = hidden["participation"]["public_profile_id"]

        with server.connect() as db:
            db.execute("UPDATE networking_intents SET discoverable = 0, profile_visible = 0 WHERE participation_id = ?", (hidden["participation"]["participation_id"],))

        owner_discovery = discovery_ready(base, owner_token, event_id)
        assert_true((owner_discovery.get("participation") or {}).get("discovery", {}).get("ready"), f"Golden Ticket owner no quedo listo: {owner_discovery}")
        supplier_discovery = request(base, "POST", "/api/networking/discovery-onboarding", {"token": registrations["supplier"]["token"], "event_id": event_id, "seeks": ["Clientes"], "offers": ["Hormigon elaborado"], "company_types": ["INDUSTRY_CONSTRUCTION"], "desired_functions": ["PROCUREMENT"], "objectives": ["Infraestructura"], "discovery_diversity": True})
        assert_true((supplier_discovery.get("participation") or {}).get("discovery", {}).get("ready"), f"Golden Ticket supplier no quedo listo: {supplier_discovery}")

        stream = request(base, "GET", f"/api/networking/discovery?token={owner_token}")
        target = first_profile_id(stream)
        assert_true(hidden_profile not in {item["profile"]["public_profile_id"] for item in stream["items"]}, "Discovery expuso perfil oculto")
        save = request(base, "POST", "/api/networking/discovery-action", {"token": owner_token, "action": "save", "public_profile_id": target})
        assert_true(save["contact_id"], "Discovery no creo contacto canonico")
        request(base, "POST", "/api/networking/discovery-action", {"token": owner_token, "action": "save", "public_profile_id": target})

        qr_target = buyer_profile if target == supplier_profile else supplier_profile
        scan = request(base, "POST", "/api/networking/scan", {"token": owner_token, "public_profile_id": qr_target})
        assert_true(scan["contact_id"], "QR/scan no creo contacto canonico")

        exhausted = request(base, "GET", f"/api/networking/discovery?token={owner_token}")
        assert_true(exhausted["status"] in {"EXHAUSTED", "RECYCLE", "READY"}, "Discovery devolvio estado invalido tras contactos")
        if exhausted["status"] != "EXHAUSTED":
            request(base, "POST", "/api/networking/discovery-action", {"token": owner_token, "action": "skip", "public_profile_id": first_profile_id(exhausted)})
            exhausted = request(base, "GET", f"/api/networking/discovery?token={owner_token}")
        assert_true(exhausted["status"] == "EXHAUSTED", "No se registro agotamiento operativo")

        external = request(base, "POST", "/api/networking/external-register", {"event_id": event_id, "first_name": "External", "last_name": "Ops", "email": "external.v22@example.test", "organization": "Geotecnia Externa", "organization_activity": "Construccion", "offers": "Geotecnia aplicada"}, 201)
        onboard(base, external["owner_token"], event_id)
        recovery = request(base, "GET", f"/api/networking/discovery?token={owner_token}")
        assert_true(recovery["items"], "Nuevo participante externo no entro al pool vivo")

        disabled_reg = register(base, disabled_id, "disabled")
        import_profiles(base, disabled_id, ["disabled"])
        onboard(base, disabled_reg["token"], disabled_id)
        disabled_ops = request(base, "GET", f"/api/networking/operations?actor=Admin&event_id={disabled_id}")
        assert_true(not disabled_ops["discovery"]["enabled"], "Discovery deshabilitado no queda claro")
        assert_true(any(w["code"] == "DISCOVERY_DISABLED" and w["severity"] == "INFO" for w in disabled_ops["warnings"]), "Discovery deshabilitado fue tratado como falla")

        isolated_reg = register(base, isolated_id, "isolated")
        import_profiles(base, isolated_id, ["isolated"])
        onboard(base, isolated_reg["token"], isolated_id)
        isolated_ops = request(base, "GET", f"/api/networking/operations?actor=Admin&event_id={isolated_id}")
        assert_true(isolated_ops["participants"]["total"] == 1 and isolated_ops["networking"]["contacts_total"] == 0, "Metricas se filtraron entre eventos")

        ops = request(base, "GET", f"/api/networking/operations?actor=Admin&event_id={event_id}")
        assert_true(ops["participants"]["total"] == 5, "Total de participantes no incluye externos canonicos")
        assert_true(ops["participants"]["active"] == 5 and ops["participants"]["passive"] == 0, "ACTIVE/PASSIVE no permanecen distintos tras activacion externa")
        readiness_check = request(base, "GET", f"/api/networking/readiness?actor=Admin&event_id={event_id}")
        assert_true(
            ops["participants"]["ready"] == readiness_check["ready"] and ops["participants"]["incomplete"] == readiness_check["incomplete"],
            "Readiness no se agrega desde el evaluador V1.2",
        )
        assert_true(ops["discovery"]["enabled"] and ops["discovery"]["configured_participants"] >= 2, "Discovery configurado no se mide")
        assert_true(ops["discovery"]["profiles_shown"] >= 1 and ops["discovery"]["users"] >= 1, "Uso Discovery no sale del historial canonico")
        assert_true(ops["discovery"]["exhausted_users"] >= 1, "Agotamiento no se cuenta cuando esta registrado")
        assert_true(ops["networking"]["contacts_total"] >= 2, "Contactos canonicos no se agregan")
        assert_true(ops["networking"]["scan_contact_events"] >= 1 and ops["networking"]["discovery_saved_events"] >= 1, "Procedencia verificable de contactos no se agrega")
        assert_true(ops["vocabulary"]["active_concepts"] >= 5 and ops["vocabulary"]["unresolved_candidates"] >= 1, "Salud de vocabulario no refleja conceptos/candidatos")
        assert_true("definitions" in ops and "participants.active" in ops["definitions"], "Definiciones de metricas faltan")
        assert_true("score" not in json.dumps(ops).lower() and "ai" not in json.dumps(ops).lower(), "Operaciones agrega scoring/AI")
        assert_true("participants" in ops and "email" not in json.dumps(ops).lower() and hidden_profile not in json.dumps(ops), "Resumen operativo filtra datos privados o roster")

        request(base, "GET", f"/api/networking/operations?actor=public&event_id={event_id}", expect=403)
        request(base, "GET", f"/api/networking/operations.csv?actor=public&event_id={event_id}", expect=403)
        csv_body, content_type = request(base, "GET", f"/api/networking/operations.csv?actor=Admin&event_id={event_id}", parse_json=False)
        assert_true("text/csv" in content_type, "Export operativo no es CSV")
        csv_text = csv_body.decode("utf-8", "ignore")
        rows = list(csv.DictReader(io.StringIO(csv_text)))
        assert_true(len(rows) == 1 and int(rows[0]["participants_total"]) == ops["participants"]["total"], "Export debe ser resumen agregado de una fila")
        assert_true("external.v22@example.test" not in csv_text and "549" not in csv_text and "public_profile_id" not in csv_text, "Export operativo filtra canales o identificadores de directorio")

        request(base, "POST", "/api/networking/import", {"actor": "Admin", "event_id": event_id, "source_system": "BITORA", "rows": [{"source_external_id": "supplier-v22", "first_name": "Supplier", "last_name": "Ops Updated", "email": "supplier.v22@example.test", "organization": "Hormigonera Operativa", "organization_activity": "Construccion", "offer_concepts": ["Hormigon elaborado"], "channels": [{"type": "website", "value": "https://supplier-updated.example", "visibility": "PUBLIC", "scope": "ORGANIZATION"}]}]})
        after_reimport = request(base, "GET", f"/api/networking/operations?actor=Admin&event_id={event_id}")
        assert_true(after_reimport["networking"]["contacts_total"] >= ops["networking"]["contacts_total"], "Reimport destruyo contactos")
        assert_true(after_reimport["discovery"]["profiles_shown"] >= ops["discovery"]["profiles_shown"], "Reimport destruyo historial Discovery")

        backup_dir = tmp_path / "event-backups"
        backup_service = EventBackupService(backup_dir, server.connect, server.DB_LOCK, "networking-v22-test")
        restore_service = EventRestoreService(server.connect, server.DB_LOCK, token_factory(), server.now_iso, app_version="test", backup_service=backup_service)
        bundle = backup_service.create_event_bundle(event_id, "Admin")
        restored = restore_service.restore_bytes(bundle.read_bytes(), actor="Admin", mode="new_event")
        restored_ops = request(base, "GET", f"/api/networking/operations?actor=Admin&event_id={int(restored['event_id'])}")
        assert_true(restored_ops["networking"]["contacts_total"] == after_reimport["networking"]["contacts_total"], "Backup/restore no preserva contactos para operaciones")
        assert_true(restored_ops["discovery"]["profiles_shown"] == after_reimport["discovery"]["profiles_shown"], "Backup/restore no preserva historial Discovery para operaciones")

        admin_html, _ = request(base, "GET", "/networking-admin.html", parse_json=False)
        admin_text = admin_html.decode("utf-8", "ignore")
        for needle in ["Operaciones Networking", "Exportar CSV", "/api/networking/operations", "Solo agregados"]:
            assert_true(needle in admin_text, f"Admin operativo falta: {needle}")
        assert_true("/api/networking/directory" not in admin_text and "leaderboard" not in admin_text.lower(), "Admin agrega directorio o ranking")

        request(base, "GET", "/api/networking/directory", expect=404)
        request(base, "GET", "/api/networking/participants", expect=404)
        print("OK: BITORA Networking V2.2 organizer operations/commercial readiness")
    finally:
        if httpd:
            httpd.shutdown()
            httpd.server_close()
        shutil.rmtree(tmp_path, ignore_errors=True)


if __name__ == "__main__":
    main()
