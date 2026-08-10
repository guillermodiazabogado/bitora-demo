from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent
FRONTEND_PORTAL = ROOT / "frontend" / "p.html"
STATIC_PORTAL = ROOT / "static" / "p.html"
FRONTEND_CSS = ROOT / "frontend" / "styles.css"
STATIC_CSS = ROOT / "static" / "styles.css"
SERVER = ROOT / "server.py"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def check(name: str, passed: bool, detail: str) -> dict:
    return {"name": name, "passed": bool(passed), "detail": detail}


def main() -> int:
    portal = read(FRONTEND_PORTAL)
    static_portal = read(STATIC_PORTAL)
    css = read(FRONTEND_CSS)
    static_css = read(STATIC_CSS)
    server = read(SERVER)
    results: list[dict] = []

    required_sections = [
        'id="inicio"',
        'id="qr"',
        'id="agenda"',
        'id="charlas"',
        'id="asistencia"',
        'id="certificado"',
        'id="notificaciones"',
        'id="perfil"',
        'id="ayuda"',
    ]
    results.append(check(
        "participant_sections",
        all(section in portal for section in required_sections),
        "Home, QR, agenda, charlas, asistencia, certificado, notificaciones, perfil y ayuda presentes.",
    ))

    nav_labels = ["Inicio", "Mi QR", "Agenda", "Mis charlas", "Asistencia", "Certificado", "Notificaciones", "Perfil"]
    results.append(check(
        "participant_navigation",
        all(label in portal for label in nav_labels) and "participant-bottom-nav" in portal,
        "Navegacion reducida y barra inferior mobile presentes.",
    ))

    results.append(check(
        "token_not_rendered",
        'id="token"' not in portal and "$(\"#token\")" not in portal and "data.token" not in re.sub(r"credential\\.(?:png|pdf)\\?token=\\$\\{[^}]+\\}", "", portal),
        "El token tecnico no se muestra como texto en la interfaz.",
    ))

    results.append(check(
        "notifications_inbox",
        "buildNotifications" in portal and "notificationsInbox" in portal and "notificationBadge" in portal,
        "Inbox de notificaciones centraliza avisos, comunicaciones, reservas y certificados.",
    ))

    results.append(check(
        "portal_event_scope",
        "WHERE a.token = ?" in server
        and "WHERE person_id = ? AND event_id = ?" in server
        and "WHERE event_id = ? AND status = 'published'" in server
        and "WHERE at.accreditation_id = ?" in server,
        "El payload del portal se resuelve por token y consultas acotadas a evento/acreditacion.",
    ))

    results.append(check(
        "reservation_contract_preserved",
        "/api/portal/reserve" in portal and "/api/portal/reservations/status" in portal,
        "Inscripcion y cancelacion de actividades conservan endpoints existentes.",
    ))

    results.append(check(
        "profile_preferences_preserved",
        "/api/portal/profile" in portal and "/api/portal/preferences" in portal,
        "Perfil y preferencias siguen usando endpoints existentes.",
    ))

    results.append(check(
        "responsive_css",
        ".participant-bottom-nav" in css and "@media (max-width: 700px)" in css and ".participant-home-grid" in css,
        "Estilos responsive especificos del portal participante presentes.",
    ))

    results.append(check(
        "static_sync",
        portal == static_portal and css == static_css,
        "frontend y static estan sincronizados para el despliegue.",
    ))

    forbidden_copy = ["dashboard administrativo", "panel administrativo", "historial tecnico", "token tecnico"]
    results.append(check(
        "participant_copy_minimal",
        not any(term in portal.lower() for term in forbidden_copy),
        "La interfaz no usa textos administrativos o tecnicos innecesarios.",
    ))

    passed = sum(1 for item in results if item["passed"])
    total = len(results)
    report = {
        "name": "BITORA V4.0.3 Participant Experience Redesign",
        "score": f"{passed}/{total}",
        "passed": passed == total,
        "results": results,
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
