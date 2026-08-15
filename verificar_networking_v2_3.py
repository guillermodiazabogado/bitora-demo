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


def register(base: str, event_id: int, key: str, *, email: str | None = None) -> dict:
    return request(
        base,
        "POST",
        "/api/register",
        {
            "actor": "Recepcion",
            "event_id": event_id,
            "first_name": key.title(),
            "last_name": "Launch",
            "email": email or f"{key}.v23@example.test",
            "type": "General",
        },
        201,
    )


def onboard(base: str, token: str, event_id: int) -> dict:
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
            "function": "COMMERCIAL",
            "website": "https://contact.example",
            "channel_visibility_default": "PUBLIC",
        },
    )


def import_profile(base: str, event_id: int, key: str, *, email: str, organization: str) -> None:
    request(
        base,
        "POST",
        "/api/networking/import",
        {
            "actor": "Admin",
            "event_id": event_id,
            "source_system": "BITORA",
            "rows": [
                {
                    "source_external_id": f"{event_id}-{key}-v23",
                    "first_name": key.title(),
                    "last_name": "Launch",
                    "email": email,
                    "organization": organization,
                    "organization_activity": "Eventos",
                    "title": "Comercial",
                    "function": "COMMERCIAL",
                    "channels": [{"type": "website", "value": "https://contact.example", "visibility": "PUBLIC", "scope": "ORGANIZATION"}],
                }
            ],
        },
    )


def configure_brand(base: str, event_id: int, *, title: str, primary: str, public_url: str = "https://networking.example.test") -> dict:
    return request(
        base,
        "POST",
        "/api/networking/brand",
        {
            "actor": "Admin",
            "event_id": event_id,
            "networking_brand_title": title,
            "networking_brand_welcome": f"Bienvenido a {title}",
            "networking_brand_mode": "POWERED_BY_BITORA",
            "landing_primary_color": primary,
            "landing_secondary_color": "#d7a63f",
            "landing_logo_data": "/assets/bitora-logo.svg",
            "networking_public_base_url": public_url,
        },
    )


def main() -> None:
    tmp_path = Path(tempfile.mkdtemp(prefix="qr-networking-v2-3-"))
    httpd = None
    try:
        server.DB_PATH = tmp_path / "networking_v2_3.sqlite3"
        server.BACKUP_DIR = tmp_path / "backups"
        server.AppHandler.log_message = lambda self, format, *args: None
        server.init_db()
        server.seed_if_empty()

        httpd = server.OperationalHTTPServer(("127.0.0.1", 0), server.AppHandler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{httpd.server_address[1]}"

        empty = request(base, "POST", "/api/events", {"actor": "Admin", "name": "Evento sin marca", "status": "published"}, 201)
        event_a = request(base, "POST", "/api/events", {"actor": "Admin", "name": "Launch Norte", "status": "published"}, 201)
        event_b = request(base, "POST", "/api/events", {"actor": "Admin", "name": "Launch Sur", "status": "published"}, 201)
        empty_id = int(empty["id"])
        event_a_id = int(event_a["id"])
        event_b_id = int(event_b["id"])

        default_brand = request(base, "GET", f"/api/networking/brand?actor=Admin&event_id={empty_id}")
        assert_true(default_brand["branding"]["title"] == "Evento sin marca", "Branding default no usa nombre del evento")
        assert_true(default_brand["branding"]["primary_color"] == "#13243a", "Color default BITORA no es seguro")

        empty_launch = request(base, "GET", f"/api/networking/launch?actor=Admin&event_id={empty_id}")
        assert_true(empty_launch["status"] == "NOT_READY" and any(c["key"] == "NO_PARTICIPANTS" for c in empty_launch["blocking"]), "Evento sin participantes no bloquea launch")

        shared_email = "same.person.v23@example.test"
        reg_a = register(base, event_a_id, "persona", email=shared_email)
        reg_b = register(base, event_b_id, "persona", email=shared_email)
        import_profile(base, event_a_id, "persona", email=shared_email, organization="Organizacion Norte")
        import_profile(base, event_b_id, "persona", email=shared_email, organization="Organizacion Sur")
        session_a = onboard(base, reg_a["token"], event_a_id)
        session_b = onboard(base, reg_b["token"], event_b_id)
        profile_a = session_a["participation"]["public_profile_id"]
        profile_b = session_b["participation"]["public_profile_id"]
        assert_true(profile_a != profile_b, "QR/profile publico no quedo ligado a EventParticipation")

        configure_brand(base, event_a_id, title="Expo Norte 2026", primary="#0a766f")
        configure_brand(base, event_b_id, title="Expo Sur 2026", primary="#7b2cbf", public_url="https://sur.example.test")

        refreshed_a = request(base, "GET", f"/api/networking/session?token={reg_a['token']}&event_id={event_a_id}")
        refreshed_b = request(base, "GET", f"/api/networking/session?token={reg_b['token']}&event_id={event_b_id}")
        assert_true(refreshed_a["participation"]["event_branding"]["title"] == "Expo Norte 2026", "Credencial no aplica marca evento A")
        assert_true(refreshed_b["participation"]["event_branding"]["title"] == "Expo Sur 2026", "Credencial no aplica marca evento B")
        assert_true(refreshed_a["participation"]["event_branding"]["primary_color"] != refreshed_b["participation"]["event_branding"]["primary_color"], "Branding se filtro entre eventos")
        assert_true(refreshed_a["participation"]["credential"]["public_url"] == f"https://networking.example.test/n/{profile_a}", "Public URL de credencial no usa fuente autoritativa")

        public_prelaunch = request(base, "GET", f"/api/networking/profile?profile_id={profile_a}", expect=404)
        assert_true(public_prelaunch.get("status") == "NOT_LIVE", "Perfil publico prelaunch no queda protegido")
        self_preview = request(base, "GET", f"/api/networking/profile?profile_id={profile_a}&token={reg_a['token']}")
        assert_true(self_preview["profile"]["public_profile_id"] == profile_a, "Preview autorizado del owner no funciona antes del launch")

        with server.connect() as db:
            production_readiness = server.networking_service().launch_readiness(db, event_a_id, fallback_base_url="http://localhost:9999", app_env="production")
        assert_true(any(c["key"] == "PUBLIC_URL_VALID" for c in production_readiness["checks"]), "URL HTTPS configurada no valida en entorno publico")
        with server.connect() as db:
            local_block = server.networking_service().launch_readiness(db, empty_id, fallback_base_url="http://localhost:9999", app_env="production")
        assert_true(any(c["key"] in {"PUBLIC_URL_LOCAL_ONLY", "PUBLIC_URL_NOT_HTTPS"} for c in local_block["blocking"]), "URL local no bloquea contexto productivo")

        denied = request(base, "POST", "/api/networking/launch", {"actor": "Participante", "event_id": event_a_id, "action": "launch"}, expect=403)
        assert_true("permiso" in denied.get("error", "").lower(), "Actor no autorizado pudo lanzar Networking")

        launched = request(base, "POST", "/api/networking/launch", {"actor": "Admin", "event_id": event_a_id, "action": "launch"})
        assert_true(launched["networking_launch_state"] == "LIVE", "Launch autorizado no deja Networking live")
        public_live = request(base, "GET", f"/api/networking/profile?profile_id={profile_a}")
        assert_true(public_live["profile"]["event_branding"]["title"] == "Expo Norte 2026", "Perfil publico live no muestra contexto del evento")
        assert_true("email" not in public_live["profile"] and "owner_token_hint" not in public_live["profile"], "QR publico expone credencial de owner")
        owner_auth_attempt = request(base, "GET", f"/api/networking/session?token={profile_a}", expect=404)
        assert_true(not owner_auth_attempt.get("ok"), "Public profile token autentico owner")

        qr_svg, content_type = request(base, "GET", f"/api/networking/qr.svg?profile_id={profile_a}", parse_json=False)
        assert_true(b"<svg" in qr_svg and "image/svg" in content_type, "QR Networking no genera SVG estructural")

        request(base, "POST", "/api/networking/config", {"actor": "Admin", "event_id": event_b_id, "networking_discovery_enabled": 0})
        launched_b = request(base, "POST", "/api/networking/launch", {"actor": "Admin", "event_id": event_b_id, "action": "launch"})
        assert_true(launched_b["networking_launch_state"] == "LIVE", "Networking no puede lanzar con Discovery deshabilitado")

        disabled = request(base, "POST", "/api/networking/launch", {"actor": "Admin", "event_id": event_a_id, "action": "disable"})
        assert_true(disabled["networking_launch_state"] == "DISABLED", "Disable no cambia estado")
        request(base, "GET", f"/api/networking/profile?profile_id={profile_a}", expect=404)
        reenabled = request(base, "POST", "/api/networking/launch", {"actor": "Admin", "event_id": event_a_id, "action": "launch"})
        assert_true(reenabled["networking_launch_state"] == "LIVE", "Re-enable no recupera launch")
        request(base, "GET", f"/api/networking/profile?profile_id={profile_a}")

        ops = request(base, "GET", f"/api/networking/operations?actor=Admin&event_id={event_a_id}")
        assert_true(ops["launch"]["launch_state"] == "LIVE" and ops["launch"]["status"] in {"READY", "READY_WITH_WARNINGS"}, "Operaciones V2.2 no integra launch state")

        with server.connect() as db:
            exported = server.networking_service().operations_export_csv(db, event_a_id, fallback_base_url=base, app_env="development")
        assert_true("launch_state" in exported and "restricted" not in exported.lower(), "Export operativo no incluye launch o fuga datos restringidos")

        with server.connect() as db:
            bundle = server.EventBackupService(server.BACKUP_DIR, server.connect, threading.Lock(), app_version="test").create_event_bundle(event_a_id, "Admin")
            restored = server.EventRestoreService(server.connect, threading.Lock(), lambda: "EVT-V23-RESTORED", server.now_iso, app_version="test").restore_bytes(bundle.read_bytes(), mode="new_event", actor="Admin", new_event_name="Launch Norte restaurado")
            restored_event_id = int(restored["event_id"])
            row = db.execute(
                "SELECT networking_brand_title, networking_public_base_url, networking_launch_state, landing_primary_color FROM events WHERE id = ?",
                (restored_event_id,),
            ).fetchone()
        assert_true(row["networking_brand_title"] == "Expo Norte 2026", "Branding no sobrevivio restore de evento")
        assert_true(row["networking_public_base_url"] == "https://networking.example.test", "Public URL no sobrevivio restore")
        assert_true(row["networking_launch_state"] in {"DRAFT", "LIVE"}, "Launch state restaurado incoherente")
        assert_true(row["landing_primary_color"] == "#0a766f", "Color de marca no sobrevivio restore")

        invalid_profile = request(base, "GET", "/api/networking/profile?profile_id=NET-INVALIDTOKEN", expect=404)
        assert_true("inexistente" in invalid_profile.get("error", "").lower(), "Token invalido no responde de forma segura")

        print("OK: BITORA Networking V2.3 launch, branding, public URL and deployment readiness")
    finally:
        if httpd:
            httpd.shutdown()
        shutil.rmtree(tmp_path, ignore_errors=True)


if __name__ == "__main__":
    main()
