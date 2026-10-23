from __future__ import annotations

import csv
import json
import shutil
import tempfile
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
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
        with urllib.request.urlopen(req, timeout=30) as response:
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


def token_factory(prefix: str):
    counter = {"value": 0}

    def make_token() -> str:
        counter["value"] += 1
        return f"{prefix}-{counter['value']:05d}"

    return make_token


def register(base: str, event_id: int, key: str, *, email: str | None = None) -> dict:
    return request(
        base,
        "POST",
        "/api/register",
        {
            "actor": "Recepcion",
            "event_id": event_id,
            "first_name": key.title(),
            "last_name": "Pilot",
            "email": email or f"{key}.v24@example.test",
            "type": "General",
        },
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


def complete_discovery(base: str, token: str, event_id: int, *, diversity: bool = True, seek: str = "Concrete services") -> dict:
    return request(
        base,
        "POST",
        "/api/networking/discovery-onboarding",
        {
            "token": token,
            "event_id": event_id,
            "seeks": [seek],
            "offers": ["Event operations"],
            "company_types": ["Construction"],
            "desired_functions": ["PROCUREMENT"],
            "objectives": ["Alliances"],
            "discovery_diversity": diversity,
        },
    )


def import_profiles(base: str, event_id: int, rows: list[dict], *, source: str = "BITORA") -> None:
    result = request(base, "POST", "/api/networking/import", {"actor": "Admin", "event_id": event_id, "source_system": source, "rows": rows})
    assert_true(result.get("ok") or result.get("created", 0) + result.get("updated", 0) > 0, f"Import Networking fallo: {result}")


def concept_setup(base: str, event_id: int) -> None:
    request(
        base,
        "POST",
        "/api/networking/taxonomy",
        {
            "actor": "Admin",
            "event_id": event_id,
            "concepts": [
                {"code": "INDUSTRY_CONSTRUCTION", "type": "INDUSTRY", "label": "Construction", "enabled": True},
                {"code": "INDUSTRY_ENERGY", "type": "INDUSTRY", "label": "Energy", "enabled": True},
                {"code": "OFFER_CONCRETE", "type": "OFFER", "label": "Concrete services", "enabled": True},
                {"code": "OFFER_LOGISTICS", "type": "OFFER", "label": "Logistics", "enabled": True},
                {"code": "OFFER_EVENT_OPS", "type": "OFFER", "label": "Event operations", "enabled": True},
                {"code": "SEEK_CONCRETE", "type": "SEEK", "label": "Concrete services", "enabled": True},
                {"code": "SEEK_CLIENTS", "type": "SEEK", "label": "Clients", "enabled": True},
                {"code": "SEEK_TECHNOLOGY", "type": "SEEK", "label": "Technology", "enabled": True},
                {"code": "INTEREST_ALLIANCES", "type": "INTEREST", "label": "Alliances", "enabled": True},
            ],
        },
    )


def pilot_rows(event_id: int, count: int, *, include_owner: bool = True, prefix: str = "pilot") -> list[dict]:
    rows: list[dict] = []
    if include_owner:
        rows.append({
            "source_external_id": f"{event_id}-{prefix}-owner",
            "first_name": "Owner",
            "last_name": "Pilot",
            "email": f"{prefix}.owner.v24@example.test",
            "organization": "Pilot Owner Org",
            "organization_activity": "Construction",
            "organization_specialty": "Event operations",
            "title": "Commercial Lead",
            "function": "COMMERCIAL",
            "seek_concepts": ["Concrete services"],
            "offer_concepts": ["Event operations"],
            "interest_concepts": ["Alliances"],
            "channels": [{"type": "website", "value": "https://owner.example", "visibility": "PUBLIC", "scope": "ORGANIZATION"}],
        })
    for index in range(count):
        org = f"Pilot Org {index % 80:03d}"
        activity = "Construction" if index % 3 else "Energy"
        offer = "Concrete services" if index % 4 else "Logistics"
        function = "PROCUREMENT" if index % 5 == 0 else "COMMERCIAL"
        visibility = "PRIVATE" if index % 47 == 0 else "PUBLIC"
        rows.append({
            "source_external_id": f"{event_id}-{prefix}-{index:04d}",
            "first_name": f"Person{index:04d}",
            "last_name": "Pilot",
            "email": f"{prefix}.{index:04d}.v24@example.test",
            "organization": org,
            "organization_activity": activity,
            "organization_specialty": offer,
            "title": "Compras" if function == "PROCUREMENT" else "Comercial",
            "function": function,
            "seek_concepts": ["Clients"] if index % 2 else ["Technology"],
            "offer_concepts": [offer],
            "interest_concepts": ["Alliances"],
            "channels": [{"type": "website", "value": f"https://{prefix}-{index}.example", "visibility": visibility, "scope": "ORGANIZATION"}],
        })
    return rows


def participant_by_email(email: str) -> dict:
    with server.connect() as db:
        row = db.execute(
            """
            SELECT nep.*
            FROM networking_event_participations nep
            JOIN people p ON p.id = nep.person_id
            WHERE p.email = ?
            """,
            (email,),
        ).fetchone()
        assert_true(row, f"No existe participacion para {email}")
        return dict(row)


def activate_event_targets(event_id: int) -> None:
    with server.DB_LOCK, server.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("UPDATE networking_event_participations SET participation_state = 'ACTIVE' WHERE event_id = ?", (event_id,))
        db.execute(
            """
            UPDATE networking_intents
            SET profile_visible = 1, discoverable = 1, channels_visible_default = 1
            WHERE participation_id IN (
                SELECT id FROM networking_event_participations WHERE event_id = ?
            )
            """,
            (event_id,),
        )
        db.execute("COMMIT")


def target_profiles(event_id: int, owner_id: int, limit: int = 8) -> list[dict]:
    with server.connect() as db:
        rows = db.execute(
            """
            SELECT networking_event_participations.id, networking_event_participations.public_profile_id
            FROM networking_event_participations
            JOIN networking_intents ni ON ni.participation_id = networking_event_participations.id
            WHERE networking_event_participations.event_id = ? AND networking_event_participations.id != ? AND participation_state = 'ACTIVE'
              AND ni.profile_visible = 1 AND ni.discoverable = 1
            ORDER BY networking_event_participations.id
            LIMIT ?
            """,
            (event_id, owner_id, limit),
        ).fetchall()
        return [dict(row) for row in rows]


def concurrent_requests(calls: list[tuple[str, str, str, dict | None, int]], *, workers: int = 20) -> list[object]:
    started = time.perf_counter()
    results = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(request, *call) for call in calls]
        for future in as_completed(futures):
            results.append(future.result())
    elapsed = time.perf_counter() - started
    return [results, elapsed]


def assert_static_parity() -> None:
    pairs = [
        ("networking.html", "Discovery participant shell"),
        ("networking-public.html", "Public profile shell"),
        ("networking-admin.html", "Organizer shell"),
        ("networking-register.html", "External registration shell"),
    ]
    root = Path(__file__).resolve().parent
    for filename, label in pairs:
        frontend = (root / "frontend" / filename).read_bytes()
        static = (root / "static" / filename).read_bytes()
        assert_true(frontend == static, f"Static parity rota en {label}: {filename}")


def first_item(stream: dict) -> dict:
    assert_true(stream.get("items"), f"Discovery sin items: {stream}")
    return stream["items"][0]


def mark(label: str) -> None:
    print(f"[v2.4] {label}", flush=True)


def main() -> None:
    tmp_path = Path(tempfile.mkdtemp(prefix="qr-networking-v2-4-"))
    httpd = None
    try:
        server.DB_PATH = tmp_path / "networking_v2_4.sqlite3"
        server.BACKUP_DIR = tmp_path / "backups"
        server.AppHandler.log_message = lambda self, format, *args: None
        server.init_db()
        server.seed_if_empty()
        assert_static_parity()
        mark("static parity and fresh DB ready")

        httpd = server.OperationalHTTPServer(("127.0.0.1", 0), server.AppHandler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{httpd.server_address[1]}"

        # Prelaunch public access stays gated, while owner/admin preview remains possible.
        pre_event = request(base, "POST", "/api/events", {"actor": "Admin", "name": "Prelaunch V24", "status": "published"}, 201)
        pre_event_id = int(pre_event["id"])
        pre_reg = register(base, pre_event_id, "pre")
        import_profiles(base, pre_event_id, [{
            "source_external_id": "pre-v24",
            "first_name": "Pre",
            "last_name": "Pilot",
            "email": "pre.v24@example.test",
            "organization": "Prelaunch Org",
            "organization_activity": "Construction",
            "title": "Comercial",
            "function": "COMMERCIAL",
            "channels": [{"type": "website", "value": "https://pre.example", "visibility": "PUBLIC", "scope": "ORGANIZATION"}],
        }])
        onboard(base, pre_reg["token"], pre_event_id)
        request(base, "POST", "/api/networking/brand", {"actor": "Admin", "event_id": pre_event_id, "networking_public_base_url": "https://pre.example.test", "networking_brand_title": "Prelaunch"})
        pre_profile = participant_by_email("pre.v24@example.test")["public_profile_id"]
        prelaunch = request(base, "GET", f"/api/networking/profile?profile_id={pre_profile}", expect=404)
        assert_true(prelaunch.get("status") == "NOT_LIVE", "Perfil publico prelaunch no queda protegido")
        owner_preview = request(base, "GET", f"/api/networking/profile?profile_id={pre_profile}&token={pre_reg['token']}")
        assert_true(owner_preview["profile"]["public_profile_id"] == pre_profile, "Preview owner prelaunch no funciona")
        mark("prelaunch gate ready")

        event = request(base, "POST", "/api/events", {"actor": "Admin", "name": "=Pilot V24", "status": "published"}, 201)
        event_id = int(event["id"])
        request(base, "POST", "/api/networking/config", {"actor": "Admin", "event_id": event_id, "networking_profile_mode": "ORGANIZATION_FIRST", "networking_discovery_enabled": 1, "networking_discovery_batch_size": 5, "networking_discovery_exploration_frequency": 4})
        request(base, "POST", "/api/networking/brand", {"actor": "Admin", "event_id": event_id, "networking_public_base_url": "https://pilot.example.test", "networking_brand_title": "Pilot V24", "landing_primary_color": "#0a766f"})
        concept_setup(base, event_id)
        owner_reg = register(base, event_id, "owner", email="pilot.owner.v24@example.test")
        import_profiles(base, event_id, pilot_rows(event_id, 90, include_owner=True, prefix="pilot"))
        activate_event_targets(event_id)
        owner = onboard(base, owner_reg["token"], event_id)
        owner_id = int(owner["participation"]["participation_id"])
        owner_discovery = complete_discovery(base, owner_reg["token"], event_id, diversity=True)
        assert_true(owner_discovery["participation"]["discovery"]["ready"], f"Discovery owner no quedo listo: {owner_discovery['participation']['discovery']}")
        launched = request(base, "POST", "/api/networking/launch", {"actor": "Admin", "event_id": event_id, "action": "launch"})
        assert_true(launched["networking_launch_state"] == "LIVE", "Launch no dejo Networking live")
        mark("main pilot event ready")

        targets = target_profiles(event_id, owner_id, 12)
        assert_true(len(targets) >= 8, "Fixture no genero candidatos suficientes")
        first_target = targets[0]["public_profile_id"]
        second_target = targets[1]["public_profile_id"]

        # Public QR/deep-link security and malformed token handling.
        public_profile = request(base, "GET", f"/api/networking/profile?profile_id={first_target}")
        assert_true(public_profile["profile"]["public_profile_id"] == first_target, "Perfil publico live no resuelve")
        assert_true("owner_token_hint" not in public_profile["profile"] and "email" not in public_profile["profile"], "Perfil publico expone credencial owner")
        request(base, "GET", "/api/networking/profile?profile_id=NET-DOESNOTEXIST", expect=404)
        request(base, "GET", "/api/networking/profile?profile_id=%3Cscript%3E", expect=404)
        assert_true(not request(base, "GET", f"/api/networking/session?token={first_target}", expect=404).get("ok"), "Public profile token autentica owner")
        qr_svg, qr_type = request(base, "GET", f"/api/networking/qr.svg?profile_id={first_target}", parse_json=False)
        assert_true(b"<svg" in qr_svg and "image/svg" in qr_type, "QR Networking no genera SVG estructural")
        with server.connect() as db:
            link = server.networking_service().public_profile_link(db, first_target, fallback_base_url=base)
        assert_true(link["url"] == f"https://pilot.example.test/n/{first_target}", "QR/deep link no usa URL publica autoritativa")
        mark("QR/security checks ready")

        # Return target injection is a static internal page load, not a server redirect.
        public_html, html_type = request(base, "GET", "/networking-public.html?return_profile=https://evil.example", parse_json=False)
        assert_true(b"return_profile" in public_html and "text/html" in html_type, "Return profile no queda en ruta local controlada")

        # Concurrent read/write certification.
        session_calls = [(base, "GET", f"/api/networking/session?token={owner_reg['token']}&event_id={event_id}", None, 200) for _ in range(20)]
        _session_results, credential_elapsed = concurrent_requests(session_calls, workers=20)
        profile_calls = [(base, "GET", f"/api/networking/profile?profile_id={targets[index % len(targets)]['public_profile_id']}", None, 200) for index in range(40)]
        _profile_results, public_elapsed = concurrent_requests(profile_calls, workers=20)
        scan_calls = [(base, "POST", "/api/networking/scan", {"token": owner_reg["token"], "public_profile_id": first_target}, 200) for _ in range(20)]
        scan_results, scan_elapsed = concurrent_requests(scan_calls, workers=20)
        with server.connect() as db:
            contact_count = db.execute("SELECT COUNT(*) AS c FROM networking_contacts WHERE event_id = ? AND owner_participation_id = ? AND target_participation_id = (SELECT id FROM networking_event_participations WHERE public_profile_id = ?)", (event_id, owner_id, first_target)).fetchone()["c"]
        assert_true(contact_count == 1 and sum(1 for item in scan_results if item.get("created")) == 1, "Race de contacto por QR duplico contacto logico")
        mark("read/contact concurrency ready")

        cross_calls = [
            (base, "POST", "/api/networking/scan", {"token": owner_reg["token"], "public_profile_id": second_target}, 200),
            (base, "POST", "/api/networking/discovery-action", {"token": owner_reg["token"], "action": "save", "public_profile_id": second_target}, 200),
        ] * 5
        cross_results, _cross_elapsed = concurrent_requests(cross_calls, workers=10)
        contact_ids = {item.get("contact_id") for item in cross_results if item.get("contact_id")}
        assert_true(len(contact_ids) == 1, "Race QR + Discovery no fue idempotente")

        stream = request(base, "GET", f"/api/networking/discovery?token={owner_reg['token']}&limit=10000")
        assert_true(len(stream["items"]) <= 5 and "score" not in json.dumps(stream).lower(), "Discovery dejo de estar bounded o expuso score")
        skip_target = first_item(stream)["profile"]["public_profile_id"]
        skip_calls = [(base, "POST", "/api/networking/discovery-action", {"token": owner_reg["token"], "action": "skip", "public_profile_id": skip_target}, 200) for _ in range(12)]
        skip_results, skip_elapsed = concurrent_requests(skip_calls, workers=12)
        next_ids = [first_item(item["next"])["profile"]["public_profile_id"] for item in skip_results if item.get("next", {}).get("items")]
        assert_true(all(item != skip_target for item in next_ids), "Race de skip devolvio inmediatamente el mismo perfil")
        with server.connect() as db:
            skip_count = db.execute(
                """
                SELECT COUNT(*) AS c
                FROM networking_interaction_events
                WHERE event_id = ? AND actor_participation_id = ? AND target_participation_id = (
                    SELECT id FROM networking_event_participations WHERE public_profile_id = ?
                ) AND event_type = 'discovery_skipped'
                """,
                (event_id, owner_id, skip_target),
            ).fetchone()["c"]
        assert_true(skip_count == 1, "Doble skip duplico historia dañina")
        mark("discovery skip race ready")

        # Current privacy/state wins over stale history.
        privacy_target = targets[3]["public_profile_id"]
        with server.DB_LOCK, server.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("UPDATE networking_intents SET profile_visible = 0, discoverable = 0 WHERE participation_id = (SELECT id FROM networking_event_participations WHERE public_profile_id = ?)", (privacy_target,))
            db.execute("COMMIT")
        request(base, "GET", f"/api/networking/profile?profile_id={privacy_target}", expect=404)
        privacy_stream = request(base, "GET", f"/api/networking/discovery?token={owner_reg['token']}&limit=5")
        assert_true(privacy_target not in {item["profile"]["public_profile_id"] for item in privacy_stream.get("items", [])}, "Discovery reciclo perfil ahora oculto")

        revoked_target = targets[4]["public_profile_id"]
        with server.DB_LOCK, server.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("UPDATE networking_event_participations SET participation_state = 'REVOKED' WHERE public_profile_id = ?", (revoked_target,))
            db.execute("COMMIT")
        request(base, "GET", f"/api/networking/profile?profile_id={revoked_target}", expect=404)
        assert_true(revoked_target not in {item["profile"]["public_profile_id"] for item in request(base, "GET", f"/api/networking/discovery?token={owner_reg['token']}&limit=5").get("items", [])}, "Discovery devolvio participacion revocada")

        # Cross-event isolation.
        other_event = request(base, "POST", "/api/events", {"actor": "Admin", "name": "Other V24", "status": "published"}, 201)
        other_event_id = int(other_event["id"])
        other_reg = register(base, other_event_id, "other", email="other.owner.v24@example.test")
        import_profiles(base, other_event_id, pilot_rows(other_event_id, 2, include_owner=True, prefix="other"))
        activate_event_targets(other_event_id)
        onboard(base, other_reg["token"], other_event_id)
        request(base, "POST", "/api/networking/brand", {"actor": "Admin", "event_id": other_event_id, "networking_public_base_url": "https://other.example.test"})
        request(base, "POST", "/api/networking/launch", {"actor": "Admin", "event_id": other_event_id, "action": "launch"})
        other_profile = participant_by_email("other.0000.v24@example.test")["public_profile_id"]
        request(base, "POST", "/api/networking/scan", {"token": owner_reg["token"], "public_profile_id": other_profile}, expect=404)

        # Emergency disable/re-enable is non-destructive.
        contacts_before_disable = request(base, "GET", f"/api/networking/contacts?token={owner_reg['token']}")["contacts"]
        request(base, "POST", "/api/networking/launch", {"actor": "Admin", "event_id": event_id, "action": "disable"})
        request(base, "GET", f"/api/networking/profile?profile_id={first_target}", expect=404)
        request(base, "POST", "/api/networking/launch", {"actor": "Admin", "event_id": event_id, "action": "launch"})
        contacts_after_disable = request(base, "GET", f"/api/networking/contacts?token={owner_reg['token']}")["contacts"]
        assert_true(len(contacts_after_disable) == len(contacts_before_disable), "Disable/re-enable altero contactos")
        request(base, "POST", "/api/networking/config", {"actor": "Admin", "event_id": event_id, "networking_discovery_enabled": 0})
        disabled_discovery = request(base, "GET", f"/api/networking/discovery?token={owner_reg['token']}")
        assert_true(disabled_discovery["status"] == "DISABLED", "Emergency Discovery disable no corta stream")
        request(base, "GET", f"/api/networking/session?token={owner_reg['token']}&event_id={event_id}")
        request(base, "POST", "/api/networking/config", {"actor": "Admin", "event_id": event_id, "networking_discovery_enabled": 1})

        # Live reimport preserves protected state.
        with server.connect() as db:
            contacts_before_reimport = db.execute("SELECT COUNT(*) AS c FROM networking_contacts WHERE event_id = ?", (event_id,)).fetchone()["c"]
            interactions_before_reimport = db.execute("SELECT COUNT(*) AS c FROM networking_interaction_events WHERE event_id = ?", (event_id,)).fetchone()["c"]
        import_profiles(base, event_id, pilot_rows(event_id, 90, include_owner=True, prefix="pilot"), source="BITORA")
        with server.connect() as db:
            contacts_after_reimport = db.execute("SELECT COUNT(*) AS c FROM networking_contacts WHERE event_id = ?", (event_id,)).fetchone()["c"]
            interactions_after_reimport = db.execute("SELECT COUNT(*) AS c FROM networking_interaction_events WHERE event_id = ?", (event_id,)).fetchone()["c"]
        assert_true(contacts_after_reimport == contacts_before_reimport and interactions_after_reimport >= interactions_before_reimport, "Reimport live destruyo contactos/historia")
        mark("state mutation and reimport ready")

        # External registrations share canonical architecture and tolerate concurrent writes.
        external_calls = []
        for index in range(12):
            external_calls.append((base, "POST", "/api/networking/external-register", {
                "event_id": event_id,
                "first_name": f"External{index}",
                "last_name": "Pilot",
                "email": f"external.{index}.v24@example.test",
                "organization": f"External Org {index}",
                "organization_activity": "Construction",
                "function": "COMMERCIAL",
            }, 201))
        external_results, _external_elapsed = concurrent_requests(external_calls, workers=12)
        assert_true(all(item.get("owner_token") for item in external_results), "External register no entrega token canonical")

        # Exhaustion recovery on a tiny event: old skips recycle, then a new import becomes fresh.
        tiny = request(base, "POST", "/api/events", {"actor": "Admin", "name": "Tiny Exhaustion V24", "status": "published"}, 201)
        tiny_id = int(tiny["id"])
        concept_setup(base, tiny_id)
        tiny_reg = register(base, tiny_id, "tiny-owner", email="tiny.owner.v24@example.test")
        tiny_rows = pilot_rows(tiny_id, 3, include_owner=True, prefix="tiny")
        import_profiles(base, tiny_id, tiny_rows)
        activate_event_targets(tiny_id)
        onboard(base, tiny_reg["token"], tiny_id)
        tiny_discovery = complete_discovery(base, tiny_reg["token"], tiny_id, diversity=True)
        tiny_owner_id = int(tiny_discovery["participation"]["participation_id"])
        assert_true(tiny_discovery["participation"]["discovery"]["ready"], "Tiny Discovery no quedo listo")
        current = request(base, "GET", f"/api/networking/discovery?token={tiny_reg['token']}")
        safety = 0
        saw_recycle = False
        while current.get("items") and safety < 12:
            if current.get("phase") == "recycle":
                saw_recycle = True
            target = first_item(current)["profile"]["public_profile_id"]
            current = request(base, "POST", "/api/networking/discovery-action", {"token": tiny_reg["token"], "action": "skip", "public_profile_id": target})["next"]
            safety += 1
        assert_true(saw_recycle and current["status"] == "EXHAUSTED", "Tiny event no certifico recycle/exhaustion")
        import_profiles(base, tiny_id, pilot_rows(tiny_id, 1, include_owner=False, prefix="tiny-new"))
        activate_event_targets(tiny_id)
        recovered = request(base, "GET", f"/api/networking/discovery?token={tiny_reg['token']}")
        assert_true(recovered["phase"] == "fresh" and recovered["items"], "Nuevo import tras exhaustion no entra como fresh")
        request(base, "POST", "/api/networking/brand", {"actor": "Admin", "event_id": tiny_id, "networking_public_base_url": "https://tiny.example.test", "networking_brand_title": "Tiny Restore V24"})
        request(base, "POST", "/api/networking/launch", {"actor": "Admin", "event_id": tiny_id, "action": "launch"})
        tiny_contact_target = target_profiles(tiny_id, tiny_owner_id, 5)[0]["public_profile_id"]
        request(base, "POST", "/api/networking/scan", {"token": tiny_reg["token"], "public_profile_id": tiny_contact_target})
        mark("exhaustion recovery ready")

        # Operations/export after activity derive from canonical state and protect CSV.
        ops = request(base, "GET", f"/api/networking/operations?actor=Admin&event_id={event_id}")
        assert_true(ops["networking"]["contacts_total"] == contacts_after_reimport and ops["discovery"]["profiles_shown"] > 0, "Operaciones post-load no reflejan estado canonico")
        with server.connect() as db:
            exported = server.networking_service().operations_export_csv(db, event_id, fallback_base_url=base, app_env="development")
        parsed = list(csv.DictReader(exported.splitlines()))
        assert_true(parsed and parsed[0]["event_name"].startswith("'=Pilot V24"), "Export CSV no neutraliza formula injection")
        assert_true("@" not in exported or "example.test" not in exported, "Export operativo fuga emails/canales privados")
        mark("operations/export ready")

        # Populated backup/restore includes launch, branding, contacts, vocabulary and interactions.
        backup_event_id = tiny_id
        with server.connect() as db:
            original = {
                "contacts": db.execute("SELECT COUNT(*) AS c FROM networking_contacts WHERE event_id = ?", (backup_event_id,)).fetchone()["c"],
                "interactions": db.execute("SELECT COUNT(*) AS c FROM networking_interaction_events WHERE event_id = ?", (backup_event_id,)).fetchone()["c"],
                "participants": db.execute("SELECT COUNT(*) AS c FROM networking_event_participations WHERE event_id = ?", (backup_event_id,)).fetchone()["c"],
                "vocabulary": db.execute("SELECT COUNT(*) AS c FROM networking_event_vocabulary_candidates WHERE event_id = ?", (backup_event_id,)).fetchone()["c"],
            }
        backup_dir = tmp_path / "event-backups"
        backup_service = EventBackupService(backup_dir, server.connect, server.DB_LOCK, "networking-v24-test")
        restore_service = EventRestoreService(server.connect, server.DB_LOCK, token_factory("V24-RESTORE"), server.now_iso, app_version="test", backup_service=backup_service)
        bundle = backup_service.create_event_bundle(backup_event_id, "Admin")
        restored = restore_service.restore_bytes(bundle.read_bytes(), actor="Admin", mode="new_event")
        restored_event_id = int(restored["event_id"])
        with server.connect() as db:
            restored_counts = {
                "contacts": db.execute("SELECT COUNT(*) AS c FROM networking_contacts WHERE event_id = ?", (restored_event_id,)).fetchone()["c"],
                "interactions": db.execute("SELECT COUNT(*) AS c FROM networking_interaction_events WHERE event_id = ?", (restored_event_id,)).fetchone()["c"],
                "participants": db.execute("SELECT COUNT(*) AS c FROM networking_event_participations WHERE event_id = ?", (restored_event_id,)).fetchone()["c"],
                "vocabulary": db.execute("SELECT COUNT(*) AS c FROM networking_event_vocabulary_candidates WHERE event_id = ?", (restored_event_id,)).fetchone()["c"],
                "launch_state": db.execute("SELECT networking_launch_state FROM events WHERE id = ?", (restored_event_id,)).fetchone()["networking_launch_state"],
            }
        assert_true(restored_counts["contacts"] == original["contacts"] and restored_counts["interactions"] == original["interactions"], "Restore no preservo contactos/interacciones pobladas")
        assert_true(restored_counts["participants"] == original["participants"] and restored_counts["vocabulary"] == original["vocabulary"], "Restore no preservo participantes/vocabulario")
        assert_true(restored_counts["launch_state"] == "LIVE", "Restore no preservo launch state")
        mark("backup/restore ready")

        # Schema idempotency/fresh migration and anti-directory endpoints.
        server.init_db()
        with server.connect() as db:
            preserved = db.execute("SELECT COUNT(*) AS c FROM networking_contacts WHERE event_id = ?", (backup_event_id,)).fetchone()["c"]
        assert_true(preserved == original["contacts"], "Init/migration idempotente altero datos existentes")
        request(base, "GET", "/api/networking/directory?event_id=1", expect=404)
        request(base, "GET", f"/api/networking/discovery?token={owner_reg['token']}&limit=10000")
        mark("schema/anti-directory ready")

        evidence = {
            "credential_concurrency_seconds": round(credential_elapsed, 3),
            "public_profile_concurrency_seconds": round(public_elapsed, 3),
            "scan_race_seconds": round(scan_elapsed, 3),
            "skip_race_seconds": round(skip_elapsed, 3),
            "participants_event": original["participants"],
            "contacts": original["contacts"],
            "interactions": original["interactions"],
            "restored_event_id": restored_event_id,
        }
        print("OK: networking V2.4 certification hardening")
        print(json.dumps(evidence, sort_keys=True))
    finally:
        if httpd:
            httpd.shutdown()
            httpd.server_close()
        shutil.rmtree(tmp_path, ignore_errors=True)


if __name__ == "__main__":
    main()
