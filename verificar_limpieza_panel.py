from __future__ import annotations

import json
import shutil
import tempfile
import threading
import urllib.error
import urllib.request
from pathlib import Path

import server


ROOT = Path(__file__).resolve().parent


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


def section(html: str, section_id: str, next_id: str) -> str:
    start = html.index(f'<section id="{section_id}"')
    end = html.index(f'<section id="{next_id}"', start)
    return html[start:end]


def check_sources() -> None:
    index = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    app_js = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    public_js = (ROOT / "frontend" / "public.js").read_text(encoding="utf-8")
    portal = (ROOT / "frontend" / "p.html").read_text(encoding="utf-8")

    assert_true('data-view="reports"' in index and '<section id="reports"' in index, "No existe pestaña/seccion Reportes")

    dashboard = section(index, "dashboard", "configure")
    configure = section(index, "configure", "reports")
    reports = section(index, "reports", "register")
    moved_labels = [
        "Estado del sistema",
        "Red local",
        "Marketing y conversion",
        "Checklist previa al evento",
        "Experiencia participante",
    ]
    for label in moved_labels:
        assert_true(label not in dashboard, f"{label} sigue visible en Panel Operativo")
        assert_true(label in reports, f"{label} no aparece en Reportes")
    assert_true("QR mas efectivos" in app_js, "QR mas efectivos no se conserva en reportes de marketing")
    assert_true("marketingStatus" not in dashboard and "marketingStatus" in reports, "Marketing no fue movido a Reportes")

    assert_true("Tipos y cupos" not in dashboard, "Tipos y cupos sigue visible en Panel Operativo")
    assert_true("Tipos y cupos" in configure, "Tipos y cupos no aparece en Configurar Evento")
    assert_true("Cupo general" not in dashboard, "Configuracion de cupo general sigue visible en Panel Operativo")
    assert_true("Por tipo" not in app_js, "Resumen operativo sigue mostrando Por tipo")

    old_visible_phrases = [
        "Reservas</h2>",
        "Reservar</button>",
        "Reserva opcional",
        "Reserva obligatoria",
        "Reservas CSV",
        "Reserva confirmada",
        "Reserva actualizada",
        "Mis reservas",
        "Confirmar reserva",
        "Cancelar esta reserva",
        "actividades reservadas",
    ]
    combined_ui = "\n".join([index, app_js, public_js, portal])
    for phrase in old_visible_phrases:
        assert_true(phrase not in combined_ui, f"Texto visible antiguo encontrado: {phrase}")
    assert_true("Gestion de inscripciones</h2>" in index, "Inscribir no usa Gestion de inscripciones")
    assert_true("Mis inscripciones" in portal, "Portal no usa Mis inscripciones")

    assert_true("copy-portal-link" not in public_js, "Landing publica conserva accion de copiar intermedia")
    assert_true("Ver mi QR" not in public_js, "Landing publica conserva accion intermedia de QR")
    assert_true("Elegir charlas" not in public_js, "Landing publica conserva accion intermedia de actividades")
    assert_true("location.href = result.portal_url" in public_js, "Landing no redirige directo al portal")

    for token in ["copyPortalBtn", "printCredentialBtn", "downloadImageBtn", "downloadPdfBtn", "portal-reserve"]:
        assert_true(token in portal, f"Portal perdio funcionalidad esperada: {token}")


def check_runtime() -> None:
    tmp_path = Path(tempfile.mkdtemp(prefix="bitora-limpieza-"))
    httpd = None
    old_values = {
        "DB_PATH": server.DB_PATH,
        "BACKUP_DIR": server.BACKUP_DIR,
        "BASE_URL": server.BASE_URL,
        "APP_ENV": server.APP_ENV,
    }
    try:
        server.DB_PATH = tmp_path / "limpieza.sqlite3"
        server.BACKUP_DIR = tmp_path / "backups"
        server.BASE_URL = ""
        server.APP_ENV = "development"
        server.AppHandler.log_message = lambda self, format, *args: None
        server.init_db()
        server.seed_if_empty()
        httpd = server.OperationalHTTPServer(("127.0.0.1", 0), server.AppHandler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{httpd.server_address[1]}"

        prepared = request(base, "POST", "/api/prepare-event", {"actor": "Admin", "name": "Limpieza Panel", "capacity": 40})
        event_id = prepared["event_id"]

        index_page, _ = request(base, "GET", "/", parse_json=False)
        assert_true(b"Reportes" in index_page, "La pagina principal no expone Reportes")
        landing, _ = request(base, "GET", f"/e.html?event_id={event_id}", parse_json=False)
        assert_true(b"publicRegisterForm" in landing, "La landing publica no carga el formulario")

        registration = request(
            base,
            "POST",
            "/api/register",
            {
                "actor": "public",
                "event_id": event_id,
                "first_name": "Flujo",
                "last_name": "Directo",
                "email": "flujo.directo@example.com",
                "type": "General",
                "source": "landing",
                "device_type": "desktop",
            },
            201,
        )
        assert_true(registration["portal_url"], "Registro publico no devuelve portal_url")
        portal_html, _ = request(base, "GET", registration["portal_url"], parse_json=False)
        assert_true(b"printCredentialBtn" in portal_html and b"copyPortalBtn" in portal_html, "Portal no mantiene imprimir/copiar")
        portal_data = request(base, "GET", f"/api/portal?token={registration['token']}")
        assert_true(portal_data["token"] == registration["token"], "Portal del participante no se puede consultar")
    finally:
        if httpd:
            httpd.shutdown()
            httpd.server_close()
        for key, value in old_values.items():
            setattr(server, key, value)
        shutil.rmtree(tmp_path, ignore_errors=True)


def main() -> None:
    check_sources()
    check_runtime()
    print("OK: limpieza visual del panel y flujo publico")


if __name__ == "__main__":
    main()
