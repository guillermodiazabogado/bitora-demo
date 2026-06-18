from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parent
INDEX = ROOT / "frontend" / "index.html"
STATIC_INDEX = ROOT / "static" / "index.html"
APP = ROOT / "frontend" / "app.js"
STATIC_APP = ROOT / "static" / "app.js"
CSS = ROOT / "frontend" / "styles.css"
STATIC_CSS = ROOT / "static" / "styles.css"
ROOM = ROOT / "frontend" / "reports-display.html"
STATIC_ROOM = ROOT / "static" / "reports-display.html"


class IdParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []
        self.sections: list[str] = []
        self.buttons: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        data = dict(attrs)
        if "id" in data:
            self.ids.append(data["id"])
        if tag == "section" and data.get("class", "").find("view") >= 0:
            self.sections.append(data.get("id", ""))
        if tag == "button" and "data-view" in data:
            self.buttons.append(data["data-view"])


def assert_true(value, message: str) -> None:
    if not value:
        raise AssertionError(message)


def block(text: str, selector: str) -> str:
    pattern = re.escape(selector) + r"\s*\{(?P<body>.*?)\}"
    match = re.search(pattern, text, re.S)
    assert_true(match, f"No se encontro bloque CSS {selector}")
    return match.group("body")


def main() -> None:
    html = INDEX.read_text(encoding="utf-8")
    static_html = STATIC_INDEX.read_text(encoding="utf-8")
    app = APP.read_text(encoding="utf-8")
    css = CSS.read_text(encoding="utf-8")
    room = ROOM.read_text(encoding="utf-8")

    assert_true(html == static_html, "frontend/static index no estan sincronizados")
    assert_true(app == STATIC_APP.read_text(encoding="utf-8"), "frontend/static app no estan sincronizados")
    assert_true(css == STATIC_CSS.read_text(encoding="utf-8"), "frontend/static styles no estan sincronizados")
    assert_true(room == STATIC_ROOM.read_text(encoding="utf-8"), "frontend/static reports-display no estan sincronizados")

    parser = IdParser()
    parser.feed(html)
    assert_true(not [item for item in set(parser.ids) if parser.ids.count(item) > 1], "Hay IDs duplicados")
    assert_true({"dashboard", "register", "agenda", "configure", "reports"}.issubset(set(parser.sections)), "Faltan secciones principales")
    assert_true(parser.buttons[:6] == ["dashboard", "register", "reception", "agenda", "access", "configure"], "Menu principal no separa operar/configurar")

    dashboard = html.split('<section id="dashboard"', 1)[1].split('<section id="configure"', 1)[0]
    assert_true("Asistencias CSV" not in dashboard, "Panel muestra Asistencias CSV")
    assert_true("Elegibles CSV" not in dashboard, "Panel muestra Elegibles CSV")
    assert_true("Captacion CSV" not in dashboard, "Panel muestra Captacion CSV")
    assert_true("Exportar JSON" not in dashboard, "Panel muestra Exportar JSON")
    for label in ("Actualizar", "Pantalla publica", "Backup", "Configurar Evento"):
        assert_true(label in dashboard, f"Panel no muestra {label}")

    configure = html.split('<section id="configure"', 1)[1].split('<section id="reports"', 1)[0]
    reports = html.split('<section id="reports"', 1)[1].split('<section id="register"', 1)[0]
    agenda = html.split('<section id="agenda"', 1)[1].split('<section id="access"', 1)[0]
    register = html.split('<section id="register"', 1)[1].split('<section id="reception"', 1)[0]

    assert_true("Configuracion del evento" in configure, "Configuracion no esta centralizada")
    assert_true("Plantillas y Agenda" in configure, "Plantillas y Agenda no esta en Configurar")
    assert_true("Tipos y cupos" in configure, "Tipos y cupos no esta en Configurar")
    assert_true("Configuracion del evento" not in reports and "Plantillas y Agenda" not in reports, "Reportes mezcla configuracion")
    assert_true("Gestion de participantes" in register and 'id="accreditations"' in register, "Gestion completa de participantes no esta en Inscribir")
    assert_true("Gestion de inscripciones" not in register and "reservationForm" not in register, "Inscribir conserva bloque viejo de inscripciones")
    assert_true("reservationForm" not in agenda and "Exportar inscripciones" not in agenda, "Agenda conserva gestion de inscripciones")
    assert_true("Inscripciones CSV" not in app and "Asistencias CSV" not in app, "Agenda conserva exportaciones operativas por actividad")

    grid = block(css, ".control-room-grid")
    card = block(css, ".control-card")
    wide = block(css, ".control-card.wide")
    body = block(css, ".control-room-body")
    room_shell = block(css, ".control-room")
    head = block(css, ".control-room-head")
    assert_true("overflow: hidden" in body and "overflow: hidden" in room_shell and "overflow: hidden" in grid, "Sala de Control permite scroll/desborde")
    assert_true("grid-template-columns: repeat(4" in grid, "Sala de Control no usa grilla de 4 columnas")
    assert_true("grid-template-rows: repeat(3" in grid, "Sala de Control no usa 3 filas definidas")
    assert_true("grid-auto-rows: 0" in grid, "Sala de Control permite filas implicitas visibles")
    assert_true("grid-column: auto" in wide, "Tarjetas wide pueden crear desborde")
    assert_true("padding:" in card and "display: flex" in card and "min-height: 0" in card, "Tarjetas sin contenedor/padding estable")
    assert_true("height: 100vh" in body and "width: 100vw" in body, "Sala de Control no fija viewport")
    assert_true("align-items: center" in head and "overflow: hidden" in head, "Header de Sala de Control no esta contenido")
    assert_true(".control-room-grid .control-card:nth-child(11):last-child" in css, "Grilla no completa hueco visual con 11 tarjetas")
    assert_true("roomClock" in room and "setInterval(tick, 1000)" in room, "Hora en tiempo real no esta activa")
    assert_true("roomGrid" in room and "control-card" in room, "Graficos/tarjetas no renderizan en contenedores")
    assert_true("kpi-health" in room and "Salud operativa" in room and "healthClass" in room, "Salud operativa no usa KPI visual")
    assert_true(".kpi-health" in css and ".kpi-health.bad" in css and ".kpi-grid > div" in css, "CSS de salud operativa no evita desborde")
    assert_true("room-progress-list" in room and "style=\"--w:" in room, "Ocupacion de salas no usa barras/progreso")
    assert_true("line-chart" in room and "<polyline" in room, "Flujo de ingreso no usa grafico de lineas")
    assert_true("heatmap-list" in room, "Mapa de calor no se mantiene")
    assert_true("alarm-counter" in room and "Sin alarmas activas" in room and "Alarmas activas" in room, "Alarmas no muestran contador operativo")
    assert_true("count > 0 ? \"red\" : \"green\"" in room, "Alarmas 0/activas no cambian verde/rojo")
    assert_true("donut(data.accreditation_status_counts)" in room, "Estado de acreditaciones no mantiene grafico circular")
    assert_true("rejection-card" in room and "Motivos de rechazo" in room, "Motivos de rechazo no muestran ranking con cantidades")
    assert_true(".room-progress-list" in css and ".line-chart polyline" in css and ".alarm-counter.green" in css and ".alarm-counter.red" in css, "CSS de nuevos graficos incompleto")

    print("OK: layout Sala de Control y reorganizacion UX")


if __name__ == "__main__":
    main()
