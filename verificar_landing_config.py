from __future__ import annotations

import base64
import json
import shutil
import tempfile
import threading
import urllib.error
import urllib.request
from io import BytesIO
from pathlib import Path

from PIL import Image

import server


ROOT = Path(__file__).resolve().parent


def req(base: str, method: str, path: str, payload=None, expect: int = 200):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read()
            status = response.status
            content_type = response.headers.get("Content-Type", "")
    except urllib.error.HTTPError as exc:
        body = exc.read()
        status = exc.code
        content_type = exc.headers.get("Content-Type", "")
    if status != expect:
        raise AssertionError(f"{method} {path}: esperado {expect}, recibido {status}: {body!r}")
    if "application/json" in content_type:
        return json.loads(body.decode("utf-8")) if body else {}
    return body.decode("utf-8", "ignore")


def data_url(color: str) -> str:
    image = Image.new("RGB", (960, 540), color)
    output = BytesIO()
    image.save(output, format="PNG")
    encoded = base64.b64encode(output.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def assert_true(value, message: str) -> None:
    if not value:
        raise AssertionError(message)


def main() -> None:
    tmp_path = Path(tempfile.mkdtemp(prefix="qr-landing-"))
    httpd = None
    try:
        server.DB_PATH = tmp_path / "landing.sqlite3"
        server.BACKUP_DIR = tmp_path / "backups"
        server.AppHandler.log_message = lambda self, format, *args: None
        server.init_db()
        server.seed_if_empty()
        httpd = server.OperationalHTTPServer(("127.0.0.1", 0), server.AppHandler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{httpd.server_address[1]}"

        created = req(base, "POST", "/api/events", {
            "actor": "Admin",
            "name": "Landing Test",
            "description": "Evento publico de prueba",
            "venue": "Centro de Convenciones Domuyo\nNeuquen Capital",
            "starts_at": "2026-11-15T09:00",
            "ends_at": "2026-11-15T18:00",
            "status": "published",
            "capacity": 100,
        }, 201)
        event_id = int(created["id"])

        event = req(base, "GET", f"/api/event?event_id={event_id}")
        assert_true(not event.get("landing_image_data"), "El evento no debe iniciar con imagen custom")

        first = req(base, "POST", "/api/event-landing", {
            "actor": "Admin",
            "event_id": event_id,
            "action": "upload",
            "filename": "fondo-a.png",
            "image_data": data_url("#d2b89a"),
        })
        assert_true(first["image"]["width"] == 960 and first["image"]["height"] == 540, "No cargo imagen valida")
        event = req(base, "GET", f"/api/event?event_id={event_id}")
        assert_true(event["landing_image_name"] == "fondo-a.png", "No asocio imagen al evento")
        assert_true(event["landing_image_data"].startswith("data:image/png;base64,"), "No devuelve imagen para landing")

        req(base, "POST", "/api/event-landing", {
            "actor": "Admin",
            "event_id": event_id,
            "action": "upload",
            "filename": "fondo-b.png",
            "image_data": data_url("#c3a381"),
        })
        event = req(base, "GET", f"/api/event?event_id={event_id}")
        assert_true(event["landing_image_name"] == "fondo-b.png", "No reemplazo imagen")

        req(base, "POST", "/api/event-landing", {
            "actor": "Admin",
            "event_id": event_id,
            "action": "delete",
        })
        event = req(base, "GET", f"/api/event?event_id={event_id}")
        assert_true(not event.get("landing_image_data"), "No elimino imagen")

        html = (ROOT / "frontend" / "e.html").read_text(encoding="utf-8")
        public_js = (ROOT / "frontend" / "public.js").read_text(encoding="utf-8")
        css = (ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")
        assert_true('id="eventDate"' in html and 'id="eventTime"' in html and 'id="eventVenue"' in html, "Fecha, horario y ubicacion no estan separados")
        assert_true("phone-help" in html and "+54 9 299 4522126" in html, "Falta ayuda de formato de telefono/WhatsApp")
        assert_true("captationActions" not in html, "Landing conserva bloque de captacion/WhatsApp")
        assert_true("renderCaptationActions(event)" not in public_js, "Landing sigue renderizando acciones alternativas")
        assert_true("--landing-image" in public_js and "landing_image_data" in public_js, "Landing no aplica imagen del evento")
        assert_true("hour12: false" in public_js, "Horario no usa formato 24h limpio")
        assert_true("renderPublicTypes" in public_js, "Landing no controla categorias publicas")
        assert_true('value: "General", label: "Publico General"' in public_js, "Publico General no esta primero/configurado")
        assert_true('value: "Disertante", label: "Disertante"' in public_js, "Falta categoria Disertante")
        assert_true('value: "Prensa", label: "Prensa"' in public_js, "Falta categoria Prensa")
        assert_true('$("#publicTypeSelect").value = "General";' in public_js, "La landing no arranca en Publico General")
        assert_true("#D2B89A".lower() in css.lower() or "#d2b89a" in css.lower(), "No existe fallback arena BITORA")
        assert_true("linear-gradient(135deg, #d2b89a" in css.lower(), "No existe fondo BITORA por defecto")
        assert_true("var(--event-secondary), var(--event-primary)" not in css, "Landing conserva fondo tematico anterior")

        print("OK: configuracion visual de landing")
    finally:
        if httpd:
            httpd.shutdown()
            httpd.server_close()
        shutil.rmtree(tmp_path, ignore_errors=True)


if __name__ == "__main__":
    main()
