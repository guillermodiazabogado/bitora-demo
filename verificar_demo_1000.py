from __future__ import annotations

import json
import shutil
import tempfile
import threading
import urllib.error
import urllib.request
from pathlib import Path

import server
from backend.services.demo_real import DemoRealService


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
    except urllib.error.HTTPError as exc:
        body = exc.read()
        status = exc.code
    if status != expect:
        raise AssertionError(f"{method} {path}: esperado {expect}, recibido {status}: {body!r}")
    return json.loads(body.decode("utf-8")) if body else {}


def assert_true(value, message: str) -> None:
    if not value:
        raise AssertionError(message)


def main() -> None:
    tmp_path = Path(tempfile.mkdtemp(prefix="qr-demo-1000-"))
    httpd = None
    try:
        server.DB_PATH = tmp_path / "demo.sqlite3"
        server.BACKUP_DIR = tmp_path / "backups"
        server.AppHandler.log_message = lambda self, format, *args: None
        server.init_db()
        server.seed_if_empty()
        httpd = server.OperationalHTTPServer(("127.0.0.1", 0), server.AppHandler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{httpd.server_address[1]}"

        result = req(base, "POST", "/api/demo-real", {"actor": "Admin", "confirm": "DEMO"}, 201)
        event_id = int(result["event_id"])
        assert_true(result["event_name"] == DemoRealService.EVENT_NAME, "Evento demo incorrecto")
        assert_true(result["participants"] == 1000, "La demo avanzada no creo 1000 inscriptos")
        assert_true(result["peak"]["entered"] == 650, "No simulo 650 personas ingresadas")
        assert_true(result["peak"]["last_60_minutes"] == 250, "No preparo 250 ingresos en 60 minutos")
        assert_true(result["peak"]["last_15_minutes"] == 120, "No preparo 120 ingresos en 15 minutos")

        system = req(base, "GET", f"/api/system-status?event_id={event_id}")
        assert_true(system["recent_access"]["granted"] >= 120, "El panel no ve ingresos de ultimos 15 minutos")
        assert_true(system["recent_access"]["total"] >= 140, "El panel no ve actividad intensa reciente")
        assert_true(system["recent_access"]["rejected"] >= 20, "No hay rechazos recientes")
        assert_true(len(system["active_operators"]) >= 30, "No hay 30 terminales activas")
        reasons = {row["reason"] for row in system["recent_rejections"]}
        assert_true(len(reasons) >= 5, "Los rechazos recientes no tienen variedad de motivos")

        visual = req(base, "GET", f"/api/reports/visual-summary?event_id={event_id}")
        access_values = [int(row["value"]) for row in visual["access_by_time"]]
        assert_true(len(access_values) >= 3, "El flujo de ingresos no tiene suficientes franjas")
        assert_true(max(access_values) > min(access_values), "El flujo de ingresos quedo plano")
        assert_true(sum(access_values) >= 650, "El flujo no refleja los accesos cargados")
        assert_true(visual["totals"]["checked"] >= 650, "Sala de Control no refleja 650 acreditados")
        assert_true(visual["rejection_reasons"], "Sala de Control no muestra motivos de rechazo")
        assert_true(visual["operator_activity"], "Sala de Control no muestra operadores activos")
        alert_titles = {row["title"] for row in visual["operational_alerts"]}
        expected_alerts = {
            "Alto flujo de ingreso",
            "Rechazos QR elevados",
            "Terminal a revisar",
            "Ocupacion baja",
            "Actividad sin asistentes",
        }
        assert_true(expected_alerts <= alert_titles, f"Faltan alertas operativas: {expected_alerts - alert_titles}")

        dashboard = req(base, "GET", f"/api/summary?event_id={event_id}")
        assert_true(dashboard["accreditation"]["checked"] >= 650, "Panel Operativo no refleja acreditados recientes")
        logs = req(base, "GET", f"/api/logs?event_id={event_id}")
        assert_true(any(row["result"] == "rejected" for row in logs), "Logs recientes no muestran rechazos")

        print("OK: demo avanzada 1000 con pico operativo")
    finally:
        if httpd:
            httpd.shutdown()
            httpd.server_close()
        shutil.rmtree(tmp_path, ignore_errors=True)


if __name__ == "__main__":
    main()
